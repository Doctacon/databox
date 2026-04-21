"""USGS domain — dlt ingestion + SQLMesh marts + Soda checks."""

import dagster as dg
import dlt
from dagster import AssetExecutionContext
from dagster_dlt import DagsterDltResource, dlt_assets
from databox_sources.usgs.source import usgs_source

from databox.config.settings import settings
from databox.orchestration._factories import (
    SODA_DIR,
    dlt_destination,
    dlt_translator,
    soda_check,
)


@dlt_assets(
    dlt_source=usgs_source(
        state_cd="AZ", parameter_cds="00060,00065,00010", days_back=settings.days_back("usgs")
    ),
    dlt_pipeline=dlt.pipeline(
        pipeline_name="usgs_api",
        destination=dlt_destination(settings.raw_usgs_path),
        dataset_name="main",
        pipelines_dir=settings.dlt_data_dir,
    ),
    group_name="usgs_ingestion",
    dagster_dlt_translator=dlt_translator("raw_usgs"),
)
def usgs_dlt_assets(context: AssetExecutionContext, dlt: DagsterDltResource):
    source = usgs_source(
        state_cd="AZ", parameter_cds="00060,00065,00010", days_back=settings.days_back("usgs")
    )
    if settings.smoke:
        source.add_limit(max_items=5)
    yield from dlt.run(context=context, dlt_source=source)


dlt_asset_keys = [spec.key for spec in usgs_dlt_assets.specs]

sqlmesh_asset_keys = [
    dg.AssetKey(["sqlmesh", "usgs_staging", "stg_usgs_daily_values"]),
    dg.AssetKey(["sqlmesh", "usgs_staging", "stg_usgs_sites"]),
    dg.AssetKey(["sqlmesh", "usgs", "fct_daily_streamflow"]),
]

asset_checks: list[dg.AssetChecksDefinition] = [
    soda_check(
        dg.AssetKey(["sqlmesh", "usgs_staging", "stg_usgs_daily_values"]),
        SODA_DIR / "contracts/usgs_staging/stg_usgs_daily_values.yaml",
    ),
    soda_check(
        dg.AssetKey(["sqlmesh", "usgs_staging", "stg_usgs_sites"]),
        SODA_DIR / "contracts/usgs_staging/stg_usgs_sites.yaml",
    ),
    soda_check(
        dg.AssetKey(["sqlmesh", "usgs", "fct_daily_streamflow"]),
        SODA_DIR / "contracts/usgs/fct_daily_streamflow.yaml",
    ),
]

daily_pipeline = dg.define_asset_job(
    name="usgs_daily_pipeline",
    selection=dg.AssetSelection.assets(*dlt_asset_keys, *sqlmesh_asset_keys),
)

schedule = dg.ScheduleDefinition(job=daily_pipeline, cron_schedule="0 6 * * *")
