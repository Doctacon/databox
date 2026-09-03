"""Offline end-to-end USFWS pipeline smoke test."""

from __future__ import annotations

from collections.abc import Mapping
from typing import cast

import pytest
from databox_sources.usfws import USFWS_MAX_TARGET_SPECIES, UsfwsTarget, usfws_source


@pytest.mark.vcr
@pytest.mark.block_network
@pytest.mark.default_cassette("usfws-public-interface.yaml")
def test_public_interface_runs_explicit_target_source(memory_duckdb_pipeline_factory) -> None:
    target: UsfwsTarget = {
        "species_code": "berhum",
        "common_name": "Berylline Hummingbird",
        "scientific_name": "Amazilia beryllina",
    }
    assert USFWS_MAX_TARGET_SPECIES == 500
    pipeline = memory_duckdb_pipeline_factory(pipeline_name="usfws_public_interface")
    info = pipeline.run(
        usfws_source(
            target_species=[cast(Mapping[str, str], target)],
            run_id="public-interface-run",
            loaded_at="2026-08-03T12:00:00Z",
            detail_workers=2,
            max_images_per_target=5,
        )
    )
    assert not info.has_failed_jobs
    with pipeline.sql_client() as client:
        assert client.execute_sql("SELECT COUNT(*) FROM image_search_runs")[0][0] == 1
        assert client.execute_sql("SELECT COUNT(*) FROM image_records")[0][0] > 0


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
