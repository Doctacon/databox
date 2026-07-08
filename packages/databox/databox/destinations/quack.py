"""DuckDB / Quack destination helpers.

Quack is the local default: one server owns ``data/databox.duckdb`` while dlt
attaches as a client. Each source physically loads into its own ``raw_*`` schema
inside that file.
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


_DLT_METADATA_TABLES = ("_dlt_loads", "_dlt_version", "_dlt_pipeline_state")

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
        raw_schema: str | None = None,
    ) -> None:
        self.uri = uri or settings.quack_uri
        self.token = token or settings.quack_token
        self.db_path = db_path or settings.database_path
        self.raw_schema = raw_schema
        self._con: Any | None = None

    def __enter__(self) -> QuackServer:
        import duckdb

        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        self._con = duckdb.connect(self.db_path)
        _drop_legacy_raw_views(self._con)
        _publish_quack_metadata_read_views(self._con, self.raw_schema)
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
            _drop_quack_metadata_read_views(self._con)
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
    a direct post-load dedupe against each physical raw schema once its Quack
    server stops. MotherDuck and legacy local keep declared dispositions.
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
def quack_ingest_session(
    raw_schema: str | None = None, db_path: str | None = None
) -> Iterator[None]:
    """Own Quack lifecycle around one hermetic dlt source asset run."""
    if settings.backend != "quack":
        yield
        return

    target = db_path or settings.database_path
    try:
        with _quack_dlt_env(), QuackServer(db_path=target, raw_schema=raw_schema):
            yield
    except BaseException:
        raise
    else:
        dedupe_quack_raw_tables(target)


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


def _relation_type(con: Any, schema: str, table: str) -> str | None:
    row = con.execute(
        """
        SELECT table_type
        FROM information_schema.tables
        WHERE table_schema = ? AND table_name = ?
        """,
        [schema, table],
    ).fetchone()
    return str(row[0]) if row is not None else None


def _base_table_exists(con: Any, schema: str, table: str) -> bool:
    return _relation_type(con, schema, table) == "BASE TABLE"


def _drop_legacy_raw_views(con: Any) -> None:
    """Drop old Quack raw-schema views so dlt can create physical raw tables."""
    schemas = sorted({schema for schema, _ in _RAW_DEDUPE_KEYS})
    metadata_relations = [(schema, table) for schema in schemas for table in _DLT_METADATA_TABLES]
    raw_relations = [*sorted(_RAW_DEDUPE_KEYS), *metadata_relations]
    for schema, table in raw_relations:
        if _relation_type(con, schema, table) == "VIEW":
            con.execute(f"DROP VIEW {schema}.{table}")


def _drop_quack_metadata_read_views(con: Any) -> None:
    """Drop transient main-schema metadata views used only while Quack serves."""
    for table in _DLT_METADATA_TABLES:
        if _relation_type(con, "main", table) == "VIEW":
            con.execute(f"DROP VIEW main.{table}")


def _publish_quack_metadata_read_views(con: Any, raw_schema: str | None) -> None:
    """Expose existing dlt metadata to Quack clients without keeping main tables.

    Quack's attached-catalog beta path currently resolves scans through the main
    schema even when the client search path is a physical raw schema. dlt reads
    `_dlt_version` on repeat loads, so publish main-schema views while the server
    is running and remove them when the hermetic source load finishes.
    """
    _drop_quack_metadata_read_views(con)
    if not raw_schema:
        return
    for table in _DLT_METADATA_TABLES:
        if _base_table_exists(con, raw_schema, table):
            con.execute(f"CREATE VIEW main.{table} AS SELECT * FROM {raw_schema}.{table}")


def _count_rows(con: Any, qualified_table: str) -> int:
    row = con.execute(f"SELECT COUNT(*) FROM {qualified_table}").fetchone()
    return int(row[0]) if row is not None else 0


def dedupe_quack_raw_tables(db_path: str) -> list[str]:
    """Deduplicate append-loaded physical raw tables after a Quack ingest."""
    import duckdb

    changed: list[str] = []
    con = duckdb.connect(db_path)
    try:
        for (schema, table), keys in _RAW_DEDUPE_KEYS.items():
            if not _base_table_exists(con, schema, table):
                continue
            cols = _columns(con, schema, table)
            if not set(keys).issubset(cols):
                continue
            order_cols = [col for col in ("_dlt_load_id", "_dlt_id") if col in cols]
            order_sql = (
                " ORDER BY " + ", ".join(f"{col} DESC" for col in order_cols) if order_cols else ""
            )
            key_sql = ", ".join(keys)
            tmp_table = f"__dedupe_{schema}_{table}"
            qualified = f"{schema}.{table}"
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
