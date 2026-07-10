from __future__ import annotations

from pathlib import Path

import pytest
from databox_sources.avonet import source
from dlt.extract.exceptions import ResourceExtractionError
from dlt.pipeline.exceptions import PipelineStepFailed

from .test_resources import _row, workbook_bytes


def test_identical_snapshot_is_idempotent_and_failed_replace_preserves_prior_table(
    memory_duckdb_pipeline_factory, monkeypatch: pytest.MonkeyPatch
) -> None:
    valid = workbook_bytes(
        _row("Accipiter albogularis", "AVIBASE-ONE"),
        _row("Buteo jamaicensis", "AVIBASE-TWO"),
    )
    current = valid

    def download(destination: Path) -> None:
        destination.write_bytes(current)

    monkeypatch.setattr(source, "download_avonet_workbook", download)
    monkeypatch.setattr(source, "AVONET_EXPECTED_ROWS", 2)
    pipeline = memory_duckdb_pipeline_factory(pipeline_name="avonet_idempotency")

    first = pipeline.run(source.avonet_source())
    assert not first.has_failed_jobs
    with pipeline.sql_client() as client:
        before = client.execute_sql(
            "SELECT avibase_id, source_scientific_name FROM species_traits ORDER BY avibase_id"
        )
    second = pipeline.run(source.avonet_source())
    assert not second.has_failed_jobs
    with pipeline.sql_client() as client:
        after = client.execute_sql(
            "SELECT avibase_id, source_scientific_name FROM species_traits ORDER BY avibase_id"
        )
    assert after == before

    current = workbook_bytes(
        _row("Changed species", "AVIBASE-CHANGED"),
        headers=(*source.EXPECTED_HEADERS[:-1], "Changed"),
    )
    with pytest.raises(PipelineStepFailed):
        pipeline.run(source.avonet_source())
    with pipeline.sql_client() as client:
        preserved = client.execute_sql(
            "SELECT avibase_id, source_scientific_name FROM species_traits ORDER BY avibase_id"
        )
    assert preserved == before


def test_temporary_directory_is_removed_after_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    observed: list[Path] = []

    def fail_download(destination: Path) -> None:
        observed.append(destination.parent)
        raise ValueError("fixture failure")

    monkeypatch.setattr(source, "download_avonet_workbook", fail_download)
    with pytest.raises(ResourceExtractionError, match="fixture failure"):
        list(source.species_traits())
    assert observed and all(not directory.exists() for directory in observed)
