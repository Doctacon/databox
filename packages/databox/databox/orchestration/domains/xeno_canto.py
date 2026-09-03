"""Xeno-canto domain — dlt ingestion assets and source schedule."""

import os
import subprocess
import sys
import typing as t
from pathlib import Path

import dagster as dg
from dagster import AssetExecutionContext
from dagster_dlt import DagsterDltResource, dlt_assets
from databox_sources.xeno_canto.source import XENO_CANTO_DEFAULT_QUERY, xeno_canto_source

from databox.config.settings import PROJECT_ROOT, settings
from databox.destinations.iceberg import (
    iceberg_destination,
    iceberg_dlt_pipeline,
    polaris_dlt_catalog,
    require_iceberg_write_credentials,
)
from databox.orchestration._factories import dlt_load_status_asset, dlt_translator


def _build_source(*, max_records: int = 1000, per_page: int = 100) -> t.Any:
    return xeno_canto_source(
        query=XENO_CANTO_DEFAULT_QUERY,
        max_records=max_records,
        per_page=per_page,
    )


_xeno_canto_dlt_pipeline = iceberg_dlt_pipeline(
    pipeline_name="xeno_canto_iceberg",
    destination=iceberg_destination(),
    dataset_name="raw_xeno_canto",
    pipelines_dir=settings.dlt_data_dir,
)


@dlt_assets(
    dlt_source=_build_source(),
    dlt_pipeline=_xeno_canto_dlt_pipeline,
    group_name="xeno_canto_ingestion",
    dagster_dlt_translator=dlt_translator("raw_xeno_canto"),
)
def xeno_canto_dlt_assets(
    context: AssetExecutionContext, dlt: DagsterDltResource
) -> t.Iterator[t.Any]:
    source = _build_source()
    if settings.smoke:
        source.add_limit(max_items=5)
    require_iceberg_write_credentials()
    with polaris_dlt_catalog():
        yield from dlt.run(context=context, dlt_source=source)


@dg.asset(
    key=dg.AssetKey(["environmental_observations", "xeno_canto_iceberg_refresh"]),
    deps=[
        dg.AssetKey(["sqlmesh", "raw_xeno_canto", "recordings"]),
        dg.AssetKey(["sqlmesh", "raw_xeno_canto", "_dlt_load_status"]),
    ],
    group_name="xeno_canto_ingestion",
)
def xeno_canto_iceberg_refresh(
    context: AssetExecutionContext,
) -> dg.MaterializeResult[t.Any]:
    """Refresh local Xeno-canto consumers after the Iceberg snapshot commits."""
    models = (
        "environmental_observations.dim_species",
        "environmental_observations.fact_bird_sound_recording",
        "analytics.platform_health",
    )
    command = [
        str(Path(sys.executable).with_name("sqlmesh")),
        "-p",
        "transforms/main",
        "plan",
        "prod",
        "--auto-apply",
        "--no-prompts",
    ]
    for flag in ("--select-model", "--restate-model"):
        for model in models:
            command.extend([flag, model])
    subprocess.run(
        command, cwd=PROJECT_ROOT, env=os.environ.copy(), check=True, capture_output=True, text=True
    )
    return dg.MaterializeResult(metadata={"sqlmesh_refreshed": True})


dlt_asset_keys = [spec.key for spec in xeno_canto_dlt_assets.specs]
xeno_canto_load_status = dlt_load_status_asset(
    pipeline=_xeno_canto_dlt_pipeline,
    dataset_name="raw_xeno_canto",
    table_names=("recordings",),
    deps=dlt_asset_keys,
    group_name="xeno_canto_ingestion",
)
xeno_canto_load_status_key = xeno_canto_load_status.key
assets = [xeno_canto_dlt_assets, xeno_canto_load_status, xeno_canto_iceberg_refresh]
sqlmesh_asset_keys = [xeno_canto_iceberg_refresh.key]
asset_checks: list[dg.AssetChecksDefinition] = []

ingest_job = dg.define_asset_job(
    name="xeno_canto_ingest",
    selection=dg.AssetSelection.assets(*dlt_asset_keys, xeno_canto_load_status_key),
    executor_def=dg.in_process_executor,
)

daily_pipeline = dg.define_asset_job(
    name="xeno_canto_daily_pipeline",
    selection=dg.AssetSelection.assets(
        *dlt_asset_keys, xeno_canto_load_status_key, xeno_canto_iceberg_refresh.key
    ),
    executor_def=dg.in_process_executor,
)

schedule = dg.ScheduleDefinition(job=daily_pipeline, cron_schedule="0 6 * * *")
