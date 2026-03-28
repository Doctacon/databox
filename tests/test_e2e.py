"""End-to-end tests: ingest -> transform -> quality -> verify.

These tests mock external APIs but use real DuckDB and real pipeline/transform logic.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import duckdb
import pytest

from pipelines.registry import get_source


class TestE2Eebird:
    """Full stack test for the eBird pipeline."""

    @pytest.mark.e2e
    def test_ingest_creates_raw_tables(self, tmp_db, mock_settings, mock_ebird_api_token, mocker):
        source = get_source("ebird")

        _mock_ebird_responses(mocker)

        source.load()

        con = duckdb.connect(str(tmp_db))
        try:
            tables = _get_tables_in_schema(con, "raw_ebird")
            assert "recent_observations" in tables
            assert "hotspots" in tables
            assert "taxonomy" in tables
            assert "species_list" in tables

            count = con.execute("SELECT COUNT(*) FROM raw_ebird.recent_observations").fetchone()[0]
            assert count > 0
        finally:
            con.close()

    @pytest.mark.e2e
    def test_raw_data_has_expected_columns(
        self, tmp_db, mock_settings, mock_ebird_api_token, mocker
    ):
        source = get_source("ebird")
        _mock_ebird_responses(mocker)
        source.load()

        con = duckdb.connect(str(tmp_db))
        try:
            cols = _get_column_names(con, "raw_ebird", "recent_observations")
            assert "species_code" in cols
            assert "sub_id" in cols
            assert "_loaded_at" in cols
            assert "_region_code" in cols
        finally:
            con.close()

    @pytest.mark.e2e
    def test_validate_config_with_token(self, mock_ebird_api_token):
        source = get_source("ebird")
        assert source.validate_config() is True

    @pytest.mark.e2e
    def test_validate_config_without_token(self, monkeypatch):
        monkeypatch.delenv("EBIRD_API_TOKEN", raising=False)
        source = get_source("ebird")
        assert source.validate_config() is False


class TestE2EQuality:
    """Test quality checks against loaded data."""

    @pytest.mark.e2e
    def test_quality_check_on_loaded_data(
        self, tmp_db, mock_settings, mock_ebird_api_token, mocker
    ):
        from typer.testing import CliRunner

        from cli.main import app

        source = get_source("ebird")
        _mock_ebird_responses(mocker)
        source.load()

        runner = CliRunner()
        result = runner.invoke(app, ["quality", "raw_ebird.recent_observations"])
        assert result.exit_code == 0
        assert "Total rows:" in result.output


class TestE2EMultipleSources:
    """Test that multiple sources coexist in the same database."""

    @pytest.mark.e2e
    def test_two_loads_dont_conflict(self, tmp_db, mock_settings, mock_ebird_api_token, mocker):
        source = get_source("ebird")
        _mock_ebird_responses(mocker)

        source.load()
        source.load()

        con = duckdb.connect(str(tmp_db))
        try:
            schemas = _get_all_schemas(con)
            assert "raw_ebird" in schemas

            count = con.execute("SELECT COUNT(*) FROM raw_ebird.recent_observations").fetchone()[0]
            assert count > 0
        finally:
            con.close()


def _mock_ebird_responses(mocker):
    """Set up comprehensive eBird API mocks."""
    import dlt.sources.helpers.requests as dlt_requests

    sample_obs = [
        {
            "speciesCode": "norcar",
            "comName": "Northern Cardinal",
            "sciName": "Cardinalis cardinalis",
            "locId": "L12345",
            "locName": "Test Park",
            "obsDt": "2025-07-20 08:30",
            "howMany": 3,
            "lat": 33.45,
            "lng": -112.07,
            "obsValid": True,
            "obsReviewed": False,
            "locationPrivate": False,
            "subId": "S100001",
        },
        {
            "speciesCode": "moudov",
            "comName": "Mourning Dove",
            "sciName": "Zenaida macroura",
            "locId": "L12346",
            "locName": "Test Garden",
            "obsDt": "2025-07-20 09:15",
            "howMany": 1,
            "lat": 33.50,
            "lng": -112.10,
            "obsValid": True,
            "obsReviewed": True,
            "locationPrivate": True,
            "subId": "S100002",
        },
    ]

    sample_hotspot = [
        {
            "locId": "L99999",
            "locName": "Gilbert Water Ranch",
            "countryCode": "US",
            "subnational1Code": "US-AZ",
            "subnational2Code": "US-AZ-013",
            "lat": 33.38,
            "lng": -111.74,
            "latestObsDt": "2025-07-19",
            "numSpeciesAllTime": 280,
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
        {
            "speciesCode": "moudov",
            "comName": "Mourning Dove",
            "sciName": "Zenaida macroura",
            "taxonOrder": 1002,
            "category": "species",
            "familyComName": "Pigeons and Doves",
            "familySciName": "Columbidae",
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
            response.json.return_value = ["norcar", "moudov"]
        elif "hotspot" in url:
            response.json.return_value = sample_hotspot
        elif "taxonomy" in url:
            response.json.return_value = sample_taxon
        else:
            response.json.return_value = []

        return response

    mocker.patch.object(dlt_requests, "get", mock_get)


def _get_tables_in_schema(con, schema: str) -> list[str]:
    rows = con.execute(
        f"SELECT table_name FROM information_schema.tables WHERE table_schema = '{schema}'"
    ).fetchall()
    return [r[0] for r in rows]


def _get_column_names(con, schema: str, table: str) -> list[str]:
    rows = con.execute(
        f"SELECT column_name FROM information_schema.columns "
        f"WHERE table_schema = '{schema}' AND table_name = '{table}'"
    ).fetchall()
    return [r[0] for r in rows]


def _get_all_schemas(con) -> list[str]:
    rows = con.execute("SELECT schema_name FROM information_schema.schemata").fetchall()
    return [r[0] for r in rows]
