"""End-to-end pipeline tests against real APIs with a temp DuckDB.

These tests hit the real eBird and NOAA APIs with small data windows,
load into a temp DuckDB, run SQLMesh transforms, and assert mart tables
have rows. They require API tokens to be set in the environment.

Run with:
    uv run pytest -m e2e -v
"""

from __future__ import annotations

import os
from pathlib import Path

import duckdb
import pytest

PROJECT_ROOT = Path(__file__).parent.parent
TRANSFORMS_DIR = PROJECT_ROOT / "transforms"


def _sqlmesh_context(project: str, db_path: Path):
    """Build a SQLMesh Context pointed at a temp DuckDB."""
    from sqlmesh import Context
    from sqlmesh.core.config import Config, GatewayConfig, ModelDefaultsConfig
    from sqlmesh.core.config.connection import DuckDBConnectionConfig

    config = Config(
        gateways={
            "duckdb": GatewayConfig(connection=DuckDBConnectionConfig(database=str(db_path)))
        },
        default_gateway="duckdb",
        model_defaults=ModelDefaultsConfig(dialect="duckdb"),
    )
    return Context(paths=[str(TRANSFORMS_DIR / project)], config=config)


class TestEbirdE2E:
    @pytest.mark.e2e
    def test_ingest_and_transform(self, e2e_db):
        if not os.getenv("EBIRD_API_TOKEN"):
            pytest.skip("EBIRD_API_TOKEN not set")

        from config.pipeline_config import PipelineConfig
        from sources.ebird.source import EbirdPipelineSource

        cfg = PipelineConfig(
            name="ebird",
            source_module="sources.ebird.source",
            params={"region_code": "US-AZ", "days_back": 1, "max_results": 25},
        )
        EbirdPipelineSource(cfg).load()

        con = duckdb.connect(str(e2e_db))
        try:
            raw_tables = {
                r[0]
                for r in con.execute(
                    "SELECT table_name FROM information_schema.tables"
                    " WHERE table_schema = 'raw_ebird'"
                ).fetchall()
            }
            assert "recent_observations" in raw_tables, (
                f"raw_ebird.recent_observations missing; found: {raw_tables}"
            )

            ctx = _sqlmesh_context("ebird", e2e_db)
            ctx.plan(auto_apply=True, no_prompts=True)

            schemas = {
                r[0]
                for r in con.execute(
                    "SELECT DISTINCT table_schema FROM information_schema.tables"
                ).fetchall()
            }
            assert "ebird" in schemas, f"ebird schema missing after transforms; schemas: {schemas}"
        finally:
            con.close()


class TestNoaaE2E:
    @pytest.mark.e2e
    def test_ingest_and_transform(self, e2e_db):
        if not os.getenv("NOAA_API_TOKEN"):
            pytest.skip("NOAA_API_TOKEN not set")

        from config.pipeline_config import PipelineConfig
        from sources.noaa.source import NoaaPipelineSource

        cfg = PipelineConfig(
            name="noaa",
            source_module="sources.noaa.source",
            params={"location_id": "FIPS:04", "dataset_id": "GHCND", "days_back": 3},
        )
        NoaaPipelineSource(cfg).load()

        con = duckdb.connect(str(e2e_db))
        try:
            raw_tables = {
                r[0]
                for r in con.execute(
                    "SELECT table_name FROM information_schema.tables"
                    " WHERE table_schema = 'raw_noaa'"
                ).fetchall()
            }
            assert "daily_weather" in raw_tables, (
                f"raw_noaa.daily_weather missing; found: {raw_tables}"
            )

            ctx = _sqlmesh_context("noaa", e2e_db)
            ctx.plan(auto_apply=True, no_prompts=True)

            schemas = {
                r[0]
                for r in con.execute(
                    "SELECT DISTINCT table_schema FROM information_schema.tables"
                ).fetchall()
            }
            assert "noaa" in schemas, f"noaa schema missing after transforms; schemas: {schemas}"
        finally:
            con.close()
