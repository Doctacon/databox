"""GBIF domain — dlt ingestion assets and source schedule."""

import typing as t

import dagster as dg
from dagster import AssetExecutionContext
from dagster_dlt import DagsterDltResource, dlt_assets
from databox_sources.gbif.source import gbif_source

from databox.config.settings import settings
from databox.destinations import (
    dlt_destination,
    dlt_pipeline,
    prepare_dlt_source,
    quack_ingest_session,
)
from databox.orchestration._factories import dlt_translator


@dlt_assets(
    dlt_source=gbif_source(
        country_code="US",
        state_province="Arizona",
        taxon_key=212,
        max_records=1000,
        has_coordinate=True,
    ),
    dlt_pipeline=dlt_pipeline(
        pipeline_name="gbif_api",
        destination=dlt_destination(settings.raw_catalog_path("gbif")),
        dataset_name=settings.raw_dataset_name("gbif"),
        pipelines_dir=settings.dlt_data_dir,
    ),
    group_name="gbif_ingestion",
    dagster_dlt_translator=dlt_translator("raw_gbif"),
)
def gbif_dlt_assets(context: AssetExecutionContext, dlt: DagsterDltResource) -> t.Iterator[t.Any]:
    source = gbif_source(
        country_code="US",
        state_province="Arizona",
        taxon_key=212,
        max_records=1000,
        has_coordinate=True,
    )
    if settings.smoke:
        source.add_limit(max_items=5)
    with quack_ingest_session(settings.raw_dataset_name("gbif")):
        yield from dlt.run(context=context, dlt_source=prepare_dlt_source(source))


dlt_asset_keys = [spec.key for spec in gbif_dlt_assets.specs]
sqlmesh_asset_keys: list[dg.AssetKey] = []
asset_checks: list[dg.AssetChecksDefinition] = []

ingest_job = dg.define_asset_job(
    name="gbif_ingest",
    selection=dg.AssetSelection.assets(*dlt_asset_keys),
    executor_def=dg.in_process_executor,
)

daily_pipeline = dg.define_asset_job(
    name="gbif_daily_pipeline",
    selection=dg.AssetSelection.assets(*dlt_asset_keys),
    executor_def=dg.in_process_executor,
)

schedule = dg.ScheduleDefinition(job=daily_pipeline, cron_schedule="0 6 * * *")
