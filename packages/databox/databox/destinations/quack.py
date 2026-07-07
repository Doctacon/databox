"""DuckDB / Quack destination helpers.

Quack is the local default: one server owns ``data/databox.duckdb`` while dlt
attaches as a client. Raw source schemas are published as views after Quack
loads complete.
"""

from __future__ import annotations

import os
import shutil
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

import dlt
from dlt.destinations.impl.duckdb.configuration import DuckDbCredentials

from databox.config.settings import DATA_DIR, settings


def configure_quack_dlt() -> None:
    """Apply dlt config needed before constructing Quack-backed pipelines."""
    if settings.backend == "quack":
        os.environ["PIPELINES__RESTORE_FROM_DESTINATION"] = "false"


@contextmanager
def _quack_dlt_env() -> Iterator[None]:
    if settings.backend != "quack":
        yield
        return
    previous = os.environ.get("PIPELINES__RESTORE_FROM_DESTINATION")
    os.environ["PIPELINES__RESTORE_FROM_DESTINATION"] = "false"
    try:
        yield
    finally:
        if previous is None:
            os.environ.pop("PIPELINES__RESTORE_FROM_DESTINATION", None)
        else:
            os.environ["PIPELINES__RESTORE_FROM_DESTINATION"] = previous


def dlt_pipeline(*args: Any, **kwargs: Any) -> Any:
    """Create a dlt pipeline with Quack-only config scoped to construction."""
    with _quack_dlt_env():
        return dlt.pipeline(*args, **kwargs)


_RAW_DEDUPE_KEYS: dict[tuple[str, str], tuple[str, ...]] = {
    ("raw_ebird", "recent_observations"): ("sub_id",),
    ("raw_ebird", "notable_observations"): ("sub_id",),
    ("raw_ebird", "hotspots"): ("loc_id",),
    ("raw_ebird", "species_list"): ("species_code",),
    ("raw_ebird", "taxonomy"): ("sci_name",),
    ("raw_ebird", "region_stats"): ("region_code", "year", "month", "day"),
    ("raw_noaa", "daily_weather"): ("date", "datatype", "station"),
    ("raw_noaa", "stations"): ("id",),
    ("raw_noaa", "datasets"): ("id",),
    ("raw_usgs", "daily_values"): ("site_no", "parameter_cd", "observation_date"),
    ("raw_usgs", "sites"): ("site_no",),
    ("raw_usgs_earthquakes", "events"): ("id",),
}


def _sql_literal(value: str) -> str:
    return value.replace("'", "''")


def _load_quack(con: Any) -> None:
    """Install/load Quack for a DuckDB connection.

    INSTALL is idempotent and keeps fresh machines from needing manual extension
    setup before the first Databox run.
    """
    con.execute("INSTALL quack")
    con.execute("LOAD quack")


class QuackServer:
    """Context manager for the local Quack server that owns databox.duckdb."""

    def __init__(
        self,
        uri: str | None = None,
        token: str | None = None,
        db_path: str | None = None,
    ) -> None:
        self.uri = uri or settings.quack_uri
        self.token = token or settings.quack_token
        self.db_path = db_path or settings.database_path
        self._con: Any | None = None

    def __enter__(self) -> QuackServer:
        import duckdb

        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        self._con = duckdb.connect(self.db_path)
        _load_quack(self._con)
        self._con.execute(
            f"CALL quack_serve('{_sql_literal(self.uri)}', token='{_sql_literal(self.token)}')"
        )
        return self

    def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
        if self._con is None:
            return
        try:
            self._con.execute(f"CALL quack_stop('{_sql_literal(self.uri)}')")
        finally:
            self._con.close()
            self._con = None


def quack_credentials() -> DuckDbCredentials:
    """Return DuckDB credentials that route dlt writes through Quack.

    dlt's DuckDB destination only exposes per-borrow PRAGMA hooks. We exploit
    DuckDB's multi-statement support by starting with a real PRAGMA and then
    installing/loading Quack, creating the client secret, attaching the remote
    Databox catalog, and making it the default catalog for dlt's normal SQL.
    """
    pid = os.getpid()
    client_dir = DATA_DIR / ".quack-clients"
    client_dir.mkdir(parents=True, exist_ok=True)
    client_db = client_dir / f"client-{pid}.duckdb"
    uri = _sql_literal(settings.quack_uri)
    token = _sql_literal(settings.quack_token)
    session_setup = (
        "enable_checkpoint_on_shutdown; "
        "INSTALL quack; "
        "LOAD quack; "
        f"CREATE OR REPLACE SECRET databox_quack (TYPE quack, TOKEN '{token}', SCOPE '{uri}'); "
        f"ATTACH IF NOT EXISTS '{uri}' AS databox (TYPE quack); "
        "USE databox"
    )
    return DuckDbCredentials(str(client_db), pragmas=[session_setup])


def prepare_dlt_source(source: Any) -> Any:
    """Apply destination-specific dlt source tweaks.

    Quack's beta attached-catalog path currently handles INSERT/DDL but not the
    DELETE statements dlt emits for merge loads. For the personal local Quack
    path, force raw loads to append during ingest; the Dagster source asset runs
    a direct post-load dedupe once its Quack server stops. MotherDuck and legacy
    local keep declared dispositions.
    """
    if settings.backend != "quack":
        return source
    for resource in source.resources.values():
        resource.apply_hints(write_disposition="append")
    return source


