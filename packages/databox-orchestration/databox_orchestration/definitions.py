"""Dagster definitions — dlt assets + dagster-sqlmesh integration."""

import os
import typing as t
from pathlib import Path

import dagster as dg
import dlt
from dagster_dlt import DagsterDltResource, dlt_assets
from dagster_sqlmesh import SQLMeshContextConfig, SQLMeshResource, sqlmesh_assets
from dagster_sqlmesh.translator import SQLMeshDagsterTranslator
from databox_config.settings import settings
from databox_sources.ebird.source import ebird_source
from databox_sources.noaa.source import noaa_source
from sqlglot import exp

PROJECT_ROOT = Path(__file__).parent.parent.parent.parent
TRANSFORMS_DIR = PROJECT_ROOT / "transforms"
MAIN_TRANSFORM_PROJECT = TRANSFORMS_DIR / "main"
SODA_DIR = PROJECT_ROOT / "soda"


# ---------------------------------------------------------------------------
# Custom translator — asset keys use ["sqlmesh", schema, table]
# ---------------------------------------------------------------------------


class DataboxSQLMeshTranslator(SQLMeshDagsterTranslator):
    def get_asset_key_name(self, fqn: str) -> t.Sequence[str]:
        table = exp.to_table(fqn)
        return ["sqlmesh", table.db, table.name]


class DataboxSQLMeshContextConfig(SQLMeshContextConfig):
    def get_translator(self) -> SQLMeshDagsterTranslator:
        return DataboxSQLMeshTranslator()


# ---------------------------------------------------------------------------
# Resources
# ---------------------------------------------------------------------------


class DataboxConfig(dg.ConfigurableResource):
    database_url: str = settings.database_url
    dlt_data_dir: str = settings.dlt_data_dir
    transforms_dir: str = str(TRANSFORMS_DIR)


_sqlmesh_config = DataboxSQLMeshContextConfig(
    path=str(MAIN_TRANSFORM_PROJECT),
    gateway="postgres",
)


# ---------------------------------------------------------------------------
# dlt assets — eBird
# ---------------------------------------------------------------------------


@dlt_assets(
    dlt_source=ebird_source(region_code="US-AZ", max_results=10000, days_back=30),
    dlt_pipeline=dlt.pipeline(
        pipeline_name="ebird_api",
        destination=dlt.destinations.postgres(credentials=settings.database_url),
        dataset_name="raw_ebird",
        pipelines_dir=settings.dlt_data_dir,
    ),
    group_name="ebird_ingestion",
)
def ebird_dlt_assets(context: dg.AssetExecutionContext, dlt: DagsterDltResource):
    source = ebird_source(region_code="US-AZ", max_results=10000, days_back=30)
    if os.getenv("DATABOX_SMOKE"):
        source.add_limit(max_items=5)
    yield from dlt.run(context=context, dlt_source=source)


# ---------------------------------------------------------------------------
# dlt assets — NOAA
# ---------------------------------------------------------------------------


@dlt_assets(
    dlt_source=noaa_source(
        location_id="FIPS:04",
        dataset_id="GHCND",
        days_back=30,
        datatypes="TMAX,TMIN,PRCP,SNOW,AWND",
    ),
    dlt_pipeline=dlt.pipeline(
        pipeline_name="noaa_api",
        destination=dlt.destinations.postgres(credentials=settings.database_url),
        dataset_name="raw_noaa",
        pipelines_dir=settings.dlt_data_dir,
    ),
    group_name="noaa_ingestion",
)
def noaa_dlt_assets(context: dg.AssetExecutionContext, dlt: DagsterDltResource):
    source = noaa_source(
        location_id="FIPS:04",
        dataset_id="GHCND",
        days_back=30,
        datatypes="TMAX,TMIN,PRCP,SNOW,AWND",
    )
    if os.getenv("DATABOX_SMOKE"):
        source.add_limit(max_items=5)
    yield from dlt.run(context=context, dlt_source=source)


# ---------------------------------------------------------------------------
# SQLMesh assets — all models as one multi-asset
# ---------------------------------------------------------------------------


