"""Offline dlt-to-DuckDB iNaturalist smoke test."""

from __future__ import annotations

from typing import Any


def test_inaturalist_pipeline_runs_in_memory(
    memory_duckdb_pipeline_factory: Any,
    inaturalist_source_factory: Any,
) -> None:
    pipeline = memory_duckdb_pipeline_factory(pipeline_name="inaturalist_public_photo_smoke")
    first = pipeline.run(inaturalist_source_factory())
    second = pipeline.run(inaturalist_source_factory())
    assert not first.has_failed_jobs
    assert not second.has_failed_jobs
    with pipeline.sql_client() as client:
        assert client.execute_sql("SELECT COUNT(*) FROM photo_discovery_runs")[0][0] == 1
        assert client.execute_sql("SELECT COUNT(*) FROM photo_species_results")[0][0] == 1
        assert client.execute_sql("SELECT COUNT(*) FROM photo_candidates")[0][0] == 3
        assert (
            client.execute_sql(
                "SELECT COUNT(*) FROM photo_candidates WHERE license_code LIKE '%NC%'"
            )[0][0]
            == 0
        )
