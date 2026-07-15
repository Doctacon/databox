"""Bounded end-to-end USGS Earthquakes pipeline smoke test."""

from __future__ import annotations

import pytest
from databox.orchestration.domains.usgs_earthquakes import _build_source


@pytest.mark.vcr
def test_usgs_earthquakes_pipeline_runs_in_memory(memory_duckdb_pipeline_factory):
    source = _build_source()
    source.add_limit(max_items=2)
    pipeline = memory_duckdb_pipeline_factory(pipeline_name="usgs_earthquakes_smoke")
    info = pipeline.run(source)
    assert not info.has_failed_jobs
    with pipeline.sql_client() as client:
        assert client.execute_sql("SELECT COUNT(*) FROM events")[0][0] == 2
