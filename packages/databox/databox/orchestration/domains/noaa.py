"""NOAA domain — dlt ingestion + SQLMesh marts + Soda checks."""

from datetime import timedelta

import dagster as dg
import dlt
from dagster import AssetExecutionContext
from dagster_dlt import DagsterDltResource, dlt_assets
from databox_sources.noaa.source import noaa_source

from databox.config.settings import settings
from databox.orchestration._factories import (
    SODA_DIR,
    dlt_destination,
    dlt_translator,
    freshness_checks,
    soda_check,
)


@dlt_assets(
    dlt_source=noaa_source(
        location_id="FIPS:04",
        dataset_id="GHCND",
        days_back=settings.days_back("noaa"),
        datatypes="TMAX,TMIN,PRCP,SNOW,AWND",
    ),
    dlt_pipeline=dlt.pipeline(
        pipeline_name="noaa_api",
        destination=dlt_destination(settings.raw_noaa_path),
        dataset_name="main",
        pipelines_dir=settings.dlt_data_dir,
    ),
    group_name="noaa_ingestion",
    dagster_dlt_translator=dlt_translator("raw_noaa"),
)
def noaa_dlt_assets(context: AssetExecutionContext, dlt: DagsterDltResource):
    source = noaa_source(
        location_id="FIPS:04",
        dataset_id="GHCND",
        days_back=settings.days_back("noaa"),
        datatypes="TMAX,TMIN,PRCP,SNOW,AWND",
    )
    if settings.smoke:
        source.add_limit(max_items=5)
    yield from dlt.run(context=context, dlt_source=source)


dlt_asset_keys = [spec.key for spec in noaa_dlt_assets.specs]

sqlmesh_asset_keys = [
    dg.AssetKey(["sqlmesh", "noaa_staging", "stg_noaa_daily_weather"]),
    dg.AssetKey(["sqlmesh", "noaa_staging", "stg_noaa_stations"]),
    dg.AssetKey(["sqlmesh", "noaa", "fct_daily_weather"]),
]

FRESHNESS_SLAS: dict[dg.AssetKey, timedelta] = {
    dg.AssetKey(["sqlmesh", "noaa", "fct_daily_weather"]): timedelta(hours=48),
}

asset_checks: list[dg.AssetChecksDefinition] = [
    soda_check(
        dg.AssetKey(["sqlmesh", "noaa_staging", "stg_noaa_daily_weather"]),
        SODA_DIR / "contracts/noaa_staging/stg_noaa_daily_weather.yaml",
    ),
    soda_check(
        dg.AssetKey(["sqlmesh", "noaa_staging", "stg_noaa_stations"]),
        SODA_DIR / "contracts/noaa_staging/stg_noaa_stations.yaml",
    ),
    soda_check(
        dg.AssetKey(["sqlmesh", "noaa", "fct_daily_weather"]),
        SODA_DIR / "contracts/noaa/fct_daily_weather.yaml",
    ),
    *freshness_checks(FRESHNESS_SLAS),
]

daily_pipeline = dg.define_asset_job(
    name="noaa_daily_pipeline",
    selection=dg.AssetSelection.assets(*dlt_asset_keys, *sqlmesh_asset_keys),
)

schedule = dg.ScheduleDefinition(job=daily_pipeline, cron_schedule="0 6 * * *")
