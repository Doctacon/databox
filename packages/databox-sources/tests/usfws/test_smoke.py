"""Offline end-to-end USFWS pipeline smoke test."""

from __future__ import annotations


def test_usfws_pipeline_runs_in_memory(
    memory_duckdb_pipeline_factory, usfws_source_factory
) -> None:
    pipeline = memory_duckdb_pipeline_factory(pipeline_name="usfws_smoke")
    info = pipeline.run(usfws_source_factory())
    assert not info.has_failed_jobs
    with pipeline.sql_client() as client:
        assert client.execute_sql("SELECT COUNT(*) FROM image_search_runs")[0][0] == 1
        assert client.execute_sql("SELECT COUNT(*) FROM image_records")[0][0] == 3
        assert (
            client.execute_sql(
                "SELECT COUNT(*) FROM image_records WHERE source_license = 'CC BY-NC 4.0'"
            )[0][0]
            == 1
        )
