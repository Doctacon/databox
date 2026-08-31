"""Offline curated Wikimedia Commons media-loader tests."""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

import duckdb
import pytest
from databox.public_export import PublicRecords, build_public_assets, write_public_assets
from databox.public_media import SOURCE_COLUMNS, PublicMediaError
from databox.public_wikimedia_media_ingest import (
    DISCOVERY_METHOD,
    MODE,
    PROVIDER,
    canonical_wikimedia_media_json,
    load_curated_wikimedia_media,
    main,
)


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
            (2476855, 2476855, 2476855, "Rufous Hummingbird", "Selasphorus rufus"),
            (2480916, 2480916, 2480916, "Elegant Trogon", "Trogon elegans"),
        ],
    )
    connection.execute("CREATE TABLE rufous_public.keep_me (value VARCHAR)")
    connection.execute("INSERT INTO rufous_public.keep_me VALUES ('untouched')")
    connection.close()


def _row(**overrides: object) -> dict[str, object]:
    row: dict[str, object] = {
        "species_code": "gbif-2476855",
        "common_name": "Rufous Hummingbird",
        "scientific_name": "Selasphorus rufus",
        "source_page_url": (
            "https://commons.wikimedia.org/wiki/File:Rufous_Hummingbird_perched.jpg"
        ),
        "source_image_url": (
            "https://upload.wikimedia.org/wikipedia/commons/thumb/a/ab/"
            "Rufous_Hummingbird_perched.jpg/1200px-Rufous_Hummingbird_perched.jpg"
        ),
        "creator": "Example Bird Photographer",
        "license": "CC BY-SA 4.0",
        "title": "Rufous Hummingbird perched on a branch",
        "caption": "A live Rufous Hummingbird perched alone on a branch.",
        "alt_text": "A live Rufous Hummingbird perched alone on a branch",
        "source_published_at": "2024-06-20T12:30:00Z",
        "source_width": 1200,
        "source_height": 800,
        "mime_type": "image/jpeg",
        "discovery_method": DISCOVERY_METHOD,
        "loaded_at": "2026-08-04T14:00:00Z",
    }
    row.update(overrides)
    return row


def _payload(*rows: dict[str, object]) -> dict[str, object]:
    return {
        "schema_version": 1,
        "mode": MODE,
        "provider": PROVIDER,
        "items": list(rows),
    }


def _write(path: Path, payload: object) -> None:
    path.write_bytes(canonical_wikimedia_media_json(payload))


def _public_catalog(path: Path) -> None:
    records = PublicRecords(
        species=[
            {
                "species_code": "gbif-2476855",
                "common_name": "Rufous Hummingbird",
                "scientific_name": "Selasphorus rufus",
                "taxonomic_category": "species",
                "family": {"common_name": None, "scientific_name": "Trochilidae"},
                "order_name": "Caprimulgiformes",
                "traits": {},
                "evidence": {
                    "licensed_occurrence_count": 0,
                    "latest_licensed_occurrence_at": None,
                },
                "media": [],
            },
            {
                "species_code": "gbif-2480916",
                "common_name": "Elegant Trogon",
                "scientific_name": "Trogon elegans",
                "taxonomic_category": "species",
                "family": {"common_name": None, "scientific_name": "Trogonidae"},
                "order_name": "Trogoniformes",
                "traits": {},
                "evidence": {
                    "licensed_occurrence_count": 0,
                    "latest_licensed_occurrence_at": None,
                },
                "media": [],
            },
        ],
        observations=[],
        places=[],
        attribution_items=[],
        rejected=Counter(),
    )
    write_public_assets(
        path,
        build_public_assets(
            records,
            mode="production",
            gnis_sha256="1" * 64,
            generated_at="2026-08-04T14:00:00Z",
        ),
    )