def cleanup_quack_clients() -> None:
    """Remove local Quack client DuckDB files after a client/server ingest run."""
    shutil.rmtree(DATA_DIR / ".quack-clients", ignore_errors=True)


@contextmanager
def quack_ingest_session(db_path: str | None = None) -> Iterator[None]:
    """Own Quack lifecycle around one hermetic dlt source asset run."""
    if settings.backend != "quack":
        yield
        return

    target = db_path or settings.database_path
    try:
        with QuackServer(db_path=target):
            yield
    except BaseException:
        raise
    else:
        dedupe_quack_raw_tables(target)


def _table_exists(con: Any, schema: str, table: str) -> bool:
    return bool(
        con.execute(
            """
            SELECT 1
            FROM information_schema.tables
            WHERE table_schema = ? AND table_name = ?
            """,
            [schema, table],
        ).fetchone()
    )


def _columns(con: Any, schema: str, table: str) -> set[str]:
    rows = con.execute(
        """
        SELECT column_name
        FROM information_schema.columns
        WHERE table_schema = ? AND table_name = ?
        """,
        [schema, table],
    ).fetchall()
    return {row[0] for row in rows}


def _publish_raw_views(con: Any) -> None:
    schemas = sorted({schema for schema, _ in _RAW_DEDUPE_KEYS})
    for schema in schemas:
        source_name = schema.removeprefix("raw_")
        dlt_schema = f"{source_name}_source"
        con.execute(f"CREATE SCHEMA IF NOT EXISTS {schema}")
        if _table_exists(con, "main", "_dlt_loads"):
            con.execute(f"DROP VIEW IF EXISTS {schema}._dlt_loads")
            con.execute(f"DROP TABLE IF EXISTS {schema}._dlt_loads")
            con.execute(
                f"""
                CREATE VIEW {schema}._dlt_loads AS
                SELECT * FROM main._dlt_loads WHERE schema_name = '{_sql_literal(dlt_schema)}'
                """
            )
        if _table_exists(con, "main", "_dlt_version"):
            con.execute(f"DROP VIEW IF EXISTS {schema}._dlt_version")
            con.execute(f"DROP TABLE IF EXISTS {schema}._dlt_version")
            con.execute(
                f"""
                CREATE VIEW {schema}._dlt_version AS
                SELECT * FROM main._dlt_version WHERE schema_name = '{_sql_literal(dlt_schema)}'
                """
            )

    for schema, table in sorted(_RAW_DEDUPE_KEYS):
        if not _table_exists(con, "main", table):
            continue
        con.execute(f"CREATE SCHEMA IF NOT EXISTS {schema}")
        con.execute(f"DROP VIEW IF EXISTS {schema}.{table}")
        con.execute(f"DROP TABLE IF EXISTS {schema}.{table}")
        con.execute(f"CREATE VIEW {schema}.{table} AS SELECT * FROM main.{table}")


def _count_rows(con: Any, qualified_table: str) -> int:
    row = con.execute(f"SELECT COUNT(*) FROM {qualified_table}").fetchone()
    return int(row[0]) if row is not None else 0


def dedupe_quack_raw_tables(db_path: str) -> list[str]:
    """Deduplicate append-loaded main tables and publish raw_<source> views."""
    import duckdb

    changed: list[str] = []
    con = duckdb.connect(db_path)
    try:
        for (_schema, table), keys in _RAW_DEDUPE_KEYS.items():
            if not _table_exists(con, "main", table):
                continue
            cols = _columns(con, "main", table)
            if not set(keys).issubset(cols):
                continue
            order_cols = [col for col in ("_dlt_load_id", "_dlt_id") if col in cols]
            order_sql = (
                " ORDER BY " + ", ".join(f"{col} DESC" for col in order_cols) if order_cols else ""
            )
            key_sql = ", ".join(keys)
            tmp_table = f"__dedupe_main_{table}"
            qualified = f"main.{table}"
            before = _count_rows(con, qualified)
            con.execute(
                f"""
                CREATE OR REPLACE TEMP TABLE {tmp_table} AS
                SELECT * EXCLUDE (rn)
                FROM (
                    SELECT *, ROW_NUMBER() OVER (
                        PARTITION BY {key_sql}{order_sql}
                    ) AS rn
                    FROM {qualified}
                )
                WHERE rn = 1
                """
            )
            after = _count_rows(con, tmp_table)
            if after != before:
                con.execute(f"CREATE OR REPLACE TABLE {qualified} AS SELECT * FROM {tmp_table}")
                changed.append(f"{qualified}: {before} -> {after}")
            con.execute(f"DROP TABLE {tmp_table}")
        _publish_raw_views(con)
    finally:
        con.close()
    return changed


def dlt_destination(db_path: str) -> Any:
    """Return the dlt destination for the current Databox backend."""
    if settings.backend == "motherduck":
        return dlt.destinations.motherduck(credentials=db_path)
    if settings.backend == "quack":
        return dlt.destinations.duckdb(credentials=quack_credentials())
    return dlt.destinations.duckdb(credentials=db_path)
