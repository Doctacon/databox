"""USGS domain — independently runnable Iceberg ingestion."""

import typing as t

import dagster as dg
from dagster import AssetExecutionContext
from dagster_dlt import DagsterDltResource, dlt_assets
from databox_sources.usgs.source import usgs_source

from databox.config.settings import settings
from databox.destinations.iceberg import (
    iceberg_destination,
    iceberg_dlt_pipeline,
    polaris_dlt_catalog,
    require_iceberg_write_credentials,
)
from databox.orchestration._factories import dlt_load_status_asset, dlt_translator


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
    require_iceberg_write_credentials()
    with polaris_dlt_catalog():
        yield from dlt.run(context=context, dlt_source=source)


dlt_asset_keys = [spec.key for spec in usgs_dlt_assets.specs]
usgs_load_status = dlt_load_status_asset(
    pipeline=_usgs_dlt_pipeline,
    dataset_name="raw_usgs",
    table_names=("daily_values", "sites"),
    deps=dlt_asset_keys,
    group_name="usgs_ingestion",
)
usgs_load_status_key = usgs_load_status.key
assets = [usgs_dlt_assets, usgs_load_status]
asset_checks: list[dg.AssetChecksDefinition] = []

ingest_job = dg.define_asset_job(
    name="usgs_ingest",
    selection=dg.AssetSelection.assets(*dlt_asset_keys, usgs_load_status_key),
    executor_def=dg.in_process_executor,
)
