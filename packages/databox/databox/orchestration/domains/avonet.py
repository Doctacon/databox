"""AVONET domain — independently runnable pinned-snapshot Iceberg ingestion."""

import os
import subprocess
import sys
import typing as t
from pathlib import Path

import dagster as dg
from dagster import AssetExecutionContext
from dagster_dlt import DagsterDltResource, dlt_assets
from databox_sources.avonet.source import avonet_source

from databox.config.settings import PROJECT_ROOT, settings
from databox.destinations.iceberg import (
    iceberg_destination,
    iceberg_dlt_pipeline,
    polaris_dlt_catalog,
    publish_dlt_load_status,
)
from databox.orchestration._factories import dlt_translator


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
    with polaris_dlt_catalog():
        yield from dlt.run(context=context, dlt_source=_build_source())
        publish_dlt_load_status(
            _avonet_dlt_pipeline,
            dataset_name="raw_avonet",
            table_names=("species_traits",),
        )


@dg.asset(
    key=dg.AssetKey(["environmental_observations", "avonet_iceberg_refresh"]),
    deps=[dg.AssetKey(["sqlmesh", "raw_avonet", "species_traits"])],
    group_name="avonet_ingestion",
)
def avonet_iceberg_refresh(context: AssetExecutionContext) -> dg.MaterializeResult:
    """Refresh local AVONET consumers after the Iceberg snapshot commits."""
    models = (
        "environmental_observations.dim_bird_species_traits",
        "rufous_public.avonet_species_traits",
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
    for model in models:
        command.extend(["--select-model", model])
    run_options = {
        "cwd": PROJECT_ROOT,
        "env": os.environ.copy(),
        "check": True,
        "capture_output": True,
        "text": True,
    }
    # Bootstrap newly introduced consumers before asking SQLMesh to restate them.
    subprocess.run(command, **run_options)
    restate_command = command.copy()
    for model in models:
        restate_command.extend(["--restate-model", model])
    subprocess.run(restate_command, **run_options)
    return dg.MaterializeResult(metadata={"sqlmesh_refreshed": True})


assets = [avonet_dlt_assets, avonet_iceberg_refresh]
dlt_asset_keys = [spec.key for spec in avonet_dlt_assets.specs]
sqlmesh_asset_keys = [avonet_iceberg_refresh.key]
asset_checks: list[dg.AssetChecksDefinition] = []

ingest_job = dg.define_asset_job(
    name="avonet_ingest",
    selection=dg.AssetSelection.assets(*dlt_asset_keys, avonet_iceberg_refresh.key),
    executor_def=dg.in_process_executor,
)
