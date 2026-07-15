"""Dagster definitions composed from the canonical source registry."""

from __future__ import annotations

from importlib import import_module
from types import ModuleType

import dagster as dg
from dagster_dlt import DagsterDltResource
from dagster_sqlmesh import SQLMeshResource

from databox.config.sources import SOURCES
from databox.orchestration._factories import (
    DataboxConfig,
    freshness_violation_sensor,
    openlineage_sensor_or_none,
    sqlmesh_project,
)
from databox.orchestration.domains import analytics
from databox.orchestration.parallel_refresh import (
    parallel_quack_full_refresh,
    parallel_quack_schedule,
)


def _load_source_domains() -> dict[str, ModuleType]:
    return {source.name: import_module(source.domain_module) for source in SOURCES}


_SOURCE_DOMAINS = _load_source_domains()
_openlineage_sensor = openlineage_sensor_or_none()

defs = dg.Definitions(
    assets=[
        *(asset for module in _SOURCE_DOMAINS.values() for asset in module.assets),
        sqlmesh_project,
    ],
    asset_checks=[
        *(check for module in _SOURCE_DOMAINS.values() for check in module.asset_checks),
        *analytics.asset_checks,
    ],
    jobs=[
        *(module.ingest_job for module in _SOURCE_DOMAINS.values()),
        *(_SOURCE_DOMAINS[source.name].daily_pipeline for source in SOURCES if source.scheduled),
        parallel_quack_full_refresh,
    ],
    schedules=[
        *(_SOURCE_DOMAINS[source.name].schedule for source in SOURCES if source.scheduled),
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
