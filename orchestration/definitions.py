"""Dagster definitions — auto-generated from pipeline registry."""

import subprocess
from pathlib import Path

import dagster as dg
from dagster_duckdb import DuckDBResource

from config.pipeline_config import load_all_pipeline_configs
from config.settings import settings

PROJECT_ROOT = Path(__file__).parent.parent
TRANSFORMS_DIR = PROJECT_ROOT / "transforms"


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


def create_transform_asset(config_name: str, transform_project: str) -> dg.AssetsDefinition:
    deps_key = dg.AssetKey([f"{config_name}_raw_data"])

    @dg.asset(
        name=f"{config_name}_transforms",
        group_name="transformation",
        description=f"Run SQLMesh transforms for {config_name}",
        deps=[deps_key],
        required_resource_keys={"databox_config"},
        key_prefix=["transformation"],
    )
    def _asset(context: dg.AssetExecutionContext) -> None:
        project_dir = TRANSFORMS_DIR / transform_project
        if not project_dir.exists():
            raise FileNotFoundError(f"Transform project not found: {project_dir}")

        venv_bin = PROJECT_ROOT / ".venv" / "bin"
        sqlmesh_path = venv_bin / "sqlmesh"

        result = subprocess.run(
            [str(sqlmesh_path), "run"],
            cwd=str(project_dir),
            capture_output=True,
            text=True,
            input="y\n",
        )

        if result.returncode != 0:
            raise Exception(f"SQLMesh failed for {transform_project}: {result.stderr}")

        context.log.info(f"SQLMesh transforms completed for {transform_project}")

    return _asset


class DataboxConfig(dg.ConfigurableResource):
    database_url: str = settings.database_url
    dlt_data_dir: str = settings.dlt_data_dir
    transforms_dir: str = str(TRANSFORMS_DIR)


assets: list[dg.AssetsDefinition] = []
jobs: list = []
schedules: list[dg.ScheduleDefinition] = []
sensors: list[dg.SensorDefinition] = []

pipeline_configs = load_all_pipeline_configs()

_all_selection: dg.AssetSelection | None = None

for _name, _cfg in pipeline_configs.items():
    ingestion_asset = create_pipeline_asset(_name, _cfg.source_module)
    assets.append(ingestion_asset)

    if _cfg.transform_project:
        transform_asset = create_transform_asset(_name, _cfg.transform_project)
        assets.append(transform_asset)

    selection = dg.AssetSelection.assets(dg.AssetKey([f"{_name}_raw_data"]))
    if _cfg.transform_project:
        selection = selection | dg.AssetSelection.assets(dg.AssetKey([f"{_name}_transforms"]))

    _all_selection = selection if _all_selection is None else _all_selection | selection

    job = dg.define_asset_job(
        name=f"{_name}_daily_pipeline",
        selection=selection,
    )
    jobs.append(job)

    if _cfg.schedule.enabled:
        schedule = dg.ScheduleDefinition(
            job=job,
            cron_schedule=_cfg.schedule.cron,
        )
        schedules.append(schedule)

# All-sources job — no schedule, intended for on-demand full refreshes
if _all_selection is not None:
    jobs.append(dg.define_asset_job(name="all_pipelines", selection=_all_selection))


defs = dg.Definitions(
    assets=assets,
    jobs=jobs,
    schedules=schedules,
    sensors=sensors,
    resources={
        "duckdb": DuckDBResource(database=settings.database_url),
        "databox_config": DataboxConfig(),
    },
)
