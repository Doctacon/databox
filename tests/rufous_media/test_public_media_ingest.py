"""Public USFWS target-catalog boundary tests."""

from __future__ import annotations

from contextlib import nullcontext
from pathlib import Path
from typing import Any

import duckdb
import pytest
from databox import public_media_ingest
from databox.config.settings import settings
from databox.public_export import PublicExportError
from databox.public_media_ingest import load_public_species_targets


def _database(path: Path) -> None:
    connection = duckdb.connect(str(path))
    connection.execute("CREATE SCHEMA rufous_public")
    connection.execute(
        """CREATE TABLE rufous_public.gbif_eod_occurrence (
          accepted_taxon_key BIGINT,
          taxon_key BIGINT,
          species_key BIGINT,
          common_name VARCHAR,
          scientific_name VARCHAR
        )"""
    )
    connection.executemany(
        "INSERT INTO rufous_public.gbif_eod_occurrence VALUES (?, ?, ?, ?, ?)",
        [
            (2476674, 2476674, 2476674, "Anna's Hummingbird", "Calypte anna"),
            (2476855, 2476855, 2476855, "Rufous Hummingbird", "Selasphorus rufus"),
            (2476855, 2476855, 2476855, "Rufous Hummingbird", "Selasphorus rufus"),
            (999, 999, 999, "Canada Goose", "Branta canadensis moffitti"),
            (999, 999, 999, "Malformed", "Bird name (Author)"),
        ],
    )
    connection.close()


def test_targets_are_exact_deduplicated_public_species_with_rufous_first(tmp_path: Path) -> None:
    database = tmp_path / "warehouse.duckdb"
    _database(database)

    assert load_public_species_targets(database) == [
        {
            "species_code": "gbif-2476855",
            "common_name": "Rufous Hummingbird",
            "scientific_name": "Selasphorus rufus",
        },
        {
            "species_code": "gbif-2476674",
            "common_name": "Anna's Hummingbird",
            "scientific_name": "Calypte anna",
        },
    ]


def test_explicit_ingest_uses_iceberg_and_publishes_status(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    database = tmp_path / "warehouse.duckdb"
    _database(database)
    source = object()
    destination = object()
    pipeline_calls: dict[str, Any] = {}
    published: dict[str, Any] = {}

    class Pipeline:
        def run(self, value: object) -> None:
            pipeline_calls["source"] = value

    pipeline = Pipeline()

    class Scan:
        def __init__(self, count: int) -> None:
            self._count = count

        def count(self) -> int:
            return self._count

    class Table:
        def __init__(self, count: int) -> None:
            self._count = count

        def scan(self, **kwargs: object) -> Scan:
            if kwargs:
                pipeline_calls["run_scan"] = kwargs
            return Scan(self._count)

    class Catalog:
        def load_table(self, identifier: str) -> Table:
            return Table(3 if identifier.endswith("image_records") else 1)

    monkeypatch.setattr(public_media_ingest, "usfws_source", lambda **kwargs: source)
    monkeypatch.setattr(public_media_ingest, "iceberg_destination", lambda: destination)

    def pipeline_factory(**kwargs: object) -> Pipeline:
        pipeline_calls["pipeline"] = kwargs
        return pipeline

    monkeypatch.setattr(public_media_ingest, "iceberg_dlt_pipeline", pipeline_factory)
    monkeypatch.setattr(public_media_ingest, "polaris_dlt_catalog", nullcontext)
    monkeypatch.setattr(
        public_media_ingest,
        "publish_dlt_load_status",
        lambda *args, **kwargs: published.update({"args": args, "kwargs": kwargs}),
    )
    monkeypatch.setattr(type(settings), "pyiceberg_catalog", lambda self: Catalog())

    result = public_media_ingest.ingest_public_usfws_media(database, max_images_per_target=2)

    assert result.target_species == 2
    assert result.raw_records == 3
    assert result.completed_runs == 1
    assert pipeline_calls["pipeline"] == {
        "pipeline_name": "usfws_media_iceberg",
        "destination": destination,
        "dataset_name": "raw_usfws",
        "pipelines_dir": settings.dlt_data_dir,
    }
    assert pipeline_calls["source"] is source
    assert published["args"] == (pipeline,)
    assert published["kwargs"] == {
        "dataset_name": "raw_usfws",
        "table_names": ("image_search_runs", "image_records"),
    }
    assert "row_filter" in pipeline_calls["run_scan"]


def test_targets_fail_closed_without_modeled_table_or_rufous(tmp_path: Path) -> None:
    empty = tmp_path / "empty.duckdb"
    duckdb.connect(str(empty)).close()
    with pytest.raises(PublicExportError, match="require"):
        load_public_species_targets(empty)

    database = tmp_path / "warehouse.duckdb"
    _database(database)
    connection = duckdb.connect(str(database))
    connection.execute(
        "DELETE FROM rufous_public.gbif_eod_occurrence WHERE scientific_name = 'Selasphorus rufus'"
    )
    connection.close()
    with pytest.raises(PublicExportError, match="missing Rufous"):
        load_public_species_targets(database)
