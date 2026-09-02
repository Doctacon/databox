"""eBird domain — dlt ingestion assets and source schedule."""

import os
import subprocess
import sys
import typing as t
from pathlib import Path

import dagster as dg
from dagster import AssetExecutionContext
from dagster_dlt import DagsterDltResource, dlt_assets
from databox_sources.ebird.source import ebird_source

from databox.config.settings import PROJECT_ROOT, settings
from databox.destinations.iceberg import (
    iceberg_destination,
    iceberg_dlt_pipeline,
    polaris_dlt_catalog,
)
from databox.orchestration._factories import dlt_load_status_asset, dlt_translator


def _build_source() -> t.Any:
    return ebird_source(
        region_code="US-AZ", max_results=10000, days_back=settings.days_back("ebird")
    )


_ebird_dlt_pipeline = iceberg_dlt_pipeline(
    pipeline_name="ebird_iceberg",
    destination=iceberg_destination(),
    dataset_name="raw_ebird",
    pipelines_dir=settings.dlt_data_dir,
)


@dlt_assets(
    dlt_source=_build_source(),
    dlt_pipeline=_ebird_dlt_pipeline,
    group_name="ebird_ingestion",
    dagster_dlt_translator=dlt_translator("raw_ebird"),
)
def ebird_dlt_assets(context: AssetExecutionContext, dlt: DagsterDltResource) -> t.Iterator[t.Any]:
    source = _build_source()
    if settings.smoke:
        source.add_limit(max_items=5)
    with polaris_dlt_catalog():
        yield from dlt.run(context=context, dlt_source=source)


@dg.asset(
    key=dg.AssetKey(["environmental_observations", "ebird_iceberg_refresh"]),
    deps=[
        dg.AssetKey(["sqlmesh", "raw_ebird", "recent_observations"]),
        dg.AssetKey(["sqlmesh", "raw_ebird", "_dlt_load_status"]),
    ],
    group_name="ebird_ingestion",
)
def ebird_iceberg_refresh(context: AssetExecutionContext) -> dg.MaterializeResult[t.Any]:
    """Refresh local eBird consumers after the Iceberg snapshots commit."""
    models = (
        "environmental_observations.dim_species",
        "environmental_observations.dim_bird_hotspot",
        "environmental_observations.fact_bird_observation",
        "environmental_observations.fact_region_daily_stats",
        "birding_agent.arizona_species_catalog",
        "analytics.platform_health",
    )
    command = [
        str(Path(sys.executable).with_name("sqlmesh")),
        "-p",
        "transforms/main",
        "plan",
        "prod",
        "--auto-apply",
        "--no-prompts",
    ]
    for flag in ("--select-model", "--restate-model"):
        for model in models:
            command.extend([flag, model])
    subprocess.run(
        command, cwd=PROJECT_ROOT, env=os.environ.copy(), check=True, capture_output=True, text=True
    )
    return dg.MaterializeResult(metadata={"sqlmesh_refreshed": True})


dlt_asset_keys = [spec.key for spec in ebird_dlt_assets.specs]
ebird_load_status = dlt_load_status_asset(
    pipeline=_ebird_dlt_pipeline,
    dataset_name="raw_ebird",
    table_names=(
        "recent_observations",
        "notable_observations",
        "hotspots",
        "species_list",
        "taxonomy",
        "region_stats",
    ),
    deps=dlt_asset_keys,
    group_name="ebird_ingestion",
)
ebird_load_status_key = ebird_load_status.key
assets = [ebird_dlt_assets, ebird_load_status, ebird_iceberg_refresh]
sqlmesh_asset_keys = [ebird_iceberg_refresh.key]
asset_checks: list[dg.AssetChecksDefinition] = []

ingest_job = dg.define_asset_job(
    name="ebird_ingest",
    selection=dg.AssetSelection.assets(*dlt_asset_keys, ebird_load_status_key),
    executor_def=dg.in_process_executor,
)

daily_pipeline = dg.define_asset_job(
    name="ebird_daily_pipeline",
    selection=dg.AssetSelection.assets(
        *dlt_asset_keys, ebird_load_status_key, ebird_iceberg_refresh.key
    ),
    executor_def=dg.in_process_executor,
)

schedule = dg.ScheduleDefinition(job=daily_pipeline, cron_schedule="0 6 * * *")
