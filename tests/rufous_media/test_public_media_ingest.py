"""Public USFWS target-catalog boundary tests."""

from __future__ import annotations

from pathlib import Path

import duckdb
import pytest
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
