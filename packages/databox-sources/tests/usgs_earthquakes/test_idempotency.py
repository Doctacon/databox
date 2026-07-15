"""USGS Earthquakes merge idempotency against one bounded feed fixture."""

from __future__ import annotations

import pytest
from databox.orchestration.domains.usgs_earthquakes import _build_source


def _source():
    source = _build_source()
    source.add_limit(max_items=2)
    return source


@pytest.mark.vcr
def test_usgs_earthquakes_events_idempotent(memory_duckdb_pipeline_factory):
    pipeline = memory_duckdb_pipeline_factory(pipeline_name="usgs_earthquakes_idempotency")
    first = pipeline.run(_source())
    assert not first.has_failed_jobs
    with pipeline.sql_client() as client:
        before = client.execute_sql("SELECT id FROM events ORDER BY id")

    second = pipeline.run(_source())
    assert not second.has_failed_jobs
    with pipeline.sql_client() as client:
        after = client.execute_sql("SELECT id FROM events ORDER BY id")

    assert before == after
    assert len(after) == 2
