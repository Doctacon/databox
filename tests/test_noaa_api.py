"""NOAA-specific API tests with HTTP mocking."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from pipelines.sources.noaa_api import (
    NoaaPipelineSource,
    _chunk_date_range,
    noaa_source,
    process_station,
    process_weather_record,
)


class TestNoaaApiHeaders:
    @pytest.mark.unit
    def test_get_api_headers(self, monkeypatch):
        from pipelines.sources.noaa_api import get_api_headers

        monkeypatch.setenv("NOAA_API_TOKEN", "test_token")
        headers = get_api_headers()
        assert headers["token"] == "test_token"

    @pytest.mark.unit
    def test_missing_token(self, monkeypatch):
        from pipelines.sources.noaa_api import get_api_headers

        monkeypatch.delenv("NOAA_API_TOKEN", raising=False)
        with pytest.raises(ValueError, match="NOAA_API_TOKEN"):
            get_api_headers()


class TestProcessWeatherRecord:
    @pytest.mark.unit
    def test_basic_record(self):
        record = {
            "date": "2025-07-20",
            "datatype": "TMAX",
            "station": "GHCND:USC00010008",
            "value": 105.3,
            "attributes": ",,S,",
        }
        result = process_weather_record(record, "FIPS:04")
        assert result["date"] == "2025-07-20"
        assert result["datatype"] == "TMAX"
        assert result["value"] == 105.3
        assert result["_location_id"] == "FIPS:04"

    @pytest.mark.unit
    def test_missing_attributes(self):
        record = {
            "date": "2025-07-20",
            "datatype": "PRCP",
            "station": "GHCND:USC00010008",
            "value": 0.0,
        }
        result = process_weather_record(record, "FIPS:04")
        assert result["attributes"] == ""


class TestProcessStation:
    @pytest.mark.unit
    def test_basic_station(self):
        station = {
            "id": "GHCND:USC00010008",
            "name": "PHOENIX",
            "latitude": 33.45,
            "longitude": -112.07,
            "elevation": 331.0,
            "elevationUnit": "METERS",
            "mindate": "1895-01-01",
            "maxdate": "2025-12-31",
            "datacoverage": 0.95,
        }
        result = process_station(station, "FIPS:04")
        assert result["id"] == "GHCND:USC00010008"
        assert result["name"] == "PHOENIX"
        assert result["_location_id"] == "FIPS:04"


class TestChunkDateRange:
    @pytest.mark.unit
    def test_short_range_no_chunking(self):
        chunks = _chunk_date_range("2025-07-01", "2025-07-15")
        assert len(chunks) == 1
        assert chunks[0] == ("2025-07-01", "2025-07-15")

    @pytest.mark.unit
    def test_long_range_chunks(self):
        chunks = _chunk_date_range("2024-01-01", "2025-12-31", max_days=365)
        assert len(chunks) == 2

    @pytest.mark.unit
    def test_exact_boundary(self):
        chunks = _chunk_date_range("2025-01-01", "2025-12-31", max_days=365)
        assert len(chunks) == 1


class TestNoaaSourceResources:
    @pytest.mark.unit
    def test_source_creates_all_resources(self):
        source = noaa_source(location_id="FIPS:04", days_back=7)
        resource_names = list(source.resources.keys())
        assert "daily_weather" in resource_names
        assert "stations" in resource_names

    @pytest.mark.unit
    def test_daily_weather_columns(self):
        source = noaa_source(location_id="FIPS:04", days_back=7)
        res = source.resources["daily_weather"]
        assert res.write_disposition == "merge"


class TestNoaaHttpMocking:
    @pytest.mark.integration
    def test_full_load_with_mocked_api(self, tmp_db, mock_settings, monkeypatch, mocker):
        import duckdb

        from config.pipeline_config import PipelineConfig

        monkeypatch.setenv("NOAA_API_TOKEN", "test_token")

        _mock_noaa_responses(mocker)

        cfg = PipelineConfig(
            name="noaa",
            source_module="pipelines.sources.noaa_api",
            params={"location_id": "FIPS:04", "dataset_id": "GHCND", "days_back": 7},
        )
        source = NoaaPipelineSource(cfg)
        source.load()

        con = duckdb.connect(str(tmp_db))
        try:
            tables = con.execute(
                "SELECT table_name FROM information_schema.tables WHERE table_schema = 'raw_noaa'"
            ).fetchall()
            table_names = [t[0] for t in tables]
            assert "daily_weather" in table_names
            assert "stations" in table_names

            count = con.execute("SELECT COUNT(*) FROM raw_noaa.daily_weather").fetchone()[0]
            assert count > 0
        finally:
            con.close()


def _mock_noaa_responses(mocker):
    import dlt.sources.helpers.requests as dlt_requests

    sample_weather = [
        {
            "date": "2025-07-20",
            "datatype": "TMAX",
            "station": "GHCND:USC00010008",
            "value": 105.3,
            "attributes": ",,S,",
        },
        {
            "date": "2025-07-20",
            "datatype": "TMIN",
            "station": "GHCND:USC00010008",
            "value": 72.1,
            "attributes": ",,S,",
        },
        {
            "date": "2025-07-20",
            "datatype": "PRCP",
            "station": "GHCND:USC00010008",
            "value": 0.0,
            "attributes": ",,S,",
        },
    ]
    sample_stations = [
        {
            "id": "GHCND:USC00010008",
            "name": "PHOENIX",
            "latitude": 33.45,
            "longitude": -112.07,
            "elevation": 331.0,
            "elevationUnit": "METERS",
            "mindate": "1895-01-01",
            "maxdate": "2025-12-31",
            "datacoverage": 0.95,
        },
    ]

    def mock_get(url, **kwargs):
        response = MagicMock()
        response.status_code = 200
        response.raise_for_status = MagicMock()

        if "/datasets/" in url:
            response.json.return_value = {
                "id": "GHCND",
                "name": "Daily Summaries",
            }
        elif "/data" in url:
            response.json.return_value = {"results": sample_weather}
        elif "/stations" in url:
            response.json.return_value = {"results": sample_stations}
        else:
            response.json.return_value = {}

        return response

    mocker.patch.object(dlt_requests, "get", mock_get)
    mocker.patch("time.sleep", return_value=None)
