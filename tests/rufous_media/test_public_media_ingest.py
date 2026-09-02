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
from pyiceberg.expressions import EqualTo


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
        def __init__(self, rows: list[dict[str, object]]) -> None:
            self._rows = rows

        def count(self) -> int:
            return len(self._rows)

        def to_arrow(self) -> Scan:
            return self

        def to_pylist(self) -> list[dict[str, object]]:
            return self._rows

    class Table:
        def __init__(self, identifier: str) -> None:
            self._identifier = identifier

        def scan(self, **kwargs: object) -> Scan:
            pipeline_calls.setdefault("scans", {})[self._identifier] = kwargs
            if self._identifier.endswith("image_records"):
                return Scan([{"run_id": "current"}] * 3)
            return Scan(
                [
                    {
                        "run_id": "current",
                        "status": "complete",
                        "target_species_count": 2,
                        "completed_target_species_count": 2,
                        "record_count": 3,
                    }
                ]
            )

    class Catalog:
        def load_table(self, identifier: str) -> Table:
            return Table(identifier)

    source_kwargs: dict[str, object] = {}

    def source_factory(**kwargs: object) -> object:
        source_kwargs.update(kwargs)
        return source

    monkeypatch.setattr(public_media_ingest, "usfws_source", source_factory)
    monkeypatch.setattr(public_media_ingest, "uuid4", lambda: type("ID", (), {"hex": "current"})())
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
    assert source_kwargs["run_id"] == "current"
    assert published["args"] == (pipeline,)
    assert published["kwargs"] == {
        "dataset_name": "raw_usfws",
        "table_names": ("image_search_runs", "image_records"),
    }
    scans = pipeline_calls["scans"]
    assert "row_filter" in scans["raw_usfws.image_records"]
    assert "row_filter" in scans["raw_usfws.image_search_runs"]


def test_current_run_cannot_be_masked_by_historical_records(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    database = tmp_path / "warehouse.duckdb"
    _database(database)

    class Scan:
        def __init__(self, rows: list[dict[str, object]]) -> None:
            self._rows = rows

        def count(self) -> int:
            return len(self._rows)

        def to_arrow(self) -> Scan:
            return self

        def to_pylist(self) -> list[dict[str, object]]:
            return self._rows

    historical_records = [{"run_id": "historical"}] * 7
    historical_runs = [
        {
            "run_id": "historical",
            "status": "complete",
            "target_species_count": 2,
            "completed_target_species_count": 2,
            "record_count": 7,
        }
    ]

    class Table:
        def __init__(self, identifier: str) -> None:
            self._identifier = identifier

        def scan(self, **kwargs: object) -> Scan:
            assert kwargs["row_filter"] == EqualTo("run_id", "current")
            if self._identifier.endswith("image_records"):
                assert historical_records
                return Scan([])
            assert historical_runs
            return Scan(
                [
                    {
                        "run_id": "current",
                        "status": "complete",
                        "target_species_count": 2,
                        "completed_target_species_count": 2,
                        "record_count": 0,
                    }
                ]
            )

    class Pipeline:
        def run(self, value: object) -> None:
            pass

    class Catalog:
        def load_table(self, identifier: str) -> Table:
            return Table(identifier)

    monkeypatch.setattr(public_media_ingest, "usfws_source", lambda **kwargs: object())
    monkeypatch.setattr(public_media_ingest, "uuid4", lambda: type("ID", (), {"hex": "current"})())
    monkeypatch.setattr(public_media_ingest, "iceberg_destination", object)
    monkeypatch.setattr(public_media_ingest, "iceberg_dlt_pipeline", lambda **kwargs: Pipeline())
    monkeypatch.setattr(public_media_ingest, "polaris_dlt_catalog", nullcontext)
    monkeypatch.setattr(
        public_media_ingest, "publish_dlt_load_status", lambda *args, **kwargs: None
    )
    monkeypatch.setattr(type(settings), "pyiceberg_catalog", lambda self: Catalog())

    with pytest.raises(PublicExportError, match="complete current snapshot"):
        public_media_ingest.ingest_public_usfws_media(database)


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
