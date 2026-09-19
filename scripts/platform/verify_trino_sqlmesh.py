"""Live isolated SQLMesh incremental upsert/view test; removes only its own schemas."""

from __future__ import annotations

import tempfile
import uuid
from pathlib import Path

from databox.config.settings import settings
from sqlmesh import Context
from sqlmesh.core.config import Config, DuckDBConnectionConfig, GatewayConfig, ModelDefaultsConfig
from trino.dbapi import connect


def main() -> None:
    schema = f"trino_mesh_probe_{uuid.uuid4().hex[:12]}"
    connection = connect(
        host=settings.trino_host,
        port=settings.trino_port,
        user="databox",
        catalog="databox",
        http_scheme="http",
    )
    cursor = connection.cursor()
    try:
        with tempfile.TemporaryDirectory(prefix="databox-trino-mesh-") as directory:
            root = Path(directory)
            (root / "models").mkdir()
            (root / "models" / "events.sql").write_text(
                f"MODEL (name {schema}.events, kind INCREMENTAL_BY_UNIQUE_KEY (unique_key id));\n"
                "SELECT 1 AS id, CAST(@start_ds AS VARCHAR) AS batch_date;\n"
            )
            config = Config(
                gateways={
                    "trino": GatewayConfig(
                        connection=settings.sqlmesh_config().gateways["trino"].connection,
                        state_connection=DuckDBConnectionConfig(
                            database=str(root / "state.duckdb")
                        ),
                    )
                },
                default_gateway="trino",
                model_defaults=ModelDefaultsConfig(dialect="duckdb", start="2026-09-15"),
            )
            context = Context(paths=[root], config=config)
            try:
                context.plan(
                    "probe", start="2026-09-15", end="2026-09-15", auto_apply=True, no_prompts=True
                )
                first = cursor.execute(
                    f"SELECT id, batch_date FROM databox.{schema}__probe.events"
                ).fetchall()
                assert first == [[1, "2026-09-15"]], first
                context.run("probe", start="2026-09-16", end="2026-09-16", ignore_cron=True)
                second = cursor.execute(
                    f"SELECT id, batch_date FROM databox.{schema}__probe.events"
                ).fetchall()
                assert second == [[1, "2026-09-16"]], second
                print("TRINO_SQLMESH_OK plan/apply/incremental-upsert/environment-view")
            finally:
                context.close()
    finally:
        try:
            for namespace in (f"{schema}__probe", f"sqlmesh__{schema}"):
                rows = cursor.execute(
                    "SELECT table_name, table_type FROM databox.information_schema.tables "
                    f"WHERE table_schema = '{namespace}'"
                ).fetchall()
                for name, kind in rows:
                    quoted = '"' + name.replace('"', '""') + '"'
                    object_type = "VIEW" if kind == "VIEW" else "TABLE"
                    cursor.execute(f"DROP {object_type} databox.{namespace}.{quoted}").fetchall()
                cursor.execute(f"DROP SCHEMA IF EXISTS databox.{namespace}").fetchall()
            print("TRINO_SQLMESH_OK cleanup")
        finally:
            connection.close()


if __name__ == "__main__":
    main()
