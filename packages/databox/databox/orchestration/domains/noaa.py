"""NOAA domain — dlt ingestion assets and source schedule."""

import typing as t

import dagster as dg
from dagster import AssetExecutionContext
from dagster_dlt import DagsterDltResource, dlt_assets
from databox_sources.noaa.source import noaa_source

from databox.config.settings import settings
from databox.destinations import (
    dlt_destination,
    dlt_pipeline,
    prepare_dlt_source,
    quack_ingest_session,
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
    dlt_pipeline=dlt_pipeline(
        pipeline_name="noaa_api",
        destination=dlt_destination(settings.raw_catalog_path("noaa")),
        dataset_name=settings.raw_dataset_name("noaa"),
        pipelines_dir=settings.dlt_data_dir,
    ),
    group_name="noaa_ingestion",
    dagster_dlt_translator=dlt_translator("raw_noaa"),
)
def noaa_dlt_assets(context: AssetExecutionContext, dlt: DagsterDltResource) -> t.Iterator[t.Any]:
    source = _build_source()
    if settings.smoke:
        source.add_limit(max_items=5)
    with quack_ingest_session(settings.raw_dataset_name("noaa")):
        yield from dlt.run(context=context, dlt_source=prepare_dlt_source(source))


assets = [noaa_dlt_assets]
dlt_asset_keys = [spec.key for spec in noaa_dlt_assets.specs]
sqlmesh_asset_keys: list[dg.AssetKey] = []
asset_checks: list[dg.AssetChecksDefinition] = []

ingest_job = dg.define_asset_job(
    name="noaa_ingest",
    selection=dg.AssetSelection.assets(*dlt_asset_keys),
    executor_def=dg.in_process_executor,
)

daily_pipeline = dg.define_asset_job(
    name="noaa_daily_pipeline",
    selection=dg.AssetSelection.assets(*dlt_asset_keys),
    executor_def=dg.in_process_executor,
)

schedule = dg.ScheduleDefinition(job=daily_pipeline, cron_schedule="0 6 * * *")
