#!/usr/bin/env python3
"""Smoke test: run every registered source's dlt assets + SQLMesh in-process.

Iterates `databox.config.sources.SOURCES` so a new source added to the
registry is exercised automatically — no edits here required. Bypasses the
dagster CLI (which spawns subprocesses that lose env vars) and runs assets
via `execute_in_process()`.
"""

import importlib
import os
import sys

os.environ["DATABOX_SMOKE"] = "1"

import dagster as dg
from dagster_dlt import DagsterDltResource
from dagster_sqlmesh import SQLMeshResource
from databox.config.sources import SOURCES
from databox.orchestration._factories import DataboxConfig, sqlmesh_project


def _dlt_assets_for(source_name: str) -> dg.AssetsDefinition:
    module = importlib.import_module(f"databox.orchestration.domains.{source_name}")
    return getattr(module, f"{source_name}_dlt_assets")


dlt_assets = [_dlt_assets_for(src.name) for src in SOURCES]

defs = dg.Definitions(
    assets=[*dlt_assets, sqlmesh_project],
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
