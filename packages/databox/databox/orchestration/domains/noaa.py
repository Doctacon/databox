"""NOAA domain — dlt ingestion assets and source schedule."""

import os
import subprocess
import sys
import typing as t
from pathlib import Path

import dagster as dg
from dagster import AssetExecutionContext
from dagster_dlt import DagsterDltResource, dlt_assets
from databox_sources.noaa.source import noaa_source

from databox.config.settings import PROJECT_ROOT, settings
from databox.destinations.iceberg import (
    iceberg_destination,
    iceberg_dlt_pipeline,
    polaris_dlt_catalog,
)
from databox.orchestration._factories import dlt_translator


def _build_source() -> t.Any:
    return noaa_source(
        location_id="FIPS:04",
        dataset_id="GHCND",
        days_back=settings.days_back("noaa"),
        datatypes="TMAX,TMIN,PRCP,SNOW,AWND",
    )


@dlt_assets(
    dlt_source=_build_source(),
    dlt_pipeline=iceberg_dlt_pipeline(
        pipeline_name="noaa_iceberg",
        destination=iceberg_destination(),
        dataset_name="raw_noaa",
        pipelines_dir=settings.dlt_data_dir,
    ),
    group_name="noaa_ingestion",
    dagster_dlt_translator=dlt_translator("raw_noaa"),
)
def noaa_dlt_assets(context: AssetExecutionContext, dlt: DagsterDltResource) -> t.Iterator[t.Any]:
    source = _build_source()
    if settings.smoke:
        source.add_limit(max_items=5)
    with polaris_dlt_catalog():
        yield from dlt.run(context=context, dlt_source=source)


@dg.asset(
    key=dg.AssetKey(["environmental_observations", "noaa_iceberg_refresh"]),
    deps=[dg.AssetKey(["sqlmesh", "raw_noaa", "daily_weather"])],
    group_name="noaa_ingestion",
)
def noaa_iceberg_refresh(context: AssetExecutionContext) -> dg.MaterializeResult:
    """Refresh local NOAA consumers after the dlt Iceberg snapshot commits."""
    subprocess.run(
        [
            str(Path(sys.executable).with_name("sqlmesh")),
            "-p",
            "transforms/main",
            "plan",
            "prod",
            "--auto-apply",
            "--no-prompts",
            "--select-model",
            "environmental_observations.dim_weather_station",
            "--select-model",
            "environmental_observations.fact_weather_observation",
            "--restate-model",
            "environmental_observations.dim_weather_station",
            "--restate-model",
            "environmental_observations.fact_weather_observation",
        ],
        cwd=PROJECT_ROOT,
        env=os.environ.copy(),
        check=True,
        capture_output=True,
        text=True,
    )
    return dg.MaterializeResult(metadata={"sqlmesh_refreshed": True})


assets = [noaa_dlt_assets, noaa_iceberg_refresh]
dlt_asset_keys = [spec.key for spec in noaa_dlt_assets.specs]
sqlmesh_asset_keys = [noaa_iceberg_refresh.key]
asset_checks: list[dg.AssetChecksDefinition] = []

ingest_job = dg.define_asset_job(
    name="noaa_ingest",
    selection=dg.AssetSelection.assets(*dlt_asset_keys, noaa_iceberg_refresh.key),
    executor_def=dg.in_process_executor,
)

daily_pipeline = dg.define_asset_job(
    name="noaa_daily_pipeline",
    selection=dg.AssetSelection.assets(*dlt_asset_keys, noaa_iceberg_refresh.key),
    executor_def=dg.in_process_executor,
)

schedule = dg.ScheduleDefinition(job=daily_pipeline, cron_schedule="0 6 * * *")
