"""USGS Earthquakes domain — dlt ingestion + SQLMesh marts + Soda checks."""

import typing as t
from datetime import timedelta

import dagster as dg
import dlt
from dagster import AssetExecutionContext
from dagster_dlt import DagsterDltResource, dlt_assets
from databox_sources.usgs_earthquakes.source import usgs_earthquakes_source

from databox.config.settings import settings
from databox.orchestration._factories import (
    SODA_DIR,
    dlt_destination,
    dlt_translator,
    freshness_checks,
    soda_check,
)


@dlt_assets(
    dlt_source=usgs_earthquakes_source(),
    dlt_pipeline=dlt.pipeline(
        pipeline_name="usgs_earthquakes_api",
        destination=dlt_destination(settings.raw_catalog_path("usgs_earthquakes")),
        dataset_name="main",
        pipelines_dir=settings.dlt_data_dir,
    ),
    group_name="usgs_earthquakes_ingestion",
    dagster_dlt_translator=dlt_translator("raw_usgs_earthquakes"),
)
def usgs_earthquakes_dlt_assets(
    context: AssetExecutionContext, dlt: DagsterDltResource
) -> t.Iterator[t.Any]:
    source = usgs_earthquakes_source()
    if settings.smoke:
        source.add_limit(max_items=5)
    yield from dlt.run(context=context, dlt_source=source)


dlt_asset_keys = [spec.key for spec in usgs_earthquakes_dlt_assets.specs]

sqlmesh_asset_keys = [
    dg.AssetKey(["sqlmesh", "usgs_earthquakes_staging", "stg_usgs_earthquakes_events"]),
    dg.AssetKey(["sqlmesh", "usgs_earthquakes", "fct_daily_earthquakes"]),
]

FRESHNESS_SLAS: dict[dg.AssetKey, timedelta] = {
    dg.AssetKey(["sqlmesh", "usgs_earthquakes", "fct_daily_earthquakes"]): timedelta(hours=30),
}

asset_checks: list[dg.AssetChecksDefinition] = [
    soda_check(
        dg.AssetKey(["sqlmesh", "usgs_earthquakes_staging", "stg_usgs_earthquakes_events"]),
        SODA_DIR / "contracts/usgs_earthquakes_staging/stg_usgs_earthquakes_events.yaml",
    ),
    soda_check(
        dg.AssetKey(["sqlmesh", "usgs_earthquakes", "fct_daily_earthquakes"]),
        SODA_DIR / "contracts/usgs_earthquakes/fct_daily_earthquakes.yaml",
    ),
    *freshness_checks(FRESHNESS_SLAS),
]

daily_pipeline = dg.define_asset_job(
    name="usgs_earthquakes_daily_pipeline",
    selection=dg.AssetSelection.assets(*dlt_asset_keys, *sqlmesh_asset_keys),
)

schedule = dg.ScheduleDefinition(job=daily_pipeline, cron_schedule="0 6 * * *")
