"""GBIF domain — dlt ingestion assets and source schedule."""

import typing as t

import dagster as dg
from dagster import AssetExecutionContext
from dagster_dlt import DagsterDltResource, dlt_assets
from databox_sources.gbif.source import (
    GBIF_EBIRD_EOD_DATASET_KEY,
    GBIF_RUFOUS_TAXON_KEY,
    GBIF_SEARCH_RECORD_CAP,
    gbif_source,
)

from databox.config.settings import settings
from databox.destinations import (
    dlt_destination,
    dlt_pipeline,
    prepare_dlt_source,
    quack_ingest_session,
)
from databox.orchestration._factories import dlt_translator


def _build_source(
    *,
    max_records: int | None = None,
    public_release: bool | None = None,
) -> t.Any:
    effective_max_records = settings.gbif_max_records if max_records is None else max_records
    if not 1 <= effective_max_records <= GBIF_SEARCH_RECORD_CAP:
        raise ValueError(f"GBIF max_records must be between 1 and {GBIF_SEARCH_RECORD_CAP:,}")
    is_public_release = settings.gbif_public_release if public_release is None else public_release
    return gbif_source(
        country_code="US",
        state_province="Arizona",
        taxon_key=212,
        dataset_key=GBIF_EBIRD_EOD_DATASET_KEY if is_public_release else None,
        max_records=effective_max_records,
        has_coordinate=True,
        required_taxon_key=GBIF_RUFOUS_TAXON_KEY if is_public_release else None,
        license_code="CC_BY_4_0" if is_public_release else None,
        occurrence_status="PRESENT" if is_public_release else None,
    )


@dlt_assets(
    dlt_source=_build_source(),
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
    source = _build_source()
    if settings.smoke:
        source.add_limit(max_items=5)
    with quack_ingest_session(settings.raw_dataset_name("gbif")):
        yield from dlt.run(context=context, dlt_source=prepare_dlt_source(source))


assets = [gbif_dlt_assets]
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
