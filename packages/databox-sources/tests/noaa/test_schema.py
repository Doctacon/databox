"""Schema snapshot tests for NOAA CDO dlt source."""

from __future__ import annotations

import pytest
from databox_sources.noaa.source import noaa_source

FROZEN_NOW = "2026-02-15T00:00:00Z"


@pytest.mark.vcr
@pytest.mark.time_machine(FROZEN_NOW)
def test_noaa_schema_snapshot(memory_duckdb_pipeline_factory, snapshot, normalize_schema):
    source = noaa_source(
        location_id="FIPS:11",
        dataset_id="GHCND",
        days_back=7,
        datatypes="TMAX",
    )

    pipeline = memory_duckdb_pipeline_factory(pipeline_name="noaa_schema_test")
    info = pipeline.run(source)
    assert not info.has_failed_jobs

    schema_yaml = pipeline.default_schema.to_pretty_yaml()
    assert normalize_schema(schema_yaml) == snapshot
