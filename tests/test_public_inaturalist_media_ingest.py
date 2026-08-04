"""Missing-species boundary for the public iNaturalist fallback ingest."""

from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Literal

import duckdb
import pytest
from databox.public_export import (
    PublicExportError,
    PublicRecords,
    build_public_assets,
    write_public_assets,
)
from databox.public_inaturalist_media_ingest import (
    _validate_ingested_snapshot,
    ingest_public_inaturalist_media,
    load_missing_public_species_targets,
    load_selected_public_species_targets,
)
from databox.public_media_approval import (
    canonical_approval_json,
    empty_approval_ledger,
    load_visual_approvals,
)

PRODUCTION_APPROVALS = (
    Path(__file__).resolve().parent.parent / "config/rufous-media-visual-approvals.json"
)


def _database_with_species(path: Path, species: list[tuple[str, str]]) -> None:
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
            (index, index, index, common_name, scientific_name)
            for index, (common_name, scientific_name) in enumerate(species, start=1)
        ],
    )
    connection.close()


def _database(path: Path) -> None:
    _database_with_species(
        path,
        [
            ("Anna's Hummingbird", "Calypte anna"),
            ("Rufous Hummingbird", "Selasphorus rufus"),
            ("Elegant Trogon", "Trogon elegans"),
        ],
    )


def _selection(
    scientific_name: str,
    *,
    sha256: str,
    source_page_url: str,
) -> dict[str, object]:
    return {
        "decision": "selected",
        "reason": "live_bird_without_human_or_migration_map",
        "reviewed_at": "2026-08-03",
        "reviewed_by": "Rufous Reviewer",
        "scientific_name": scientific_name,
        "sha256": sha256,
        "source_page_urls": [source_page_url],
    }


def _ledger(
    path: Path,
    *,
    selected_name: str = "Calypte anna",
    include_inaturalist_selection: bool = False,
    include_wikimedia_selection: bool = False,
) -> None:
    payload = empty_approval_ledger()
    payload["selections"] = [
        _selection(
            selected_name,
            sha256="a" * 64,
            source_page_url="https://www.fws.gov/media/annas-hummingbird",
        )
    ]
    if include_inaturalist_selection:
        payload["selections"].append(
            _selection(
                "Selasphorus rufus",
                sha256="c" * 64,
                source_page_url="https://www.inaturalist.org/photos/12345",
            )
        )
        payload["selections"][-1]["source_page_urls"] = [
            "https://www.inaturalist.org/photos/12345",
            "https://www.inaturalist.org/photos/67890",
        ]
    if include_wikimedia_selection:
        payload["selections"].append(
            _selection(
                "Trogon elegans",
                sha256="d" * 64,
                source_page_url=("https://commons.wikimedia.org/wiki/File:Trogon_elegans.jpg"),
            )
        )
    payload["selections"] = sorted(
        payload["selections"],
        key=lambda item: (str(item["scientific_name"]).casefold(), str(item["sha256"])),
    )
    payload["species_exclusions"] = (
        []
        if include_wikimedia_selection
        else [
            {
                "candidates": [
                    {
                        "sha256": "b" * 64,
                        "source_page_urls": ["https://www.fws.gov/media/elegant-trogon"],
                    }
                ],
                "decision": "no_safe_image",
                "reason": "no_compliant_candidate",
                "reviewed_at": "2026-08-03",
                "reviewed_by": "Rufous Reviewer",
                "scientific_name": "Trogon elegans",
            }
        ]
    )
    path.write_bytes(canonical_approval_json(payload))


def _public_output(
    path: Path,
    *,
    mode: Literal["production", "synthetic"] = "production",
    include_rufous: bool = True,
    rufous_media: list[dict[str, object]] | None = None,
) -> None:
    species: list[dict[str, object]] = [
        {
            "species_code": "gbif-1",
            "common_name": "Anna's Hummingbird",
            "scientific_name": "Calypte anna",
            "taxonomic_category": "species",
            "family": {"common_name": None, "scientific_name": "Trochilidae"},
            "order_name": "Caprimulgiformes",
            "traits": {},
            "evidence": {
                "licensed_occurrence_count": 0,
                "latest_licensed_occurrence_at": None,
            },
            "media": [{"provider": "usfws"}],
        }
    ]
    if include_rufous:
        species.append(
            {
                "species_code": "gbif-2",
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
                "media": rufous_media or [],
            }
        )
    species.append(
        {
            "species_code": "gbif-3",
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
        }
    )
    records = PublicRecords(
        species=species,
        observations=[],
        places=[],
        attribution_items=[],
        rejected=Counter(),
        source_generated_at="2026-08-03T12:00:00+00:00",
    )
    assets = build_public_assets(
        records,
        mode=mode,
        gnis_sha256="d" * 64 if mode == "production" else None,
    )
    write_public_assets(path, assets)


