"""Dagster project definitions for Databox orchestration."""

import os
from pathlib import Path

import dagster as dg
from dagster_dlt import DagsterDltResource, dlt_assets
from dagster_duckdb import DuckDBResource

# Project paths
PROJECT_ROOT = Path(__file__).parent.parent
PIPELINES_DIR = PROJECT_ROOT / "pipelines"
TRANSFORMATIONS_DIR = PROJECT_ROOT / "transformations"
DATA_DIR = PROJECT_ROOT / "data"

# Environment setup
DATABASE_URL = os.getenv("DATABASE_URL", f"duckdb:///{DATA_DIR}/databox.db")
DLT_DATA_DIR = os.getenv("DLT_DATA_DIR", str(DATA_DIR / "dlt"))


# Resources
@dg.ConfigurableResource
class DataboxConfig:
    """Configuration for Databox resources."""
    
    database_url: str = DATABASE_URL
    dlt_data_dir: str = DLT_DATA_DIR
    transformations_dir: str = str(TRANSFORMATIONS_DIR)
    ebird_api_token: str = os.getenv("EBIRD_API_TOKEN", "")


# DLT Assets
@dlt_assets(
    dlt_source=dg.file_relative_path(__file__, "../pipelines/sources/ebird_api.py"),
    dlt_pipeline=dg.file_relative_path(__file__, "../pipelines/sources/ebird_api.py"),
    name="ebird_raw_data",
    group_name="ingestion",
)
def ebird_assets(context: dg.AssetExecutionContext, dlt: DagsterDltResource):
    """Ingest eBird data using DLT."""
    # Import here to avoid circular imports
    import sys
    sys.path.append(str(PROJECT_ROOT))
    from pipelines.sources.ebird_api import ebird_source
    
    # Get config from context
    config = context.resources.databox_config
    region = context.op_execution_context.op_config.get("region", "US-CA")
    days_back = context.op_execution_context.op_config.get("days_back", 7)
    
    # Create and run the pipeline
    pipeline = dlt.create_pipeline(
        pipeline_name="ebird_api",
        dataset_name="raw_ebird_data",
        destination="duckdb",
        credentials=config.database_url,
    )
    
    # Load the data
    results = pipeline.run(
        ebird_source(region_code=region, days_back=days_back)
    )
    
    context.log.info(f"Loaded eBird data for region {region}")
    yield from results


# SQLMesh Assets
@dg.asset(
    deps=["ebird_raw_data"],
    group_name="transformation",
    description="Run SQLMesh transformations for staging models",
)
def sqlmesh_staging(context: dg.AssetExecutionContext) -> None:
    """Run SQLMesh staging transformations."""
    import subprocess
    
    config = context.resources.databox_config
    
    # Run sqlmesh plan and apply
    result = subprocess.run(
        ["sqlmesh", "run", "--no-prompts"],
        cwd=config.transformations_dir + "/home_team",
        capture_output=True,
        text=True,
    )
    
    if result.returncode != 0:
        raise Exception(f"SQLMesh failed: {result.stderr}")
    
    context.log.info("SQLMesh transformations completed successfully")


@dg.asset(
    deps=["sqlmesh_staging"],
    group_name="transformation",
    description="Data quality checks on transformed data",
)
def data_quality_checks(context: dg.AssetExecutionContext) -> dict:
    """Run data quality checks on transformed data."""
    duckdb = context.resources.duckdb
    
    with duckdb.get_connection() as conn:
        # Check for nulls in critical columns
        null_checks = conn.execute("""
            SELECT 
                'stg_ebird_observations' as table_name,
                COUNT(*) FILTER (WHERE speciesCode IS NULL) as null_species,
                COUNT(*) FILTER (WHERE obsDt IS NULL) as null_dates,
                COUNT(*) as total_rows
            FROM sqlmesh_example.stg_ebird_observations
        """).fetchone()
        
        # Check for data freshness
        freshness = conn.execute("""
            SELECT 
                MAX(obsDt) as latest_observation,
                CURRENT_DATE - MAX(obsDt)::DATE as days_old
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
        "dlt": DagsterDltResource(),
        "duckdb": DuckDBResource(database=DATABASE_URL),
        "databox_config": DataboxConfig(),
    },
    config={
        "ops": {
            "ebird_assets": {
                "config": {
                    "region": "US-CA",
                    "days_back": 7,
                }
            }
        }
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
        "dlt": DagsterDltResource(),
        "duckdb": DuckDBResource(database=DATABASE_URL),
        "databox_config": DataboxConfig(),
    },
)