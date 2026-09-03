"""GBIF ingestion into the authoritative Polaris Iceberg catalog."""

import os
import subprocess
import sys
import typing as t
from pathlib import Path

import dagster as dg
from dagster import AssetExecutionContext
from dagster_dlt import DagsterDltResource, dlt_assets
from databox_sources.gbif.source import (
    GBIF_EBIRD_EOD_DATASET_KEY,
    GBIF_RUFOUS_TAXON_KEY,
    GBIF_SEARCH_RECORD_CAP,
    gbif_source,
)

from databox.config.settings import PROJECT_ROOT, settings
from databox.destinations.iceberg import (
    iceberg_destination,
    iceberg_dlt_pipeline,
    polaris_dlt_catalog,
    require_iceberg_write_credentials,
)
from databox.orchestration._factories import dlt_load_status_asset, dlt_translator


def _build_source(*, max_records: int | None = None, public_release: bool | None = None) -> t.Any:
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


_gbif_dlt_pipeline = iceberg_dlt_pipeline(
    pipeline_name="gbif_iceberg",
    destination=iceberg_destination(),
    dataset_name="raw_gbif",
    pipelines_dir=settings.dlt_data_dir,
)


@dlt_assets(
    dlt_source=_build_source(),
    dlt_pipeline=_gbif_dlt_pipeline,
    group_name="gbif_ingestion",
    dagster_dlt_translator=dlt_translator("raw_gbif"),
)
def gbif_dlt_assets(context: AssetExecutionContext, dlt: DagsterDltResource) -> t.Iterator[t.Any]:
    source = _build_source()
    if settings.smoke:
        source.add_limit(max_items=5)
    require_iceberg_write_credentials()
    with polaris_dlt_catalog():
        yield from dlt.run(context=context, dlt_source=source)


dlt_asset_keys = [spec.key for spec in gbif_dlt_assets.specs]
gbif_load_status = dlt_load_status_asset(
    pipeline=_gbif_dlt_pipeline,
    dataset_name="raw_gbif",
    table_names=("occurrences",),
    deps=dlt_asset_keys,
    group_name="gbif_ingestion",
)
gbif_load_status_key = gbif_load_status.key


@dg.asset(
    key=dg.AssetKey(["environmental_observations", "gbif_iceberg_refresh"]),
    deps=[
        dg.AssetKey(["sqlmesh", "raw_gbif", "occurrences"]),
        dg.AssetKey(["sqlmesh", "raw_gbif", "_dlt_load_status"]),
    ],
    group_name="gbif_ingestion",
)
def gbif_iceberg_refresh(
    context: AssetExecutionContext,
) -> dg.MaterializeResult[t.Any]:
    """Refresh the local GBIF projection after dlt commits its Iceberg snapshot."""
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
            "environmental_observations.fact_bird_occurrence",
            "--restate-model",
            "environmental_observations.fact_bird_occurrence",
        ],
        cwd=PROJECT_ROOT,
        env=os.environ.copy(),
        check=True,
        capture_output=True,
        text=True,
    )
    return dg.MaterializeResult(metadata={"sqlmesh_refreshed": True})


assets = [gbif_dlt_assets, gbif_load_status, gbif_iceberg_refresh]
sqlmesh_asset_keys = [gbif_iceberg_refresh.key]
asset_checks: list[dg.AssetChecksDefinition] = []

ingest_job = dg.define_asset_job(
    name="gbif_ingest",
    selection=dg.AssetSelection.assets(*dlt_asset_keys, gbif_load_status_key),
    executor_def=dg.in_process_executor,
)
daily_pipeline = dg.define_asset_job(
    name="gbif_daily_pipeline",
    selection=dg.AssetSelection.assets(
        *dlt_asset_keys, gbif_load_status_key, gbif_iceberg_refresh.key
    ),
    executor_def=dg.in_process_executor,
)
schedule = dg.ScheduleDefinition(job=daily_pipeline, cron_schedule="0 6 * * *")