@sqlmesh_assets(
    environment="prod",
    config=_sqlmesh_config,
    enabled_subsetting=True,
)
def sqlmesh_project(context: dg.AssetExecutionContext, sqlmesh: SQLMeshResource):
    yield from sqlmesh.run(context=context, config=_sqlmesh_config)


# ---------------------------------------------------------------------------
# Soda asset check factory
# ---------------------------------------------------------------------------


def _soda_datasource_yaml() -> str:
    return f"""
name: databox
type: postgres
connection:
  host: {os.getenv("POSTGRES_HOST", "localhost")}
  port: {int(os.getenv("POSTGRES_PORT", "5432"))}
  database: {os.getenv("POSTGRES_DB", "databox")}
  user: {os.getenv("POSTGRES_USER", "databox")}
  password: {os.getenv("POSTGRES_PASSWORD", "databox")}
"""


def create_soda_asset_check(
    asset_key: dg.AssetKey,
    contract_path: Path,
    check_name: str = "soda_contract",
) -> dg.AssetChecksDefinition:
    @dg.asset_check(asset=asset_key, name=check_name)
    def _check() -> dg.AssetCheckResult:
        from soda_core.common.yaml import ContractYamlSource, DataSourceYamlSource
        from soda_core.contracts.contract_verification import ContractVerificationSession

        result = ContractVerificationSession.execute(
            contract_yaml_sources=[ContractYamlSource.from_str(contract_path.read_text())],
            data_source_yaml_sources=[DataSourceYamlSource.from_str(_soda_datasource_yaml())],
        )
        metadata: dict = {
            "checks_total": result.number_of_checks,
            "checks_passed": result.number_of_checks_passed,
            "checks_failed": result.number_of_checks_failed,
        }
        if result.is_failed:
            return dg.AssetCheckResult(
                passed=False,
                description=result.get_errors_str(),
                metadata=metadata,
            )
        return dg.AssetCheckResult(passed=True, metadata=metadata)

    return _check


# ---------------------------------------------------------------------------
# Soda asset checks — one per SQLMesh model
# ---------------------------------------------------------------------------

_soda_checks: list[dg.AssetChecksDefinition] = [
    create_soda_asset_check(
        dg.AssetKey(["sqlmesh", "ebird_staging", "stg_ebird_observations"]),
        SODA_DIR / "contracts/ebird_staging/stg_ebird_observations.yaml",
    ),
    create_soda_asset_check(
        dg.AssetKey(["sqlmesh", "ebird_staging", "stg_ebird_taxonomy"]),
        SODA_DIR / "contracts/ebird_staging/stg_ebird_taxonomy.yaml",
    ),
    create_soda_asset_check(
        dg.AssetKey(["sqlmesh", "ebird_staging", "stg_ebird_hotspots"]),
        SODA_DIR / "contracts/ebird_staging/stg_ebird_hotspots.yaml",
    ),
    create_soda_asset_check(
        dg.AssetKey(["sqlmesh", "ebird", "int_ebird_enriched_observations"]),
        SODA_DIR / "contracts/ebird/int_ebird_enriched_observations.yaml",
    ),
    create_soda_asset_check(
        dg.AssetKey(["sqlmesh", "ebird", "fct_daily_bird_observations"]),
        SODA_DIR / "contracts/ebird/fct_daily_bird_observations.yaml",
    ),
    create_soda_asset_check(
        dg.AssetKey(["sqlmesh", "ebird", "dim_species"]),
        SODA_DIR / "contracts/ebird/dim_species.yaml",
    ),
    create_soda_asset_check(
        dg.AssetKey(["sqlmesh", "ebird", "fct_hotspot_species_diversity"]),
        SODA_DIR / "contracts/ebird/fct_hotspot_species_diversity.yaml",
    ),
    create_soda_asset_check(
        dg.AssetKey(["sqlmesh", "noaa_staging", "stg_noaa_daily_weather"]),
        SODA_DIR / "contracts/noaa_staging/stg_noaa_daily_weather.yaml",
    ),
    create_soda_asset_check(
        dg.AssetKey(["sqlmesh", "noaa_staging", "stg_noaa_stations"]),
        SODA_DIR / "contracts/noaa_staging/stg_noaa_stations.yaml",
    ),
    create_soda_asset_check(
        dg.AssetKey(["sqlmesh", "noaa", "fct_daily_weather"]),
        SODA_DIR / "contracts/noaa/fct_daily_weather.yaml",
    ),
    create_soda_asset_check(
        dg.AssetKey(["sqlmesh", "analytics", "fct_bird_weather_daily"]),
        SODA_DIR / "contracts/analytics/fct_bird_weather_daily.yaml",
    ),
    create_soda_asset_check(
        dg.AssetKey(["sqlmesh", "analytics", "fct_species_weather_preferences"]),
        SODA_DIR / "contracts/analytics/fct_species_weather_preferences.yaml",
    ),
]

