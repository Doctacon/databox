"""Dynamic tests for any registered pipeline source.

Tests are parametrized from the pipeline registry — new sources get
test coverage automatically without writing any test-specific code.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import pytest

from pipelines.base import PipelineSource
from pipelines.registry import get_registry, get_source


def _registered_pipeline_names():
    try:
        return sorted(get_registry(refresh=True).keys())
    except Exception:
        return []


@pytest.mark.parametrize("pipeline_name", _registered_pipeline_names())
class TestAnySource:
    """Tests that run for every registered pipeline source."""

    @pytest.mark.unit
    def test_implements_protocol(self, pipeline_name):
        source = get_source(pipeline_name)
        assert isinstance(source, PipelineSource)

    @pytest.mark.unit
    def test_has_name(self, pipeline_name):
        source = get_source(pipeline_name)
        assert source.name == pipeline_name

    @pytest.mark.unit
    def test_has_config(self, pipeline_name):
        source = get_source(pipeline_name)
        assert source.config is not None
        assert source.config.name == pipeline_name
        assert source.config.source_module

    @pytest.mark.unit
    def test_validate_config_returns_bool(self, pipeline_name):
        source = get_source(pipeline_name)
        result = source.validate_config()
        assert isinstance(result, bool)

    @pytest.mark.unit
    def test_resources_returns_data(self, pipeline_name):
        source = get_source(pipeline_name)
        result = source.resources()
        assert hasattr(result, "__iter__")
        assert len(list(result)) > 0

    @pytest.mark.unit
    def test_resolve_schema_name(self, pipeline_name):
        source = get_source(pipeline_name)
        schema = source.config.resolve_schema_name()
        assert schema.startswith("raw_")


@pytest.mark.parametrize("pipeline_name", _registered_pipeline_names())
class TestAnySourceIntegration:
    """Integration tests requiring DuckDB (but no API calls)."""

    @pytest.mark.integration
    def test_load_creates_schema_and_tables(
        self, pipeline_name, tmp_db, mock_settings, mock_ebird_api_token, mocker
    ):
        source = get_source(pipeline_name)

        mock_api_data = _make_mock_api_data(pipeline_name)
        _mock_source_api(source, mocker, mock_api_data)

        source.load()

        import duckdb

        con = duckdb.connect(str(tmp_db))
        try:
            schema = source.config.resolve_schema_name()
            schemas = con.execute("SELECT schema_name FROM information_schema.schemata").fetchall()
            schema_names = [s[0] for s in schemas]
            assert schema in schema_names, f"Schema '{schema}' not found in: {schema_names}"

            tables = con.execute(
                f"SELECT table_name FROM information_schema.tables WHERE table_schema = '{schema}'"
            ).fetchall()
            assert len(tables) > 0, f"No tables created in schema '{schema}'"
        finally:
            con.close()


def _make_mock_api_data(pipeline_name: str) -> dict[str, list[dict]]:
    """Return mock API data for a given pipeline.

    Extend this for new data sources.
    """
    if pipeline_name == "ebird":
        return {
            "recent_observations": [
                {
                    "speciesCode": "norcar",
                    "comName": "Northern Cardinal",
                    "sciName": "Cardinalis cardinalis",
                    "locId": "L123",
                    "locName": "Test",
                    "obsDt": "2025-07-20 08:30",
                    "howMany": 2,
                    "lat": 33.45,
                    "lng": -112.07,
                    "obsValid": True,
                    "obsReviewed": False,
                    "locationPrivate": False,
                    "subId": "S001",
                },
            ],
            "notable_observations": [],
            "species_list": ["norcar"],
            "hotspots": [
                {
                    "locId": "L123",
                    "locName": "Test Park",
                    "countryCode": "US",
                    "subnational1Code": "US-AZ",
                    "subnational2Code": "US-AZ-013",
                    "lat": 33.38,
                    "lng": -111.74,
                    "latestObsDt": "2025-07-19",
                    "numSpeciesAllTime": 10,
                },
            ],
            "taxonomy": [
                {
                    "speciesCode": "norcar",
                    "comName": "Northern Cardinal",
                    "sciName": "Cardinalis cardinalis",
                    "taxonOrder": 1001,
                    "category": "species",
                    "familyComName": "Cardinals",
                    "familySciName": "Cardinalidae",
                },
            ],
        }
    return {}


def _mock_source_api(source: Any, mocker: Any, mock_data: dict[str, list[dict]]):
    """Patch dlt HTTP requests for a source to return mock data.

    Currently handles eBird. Extend for new sources.
    """
    if source.name == "ebird":
        _mock_ebird_api(mocker, mock_data)


def _mock_ebird_api(mocker: Any, mock_data: dict[str, list[dict]]):
    """Mock eBird API HTTP responses."""
    import dlt.sources.helpers.requests as dlt_requests

    def mock_get(url, **kwargs):
        response = MagicMock()
        response.status_code = 200

        if "recent/notable" in url:
            response.json.return_value = mock_data.get("notable_observations", [])
        elif "recent" in url:
            response.json.return_value = mock_data.get("recent_observations", [])
        elif "spplist" in url:
            response.json.return_value = mock_data.get("species_list", [])
        elif "hotspot" in url:
            response.json.return_value = mock_data.get("hotspots", [])
        elif "taxonomy" in url:
            response.json.return_value = mock_data.get("taxonomy", [])
        else:
            response.json.return_value = []

        response.raise_for_status = MagicMock()
        return response

    mocker.patch.object(dlt_requests, "get", mock_get)