def test_loader_creates_exact_source_table_without_network_or_other_mutation(
    tmp_path: Path,
) -> None:
    database = tmp_path / "warehouse.duckdb"
    source = tmp_path / "wikimedia.json"
    _database(database)
    _write(source, _payload(_row()))

    result = load_curated_wikimedia_media(database, source)

    assert result.items == 1
    assert result.species == 1
    assert len(result.input_sha256) == 64
    connection = duckdb.connect(str(database), read_only=True)
    try:
        columns = [
            str(item[0])
            for item in connection.execute(
                """SELECT column_name
                FROM information_schema.columns
                WHERE table_schema = 'rufous_public'
                  AND table_name = 'wikimedia_commercial_image'
                ORDER BY ordinal_position"""
            ).fetchall()
        ]
        loaded = connection.execute(
            """SELECT
              species_code,
              common_name,
              scientific_name,
              source_page_url,
              source_image_url,
              creator,
              license,
              source_width,
              source_height,
              mime_type,
              discovery_method
            FROM rufous_public.wikimedia_commercial_image"""
        ).fetchone()
        sentinel = connection.execute("SELECT value FROM rufous_public.keep_me").fetchone()
    finally:
        connection.close()

    assert columns == list(SOURCE_COLUMNS)
    assert loaded == (
        "gbif-2476855",
        "Rufous Hummingbird",
        "Selasphorus rufus",
        "https://commons.wikimedia.org/wiki/File:Rufous_Hummingbird_perched.jpg",
        (
            "https://upload.wikimedia.org/wikipedia/commons/thumb/a/ab/"
            "Rufous_Hummingbird_perched.jpg/1200px-Rufous_Hummingbird_perched.jpg"
        ),
        "Example Bird Photographer",
        "CC BY-SA 4.0",
        1200,
        800,
        "image/jpeg",
        DISCOVERY_METHOD,
    )
    assert sentinel == ("untouched",)


def test_loader_idempotently_replaces_only_the_wikimedia_table(tmp_path: Path) -> None:
    database = tmp_path / "warehouse.duckdb"
    first = tmp_path / "first.json"
    second = tmp_path / "second.json"
    _database(database)
    _write(first, _payload(_row()))
    _write(
        second,
        _payload(
            _row(
                species_code="gbif-2480916",
                common_name="Elegant Trogon",
                scientific_name="Trogon elegans",
                source_page_url="https://commons.wikimedia.org/wiki/File:Trogon_elegans.jpg",
                source_image_url=(
                    "https://upload.wikimedia.org/wikipedia/commons/1/12/Trogon_elegans.jpg"
                ),
                title="Elegant Trogon perched in a tree",
                caption="A live Elegant Trogon perched alone in a tree.",
                alt_text="A live Elegant Trogon perched alone in a tree",
                source_width=1600,
                source_height=1200,
            )
        ),
    )

    load_curated_wikimedia_media(database, first)
    load_curated_wikimedia_media(database, second)
    load_curated_wikimedia_media(database, second)

    connection = duckdb.connect(str(database), read_only=True)
    try:
        rows = connection.execute(
            "SELECT species_code FROM rufous_public.wikimedia_commercial_image"
        ).fetchall()
        sentinel = connection.execute("SELECT value FROM rufous_public.keep_me").fetchone()
        catalog_count = connection.execute(
            "SELECT COUNT(*) FROM rufous_public.gbif_eod_occurrence"
        ).fetchone()
    finally:
        connection.close()
    assert rows == [("gbif-2480916",)]
    assert sentinel == ("untouched",)
    assert catalog_count == (2,)


def test_loader_can_validate_against_hydrated_active_public_catalog(tmp_path: Path) -> None:
    database = tmp_path / "warehouse.duckdb"
    source = tmp_path / "wikimedia.json"
    public_output = tmp_path / "active-public"
    duckdb.connect(str(database)).close()
    _public_catalog(public_output)
    _write(source, _payload(_row()))

    result = load_curated_wikimedia_media(
        database,
        source,
        targets_from_public_output=public_output,
    )

    assert result.items == result.species == 1
    connection = duckdb.connect(str(database), read_only=True)
    try:
        loaded = connection.execute(
            "SELECT species_code FROM rufous_public.wikimedia_commercial_image"
        ).fetchall()
    finally:
        connection.close()
    assert loaded == [("gbif-2476855",)]


