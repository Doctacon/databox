"""USGS domain — dlt ingestion assets and source schedule."""

import typing as t

import dagster as dg
from dagster import AssetExecutionContext
from dagster_dlt import DagsterDltResource, dlt_assets
from databox_sources.usgs.source import usgs_source

from databox.config.settings import settings
from databox.destinations import (
    dlt_destination,
    dlt_pipeline,
    prepare_dlt_source,
    quack_ingest_session,
)
from databox.orchestration._factories import dlt_translator


@dlt_assets(
    dlt_source=usgs_source(
        state_cd="AZ", parameter_cds="00060,00065,00010", days_back=settings.days_back("usgs")
    ),
    dlt_pipeline=dlt_pipeline(
        pipeline_name="usgs_api",
        destination=dlt_destination(settings.raw_catalog_path("usgs")),
        dataset_name=settings.raw_dataset_name("usgs"),
        pipelines_dir=settings.dlt_data_dir,
    ),
    group_name="usgs_ingestion",
    dagster_dlt_translator=dlt_translator("raw_usgs"),
)
def usgs_dlt_assets(context: AssetExecutionContext, dlt: DagsterDltResource) -> t.Iterator[t.Any]:
    source = usgs_source(
        state_cd="AZ", parameter_cds="00060,00065,00010", days_back=settings.days_back("usgs")
    )
    if settings.smoke:
        source.add_limit(max_items=5)
    with quack_ingest_session():
        yield from dlt.run(context=context, dlt_source=prepare_dlt_source(source))


dlt_asset_keys = [spec.key for spec in usgs_dlt_assets.specs]
sqlmesh_asset_keys: list[dg.AssetKey] = []
asset_checks: list[dg.AssetChecksDefinition] = []

ingest_job = dg.define_asset_job(
    name="usgs_ingest",
    selection=dg.AssetSelection.assets(*dlt_asset_keys),
    executor_def=dg.in_process_executor,
)

daily_pipeline = dg.define_asset_job(
    name="usgs_daily_pipeline",
    selection=dg.AssetSelection.assets(*dlt_asset_keys),
    executor_def=dg.in_process_executor,
)

schedule = dg.ScheduleDefinition(job=daily_pipeline, cron_schedule="0 6 * * *")
