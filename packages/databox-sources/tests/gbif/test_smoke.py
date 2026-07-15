"""Bounded end-to-end GBIF pipeline smoke test."""

from __future__ import annotations

import pytest
from databox.orchestration.domains.gbif import _build_source


@pytest.mark.vcr
def test_gbif_pipeline_runs_in_memory(memory_duckdb_pipeline_factory):
    source = _build_source(max_records=2)
    pipeline = memory_duckdb_pipeline_factory(pipeline_name="gbif_smoke")
    info = pipeline.run(source)
    assert not info.has_failed_jobs
    with pipeline.sql_client() as client:
        assert client.execute_sql("SELECT COUNT(*) FROM occurrences")[0][0] == 2
