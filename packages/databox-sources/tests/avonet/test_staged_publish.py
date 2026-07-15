"""File-profile proof of the production AVONET staged publication path."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import databox.destinations.quack as quack_module
import duckdb
import pytest
from databox.destinations import (
    dlt_destination,
    dlt_pipeline,
    prepare_dlt_source,
    quack_ingest_session,
)
from databox.orchestration.domains import avonet
from databox_sources.avonet import source

from .test_resources import _row, workbook_bytes


def _pipeline(database: Path, pipelines_dir: Path):
    return dlt_pipeline(
        pipeline_name="avonet_profile_staged_publish",
        destination=dlt_destination(str(database)),
        dataset_name=avonet._AVONET_STAGING_SCHEMA,
        pipelines_dir=str(pipelines_dir),
    )


def _publish(
    database: Path,
    pipelines_dir: Path,
    monkeypatch: pytest.MonkeyPatch,
    *rows: list[object],
    publish_expected_rows: int | None = None,
) -> None:
    fixture = workbook_bytes(*rows)

    def download(destination: Path) -> None:
        destination.write_bytes(fixture)

    monkeypatch.setattr(source, "download_avonet_workbook", download)
    monkeypatch.setattr(source, "AVONET_EXPECTED_ROWS", len(rows))
    pipeline = _pipeline(database, pipelines_dir)
    with avonet.avonet_staged_publish(
        str(database),
        expected_rows=publish_expected_rows or len(rows),
    ):
        with patch("databox.destinations.quack.settings.quack_shared_server", False):
            with quack_ingest_session(avonet._AVONET_STAGING_SCHEMA, str(database)):
                info = pipeline.run(prepare_dlt_source(avonet._build_source()))
    assert not info.has_failed_jobs


def _final_rows(database: Path) -> list[tuple[str, str]]:
    with duckdb.connect(str(database), read_only=True) as connection:
        return connection.execute(
            """
            SELECT source_scientific_name, avibase_id
            FROM raw_avonet.species_traits
            ORDER BY avibase_id
            """
        ).fetchall()


def _assert_staging_removed(database: Path) -> None:
    with duckdb.connect(str(database), read_only=True) as connection:
        assert connection.execute(
            """
            SELECT count(*)
            FROM information_schema.schemata
            WHERE schema_name = 'raw_avonet_staging'
            """
        ).fetchone() == (0,)


def test_profile_uses_atomic_production_publish_and_preserves_prior_on_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(avonet, "DATA_DIR", tmp_path)
    monkeypatch.setattr(quack_module, "DATA_DIR", tmp_path)
    database = tmp_path / "databox.duckdb"

    _publish(
        database,
        tmp_path / "pipelines-1",
        monkeypatch,
        _row("Accipiter albogularis", "AVIBASE-ONE"),
        _row("Buteo jamaicensis", "AVIBASE-TWO"),
    )
    assert _final_rows(database) == [
        ("Accipiter albogularis", "AVIBASE-ONE"),
        ("Buteo jamaicensis", "AVIBASE-TWO"),
    ]

    _publish(
        database,
        tmp_path / "pipelines-2",
        monkeypatch,
        _row("Corvus corax", "AVIBASE-THREE"),
    )
    prior = [("Corvus corax", "AVIBASE-THREE")]
    assert _final_rows(database) == prior
    _assert_staging_removed(database)

    with pytest.raises(RuntimeError, match="row or uniqueness"):
        _publish(
            database,
            tmp_path / "pipelines-3",
            monkeypatch,
            _row("Cyanocitta stelleri", "AVIBASE-FOUR"),
            publish_expected_rows=2,
        )

    assert _final_rows(database) == prior
    _assert_staging_removed(database)
    assert not (tmp_path / ".quack-clients").exists()