def test_only_usfws_selected_species_are_removed_from_targets(tmp_path: Path) -> None:
    database = tmp_path / "warehouse.duckdb"
    approvals = tmp_path / "approvals.json"
    _database(database)
    _ledger(approvals)

    assert load_missing_public_species_targets(database, approvals) == [
        {
            "species_code": "gbif-2",
            "common_name": "Rufous Hummingbird",
            "scientific_name": "Selasphorus rufus",
        },
        {
            "species_code": "gbif-3",
            "common_name": "Elegant Trogon",
            "scientific_name": "Trogon elegans",
        },
    ]


def test_selected_inaturalist_species_is_not_rediscovered(tmp_path: Path) -> None:
    database = tmp_path / "warehouse.duckdb"
    approvals = tmp_path / "approvals.json"
    _database(database)
    _ledger(approvals, include_inaturalist_selection=True)

    assert load_missing_public_species_targets(database, approvals) == [
        {
            "species_code": "gbif-3",
            "common_name": "Elegant Trogon",
            "scientific_name": "Trogon elegans",
        },
    ]


def test_all_existing_provider_selections_stay_excluded_from_discovery(
    tmp_path: Path,
) -> None:
    selections = load_visual_approvals(PRODUCTION_APPROVALS)
    usfws_selections = {
        name: selection
        for name, selection in selections.items()
        if all(url.startswith("https://www.fws.gov/media/") for url in selection.source_page_urls)
    }
    inaturalist_selections = {
        name: selection
        for name, selection in selections.items()
        if all(
            url.startswith("https://www.inaturalist.org/photos/")
            for url in selection.source_page_urls
        )
    }
    wikimedia_selections = {
        name: selection
        for name, selection in selections.items()
        if all(
            url.startswith("https://commons.wikimedia.org/wiki/File:")
            for url in selection.source_page_urls
        )
    }
    assert len(usfws_selections) == 167
    assert len(inaturalist_selections) == 16
    assert len(wikimedia_selections) == 24
    assert len(selections) == 207
    assert "selasphorus rufus" in usfws_selections

    database = tmp_path / "warehouse.duckdb"
    _database_with_species(
        database,
        [
            (f"Selected fixture {index}", selection.scientific_name)
            for index, selection in enumerate(usfws_selections.values(), start=1)
        ]
        + [
            (f"Fallback fixture {index}", selection.scientific_name)
            for index, selection in enumerate(inaturalist_selections.values(), start=1)
        ]
        + [
            (f"Commons fixture {index}", selection.scientific_name)
            for index, selection in enumerate(wikimedia_selections.values(), start=1)
        ]
        + [("Unpictured Fixture Bird", "Fixturebird missingus")],
    )

    targets = load_missing_public_species_targets(database, PRODUCTION_APPROVALS)
    target_names = {item["scientific_name"].casefold() for item in targets}

    assert target_names == {"fixturebird missingus"}
    assert not target_names.intersection(usfws_selections)
    assert not target_names.intersection(inaturalist_selections)
    assert not target_names.intersection(wikimedia_selections)


def test_stale_selection_cannot_silently_change_the_missing_set(tmp_path: Path) -> None:
    database = tmp_path / "warehouse.duckdb"
    approvals = tmp_path / "approvals.json"
    _database(database)
    _ledger(approvals, selected_name="Cardinalis cardinalis")

    with pytest.raises(PublicExportError, match="outside the current public catalog"):
        load_missing_public_species_targets(database, approvals)


def test_media_delta_targets_only_selected_inaturalist_species(tmp_path: Path) -> None:
    public_output = tmp_path / "public"
    approvals = tmp_path / "approvals.json"
    _public_output(public_output)
    _ledger(approvals, include_inaturalist_selection=True)

    assert load_selected_public_species_targets(public_output, approvals) == [
        {
            "species_code": "gbif-2",
            "common_name": "Rufous Hummingbird",
            "scientific_name": "Selasphorus rufus",
        }
    ]


def test_media_delta_ignores_committed_wikimedia_selection(tmp_path: Path) -> None:
    public_output = tmp_path / "public"
    approvals = tmp_path / "approvals.json"
    _public_output(public_output)
    _ledger(
        approvals,
        include_inaturalist_selection=True,
        include_wikimedia_selection=True,
    )

    assert load_selected_public_species_targets(public_output, approvals) == [
        {
            "species_code": "gbif-2",
            "common_name": "Rufous Hummingbird",
            "scientific_name": "Selasphorus rufus",
        }
    ]


def test_media_delta_rejects_stale_selected_species(tmp_path: Path) -> None:
    public_output = tmp_path / "public"
    approvals = tmp_path / "approvals.json"
    _public_output(public_output, include_rufous=False)
    _ledger(approvals, include_inaturalist_selection=True)

    with pytest.raises(PublicExportError, match="outside the active public catalog"):
        load_selected_public_species_targets(public_output, approvals)


