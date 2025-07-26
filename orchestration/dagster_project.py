"""Dagster project definitions for Databox orchestration."""

import os
from pathlib import Path

import dagster as dg
from dagster_duckdb import DuckDBResource

# Project paths
PROJECT_ROOT = Path(__file__).parent.parent
PIPELINES_DIR = PROJECT_ROOT / "pipelines"
TRANSFORMATIONS_DIR = PROJECT_ROOT / "transformations"
DATA_DIR = PROJECT_ROOT / "data"

# Environment setup
DATABASE_URL = os.getenv(
    "DATABASE_URL", str(PROJECT_ROOT / "pipelines" / "sources" / "data" / "databox.db")
)
DLT_DATA_DIR = os.getenv("DLT_DATA_DIR", str(DATA_DIR / "dlt"))


# Resources
class DataboxConfig(dg.ConfigurableResource):
    """Configuration for Databox resources."""

    database_url: str = DATABASE_URL
    dlt_data_dir: str = DLT_DATA_DIR
    transformations_dir: str = str(TRANSFORMATIONS_DIR)
    ebird_api_token: str = os.getenv("EBIRD_API_TOKEN", "")


# Assets
@dg.asset(
    name="ebird_raw_data",
    group_name="ingestion",
    description="Ingest eBird data using DLT",
    required_resource_keys={"databox_config"},
)
def ebird_assets(context: dg.AssetExecutionContext):
    """Ingest eBird data using DLT."""
    # Import the ebird source
    from pipelines.sources.ebird_api import load_ebird_data

    # Get config from context
    config = context.resources.databox_config
    region = "US-AZ"  # Default region
    days_back = 30  # Default days back

    # Load the data
    load_ebird_data(
        region_code=region, days_back=days_back, database_url=f"duckdb:///{config.database_url}"
    )

    context.log.info(f"Loaded eBird data for region {region}")
    return {"status": "completed", "region": region, "days_back": days_back}


# SQLMesh Assets
@dg.asset(
    deps=["ebird_raw_data"],
    group_name="transformation",
    description="Run SQLMesh transformations for staging models",
    required_resource_keys={"databox_config"},
)
def sqlmesh_staging(context: dg.AssetExecutionContext) -> None:
    """Run SQLMesh staging transformations."""
    import subprocess

    config = context.resources.databox_config

    # Get the path to sqlmesh in the virtual environment
    venv_bin = PROJECT_ROOT / ".venv" / "bin"
    sqlmesh_path = venv_bin / "sqlmesh"

    # Run sqlmesh plan and apply
    result = subprocess.run(
        [str(sqlmesh_path), "run"],
        cwd=config.transformations_dir + "/home_team",
        capture_output=True,
        text=True,
        input="y\n",  # Auto-confirm prompts
    )

    if result.returncode != 0:
        raise Exception(f"SQLMesh failed: {result.stderr}")

    context.log.info("SQLMesh transformations completed successfully")


@dg.asset(
    deps=["sqlmesh_staging"],
    group_name="transformation",
    description="Data quality checks on transformed data",
    required_resource_keys={"duckdb"},
)
def data_quality_checks(context: dg.AssetExecutionContext) -> dict:
    """Run data quality checks on transformed data."""
    duckdb = context.resources.duckdb

    with duckdb.get_connection() as conn:
        # Check for nulls in critical columns
        null_checks = conn.execute("""
            SELECT
                'stg_ebird_observations' as table_name,
                COUNT(*) FILTER (WHERE species_code IS NULL) as null_species,
                COUNT(*) FILTER (WHERE observation_datetime IS NULL) as null_dates,
                COUNT(*) as total_rows
            FROM sqlmesh_example.stg_ebird_observations
        """).fetchone()

        # Check for data freshness
        freshness = conn.execute("""
            SELECT
                MAX(observation_datetime) as latest_observation,
                CURRENT_DATE - MAX(observation_datetime)::DATE as days_old
            FROM sqlmesh_example.stg_ebird_observations
        """).fetchone()

    results = {
        "null_species_count": null_checks[1],
        "null_dates_count": null_checks[2],
        "total_rows": null_checks[3],
        "latest_observation": str(freshness[0]),
        "data_age_days": freshness[1],
    }

    context.log.info(f"Data quality check results: {results}")

    # Fail if critical issues
    if null_checks[1] > 0 or null_checks[2] > 0:
        raise Exception("Data quality check failed: Found null values in critical columns")

    return results


# Jobs
@dg.job(
    resource_defs={
        "duckdb": DuckDBResource(database=DATABASE_URL),
        "databox_config": DataboxConfig(),
    },
)
def daily_ebird_pipeline():
    """Daily pipeline to ingest and transform eBird data."""
    data_quality_checks()


# Schedules
@dg.schedule(
    job=daily_ebird_pipeline,
    cron_schedule="0 6 * * *",  # 6 AM daily
)
def daily_ebird_schedule(context: dg.ScheduleEvaluationContext):
    """Schedule for daily eBird data pipeline."""
    return {}


# Sensors
@dg.sensor(
    job=daily_ebird_pipeline,
    minimum_interval_seconds=3600,  # Check hourly
)
def ebird_api_availability_sensor(context: dg.SensorEvaluationContext):
    """Check if eBird API is available before running pipeline."""
    import requests

    try:
        # Check API health
        response = requests.get(
            "https://api.ebird.org/v2/ref/region/list/country/world",
            headers={"X-eBirdApiToken": os.getenv("EBIRD_API_TOKEN", "")},
            timeout=10,
        )

        if response.status_code == 200:
            return dg.RunRequest(run_key=f"ebird_api_available_{context.cursor}")
    except Exception as e:
        context.log.error(f"eBird API check failed: {e}")

    return dg.SkipReason("eBird API not available")


# Definitions
defs = dg.Definitions(
    assets=[ebird_assets, sqlmesh_staging, data_quality_checks],
    jobs=[daily_ebird_pipeline],
    schedules=[daily_ebird_schedule],
    sensors=[ebird_api_availability_sensor],
    resources={
        "duckdb": DuckDBResource(database=DATABASE_URL),
        "databox_config": DataboxConfig(),
    },
)
