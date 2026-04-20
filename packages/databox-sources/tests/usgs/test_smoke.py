"""End-to-end smoke test: USGS source loads into in-memory duckdb."""

from __future__ import annotations

import pytest
from databox_sources.usgs.source import usgs_source

FROZEN_NOW = "2026-02-15T00:00:00Z"


@pytest.mark.vcr
@pytest.mark.time_machine(FROZEN_NOW)
def test_usgs_pipeline_runs_in_memory(memory_duckdb_pipeline_factory):
    source = usgs_source(state_cd="RI", parameter_cds="00060", days_back=3)

    pipeline = memory_duckdb_pipeline_factory(pipeline_name="usgs_smoke")
    info = pipeline.run(source)

    assert not info.has_failed_jobs, f"pipeline had failed jobs: {info}"

    counts = pipeline.last_trace.last_normalize_info.row_counts if pipeline.last_trace else {}
    total = sum(v for k, v in counts.items() if not k.startswith("_dlt_"))
    assert total > 0, f"pipeline loaded zero rows across all tables: {counts}"
