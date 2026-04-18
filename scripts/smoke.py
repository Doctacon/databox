#!/usr/bin/env python3
"""Smoke test: run all pipeline assets in-process with DATABOX_SMOKE=1 limits.

Bypasses dagster CLI infrastructure (which spawns subprocesses that lose env vars)
and runs assets directly via execute_in_process().
"""

import os
import sys

os.environ["DATABOX_SMOKE"] = "1"

import dagster as dg
from dagster_dlt import DagsterDltResource
from dagster_sqlmesh import SQLMeshResource
from databox_orchestration.definitions import (
    DataboxConfig,
    ebird_dlt_assets,
    noaa_dlt_assets,
    sqlmesh_project,
)

defs = dg.Definitions(
    assets=[ebird_dlt_assets, noaa_dlt_assets, sqlmesh_project],
    resources={
        "databox_config": DataboxConfig(),
        "dlt": DagsterDltResource(),
        "sqlmesh": SQLMeshResource(),
    },
    executor=dg.in_process_executor,
)

result = defs.get_implicit_global_asset_job_def().execute_in_process()

if not result.success:
    print("SMOKE TEST FAILED")
    sys.exit(1)

print("SMOKE TEST PASSED")
