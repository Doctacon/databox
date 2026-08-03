"""USFWS merge idempotency for one explicit snapshot identity."""

from __future__ import annotations


def test_usfws_snapshot_idempotent(memory_duckdb_pipeline_factory, usfws_source_factory) -> None:
    pipeline = memory_duckdb_pipeline_factory(pipeline_name="usfws_idempotency")
    first = pipeline.run(usfws_source_factory())
    second = pipeline.run(usfws_source_factory())
    assert not first.has_failed_jobs
    assert not second.has_failed_jobs
    with pipeline.sql_client() as client:
        assert client.execute_sql("SELECT COUNT(*) FROM image_search_runs")[0][0] == 1
        assert client.execute_sql("SELECT COUNT(*) FROM image_records")[0][0] == 3