def test_media_delta_refuses_to_replace_existing_species_media(tmp_path: Path) -> None:
    public_output = tmp_path / "public"
    approvals = tmp_path / "approvals.json"
    _public_output(public_output, rufous_media=[{"provider": "usfws"}])
    _ledger(approvals, include_inaturalist_selection=True)

    with pytest.raises(PublicExportError, match="refuses to replace existing media"):
        load_selected_public_species_targets(public_output, approvals)


def test_media_delta_skips_exact_active_inaturalist_selection(tmp_path: Path) -> None:
    public_output = tmp_path / "public"
    approvals = tmp_path / "approvals.json"
    _public_output(
        public_output,
        rufous_media=[
            {
                "provider": "inaturalist",
                "sha256": "c" * 64,
                "source_url": "https://www.inaturalist.org/photos/12345",
            }
        ],
    )
    _ledger(approvals, include_inaturalist_selection=True)

    assert load_selected_public_species_targets(public_output, approvals) == []


def test_media_delta_zero_pending_targets_never_constructs_source(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    public_output = tmp_path / "public"
    approvals = tmp_path / "approvals.json"
    _public_output(
        public_output,
        rufous_media=[
            {
                "provider": "inaturalist",
                "sha256": "c" * 64,
                "source_url": "https://www.inaturalist.org/photos/12345",
            }
        ],
    )
    _ledger(approvals, include_inaturalist_selection=True)

    def unexpected_source(**_kwargs: object) -> object:
        pytest.fail("zero pending targets must not construct the iNaturalist source")

    monkeypatch.setattr(
        "databox.public_inaturalist_media_ingest.inaturalist_public_photo_source",
        unexpected_source,
    )

    result = ingest_public_inaturalist_media(
        tmp_path / "unused.duckdb",
        approvals,
        targets_from_public_output=public_output,
    )

    assert result.missing_species == 0
    assert result.exact_species == 0
    assert result.species_with_candidates == 0
    assert result.candidate_records == 0
    assert result.completed_runs == 0


def test_media_delta_rejects_nonproduction_snapshot(tmp_path: Path) -> None:
    public_output = tmp_path / "public"
    approvals = tmp_path / "approvals.json"
    _public_output(public_output, mode="synthetic")
    _ledger(approvals, include_inaturalist_selection=True)

    with pytest.raises(PublicExportError, match="requires a production public snapshot"):
        load_selected_public_species_targets(public_output, approvals)


def test_snapshot_validation_never_falls_back_to_an_older_complete_run(tmp_path: Path) -> None:
    database = tmp_path / "warehouse.duckdb"
    connection = duckdb.connect(str(database))
    connection.execute("CREATE SCHEMA raw_inaturalist")
    connection.execute(
        """CREATE TABLE raw_inaturalist.photo_discovery_runs (
          run_id VARCHAR,
          status VARCHAR,
          target_species_count BIGINT,
          exact_species_count BIGINT,
          species_with_candidates BIGINT,
          eligible_candidate_count BIGINT
        )"""
    )
    connection.execute("CREATE TABLE raw_inaturalist.photo_species_results (run_id VARCHAR)")
    connection.execute("CREATE TABLE raw_inaturalist.photo_candidates (run_id VARCHAR)")
    connection.execute(
        "INSERT INTO raw_inaturalist.photo_discovery_runs VALUES ('old', 'complete', 2, 2, 1, 1)"
    )
    connection.execute("INSERT INTO raw_inaturalist.photo_species_results VALUES ('old'), ('old')")
    connection.execute("INSERT INTO raw_inaturalist.photo_candidates VALUES ('old')")
    connection.close()

    with pytest.raises(PublicExportError, match="no exact complete snapshot"):
        _validate_ingested_snapshot(database, run_id="new", expected_target_count=2)


def test_snapshot_validation_requires_every_declared_candidate_row(tmp_path: Path) -> None:
    database = tmp_path / "warehouse.duckdb"
    connection = duckdb.connect(str(database))
    connection.execute("CREATE SCHEMA raw_inaturalist")
    connection.execute(
        """CREATE TABLE raw_inaturalist.photo_discovery_runs (
          run_id VARCHAR,
          status VARCHAR,
          target_species_count BIGINT,
          exact_species_count BIGINT,
          species_with_candidates BIGINT,
          eligible_candidate_count BIGINT
        )"""
    )
    connection.execute("CREATE TABLE raw_inaturalist.photo_species_results (run_id VARCHAR)")
    connection.execute("CREATE TABLE raw_inaturalist.photo_candidates (run_id VARCHAR)")
    connection.execute(
        "INSERT INTO raw_inaturalist.photo_discovery_runs VALUES ('new', 'complete', 2, 2, 1, 2)"
    )
    connection.execute("INSERT INTO raw_inaturalist.photo_species_results VALUES ('new'), ('new')")
    connection.execute("INSERT INTO raw_inaturalist.photo_candidates VALUES ('new')")
    connection.close()

    with pytest.raises(PublicExportError, match="incomplete snapshot"):
        _validate_ingested_snapshot(database, run_id="new", expected_target_count=2)
