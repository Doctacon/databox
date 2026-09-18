"""AVONET domain — independently runnable pinned-snapshot Iceberg ingestion."""

import typing as t

import dagster as dg
from dagster import AssetExecutionContext
from dagster_dlt import DagsterDltResource, dlt_assets
from databox_sources.avonet.source import avonet_source

from databox.config.settings import settings
from databox.destinations.iceberg import (
    iceberg_destination,
    iceberg_dlt_pipeline,
    polaris_dlt_catalog,
    require_iceberg_write_credentials,
)
from databox.orchestration._factories import dlt_load_status_asset, dlt_translator


def _build_source() -> t.Any:
    return avonet_source()


_avonet_dlt_pipeline = iceberg_dlt_pipeline(
    pipeline_name="avonet_iceberg",
    destination=iceberg_destination(),
    dataset_name="raw_avonet",
    pipelines_dir=settings.dlt_data_dir,
)


@dlt_assets(
    dlt_source=_build_source(),
    dlt_pipeline=_avonet_dlt_pipeline,
    group_name="avonet_ingestion",
    dagster_dlt_translator=dlt_translator("raw_avonet"),
)
def avonet_dlt_assets(context: AssetExecutionContext, dlt: DagsterDltResource) -> t.Iterator[t.Any]:
    require_iceberg_write_credentials()
    with polaris_dlt_catalog():
        yield from dlt.run(context=context, dlt_source=_build_source())


dlt_asset_keys = [spec.key for spec in avonet_dlt_assets.specs]
avonet_load_status = dlt_load_status_asset(
    pipeline=_avonet_dlt_pipeline,
    dataset_name="raw_avonet",
    table_names=("species_traits",),
    deps=dlt_asset_keys,
    group_name="avonet_ingestion",
)
avonet_load_status_key = avonet_load_status.key
assets = [avonet_dlt_assets, avonet_load_status]
asset_checks: list[dg.AssetChecksDefinition] = []

ingest_job = dg.define_asset_job(
    name="avonet_ingest",
    selection=dg.AssetSelection.assets(*dlt_asset_keys, avonet_load_status_key),
    executor_def=dg.in_process_executor,
)
