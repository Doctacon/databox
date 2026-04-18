"""End-to-end pipeline tests against real APIs with a Postgres database.

These tests hit the real eBird and NOAA APIs with small data windows,
load into Postgres, run SQLMesh transforms, and assert mart tables
have rows. They require API tokens and DATABASE_URL to be set in the environment.

Run with:
    uv run pytest -m e2e -v
"""

from __future__ import annotations

import os
from pathlib import Path

import psycopg2
import pytest

PROJECT_ROOT = Path(__file__).parent.parent
TRANSFORMS_DIR = PROJECT_ROOT / "transforms"


def _sqlmesh_context(project: str, database_url: str):
    """Build a SQLMesh Context pointed at a Postgres database."""
    # Parse postgresql://user:pass@host:port/dbname
    import urllib.parse

    from sqlmesh import Context
    from sqlmesh.core.config import Config, GatewayConfig, ModelDefaultsConfig
    from sqlmesh.core.config.connection import PostgresConnectionConfig

    parsed = urllib.parse.urlparse(database_url)
    config = Config(
        gateways={
            "postgres": GatewayConfig(
                connection=PostgresConnectionConfig(
                    host=parsed.hostname or "localhost",
                    port=parsed.port or 5432,
                    database=parsed.path.lstrip("/"),
                    user=parsed.username or "databox",
                    password=parsed.password or "databox",
                )
            )
        },
        default_gateway="postgres",
        model_defaults=ModelDefaultsConfig(dialect="postgres"),
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

        con = psycopg2.connect(e2e_db)
        try:
            cur = con.cursor()
            cur.execute(
                "SELECT table_name FROM information_schema.tables WHERE table_schema = 'raw_ebird'"
            )
            raw_tables = {r[0] for r in cur.fetchall()}
            assert "recent_observations" in raw_tables, (
                f"raw_ebird.recent_observations missing; found: {raw_tables}"
            )

            ctx = _sqlmesh_context("ebird", e2e_db)
            ctx.plan(auto_apply=True, no_prompts=True)

            cur.execute("SELECT DISTINCT table_schema FROM information_schema.tables")
            schemas = {r[0] for r in cur.fetchall()}
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
            params={"location_id": "FIPS:04", "dataset_id": "GHCND", "days_back": 30},
        )
        NoaaPipelineSource(cfg).load()

        con = psycopg2.connect(e2e_db)
        try:
            cur = con.cursor()
            cur.execute(
                "SELECT table_name FROM information_schema.tables WHERE table_schema = 'raw_noaa'"
            )
            raw_tables = {r[0] for r in cur.fetchall()}
            assert "daily_weather" in raw_tables, (
                f"raw_noaa.daily_weather missing; found: {raw_tables}"
            )

            ctx = _sqlmesh_context("noaa", e2e_db)
            ctx.plan(auto_apply=True, no_prompts=True)

            cur.execute("SELECT DISTINCT table_schema FROM information_schema.tables")
            schemas = {r[0] for r in cur.fetchall()}
            assert "noaa" in schemas, f"noaa schema missing after transforms; schemas: {schemas}"
        finally:
            con.close()