def test_hydrated_public_catalog_mismatch_fails_before_table_replacement(
    tmp_path: Path,
) -> None:
    database = tmp_path / "warehouse.duckdb"
    source = tmp_path / "wikimedia.json"
    public_output = tmp_path / "active-public"
    _database(database)
    _public_catalog(public_output)
    _write(source, _payload(_row(common_name="Wrong Common Name")))

    with pytest.raises(PublicMediaError, match="production species identity"):
        load_curated_wikimedia_media(
            database,
            source,
            targets_from_public_output=public_output,
        )

    connection = duckdb.connect(str(database), read_only=True)
    try:
        tables = connection.execute(
            "SELECT table_name FROM information_schema.tables WHERE table_schema = 'rufous_public'"
        ).fetchall()
    finally:
        connection.close()
    assert ("wikimedia_commercial_image",) not in tables


def test_loader_rejects_noncanonical_or_unsorted_input(tmp_path: Path) -> None:
    database = tmp_path / "warehouse.duckdb"
    source = tmp_path / "wikimedia.json"
    _database(database)
    payload = _payload(_row())
    source.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(PublicMediaError, match="canonical sorted JSON"):
        load_curated_wikimedia_media(database, source)

    unsorted = _payload(
        _row(
            species_code="gbif-2480916",
            common_name="Elegant Trogon",
            scientific_name="Trogon elegans",
            source_page_url="https://commons.wikimedia.org/wiki/File:Trogon_elegans.jpg",
            source_image_url="https://upload.wikimedia.org/wikipedia/commons/1/12/Trogon_elegans.jpg",
            title="Elegant Trogon perched in a tree",
            caption="A live Elegant Trogon perched alone in a tree.",
            alt_text="A live Elegant Trogon perched alone in a tree",
            source_width=1600,
            source_height=1200,
        ),
        _row(),
    )
    _write(source, unsorted)
    with pytest.raises(PublicMediaError, match="uniquely sorted"):
        load_curated_wikimedia_media(database, source)


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"license": "CC BY-NC 4.0"}, "commercially reusable"),
        (
            {
                "source_image_url": (
                    "https://upload.wikimedia.org/wikipedia/commons/a/ab/Different_file.jpg"
                )
            },
            "different files",
        ),
        ({"loaded_at": "2026-08-04T07:00:00-07:00"}, "noncanonical field values"),
    ],
)
def test_loader_revalidates_commons_metadata_through_public_media_contract(
    tmp_path: Path,
    overrides: dict[str, object],
    message: str,
) -> None:
    database = tmp_path / "warehouse.duckdb"
    source = tmp_path / "wikimedia.json"
    _database(database)
    _write(source, _payload(_row(**overrides)))

    with pytest.raises(PublicMediaError, match=message):
        load_curated_wikimedia_media(database, source)


def test_catalog_mismatch_fails_before_replacing_an_existing_table(tmp_path: Path) -> None:
    database = tmp_path / "warehouse.duckdb"
    accepted = tmp_path / "accepted.json"
    mismatch = tmp_path / "mismatch.json"
    _database(database)
    _write(accepted, _payload(_row()))
    load_curated_wikimedia_media(database, accepted)
    _write(mismatch, _payload(_row(common_name="Wrong Common Name")))

    with pytest.raises(PublicMediaError, match="production species identity"):
        load_curated_wikimedia_media(database, mismatch)

    connection = duckdb.connect(str(database), read_only=True)
    try:
        preserved = connection.execute(
            """SELECT common_name
            FROM rufous_public.wikimedia_commercial_image"""
        ).fetchall()
    finally:
        connection.close()
    assert preserved == [("Rufous Hummingbird",)]


def test_cli_reports_success_and_failure(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    database = tmp_path / "warehouse.duckdb"
    source = tmp_path / "wikimedia.json"
    _database(database)
    _write(source, _payload(_row()))

    assert main(["--database", str(database), "--input", str(source)]) == 0
    success = json.loads(capsys.readouterr().out)
    assert success["items"] == 1
    assert success["species"] == 1

    assert main(["--database", str(database), "--input", str(tmp_path / "missing.json")]) == 1
    assert "missing or unsafe" in capsys.readouterr().out
