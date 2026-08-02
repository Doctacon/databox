"""Static public export, source-boundary, and fail-closed license tests."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from unittest.mock import ANY

import duckdb
import pytest
from databox.public_export import (
    GBIF_EBIRD_EOD_DATASET_KEY,
    GBIF_EBIRD_EOD_DATASET_URL,
    PublicExportError,
    build_public_assets,
    canonical_license,
    export_public_data,
    load_gnis_places,
    records_from_database,
    write_public_assets,
)
from databox.public_export_audit import audit_public_site


@pytest.mark.parametrize(
    ("provider", "value", "expected"),
    [
        ("inaturalist", "CC0 1.0", "CC0 1.0"),
        ("inaturalist", "https://creativecommons.org/licenses/by/4.0/", "CC BY 4.0"),
        ("xeno_canto", "CC BY-SA 2.5", "CC BY-SA 2.5"),
        ("gbif", "http://creativecommons.org/publicdomain/zero/1.0/legalcode", "CC0 1.0"),
        ("gbif", "http://creativecommons.org/licenses/by/4.0/legalcode", "CC BY 4.0"),
    ],
)
def test_license_allowlist_accepts_only_normalized_public_families(
    provider: str, value: str, expected: str
) -> None:
    result = canonical_license(provider, value)
    assert result is not None
    assert result[0] == expected
    assert result[1].startswith("https://creativecommons.org/")


@pytest.mark.parametrize(
    ("provider", "value"),
    [
        ("inaturalist", "CC BY-NC 4.0"),
        ("inaturalist", "CC BY-ND 4.0"),
        ("xeno_canto", "CC BY-NC-SA 4.0"),
        ("xeno_canto", "CC BY-ND 4.0"),
        ("gbif", "CC BY-SA 4.0"),
        ("gbif", "all rights reserved"),
        ("gbif", ""),
        ("gbif", "https://evil.example/creativecommons.org/licenses/by/4.0/"),
        ("gbif", "license: https://creativecommons.org/licenses/by/4.0/"),
        ("gbif", "https://creativecommons.org/licenses/by/4.0/?unexpected=true"),
        ("unknown", "CC0 1.0"),
    ],
)
def test_license_allowlist_rejects_nc_nd_sa_for_gbif_and_missing(provider: str, value: str) -> None:
    assert canonical_license(provider, value) is None


def test_synthetic_export_is_offline_deterministic_and_complete(tmp_path: Path) -> None:
    output = tmp_path / "public"
    manifest = export_public_data(mode="synthetic", output_dir=output)

    assert manifest["mode"] == "public"
    assert manifest["release_mode"] == "synthetic"
    assert manifest["source_policy"] == {
        "direct_ebird": "excluded",
        "occurrence_source": "synthetic",
        "gbif_dataset_key": None,
        "coverage": "fictional_fixture",
        "required_taxon_key": None,
    }
    assert manifest["counts"] == {
        "species": 2,
        "observations": 2,
        "places": 2,
        "attribution_items": 0,
    }
    assert (output / "data/manifest.json").is_file()
    assert (output / "data/attribution.json").is_file()
    assert len(list((output / "data/species").glob("*.json"))) == 2
    assert list((output / "data/cells").glob("*.json"))
    assert list((output / "data/places").glob("*.json"))
    attribution = json.loads((output / "data/attribution.json").read_text(encoding="utf-8"))
    assert {source["provider"] for source in attribution["sources"]} == {
        "synthetic",
        "us_census_tigerweb",
    }

    second = export_public_data(mode="synthetic", output_dir=output)
    assert second["data_version"] == manifest["data_version"]


def _gnis_file(tmp_path: Path) -> tuple[Path, str]:
    source = tmp_path / "gnis.txt"
    source.write_text(
        "feature_id|feature_name|feature_class|state_name|prim_lat_dec|prim_long_dec\n"
        "1|Madera Canyon|Valley|Arizona|31.73|-110.88\n"
        "3|Northeast Arizona Place|Locale|Arizona|36.15|-109.54\n"
        "4|Rectangle Only|Locale|Arizona|31.50|-114.00\n"
        "2|Outside|Park|New Mexico|35.0|-106.0\n",
        encoding="utf-8-sig",
    )
    return source, hashlib.sha256(source.read_bytes()).hexdigest()


def test_gnis_loader_pins_hash_filters_state_and_adds_timezone(tmp_path: Path) -> None:
    source, checksum = _gnis_file(tmp_path)
    assert load_gnis_places(source, checksum) == [
        {
            "public_id": ANY,
            "name": "Madera Canyon",
            "kind": "place",
            "source": "usgs_gnis",
            "feature_class": "Valley",
            "is_historical": False,
            "latitude": 31.73,
            "longitude": -110.88,
            "timezone": "America/Phoenix",
            "timezone_source": "arizona_no_dst",
        },
        {
            "public_id": ANY,
            "name": "Northeast Arizona Place",
            "kind": "place",
            "source": "usgs_gnis",
            "feature_class": "Locale",
            "is_historical": False,
            "latitude": 36.15,
            "longitude": -109.54,
            "timezone": None,
            "timezone_source": "nws_or_visitor_required",
        },
    ]
    with pytest.raises(PublicExportError, match="does not match"):
        load_gnis_places(source, "0" * 64)


def _database(path: Path) -> None:
    connection = duckdb.connect(str(path))
    connection.execute("CREATE SCHEMA rufous_public")
    connection.execute(
        """CREATE TABLE rufous_public.gbif_eod_occurrence (
        source_id VARCHAR, gbif_key BIGINT, gbif_id VARCHAR, occurrence_id VARCHAR,
        dataset_key VARCHAR, dataset_title VARCHAR, dataset_publisher VARCHAR,
        dataset_citation VARCHAR, dataset_doi VARCHAR, dataset_source_url VARCHAR,
        dataset_license VARCHAR, scientific_name VARCHAR,
        accepted_scientific_name VARCHAR, common_name VARCHAR, taxon_rank VARCHAR,
        family VARCHAR, order_name VARCHAR, accepted_taxon_key BIGINT,
        taxon_key BIGINT, species_key BIGINT, event_date DATE, event_date_text VARCHAR,
        latitude DOUBLE, longitude DOUBLE, coordinate_uncertainty_in_meters DOUBLE,
        basis_of_record VARCHAR, occurrence_status VARCHAR, license VARCHAR,
        source_reference_url VARCHAR, loaded_at TIMESTAMPTZ,
        recorded_by VARCHAR, locality VARCHAR)"""
    )
    rows = [
        (
            "GBIF-SENSITIVE-ID",
            1,
            "gbif-id",
            "occurrence-id",
            GBIF_EBIRD_EOD_DATASET_KEY,
            "EOD – eBird Observation Dataset",
            "Cornell Lab of Ornithology",
            "Cornell Lab of Ornithology. EOD – eBird Observation Dataset.",
            "10.15468/aomfnb",
            GBIF_EBIRD_EOD_DATASET_URL,
            "CC BY 4.0",
            "Selasphorus rufus (J.F.Gmelin, 1788)",
            "Selasphorus rufus",
            "Rufous Hummingbird",
            "SPECIES",
            "Trochilidae",
            "Caprimulgiformes",
            2476855,
            2476855,
            2476855,
            "2026-01-14",
            "2026-01-14",
            33.4012,
            -112.1034,
            20.0,
            "HUMAN_OBSERVATION",
            "PRESENT",
            "CC BY 4.0",
            "https://www.gbif.org/occurrence/1",
            "2026-01-15 14:12:00+00",
            "Example Observer",
            "Rare nest behind 123 Example Street",
        ),
        (
            "OTHER-DATASET-ID",
            2,
            "gbif-id-2",
            "occurrence-id-2",
            "not-the-eod-dataset",
            "Other Dataset",
            "Other Publisher",
            "Other citation",
            "10.0000/other",
            "https://www.gbif.org/dataset/not-eod",
            "CC0 1.0",
            "Calypte anna",
            "Calypte anna",
            "Anna's Hummingbird",
            "SPECIES",
            "Trochilidae",
            "Caprimulgiformes",
            2476674,
            2476674,
            2476674,
            "2026-01-13",
            "2026-01-13",
            33.4,
            -112.1,
            20.0,
            "HUMAN_OBSERVATION",
            "PRESENT",
            "CC0 1.0",
            "https://www.gbif.org/occurrence/2",
            "2026-01-15 14:12:00+00",
            "Another Observer",
            "Another private-looking locality",
        ),
    ]
    connection.executemany(
        "INSERT INTO rufous_public.gbif_eod_occurrence VALUES "
        "(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        rows,
    )

    # These direct eBird relations and their sensitive values must be irrelevant
    # to the public projection even if the private warehouse contains them.
    connection.execute("CREATE SCHEMA birding_agent")
    connection.execute("CREATE TABLE birding_agent.recent_observation_evidence (secret VARCHAR)")
    connection.execute(
        "INSERT INTO birding_agent.recent_observation_evidence VALUES ('DIRECT-EBIRD-SECRET')"
    )
    connection.execute("CREATE SCHEMA environmental_observations")
    connection.execute("CREATE TABLE environmental_observations.dim_bird_hotspot (secret VARCHAR)")
    connection.execute(
        "INSERT INTO environmental_observations.dim_bird_hotspot VALUES ('PRIVATE-HOTSPOT')"
    )
    connection.close()


def _gnis_places() -> list[dict[str, object]]:
    return [
        {
            "public_id": "gnis-public",
            "name": "Madera Canyon",
            "kind": "place",
            "source": "usgs_gnis",
            "feature_class": "Valley",
            "is_historical": False,
            "latitude": 31.73,
            "longitude": -110.88,
            "timezone": "America/Phoenix",
            "timezone_source": "arizona_no_dst",
        }
    ]


def test_database_projection_is_gbif_eod_only_and_strips_personal_values(
    tmp_path: Path,
) -> None:
    database = tmp_path / "source.duckdb"
    _database(database)

    records = records_from_database(database, _gnis_places())

    assert records.rejected == {"gbif_non_eod_dataset": 1}
    assert len(records.observations) == 1
    assert records.places == _gnis_places()
    observation = records.observations[0]
    assert observation["species_code"] == "gbif-2476855"
    assert observation["source"] == "gbif"
    assert observation["location"] == {
        "name": "Generalized Arizona occurrence",
        "latitude": 33.4,
        "longitude": -112.1,
        "kind": "generalized",
        "timezone": "America/Phoenix",
        "timezone_source": "arizona_no_dst",
    }
    assert records.species == [
        {
            "species_code": "gbif-2476855",
            "common_name": "Rufous Hummingbird",
            "scientific_name": "Selasphorus rufus",
            "taxonomic_category": "SPECIES",
            "family": {"common_name": None, "scientific_name": "Trochilidae"},
            "order_name": "Caprimulgiformes",
            "traits": {},
            "evidence": {
                "licensed_occurrence_count": 1,
                "latest_licensed_occurrence_at": "2026-01-14",
            },
            "media": [],
        }
    ]
    assert records.attribution_items == [
        {
            "attribution_id": ANY,
            "provider": "gbif",
            "creator": "Cornell Lab of Ornithology",
            "source_url": GBIF_EBIRD_EOD_DATASET_URL,
            "license": "CC BY 4.0",
            "license_url": "https://creativecommons.org/licenses/by/4.0/",
            "dataset_title": "EOD – eBird Observation Dataset",
            "dataset_key": GBIF_EBIRD_EOD_DATASET_KEY,
            "publisher": "Cornell Lab of Ornithology",
            "dataset_citation": "Cornell Lab of Ornithology. EOD – eBird Observation Dataset.",
            "dataset_doi": "10.15468/aomfnb",
        }
    ]

    assets = build_public_assets(
        records,
        mode="production",
        gnis_sha256="a" * 64,
    )
    assert assets["data/manifest.json"]["source_policy"] == {
        "direct_ebird": "excluded",
        "occurrence_source": "gbif",
        "gbif_dataset_key": GBIF_EBIRD_EOD_DATASET_KEY,
        "coverage": "bounded_sample",
        "required_taxon_key": 2476855,
    }
    eod_source = next(
        source
        for source in assets["data/attribution.json"]["sources"]
        if source["provider"] == "gbif_ebird_eod"
    )
    assert "selected Arizona records" in eod_source["modifications"]
    assert "rounded coordinates to 0.01°" in eod_source["modifications"]
    assert eod_source["disclaimer"] == (
        "No warranty either expressed or implied is made regarding the accuracy of these data."
    )
    encoded = json.dumps(assets)
    legacy_raw_identifier = hashlib.sha256(
        b"rufous-public-v1|gbif-eod-observation|GBIF-SENSITIVE-ID"
    ).hexdigest()[:24]
    assert legacy_raw_identifier not in encoded
    for forbidden in (
        "GBIF-SENSITIVE-ID",
        "OTHER-DATASET-ID",
        "Example Observer",
        "Rare nest",
        "DIRECT-EBIRD-SECRET",
        "PRIVATE-HOTSPOT",
        "source_record_id",
        "ebird.org/checklist",
    ):
        assert forbidden not in encoded

    public_id = str(observation["public_id"])
    connection = duckdb.connect(str(database))
    connection.execute(
        "UPDATE rufous_public.gbif_eod_occurrence SET source_id='RELABELED-RAW-ID' "
        "WHERE dataset_key=?",
        [GBIF_EBIRD_EOD_DATASET_KEY],
    )
    connection.close()
    relabeled = records_from_database(database, _gnis_places())
    assert relabeled.observations[0]["public_id"] == public_id


def test_production_export_needs_no_cornell_approval_environment(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    for name in (
        "EBIRD_PUBLIC_USE_APPROVED",
        "EBIRD_PUBLIC_USE_APPROVAL_REFERENCE",
        "EBIRD_PUBLIC_USE_APPROVAL_TERMS",
    ):
        monkeypatch.delenv(name, raising=False)
    database = tmp_path / "source.duckdb"
    _database(database)
    gnis, checksum = _gnis_file(tmp_path)

    manifest = export_public_data(
        mode="production",
        output_dir=tmp_path / "public",
        database_path=database,
        gnis_path=gnis,
        gnis_sha256=checksum,
    )

    assert manifest["release_mode"] == "production"
    assert manifest["counts"]["observations"] == 1
    assert manifest["source_policy"]["direct_ebird"] == "excluded"
    assert audit_public_site(tmp_path / "public") == []


def test_production_audit_rejects_more_specific_occurrence_details(tmp_path: Path) -> None:
    database = tmp_path / "source.duckdb"
    _database(database)
    gnis, checksum = _gnis_file(tmp_path)
    output = tmp_path / "public"
    manifest = export_public_data(
        mode="production",
        output_dir=output,
        database_path=database,
        gnis_path=gnis,
        gnis_sha256=checksum,
    )
    cell_path = output / str(manifest["cells"][0]["path"]).removeprefix("/")
    cell = json.loads(cell_path.read_text(encoding="utf-8"))
    observation = cell["observations"][0]
    observation["observed_at"] = "2026-01-14T12:34:56-07:00"
    observation["count"] = 7
    observation["count_display"] = "7 birds"
    observation["is_notable"] = True
    observation["location"].update(
        {
            "name": "Specific backyard",
            "kind": "site",
            "latitude": 33.4012,
            "longitude": -112.1034,
        }
    )
    cell_path.write_text(json.dumps(cell), encoding="utf-8")

    findings = audit_public_site(output)

    assert any("day-level observation date" in item for item in findings)
    assert any("source occurrence count" in item for item in findings)
    assert any("source notability" in item for item in findings)
    assert any("generalized production location label" in item for item in findings)
    assert sum("rounded to 0.01 degrees" in item for item in findings) == 2


def test_gbif_projection_fails_closed_on_license_and_attribution(tmp_path: Path) -> None:
    database = tmp_path / "source.duckdb"
    _database(database)
    connection = duckdb.connect(str(database))
    connection.execute(
        "UPDATE rufous_public.gbif_eod_occurrence SET license='CC BY-NC 4.0' WHERE dataset_key=?",
        [GBIF_EBIRD_EOD_DATASET_KEY],
    )
    connection.close()

    records = records_from_database(database, _gnis_places())

    assert records.observations == []
    assert records.species == []
    assert records.rejected == {"gbif_license": 1, "gbif_non_eod_dataset": 1}


def test_database_projection_rejects_non_gnis_place_input(tmp_path: Path) -> None:
    database = tmp_path / "source.duckdb"
    _database(database)
    place = _gnis_places()[0] | {"source": "ebird_hotspot", "kind": "hotspot"}

    with pytest.raises(PublicExportError, match="only GNIS places"):
        records_from_database(database, [place])


def test_write_refuses_broad_output_directory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    with pytest.raises(PublicExportError, match="unsafe"):
        write_public_assets(tmp_path, {"data/manifest.json": {}})
