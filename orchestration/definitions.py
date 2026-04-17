"""Dagster definitions — auto-generated from pipeline registry."""

import subprocess
from pathlib import Path

import dagster as dg
from dagster_duckdb import DuckDBResource

from config.pipeline_config import load_all_pipeline_configs
from config.settings import settings

PROJECT_ROOT = Path(__file__).parent.parent
TRANSFORMS_DIR = PROJECT_ROOT / "transforms"
MAIN_TRANSFORM_PROJECT = TRANSFORMS_DIR / "main"


def create_pipeline_asset(config_name: str, source_module: str) -> dg.AssetsDefinition:
    @dg.asset(
        name=f"{config_name}_raw_data",
        group_name="ingestion",
        description=f"Ingest {config_name} data",
        required_resource_keys={"databox_config"},
        key_prefix=["ingestion"],
    )
    def _asset(context: dg.AssetExecutionContext) -> dict:
        import importlib

        mod = importlib.import_module(source_module)
        factory = mod.create_pipeline
        cfg = load_all_pipeline_configs().get(config_name)
        if cfg is None:
            raise ValueError(f"No config for pipeline '{config_name}'")

        source = factory(cfg)
        source.load()

        context.log.info(f"Loaded {config_name} data")
        return {"status": "completed", "pipeline": config_name}

    return _asset


def create_main_transforms_asset(
    ingestion_keys: list[dg.AssetKey],
) -> dg.AssetsDefinition:
    @dg.asset(
        name="main_transforms",
        group_name="transformation",
        description="Run SQLMesh transforms for all sources (transforms/main/)",
        deps=ingestion_keys,
        required_resource_keys={"databox_config"},
        key_prefix=["transformation"],
    )
    def _asset(context: dg.AssetExecutionContext) -> None:
        if not MAIN_TRANSFORM_PROJECT.exists():
            raise FileNotFoundError(f"Transform project not found: {MAIN_TRANSFORM_PROJECT}")

        sqlmesh_path = PROJECT_ROOT / ".venv" / "bin" / "sqlmesh"

        result = subprocess.run(
            [str(sqlmesh_path), "run"],
            cwd=str(MAIN_TRANSFORM_PROJECT),
            capture_output=True,
            text=True,
        )

        if result.returncode != 0:
            raise Exception(f"SQLMesh failed:\n{result.stderr}")

        context.log.info("SQLMesh transforms completed")

    return _asset


class DataboxConfig(dg.ConfigurableResource):
    database_url: str = settings.database_url
    dlt_data_dir: str = settings.dlt_data_dir
    transforms_dir: str = str(TRANSFORMS_DIR)


pipeline_configs = load_all_pipeline_configs()

assets: list[dg.AssetsDefinition] = []
jobs: list = []
schedules: list[dg.ScheduleDefinition] = []
sensors: list[dg.SensorDefinition] = []

ingestion_keys: list[dg.AssetKey] = []

for _name, _cfg in pipeline_configs.items():
    ingestion_asset = create_pipeline_asset(_name, _cfg.source_module)
    assets.append(ingestion_asset)
    ingestion_keys.append(dg.AssetKey(["ingestion", f"{_name}_raw_data"]))

    job = dg.define_asset_job(
        name=f"{_name}_daily_pipeline",
        selection=dg.AssetSelection.assets(dg.AssetKey(["ingestion", f"{_name}_raw_data"])),
    )
    jobs.append(job)

    if _cfg.schedule.enabled:
        schedules.append(dg.ScheduleDefinition(job=job, cron_schedule=_cfg.schedule.cron))

# Single shared transform asset depending on all ingestion assets
transforms_asset = create_main_transforms_asset(ingestion_keys)
assets.append(transforms_asset)

# All-sources job: all ingestion + transforms
all_selection = dg.AssetSelection.assets(*ingestion_keys) | dg.AssetSelection.assets(
    dg.AssetKey(["transformation", "main_transforms"])
)
jobs.append(dg.define_asset_job(name="all_pipelines", selection=all_selection))


defs = dg.Definitions(
    assets=assets,
    jobs=jobs,
    schedules=schedules,
    sensors=sensors,
    resources={
        "duckdb": DuckDBResource(database=settings.database_url),
        "databox_config": DataboxConfig(),
    },
    executor=dg.multiprocess_executor.configured({"max_concurrent": 1}),
)
