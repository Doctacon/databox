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
    freshness_violation_sensor,
    openlineage_sensor_or_none,
    sqlmesh_project,
)
from databox.orchestration.domains import (
    analytics,
    ebird,
    gbif,
    noaa,
    usgs,
    usgs_earthquakes,
    xeno_canto,
)
from databox.orchestration.parallel_refresh import (
    parallel_quack_full_refresh,
    parallel_quack_schedule,
)

_openlineage_sensor = openlineage_sensor_or_none()

defs = dg.Definitions(
    assets=[
        ebird.ebird_dlt_assets,
        gbif.gbif_dlt_assets,
        xeno_canto.xeno_canto_dlt_assets,
        noaa.noaa_dlt_assets,
        usgs.usgs_dlt_assets,
        usgs_earthquakes.usgs_earthquakes_dlt_assets,
        sqlmesh_project,
    ],
    asset_checks=[
        *ebird.asset_checks,
        *gbif.asset_checks,
        *xeno_canto.asset_checks,
        *noaa.asset_checks,
        *usgs.asset_checks,
        *usgs_earthquakes.asset_checks,
        *analytics.asset_checks,
    ],
    jobs=[
        ebird.ingest_job,
        gbif.ingest_job,
        xeno_canto.ingest_job,
        noaa.ingest_job,
        usgs.ingest_job,
        usgs_earthquakes.ingest_job,
        ebird.daily_pipeline,
        gbif.daily_pipeline,
        xeno_canto.daily_pipeline,
        noaa.daily_pipeline,
        usgs.daily_pipeline,
        usgs_earthquakes.daily_pipeline,
        parallel_quack_full_refresh,
    ],
    schedules=[
        ebird.schedule,
        gbif.schedule,
        xeno_canto.schedule,
        noaa.schedule,
        usgs.schedule,
        usgs_earthquakes.schedule,
        parallel_quack_schedule,
    ],
    sensors=[freshness_violation_sensor, *([_openlineage_sensor] if _openlineage_sensor else [])],
    resources={
        "databox_config": DataboxConfig(),
        "dlt": DagsterDltResource(),
        "sqlmesh": SQLMeshResource(),
    },
    executor=dg.in_process_executor,
)
