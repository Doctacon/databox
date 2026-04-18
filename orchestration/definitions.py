"""Dagster definitions — fine-grained assets per dlt resource and sqlmesh model."""

import os
import subprocess
from datetime import date, timedelta
from pathlib import Path

import dagster as dg
import dlt
from dagster_dlt import DagsterDltResource, dlt_assets

from config.settings import settings
from sources.ebird.source import ebird_source
from sources.noaa.source import noaa_source

PROJECT_ROOT = Path(__file__).parent.parent
TRANSFORMS_DIR = PROJECT_ROOT / "transforms"
MAIN_TRANSFORM_PROJECT = TRANSFORMS_DIR / "main"


# ---------------------------------------------------------------------------
# Resources
# ---------------------------------------------------------------------------


class DataboxConfig(dg.ConfigurableResource):
    database_url: str = settings.database_url
    dlt_data_dir: str = settings.dlt_data_dir
    transforms_dir: str = str(TRANSFORMS_DIR)


# ---------------------------------------------------------------------------
# dlt assets — eBird (one asset per resource)
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
# dlt assets — NOAA (one asset per resource)
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
# SQLMesh per-model asset factory
# ---------------------------------------------------------------------------


def create_sqlmesh_model_asset(
    model_name: str,
    group: str,
    deps: list[dg.AssetKey],
) -> dg.AssetsDefinition:
    """Return a single @asset that runs `sqlmesh run --select-model <model_name>`."""
    # Convert "ebird.stg_ebird_observations" → ["sqlmesh", "ebird", "stg_ebird_observations"]
    parts = model_name.split(".")
    asset_key = dg.AssetKey(["sqlmesh"] + parts)

    @dg.asset(
        key=asset_key,
        group_name=group,
        description=f"SQLMesh model: {model_name}",
        deps=deps,
        required_resource_keys={"databox_config"},
    )
    def _asset(context: dg.AssetExecutionContext) -> None:
        if not MAIN_TRANSFORM_PROJECT.exists():
            raise FileNotFoundError(f"Transform project not found: {MAIN_TRANSFORM_PROJECT}")
        sqlmesh_bin = PROJECT_ROOT / ".venv" / "bin" / "sqlmesh"
        cmd = [str(sqlmesh_bin), "run", "--select-model", model_name]
        if os.getenv("DATABOX_SMOKE"):
            start = (date.today() - timedelta(days=3)).isoformat()
            cmd.extend(["--start", start])
        result = subprocess.run(
            cmd,
            cwd=str(MAIN_TRANSFORM_PROJECT),
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            raise Exception(f"SQLMesh failed for model '{model_name}':\n{result.stderr}")
        context.log.info(f"SQLMesh model '{model_name}' completed successfully")

    return _asset


# ---------------------------------------------------------------------------
# SQLMesh model assets
# ---------------------------------------------------------------------------

# Keys for all ebird dlt assets (as upstream deps for staging models)
_ebird_dlt_keys = [spec.key for spec in ebird_dlt_assets.specs]
_noaa_dlt_keys = [spec.key for spec in noaa_dlt_assets.specs]

# eBird staging
stg_ebird_observations = create_sqlmesh_model_asset(
    "ebird.stg_ebird_observations", "ebird_staging", _ebird_dlt_keys
)
stg_ebird_taxonomy = create_sqlmesh_model_asset(
    "ebird.stg_ebird_taxonomy", "ebird_staging", _ebird_dlt_keys
)
stg_ebird_hotspots = create_sqlmesh_model_asset(
    "ebird.stg_ebird_hotspots", "ebird_staging", _ebird_dlt_keys
)

# eBird intermediate
int_ebird_enriched_observations = create_sqlmesh_model_asset(
    "ebird.int_ebird_enriched_observations",
    "ebird_intermediate",
    [
        dg.AssetKey(["sqlmesh", "ebird", "stg_ebird_observations"]),
        dg.AssetKey(["sqlmesh", "ebird", "stg_ebird_taxonomy"]),
    ],
)

# eBird mart
fct_daily_bird_observations = create_sqlmesh_model_asset(
    "ebird.fct_daily_bird_observations",
    "ebird_marts",
    [
        dg.AssetKey(["sqlmesh", "ebird", "int_ebird_enriched_observations"]),
        dg.AssetKey(["sqlmesh", "ebird", "stg_ebird_hotspots"]),
    ],
)

# NOAA staging
stg_noaa_daily_weather = create_sqlmesh_model_asset(
    "noaa.stg_noaa_daily_weather", "noaa_staging", _noaa_dlt_keys
)
stg_noaa_stations = create_sqlmesh_model_asset(
    "noaa.stg_noaa_stations", "noaa_staging", _noaa_dlt_keys
)

# NOAA mart
fct_daily_weather = create_sqlmesh_model_asset(
    "noaa.fct_daily_weather",
    "noaa_marts",
    [
        dg.AssetKey(["sqlmesh", "noaa", "stg_noaa_daily_weather"]),
        dg.AssetKey(["sqlmesh", "noaa", "stg_noaa_stations"]),
    ],
)

# ---------------------------------------------------------------------------
# Collect all assets
# ---------------------------------------------------------------------------

_ebird_sqlmesh_assets = [
    stg_ebird_observations,
    stg_ebird_taxonomy,
    stg_ebird_hotspots,
    int_ebird_enriched_observations,
    fct_daily_bird_observations,
]
_noaa_sqlmesh_assets = [
    stg_noaa_daily_weather,
    stg_noaa_stations,
    fct_daily_weather,
]

assets: list[dg.AssetsDefinition] = (
    [ebird_dlt_assets] + [noaa_dlt_assets] + _ebird_sqlmesh_assets + _noaa_sqlmesh_assets
)

# ---------------------------------------------------------------------------
# Jobs
# ---------------------------------------------------------------------------

_ebird_sqlmesh_keys = [a.key for a in _ebird_sqlmesh_assets]
_noaa_sqlmesh_keys = [a.key for a in _noaa_sqlmesh_assets]

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
    ),
)

jobs = [ebird_daily_pipeline, noaa_daily_pipeline, all_pipelines]

# ---------------------------------------------------------------------------
# Schedules (both pipelines have enabled: true, cron: "0 6 * * *")
# ---------------------------------------------------------------------------

schedules = [
    dg.ScheduleDefinition(job=ebird_daily_pipeline, cron_schedule="0 6 * * *"),
    dg.ScheduleDefinition(job=noaa_daily_pipeline, cron_schedule="0 6 * * *"),
]

# ---------------------------------------------------------------------------
# Definitions
# ---------------------------------------------------------------------------

defs = dg.Definitions(
    assets=assets,
    jobs=jobs,
    schedules=schedules,
    sensors=[],
    resources={
        "databox_config": DataboxConfig(),
        "dlt": DagsterDltResource(),
    },
    executor=dg.multiprocess_executor.configured({"max_concurrent": 1}),
)
