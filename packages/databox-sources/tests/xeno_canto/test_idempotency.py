"""Xeno-canto merge idempotency against one bounded fixture page."""

from __future__ import annotations

import pytest
from databox.orchestration.domains.xeno_canto import _build_source


def _source():
    return _build_source(max_records=2, per_page=2)


@pytest.mark.vcr
def test_xeno_canto_recordings_idempotent(memory_duckdb_pipeline_factory):
    pipeline = memory_duckdb_pipeline_factory(pipeline_name="xeno_canto_idempotency")
    first = pipeline.run(_source())
    assert not first.has_failed_jobs
    with pipeline.sql_client() as client:
        before = client.execute_sql("SELECT id FROM recordings ORDER BY id")

    second = pipeline.run(_source())
    assert not second.has_failed_jobs
    with pipeline.sql_client() as client:
        after = client.execute_sql("SELECT id FROM recordings ORDER BY id")

    assert before == after
    assert len(after) == 2
