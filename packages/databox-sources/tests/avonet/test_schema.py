"""Schema snapshot test for the bounded local AVONET workbook fixture."""

from __future__ import annotations

from pathlib import Path

from databox_sources.avonet import source

from .test_resources import _row, workbook_bytes


def test_avonet_schema_snapshot(
    memory_duckdb_pipeline_factory, monkeypatch, snapshot, normalize_schema
):
    fixture = workbook_bytes(
        _row("Accipiter albogularis", "AVIBASE-ONE"),
        _row("Buteo jamaicensis", "AVIBASE-TWO"),
    )

    def download(destination: Path) -> None:
        destination.write_bytes(fixture)

    monkeypatch.setattr(source, "download_avonet_workbook", download)
    monkeypatch.setattr(source, "AVONET_EXPECTED_ROWS", 2)
    pipeline = memory_duckdb_pipeline_factory(pipeline_name="avonet_schema_test")
    info = pipeline.run(source.avonet_source())
    assert not info.has_failed_jobs
    assert normalize_schema(pipeline.default_schema.to_pretty_yaml()) == snapshot
