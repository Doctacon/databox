"""eBird-specific API tests with HTTP mocking."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from sources.ebird.source import ebird_source, process_observation


class TestEbirdApiHeaders:
    @pytest.mark.unit
    def test_get_api_headers(self, monkeypatch):
        from sources.ebird.source import get_api_headers

        monkeypatch.setenv("EBIRD_API_TOKEN", "test_token")
        headers = get_api_headers()
        assert headers["X-eBirdApiToken"] == "test_token"

    @pytest.mark.unit
    def test_missing_token(self, monkeypatch):
        from sources.ebird.source import get_api_headers

        monkeypatch.delenv("EBIRD_API_TOKEN", raising=False)
        with pytest.raises(ValueError, match="EBIRD_API_TOKEN"):
            get_api_headers()


class TestProcessObservation:
    @pytest.mark.unit
    def test_basic_observation(self):
        obs = {
            "speciesCode": "norcar",
            "comName": "Northern Cardinal",
            "sciName": "Cardinalis cardinalis",
            "locId": "L123",
            "locName": "Test Park",
            "obsDt": "2025-07-20 08:30",
            "howMany": 3,
            "lat": 33.45,
            "lng": -112.07,
            "obsValid": True,
            "obsReviewed": False,
            "locationPrivate": False,
            "subId": "S001",
        }
        result = process_observation(obs, "US-AZ", is_notable=False)
        assert result["_region_code"] == "US-AZ"
        assert result["_is_notable"] is False
        assert result["howMany"] == 3

    @pytest.mark.unit
    def test_notable_observation(self):
        obs = {"subId": "S002", "obsDt": "2025-07-20 08:30", "howMany": None}
        result = process_observation(obs, "US-AZ", is_notable=True)
        assert result["_is_notable"] is True
        assert result["howMany"] is None

    @pytest.mark.unit
    def test_count_cast_to_int(self):
        obs = {"subId": "S003", "howMany": "5"}
        result = process_observation(obs, "US-AZ")
        assert result["howMany"] == 5

    @pytest.mark.unit
    def test_invalid_count_becomes_none(self):
        obs = {"subId": "S004", "howMany": "abc"}
        result = process_observation(obs, "US-AZ")
        assert result["howMany"] is None


class TestEbirdSourceResources:
    @pytest.mark.unit
    def test_source_creates_all_resources(self):
        source = ebird_source(region_code="US-AZ", max_results=10, days_back=1)
        resource_names = list(source.resources.keys())
        assert "recent_observations" in resource_names
        assert "notable_observations" in resource_names
        assert "species_list" in resource_names
        assert "hotspots" in resource_names
        assert "taxonomy" in resource_names

    @pytest.mark.unit
    def test_recent_observations_has_columns(self):
        source = ebird_source(region_code="US-AZ", max_results=10, days_back=1)
        res = source.resources["recent_observations"]
        assert res.write_disposition == "merge"
        assert "howMany" in res.columns


class TestEbirdHttpMocking:
    @pytest.mark.integration
    def test_full_load_with_mocked_api(self, tmp_db, mock_settings, mock_ebird_api_token, mocker):
        import duckdb

        from config.pipeline_config import PipelineConfig
        from sources.ebird.source import EbirdPipelineSource

        _mock_ebird_responses(mocker)

        cfg = PipelineConfig(
            name="ebird",
            source_module="sources.ebird.source",
            params={"region_code": "US-AZ", "max_results": 10, "days_back": 1},
        )
        source = EbirdPipelineSource(cfg)
        source.load()

        con = duckdb.connect(str(tmp_db))
        try:
            tables = con.execute(
                "SELECT table_name FROM information_schema.tables WHERE table_schema = 'raw_ebird'"
            ).fetchall()
            table_names = [t[0] for t in tables]
            assert "recent_observations" in table_names
            assert "hotspots" in table_names
            assert "taxonomy" in table_names

            count = con.execute("SELECT COUNT(*) FROM raw_ebird.recent_observations").fetchone()[0]
            assert count > 0
        finally:
            con.close()


def _mock_ebird_responses(mocker):
    import dlt.sources.helpers.requests as dlt_requests

    sample_obs = [
        {
            "speciesCode": "norcar",
            "comName": "Northern Cardinal",
            "sciName": "Cardinalis cardinalis",
            "locId": "L123",
            "locName": "Test Park",
            "obsDt": "2025-07-20 08:30",
            "howMany": 3,
            "lat": 33.45,
            "lng": -112.07,
            "obsValid": True,
            "obsReviewed": False,
            "locationPrivate": False,
            "subId": "S001",
        },
    ]
    sample_hotspot = [
        {
            "locId": "L999",
            "locName": "Test Hotspot",
            "countryCode": "US",
            "subnational1Code": "US-AZ",
            "subnational2Code": "US-AZ-013",
            "lat": 33.38,
            "lng": -111.74,
            "latestObsDt": "2025-07-19",
            "numSpeciesAllTime": 100,
        },
    ]
    sample_taxon = [
        {
            "speciesCode": "norcar",
            "comName": "Northern Cardinal",
            "sciName": "Cardinalis cardinalis",
            "taxonOrder": 1001,
            "category": "species",
            "familyComName": "Cardinals and Allies",
            "familySciName": "Cardinalidae",
        },
    ]

    def mock_get(url, **kwargs):
        response = MagicMock()
        response.status_code = 200
        response.raise_for_status = MagicMock()

        if "recent/notable" in url:
            response.json.return_value = []
        elif "/recent" in url:
            response.json.return_value = sample_obs
        elif "spplist" in url:
            response.json.return_value = ["norcar"]
        elif "hotspot" in url:
            response.json.return_value = sample_hotspot
        elif "taxonomy" in url:
            response.json.return_value = sample_taxon
        else:
            response.json.return_value = []

        return response

    mocker.patch.object(dlt_requests, "get", mock_get)
