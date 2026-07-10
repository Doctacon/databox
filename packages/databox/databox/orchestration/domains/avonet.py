"""AVONET domain — independently runnable pinned-snapshot ingestion."""

import typing as t
from collections.abc import Iterator
from contextlib import contextmanager, suppress

import dagster as dg
from dagster import AssetExecutionContext
from dagster_dlt import DagsterDltResource, dlt_assets
from databox_sources.avonet import source as avonet_source_module
from databox_sources.avonet.source import avonet_source

from databox.config.settings import DATA_DIR, settings
from databox.destinations import (
    dlt_destination,
    dlt_pipeline,
    prepare_dlt_source,
    quack_ingest_session,
)
from databox.orchestration._factories import dlt_translator

_AVONET_STAGING_SCHEMA = "raw_avonet_staging"
_AVONET_FINAL_SCHEMA = "raw_avonet"
_AVONET_BUSINESS_TABLE = "species_traits"
_AVONET_REQUIRED_METADATA = ("_dlt_loads", "_dlt_version")
_AVONET_OPTIONAL_METADATA = ("_dlt_pipeline_state",)
_AVONET_EXPECTED_COLUMNS = (
    *avonet_source_module._COLUMNS,
    "_dlt_load_id",
    "_dlt_id",
)


def _table_exists(connection: t.Any, schema: str, table: str) -> bool:
    row = connection.execute(
        """
        SELECT count(*)
        FROM information_schema.tables
        WHERE table_schema = ? AND table_name = ? AND table_type = 'BASE TABLE'
        """,
        [schema, table],
    ).fetchone()
    return bool(row and row[0] == 1)


def _drop_avonet_staging(database_path: str) -> None:
    import duckdb

    connection = duckdb.connect(database_path)
    try:
        connection.execute(f"DROP SCHEMA IF EXISTS {_AVONET_STAGING_SCHEMA} CASCADE")
    finally:
        connection.close()


def _cleanup_avonet_staging_best_effort(database_path: str) -> None:
    with suppress(Exception):
        _drop_avonet_staging(database_path)


def _validate_avonet_staging(
    connection: t.Any,
    *,
    expected_rows: int,
    expected_columns: tuple[str, ...],
) -> None:
    if not _table_exists(connection, _AVONET_STAGING_SCHEMA, _AVONET_BUSINESS_TABLE):
        raise RuntimeError("AVONET staging business table is missing")
    columns = tuple(
        row[0]
        for row in connection.execute(
            """
            SELECT column_name
            FROM information_schema.columns
            WHERE table_schema = ? AND table_name = ?
            ORDER BY ordinal_position
            """,
            [_AVONET_STAGING_SCHEMA, _AVONET_BUSINESS_TABLE],
        ).fetchall()
    )
    if columns != expected_columns:
        raise RuntimeError("AVONET staging columns do not match the publish contract")
    row = connection.execute(
        f"""
        SELECT
            count(*),
            count(DISTINCT avibase_id),
            count(DISTINCT source_scientific_name)
        FROM {_AVONET_STAGING_SCHEMA}.{_AVONET_BUSINESS_TABLE}
        """
    ).fetchone()
    counts = tuple(int(value) for value in row) if row is not None else (0, 0, 0)
    if counts != (expected_rows, expected_rows, expected_rows):
        raise RuntimeError("AVONET staging row or uniqueness validation failed")
    for table in _AVONET_REQUIRED_METADATA:
        if not _table_exists(connection, _AVONET_STAGING_SCHEMA, table):
            raise RuntimeError(f"AVONET staging metadata table {table} is missing")


def _replace_avonet_final_table(connection: t.Any, table: str) -> None:
    connection.execute(
        f"""
        CREATE OR REPLACE TABLE {_AVONET_FINAL_SCHEMA}.{table} AS
        SELECT * FROM {_AVONET_STAGING_SCHEMA}.{table}
        """
    )


def _publish_avonet_staging(
    database_path: str,
    *,
    expected_rows: int,
    expected_columns: tuple[str, ...] = _AVONET_EXPECTED_COLUMNS,
) -> None:
    import duckdb

    connection = duckdb.connect(database_path)
    try:
        connection.execute("BEGIN TRANSACTION")
        try:
            _validate_avonet_staging(
                connection,
                expected_rows=expected_rows,
                expected_columns=expected_columns,
            )
            connection.execute(f"CREATE SCHEMA IF NOT EXISTS {_AVONET_FINAL_SCHEMA}")
            _replace_avonet_final_table(connection, _AVONET_BUSINESS_TABLE)
            for table in _AVONET_REQUIRED_METADATA:
                _replace_avonet_final_table(connection, table)
            for table in _AVONET_OPTIONAL_METADATA:
                if _table_exists(connection, _AVONET_STAGING_SCHEMA, table):
                    _replace_avonet_final_table(connection, table)
                elif _table_exists(connection, _AVONET_FINAL_SCHEMA, table):
                    connection.execute(f"DROP TABLE {_AVONET_FINAL_SCHEMA}.{table}")
            connection.execute(f"DROP SCHEMA {_AVONET_STAGING_SCHEMA} CASCADE")
            connection.execute("COMMIT")
        except BaseException:
            with suppress(Exception):
                connection.execute("ROLLBACK")
            raise
    finally:
        connection.close()


@contextmanager
def avonet_staged_publish(
    database_path: str,
    *,
    expected_rows: int,
    expected_columns: tuple[str, ...] = _AVONET_EXPECTED_COLUMNS,
) -> Iterator[None]:
    """Clear crash residue and atomically publish one validated AVONET snapshot."""

    _drop_avonet_staging(database_path)
    (DATA_DIR / ".quack-clients").mkdir(parents=True, exist_ok=True)
    try:
        yield
        _publish_avonet_staging(
            database_path,
            expected_rows=expected_rows,
            expected_columns=expected_columns,
        )
    except BaseException:
        _cleanup_avonet_staging_best_effort(database_path)
        raise


@dlt_assets(
    dlt_source=avonet_source(),
    dlt_pipeline=dlt_pipeline(
        pipeline_name="avonet_file",
        destination=dlt_destination(settings.raw_catalog_path("avonet")),
        dataset_name=_AVONET_STAGING_SCHEMA,
        pipelines_dir=settings.dlt_data_dir,
    ),
    group_name="avonet_ingestion",
    dagster_dlt_translator=dlt_translator("raw_avonet"),
)
def avonet_dlt_assets(context: AssetExecutionContext, dlt: DagsterDltResource) -> t.Iterator[t.Any]:
    if settings.quack_shared_server:
        raise RuntimeError("AVONET ingest requires its independent Quack server")
    with avonet_staged_publish(
        settings.database_path,
        expected_rows=avonet_source_module.AVONET_EXPECTED_ROWS,
    ):
        with quack_ingest_session(_AVONET_STAGING_SCHEMA):
            yield from dlt.run(context=context, dlt_source=prepare_dlt_source(avonet_source()))


dlt_asset_keys = [spec.key for spec in avonet_dlt_assets.specs]
sqlmesh_asset_keys: list[dg.AssetKey] = []
asset_checks: list[dg.AssetChecksDefinition] = []

ingest_job = dg.define_asset_job(
    name="avonet_ingest",
    selection=dg.AssetSelection.assets(*dlt_asset_keys),
    executor_def=dg.in_process_executor,
)
