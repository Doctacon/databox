"""Schema snapshot tests for USGS NWIS dlt source."""

from __future__ import annotations

import pytest
from databox_sources.usgs.source import usgs_source

FROZEN_NOW = "2026-02-15T00:00:00Z"


@pytest.mark.vcr
@pytest.mark.time_machine(FROZEN_NOW)
def test_usgs_schema_snapshot(memory_duckdb_pipeline_factory, snapshot, normalize_schema):
    source = usgs_source(state_cd="RI", parameter_cds="00060", days_back=3)

    pipeline = memory_duckdb_pipeline_factory(pipeline_name="usgs_schema_test")
    info = pipeline.run(source)
    assert not info.has_failed_jobs

    schema_yaml = pipeline.default_schema.to_pretty_yaml()
    assert normalize_schema(schema_yaml) == snapshot
