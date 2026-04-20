"""End-to-end smoke test: eBird source loads into in-memory duckdb without error.

Runs the full source minus `taxonomy` (which is ~5MB and blows cassette size).
Asserts the pipeline reports no failed jobs and at least one table has rows.
"""

from __future__ import annotations

import pytest
from databox_sources.ebird.source import ebird_source


@pytest.mark.vcr
def test_ebird_pipeline_runs_in_memory(memory_duckdb_pipeline_factory):
    source = ebird_source(region_code="US-DC", max_results=50, days_back=1)
    source = source.with_resources(
        "recent_observations", "notable_observations", "hotspots", "species_list"
    )

    pipeline = memory_duckdb_pipeline_factory(pipeline_name="ebird_smoke")
    info = pipeline.run(source)

    assert not info.has_failed_jobs, f"pipeline had failed jobs: {info}"

    counts = pipeline.last_trace.last_normalize_info.row_counts if pipeline.last_trace else {}
    total = sum(v for k, v in counts.items() if not k.startswith("_dlt_"))
    assert total > 0, f"pipeline loaded zero rows across all tables: {counts}"
