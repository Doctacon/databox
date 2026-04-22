"""Dagster definitions — assembles per-domain modules into one Definitions.

Each domain (ebird, noaa, usgs, analytics) owns its own dlt assets, SQLMesh
asset key list, Soda checks, job, and schedule. This file only composes them.
"""

from __future__ import annotations

import dagster as dg
from dagster_dlt import DagsterDltResource
from dagster_sqlmesh import SQLMeshResource

from databox.orchestration._factories import (
    DataboxConfig,
    apply_freshness,
    ensure_motherduck_databases,
    freshness_violation_sensor,
    openlineage_sensor_or_none,
    sqlmesh_project,
)
from databox.orchestration.domains import analytics, ebird, noaa, usgs, usgs_earthquakes

ensure_motherduck_databases()

_openlineage_sensor = openlineage_sensor_or_none()

all_pipelines = dg.define_asset_job(
    name="all_pipelines",
    selection=dg.AssetSelection.assets(
        *ebird.dlt_asset_keys,
        *noaa.dlt_asset_keys,
        *usgs.dlt_asset_keys,
        *usgs_earthquakes.dlt_asset_keys,
        *ebird.sqlmesh_asset_keys,
        *noaa.sqlmesh_asset_keys,
        *usgs.sqlmesh_asset_keys,
        *usgs_earthquakes.sqlmesh_asset_keys,
        *analytics.sqlmesh_asset_keys,
    ),
)

defs = dg.Definitions(
    assets=[
        ebird.ebird_dlt_assets,
        noaa.noaa_dlt_assets,
        usgs.usgs_dlt_assets,
        usgs_earthquakes.usgs_earthquakes_dlt_assets,
        sqlmesh_project,
        analytics.mart_cost_summary,
    ],
    asset_checks=[
        *ebird.asset_checks,
        *noaa.asset_checks,
        *usgs.asset_checks,
        *usgs_earthquakes.asset_checks,
        *analytics.asset_checks,
    ],
    jobs=[
        ebird.daily_pipeline,
        noaa.daily_pipeline,
        usgs.daily_pipeline,
        usgs_earthquakes.daily_pipeline,
        analytics.cost_pipeline,
        all_pipelines,
    ],
    schedules=[
        ebird.schedule,
        noaa.schedule,
        usgs.schedule,
        usgs_earthquakes.schedule,
        analytics.cost_schedule,
    ],
    sensors=[freshness_violation_sensor, *([_openlineage_sensor] if _openlineage_sensor else [])],
    resources={
        "databox_config": DataboxConfig(),
        "dlt": DagsterDltResource(),
        "sqlmesh": SQLMeshResource(),
    },
    executor=dg.multiprocess_executor,
)

defs = defs.map_asset_specs(func=apply_freshness)
