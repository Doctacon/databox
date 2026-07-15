"""Bounded local-fixture AVONET pipeline smoke test."""

from __future__ import annotations

from pathlib import Path

from databox_sources.avonet import source

from .test_resources import _row, workbook_bytes


def test_avonet_pipeline_runs_in_memory(memory_duckdb_pipeline_factory, monkeypatch):
    fixture = workbook_bytes(
        _row("Accipiter albogularis", "AVIBASE-ONE"),
        _row("Buteo jamaicensis", "AVIBASE-TWO"),
    )

    def download(destination: Path) -> None:
        destination.write_bytes(fixture)

    monkeypatch.setattr(source, "download_avonet_workbook", download)
    monkeypatch.setattr(source, "AVONET_EXPECTED_ROWS", 2)
    pipeline = memory_duckdb_pipeline_factory(pipeline_name="avonet_smoke")
    info = pipeline.run(source.avonet_source())
    assert not info.has_failed_jobs
    with pipeline.sql_client() as client:
        assert client.execute_sql("SELECT COUNT(*) FROM species_traits")[0][0] == 2
