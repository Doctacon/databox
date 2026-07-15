"""GBIF merge idempotency against one bounded fixture page."""

from __future__ import annotations

import pytest
from databox.orchestration.domains.gbif import _build_source


def _source():
    return _build_source(max_records=2)


@pytest.mark.vcr
def test_gbif_occurrences_idempotent(memory_duckdb_pipeline_factory):
    pipeline = memory_duckdb_pipeline_factory(pipeline_name="gbif_idempotency")
    first = pipeline.run(_source())
    assert not first.has_failed_jobs
    with pipeline.sql_client() as client:
        before = client.execute_sql("SELECT key FROM occurrences ORDER BY key")

    second = pipeline.run(_source())
    assert not second.has_failed_jobs
    with pipeline.sql_client() as client:
        after = client.execute_sql("SELECT key FROM occurrences ORDER BY key")

    assert before == after
    assert len(after) == 2
