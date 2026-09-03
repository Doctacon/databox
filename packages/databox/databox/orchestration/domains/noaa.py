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
    require_iceberg_write_credentials,
)
from databox.orchestration._factories import dlt_load_status_asset, dlt_translator


def _build_source() -> t.Any:
    return noaa_source(
        location_id="FIPS:04",
        dataset_id="GHCND",
        days_back=settings.days_back("noaa"),
        datatypes="TMAX,TMIN,PRCP,SNOW,AWND",
    )


_noaa_dlt_pipeline = iceberg_dlt_pipeline(
    pipeline_name="noaa_iceberg",
    destination=iceberg_destination(),
    dataset_name="raw_noaa",
    pipelines_dir=settings.dlt_data_dir,
)


@dlt_assets(
    dlt_source=_build_source(),
    dlt_pipeline=_noaa_dlt_pipeline,
    group_name="noaa_ingestion",
    dagster_dlt_translator=dlt_translator("raw_noaa"),
)
def noaa_dlt_assets(context: AssetExecutionContext, dlt: DagsterDltResource) -> t.Iterator[t.Any]:
    source = _build_source()
    if settings.smoke:
        source.add_limit(max_items=5)
    require_iceberg_write_credentials()
    with polaris_dlt_catalog():
        yield from dlt.run(context=context, dlt_source=source)


@dg.asset(
    key=dg.AssetKey(["environmental_observations", "noaa_iceberg_refresh"]),
    deps=[
        dg.AssetKey(["sqlmesh", "raw_noaa", "daily_weather"]),
        dg.AssetKey(["sqlmesh", "raw_noaa", "_dlt_load_status"]),
    ],
    group_name="noaa_ingestion",
)
def noaa_iceberg_refresh(context: AssetExecutionContext) -> dg.MaterializeResult[t.Any]:
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


dlt_asset_keys = [spec.key for spec in noaa_dlt_assets.specs]
noaa_load_status = dlt_load_status_asset(
    pipeline=_noaa_dlt_pipeline,
    dataset_name="raw_noaa",
    table_names=("daily_weather", "stations", "datasets"),
    deps=dlt_asset_keys,
    group_name="noaa_ingestion",
)
noaa_load_status_key = noaa_load_status.key
assets = [noaa_dlt_assets, noaa_load_status, noaa_iceberg_refresh]
sqlmesh_asset_keys = [noaa_iceberg_refresh.key]
asset_checks: list[dg.AssetChecksDefinition] = []

ingest_job = dg.define_asset_job(
    name="noaa_ingest",
    selection=dg.AssetSelection.assets(*dlt_asset_keys, noaa_load_status_key),
    executor_def=dg.in_process_executor,
)

daily_pipeline = dg.define_asset_job(
    name="noaa_daily_pipeline",
    selection=dg.AssetSelection.assets(
        *dlt_asset_keys, noaa_load_status_key, noaa_iceberg_refresh.key
    ),
    executor_def=dg.in_process_executor,
)

schedule = dg.ScheduleDefinition(job=daily_pipeline, cron_schedule="0 6 * * *")
