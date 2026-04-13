"""Shared test fixtures for databox."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import duckdb
import pytest

from config.pipeline_config import PipelineConfig, PipelineSchedule


@pytest.fixture(autouse=True)
def reset_registry():
    """Clear the pipeline registry cache between tests."""
    import sources.registry as reg

    original = reg._REGISTRY
    reg._REGISTRY = None
    yield
    reg._REGISTRY = original


@pytest.fixture
def tmp_db(tmp_path):
    """Create a temp DuckDB database file and return its path."""
    db_path = tmp_path / "test.db"
    con = duckdb.connect(str(db_path))
    con.close()
    return db_path


@pytest.fixture
def tmp_db_con(tmp_db):
    """Return an open DuckDB connection to the temp database."""
    con = duckdb.connect(str(tmp_db))
    yield con
    con.close()


@pytest.fixture
def mock_settings(tmp_db, monkeypatch):
    """Override settings to point at temp database."""
    import config.settings as settings_mod

    test_url = f"duckdb:///{tmp_db}"
    monkeypatch.setattr(settings_mod.settings, "database_url", test_url)
    monkeypatch.setattr(settings_mod.settings, "dlt_data_dir", str(tmp_db.parent / ".dlt"))
    return settings_mod.settings


@pytest.fixture
def mock_pipeline_config():
    """Create a minimal PipelineConfig for testing."""
    return PipelineConfig(
        name="test_source",
        source_module="sources.ebird.source",
        description="Test pipeline",
        schedule=PipelineSchedule(cron="0 6 * * *", enabled=True),
        params={"region_code": "US-AZ", "max_results": 100, "days_back": 7},
        quality_rules=[],
        transform_project="ebird",
    )


@pytest.fixture
def mock_sources_dir(tmp_path):
    """Create a temp sources/ directory with a YAML config for ebird."""
    sources_dir = tmp_path / "sources"
    sources_dir.mkdir()
    ebird_dir = sources_dir / "ebird"
    ebird_dir.mkdir()
    yaml_content = """
source_module: "sources.ebird.source"
description: "Test eBird pipeline"
schedule:
  cron: "0 6 * * *"
  enabled: true
params:
  region_code: "US-AZ"
  max_results: 100
  days_back: 7
transform_project: "ebird"
"""
    (ebird_dir / "config.yaml").write_text(yaml_content)
    return sources_dir


@pytest.fixture
def mock_source():
    """Create a mock PipelineSource for testing."""

    class MockSource:
        name = "mock_source"

        def __init__(self, config):
            self.config = config

        def resources(self):
            return []

        def load(self):
            return MagicMock()

        def validate_config(self):
            return True

    return MockSource


def _make_mock_source(
    name: str = "mock_source",
    *,
    valid: bool = True,
    resources: list | None = None,
    load_result: Any = None,
):
    """Factory for creating mock PipelineSource instances."""

    class _MockSource:
        pass

    source = _MockSource()
    source.name = name
    source.config = PipelineConfig(
        name=name,
        source_module="mock.module",
        schedule=PipelineSchedule(),
    )
    source.resources = MagicMock(return_value=resources or [])
    source.load = MagicMock(return_value=load_result or MagicMock())
    source.validate_config = MagicMock(return_value=valid)
    return source


@pytest.fixture
def make_mock_source():
    """Fixture that returns the mock source factory."""
    return _make_mock_source


@pytest.fixture
def mock_ebird_api_token(monkeypatch):
    """Set a fake eBird API token."""
    monkeypatch.setenv("EBIRD_API_TOKEN", "test_token_12345")


@pytest.fixture
def ebird_sample_observations():
    """Sample eBird observation data matching API response shape."""
    return [
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


@pytest.fixture
def ebird_sample_hotspots():
    """Sample eBird hotspot data."""
    return [
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


@pytest.fixture
def ebird_sample_taxonomy():
    """Sample eBird taxonomy data."""
    return [
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


@pytest.fixture
def ebird_sample_species_list():
    """Sample species code list."""
    return ["norcar", "moudov", "amecro", "bkcchi"]


@pytest.fixture
def e2e_db(tmp_path, monkeypatch):
    """Temp DuckDB for e2e tests — overrides both dlt settings and SQLMesh connection."""
    import config.settings as settings_mod

    db_path = tmp_path / "e2e_test.db"
    duckdb.connect(str(db_path)).close()

    monkeypatch.setattr(settings_mod.settings, "database_url", f"duckdb:///{db_path}")
    monkeypatch.setattr(settings_mod.settings, "dlt_data_dir", str(tmp_path / ".dlt"))
    return db_path


def load_test_data_to_db(con, schema: str, table: str, rows: list[dict]):
    """Load test data rows into a DuckDB table, creating schema if needed."""
    if not rows:
        return
    con.execute(f"CREATE SCHEMA IF NOT EXISTS {schema}")
    import pandas as pd

    con.register("_tmp", pd.DataFrame(rows))
    con.execute(f"CREATE TABLE IF NOT EXISTS {schema}.{table} AS SELECT * FROM _tmp")
    con.execute(f"INSERT INTO {schema}.{table} SELECT * FROM _tmp")
    con.unregister("_tmp")
