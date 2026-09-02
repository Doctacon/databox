"""USGS domain — dlt ingestion assets and source schedule."""

import os
import subprocess
import sys
import typing as t
from pathlib import Path

import dagster as dg
from dagster import AssetExecutionContext
from dagster_dlt import DagsterDltResource, dlt_assets
from databox_sources.usgs.source import usgs_source

from databox.config.settings import PROJECT_ROOT, settings
from databox.destinations.iceberg import (
    iceberg_destination,
    iceberg_dlt_pipeline,
    polaris_dlt_catalog,
    publish_dlt_load_status,
)
from databox.orchestration._factories import dlt_translator


def _build_source() -> t.Any:
    return usgs_source(
        state_cd="AZ", parameter_cds="00060,00065,00010", days_back=settings.days_back("usgs")
    )


_usgs_dlt_pipeline = iceberg_dlt_pipeline(
    pipeline_name="usgs_iceberg",
    destination=iceberg_destination(),
    dataset_name="raw_usgs",
    pipelines_dir=settings.dlt_data_dir,
)


@dlt_assets(
    dlt_source=_build_source(),
    dlt_pipeline=_usgs_dlt_pipeline,
    group_name="usgs_ingestion",
    dagster_dlt_translator=dlt_translator("raw_usgs"),
)
def usgs_dlt_assets(context: AssetExecutionContext, dlt: DagsterDltResource) -> t.Iterator[t.Any]:
    source = _build_source()
    if settings.smoke:
        source.add_limit(max_items=5)
    with polaris_dlt_catalog():
        yield from dlt.run(context=context, dlt_source=source)
        publish_dlt_load_status(
            _usgs_dlt_pipeline,
            dataset_name="raw_usgs",
            table_names=("daily_values", "sites"),
        )


@dg.asset(
    key=dg.AssetKey(["environmental_observations", "usgs_iceberg_refresh"]),
    deps=[dg.AssetKey(["sqlmesh", "raw_usgs", "daily_values"])],
    group_name="usgs_ingestion",
)
def usgs_iceberg_refresh(context: AssetExecutionContext) -> dg.MaterializeResult:
    """Refresh local USGS consumers after the Iceberg snapshot commits."""
    models = (
        "environmental_observations.dim_streamgage_site",
        "environmental_observations.fact_streamflow_observation",
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


assets = [usgs_dlt_assets, usgs_iceberg_refresh]
dlt_asset_keys = [spec.key for spec in usgs_dlt_assets.specs]
sqlmesh_asset_keys = [usgs_iceberg_refresh.key]
asset_checks: list[dg.AssetChecksDefinition] = []

ingest_job = dg.define_asset_job(
    name="usgs_ingest",
    selection=dg.AssetSelection.assets(*dlt_asset_keys, usgs_iceberg_refresh.key),
    executor_def=dg.in_process_executor,
)

daily_pipeline = dg.define_asset_job(
    name="usgs_daily_pipeline",
    selection=dg.AssetSelection.assets(*dlt_asset_keys, usgs_iceberg_refresh.key),
    executor_def=dg.in_process_executor,
)

schedule = dg.ScheduleDefinition(job=daily_pipeline, cron_schedule="0 6 * * *")
