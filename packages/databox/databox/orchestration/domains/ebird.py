"""eBird domain — dlt ingestion + SQLMesh marts + Soda checks."""

import typing as t
from datetime import timedelta

import dagster as dg
import dlt
from dagster import AssetExecutionContext
from dagster_dlt import DagsterDltResource, dlt_assets
from databox_sources.ebird.source import ebird_source

from databox.config.settings import settings
from databox.orchestration._factories import (
    SODA_DIR,
    dlt_destination,
    dlt_translator,
    freshness_checks,
    soda_check,
)


@dlt_assets(
    dlt_source=ebird_source(
        region_code="US-AZ", max_results=10000, days_back=settings.days_back("ebird")
    ),
    dlt_pipeline=dlt.pipeline(
        pipeline_name="ebird_api",
        destination=dlt_destination(settings.raw_catalog_path("ebird")),
        dataset_name="main",
        pipelines_dir=settings.dlt_data_dir,
    ),
    group_name="ebird_ingestion",
    dagster_dlt_translator=dlt_translator("raw_ebird"),
)
def ebird_dlt_assets(context: AssetExecutionContext, dlt: DagsterDltResource) -> t.Iterator[t.Any]:
    source = ebird_source(
        region_code="US-AZ", max_results=10000, days_back=settings.days_back("ebird")
    )
    if settings.smoke:
        source.add_limit(max_items=5)
    yield from dlt.run(context=context, dlt_source=source)


dlt_asset_keys = [spec.key for spec in ebird_dlt_assets.specs]

sqlmesh_asset_keys = [
    dg.AssetKey(["sqlmesh", "ebird_staging", "stg_ebird_observations"]),
    dg.AssetKey(["sqlmesh", "ebird_staging", "stg_ebird_taxonomy"]),
    dg.AssetKey(["sqlmesh", "ebird_staging", "stg_ebird_hotspots"]),
    dg.AssetKey(["sqlmesh", "ebird", "int_ebird_enriched_observations"]),
    dg.AssetKey(["sqlmesh", "ebird", "fct_daily_bird_observations"]),
    dg.AssetKey(["sqlmesh", "ebird", "dim_species"]),
    dg.AssetKey(["sqlmesh", "ebird", "fct_hotspot_species_diversity"]),
]

FRESHNESS_SLAS: dict[dg.AssetKey, timedelta] = {
    dg.AssetKey(["sqlmesh", "ebird", "fct_daily_bird_observations"]): timedelta(hours=30),
    dg.AssetKey(["sqlmesh", "ebird", "dim_species"]): timedelta(days=7),
    dg.AssetKey(["sqlmesh", "ebird", "fct_hotspot_species_diversity"]): timedelta(hours=30),
}

asset_checks: list[dg.AssetChecksDefinition] = [
    soda_check(
        dg.AssetKey(["sqlmesh", "ebird_staging", "stg_ebird_observations"]),
        SODA_DIR / "contracts/ebird_staging/stg_ebird_observations.yaml",
    ),
    soda_check(
        dg.AssetKey(["sqlmesh", "ebird_staging", "stg_ebird_taxonomy"]),
        SODA_DIR / "contracts/ebird_staging/stg_ebird_taxonomy.yaml",
    ),
    soda_check(
        dg.AssetKey(["sqlmesh", "ebird_staging", "stg_ebird_hotspots"]),
        SODA_DIR / "contracts/ebird_staging/stg_ebird_hotspots.yaml",
    ),
    soda_check(
        dg.AssetKey(["sqlmesh", "ebird", "int_ebird_enriched_observations"]),
        SODA_DIR / "contracts/ebird/int_ebird_enriched_observations.yaml",
    ),
    soda_check(
        dg.AssetKey(["sqlmesh", "ebird", "fct_daily_bird_observations"]),
        SODA_DIR / "contracts/ebird/fct_daily_bird_observations.yaml",
    ),
    soda_check(
        dg.AssetKey(["sqlmesh", "ebird", "dim_species"]),
        SODA_DIR / "contracts/ebird/dim_species.yaml",
    ),
    soda_check(
        dg.AssetKey(["sqlmesh", "ebird", "fct_hotspot_species_diversity"]),
        SODA_DIR / "contracts/ebird/fct_hotspot_species_diversity.yaml",
    ),
    *freshness_checks(FRESHNESS_SLAS),
]

daily_pipeline = dg.define_asset_job(
    name="ebird_daily_pipeline",
    selection=dg.AssetSelection.assets(*dlt_asset_keys, *sqlmesh_asset_keys),
)

schedule = dg.ScheduleDefinition(job=daily_pipeline, cron_schedule="0 6 * * *")