# ---------------------------------------------------------------------------
# Asset key constants for jobs
# ---------------------------------------------------------------------------

_ebird_dlt_keys = [spec.key for spec in ebird_dlt_assets.specs]
_noaa_dlt_keys = [spec.key for spec in noaa_dlt_assets.specs]

_ebird_sqlmesh_keys = [
    dg.AssetKey(["sqlmesh", "ebird_staging", "stg_ebird_observations"]),
    dg.AssetKey(["sqlmesh", "ebird_staging", "stg_ebird_taxonomy"]),
    dg.AssetKey(["sqlmesh", "ebird_staging", "stg_ebird_hotspots"]),
    dg.AssetKey(["sqlmesh", "ebird", "int_ebird_enriched_observations"]),
    dg.AssetKey(["sqlmesh", "ebird", "fct_daily_bird_observations"]),
    dg.AssetKey(["sqlmesh", "ebird", "dim_species"]),
    dg.AssetKey(["sqlmesh", "ebird", "fct_hotspot_species_diversity"]),
]
_noaa_sqlmesh_keys = [
    dg.AssetKey(["sqlmesh", "noaa_staging", "stg_noaa_daily_weather"]),
    dg.AssetKey(["sqlmesh", "noaa_staging", "stg_noaa_stations"]),
    dg.AssetKey(["sqlmesh", "noaa", "fct_daily_weather"]),
]
_analytics_sqlmesh_keys = [
    dg.AssetKey(["sqlmesh", "analytics", "fct_bird_weather_daily"]),
    dg.AssetKey(["sqlmesh", "analytics", "fct_species_weather_preferences"]),
]

# ---------------------------------------------------------------------------
# Jobs
# ---------------------------------------------------------------------------

ebird_daily_pipeline = dg.define_asset_job(
    name="ebird_daily_pipeline",
    selection=dg.AssetSelection.assets(*_ebird_dlt_keys, *_ebird_sqlmesh_keys),
)

noaa_daily_pipeline = dg.define_asset_job(
    name="noaa_daily_pipeline",
    selection=dg.AssetSelection.assets(*_noaa_dlt_keys, *_noaa_sqlmesh_keys),
)

all_pipelines = dg.define_asset_job(
    name="all_pipelines",
    selection=dg.AssetSelection.assets(
        *_ebird_dlt_keys,
        *_noaa_dlt_keys,
        *_ebird_sqlmesh_keys,
        *_noaa_sqlmesh_keys,
        *_analytics_sqlmesh_keys,
    ),
)

jobs = [ebird_daily_pipeline, noaa_daily_pipeline, all_pipelines]

# ---------------------------------------------------------------------------
# Schedules
# ---------------------------------------------------------------------------

schedules = [
    dg.ScheduleDefinition(job=ebird_daily_pipeline, cron_schedule="0 6 * * *"),
    dg.ScheduleDefinition(job=noaa_daily_pipeline, cron_schedule="0 6 * * *"),
]

# ---------------------------------------------------------------------------
# Definitions
# ---------------------------------------------------------------------------

defs = dg.Definitions(
    assets=[ebird_dlt_assets, noaa_dlt_assets, sqlmesh_project],
    asset_checks=_soda_checks,
    jobs=jobs,
    schedules=schedules,
    sensors=[],
    resources={
        "databox_config": DataboxConfig(),
        "dlt": DagsterDltResource(),
        "sqlmesh": SQLMeshResource(),
    },
    executor=dg.multiprocess_executor.configured({"max_concurrent": 1}),
)
