"""Static public export, source-boundary, and fail-closed license tests."""

from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path
from unittest.mock import ANY

import databox.public_export as public_export
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
    load_public_media_manifest,
    records_from_database,
    write_public_assets,
)
from databox.public_export_audit import audit_public_site
from databox.public_media_approval import SELECTION_REASON, canonical_approval_json


@pytest.mark.parametrize(
    ("provider", "value", "expected"),
    [
        ("inaturalist", "CC0 1.0", "CC0 1.0"),
        ("inaturalist", "https://creativecommons.org/licenses/by/4.0/", "CC BY 4.0"),
        ("inaturalist", "CC BY-SA 4.0", "CC BY-SA 4.0"),
        ("xeno_canto", "CC BY-SA 2.5", "CC BY-SA 2.5"),
        ("gbif", "http://creativecommons.org/publicdomain/zero/1.0/legalcode", "CC0 1.0"),
        ("gbif", "http://creativecommons.org/licenses/by/4.0/legalcode", "CC BY 4.0"),
        ("usfws", "Public Domain", "Public Domain"),
        ("usfws", "CC BY-SA 4.0", "CC BY-SA 4.0"),
    ],
)
def test_license_allowlist_accepts_only_normalized_public_families(
    provider: str, value: str, expected: str
) -> None:
    result = canonical_license(provider, value)
    assert result is not None
    assert result[0] == expected
    expected_origin = (
        "https://www.fws.gov/notices"
        if expected == "Public Domain"
        else "https://creativecommons.org/"
    )
    assert result[1].startswith(expected_origin)


@pytest.mark.parametrize(
    ("provider", "value"),
    [
        ("inaturalist", "CC BY-NC 4.0"),
        ("inaturalist", "CC BY-ND 4.0"),
        ("inaturalist", "CC BY 3.0"),
        ("inaturalist", "CC BY-SA 3.0"),
        ("xeno_canto", "CC BY-NC-SA 4.0"),
        ("xeno_canto", "CC BY-ND 4.0"),
        ("gbif", "CC BY-SA 4.0"),
        ("gbif", "all rights reserved"),
        ("gbif", ""),
        ("gbif", "https://evil.example/creativecommons.org/licenses/by/4.0/"),
        ("gbif", "license: https://creativecommons.org/licenses/by/4.0/"),
        ("gbif", "https://creativecommons.org/licenses/by/4.0/?unexpected=true"),
        ("usfws", "CC BY-NC 4.0"),
        ("usfws", "CC BY-ND 4.0"),
        ("usfws", "public domain"),
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
        "media_source": "none",
        "media_delivery": "none",
        "audio_source": "none",
        "audio_delivery": "none",
    }
    assert manifest["counts"] == {
        "species": 2,
        "observations": 2,
        "places": 2,
        "attribution_items": 0,
        "media_items": 0,
        "species_with_media": 0,
        "audio_items": 0,
        "species_with_audio": 0,
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


def test_manifest_and_attribution_represent_mixed_public_media_providers() -> None:
    records = public_export.synthetic_records()
    records.species[0]["media"] = [{"provider": "usfws"}]
    records.species[1]["media"] = [{"provider": "inaturalist"}]

    assets = build_public_assets(records, mode="synthetic", gnis_sha256=None)

    assert assets["data/manifest.json"]["source_policy"]["media_source"] == ("usfws+inaturalist")
    assert assets["data/manifest.json"]["source_policy"]["media_delivery"] == "immutable_r2"
    assert {source["provider"] for source in assets["data/attribution.json"]["sources"]} == {
        "synthetic",
        "us_census_tigerweb",
        "usfws",
        "inaturalist",
    }


def test_manifest_rejects_an_unreviewed_media_provider() -> None:
    records = public_export.synthetic_records()
    records.species[0]["media"] = [{"provider": "wikimedia_commons"}]

    with pytest.raises(PublicExportError, match="unsupported public provider"):
        build_public_assets(records, mode="synthetic", gnis_sha256=None)


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
            "Selasphorus rufus",
            "Selasphorus rufus (J.F.Gmelin, 1788)",
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
    connection.execute(
        """INSERT INTO rufous_public.gbif_eod_occurrence (
          source_id, gbif_key, gbif_id, occurrence_id, dataset_key, dataset_title,
          dataset_publisher, dataset_citation, dataset_doi, dataset_source_url,
          dataset_license, scientific_name, accepted_scientific_name, common_name,
          taxon_rank, family, order_name, accepted_taxon_key, taxon_key, event_date,
          event_date_text, latitude, longitude, occurrence_status, license, loaded_at
        ) VALUES
          ('GENUS-COOPERS', 3, 'gbif-id-3', 'occurrence-id-3',
           ?, 'EOD – eBird Observation Dataset', 'Cornell Lab of Ornithology',
           'Cornell Lab of Ornithology. EOD – eBird Observation Dataset.',
           '10.15468/aomfnb', ?, 'CC BY 4.0',
           'Astur Lacepède, 1799', 'Astur Lacepède, 1799', 'Cooper''s Hawk',
           'GENUS', 'Accipitridae', 'Accipitriformes', 3242735, 3242735,
           '2026-01-12', '2026-01-12', 33.4, -112.1, 'PRESENT', 'CC BY 4.0',
           '2026-01-15 14:12:00+00'),
          ('GENUS-MOUNTAIN-PLOVER', 4, 'gbif-id-4', 'occurrence-id-4',
           ?, 'EOD – eBird Observation Dataset', 'Cornell Lab of Ornithology',
           'Cornell Lab of Ornithology. EOD – eBird Observation Dataset.',
           '10.15468/aomfnb', ?, 'CC BY 4.0',
           'Anarhynchus Quoy & Gaimard, 1832', 'Anarhynchus Quoy & Gaimard, 1832',
           'Mountain Plover', 'GENUS', 'Charadriidae', 'Charadriiformes',
           2480251, 2480251, '2026-01-11', '2026-01-11', 33.4, -112.1,
           'PRESENT', 'CC BY 4.0', '2026-01-15 14:12:00+00')""",
        [
            GBIF_EBIRD_EOD_DATASET_KEY,
            GBIF_EBIRD_EOD_DATASET_URL,
            GBIF_EBIRD_EOD_DATASET_KEY,
            GBIF_EBIRD_EOD_DATASET_URL,
        ],
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


def _media_manifest(tmp_path: Path) -> Path:
    digest = "d" * 64
    path = tmp_path / "media-manifest.json"
    path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "mode": "rufous-media-preparation",
                "generated_at": "2026-08-03T00:00:00Z",
                "items": [
                    {
                        "species_code": "rufhum",
                        "common_name": "Rufous Hummingbird",
                        "scientific_name": "Selasphorus rufus",
                        "media_id": "usfws-" + "a" * 24,
                        "source_page_url": "https://www.fws.gov/media/rufous-hummingbird-5",
                        "source_image_url": ("https://www.fws.gov/sites/default/files/rufous.jpg"),
                        "creator": "Tom Koerner/USFWS",
                        "license": "Public Domain",
                        "license_url": "https://www.fws.gov/notices",
                        "title": "Rufous Hummingbird in flight",
                        "caption": "An adult Rufous Hummingbird.",
                        "alt_text": "A Rufous Hummingbird hovering beside flowers.",
                        "width": 650,
                        "height": 433,
                        "mime_type": "image/webp",
                        "sha256": digest,
                        "url": (
                            "https://rufous-data.loughondata.com/rufous-media/v1/objects/"
                            f"{digest[:2]}/{digest}.webp"
                        ),
                        "attribution_id": "usfws-attribution-" + "b" * 24,
                        "hero_score": 42.0,
                    }
                ],
                "counts": {"items": 1, "objects": 1, "species": 1},
            }
        ),
        encoding="utf-8",
    )
    return path


def _media_approvals(tmp_path: Path, manifest_path: Path) -> Path:
    item = json.loads(manifest_path.read_text(encoding="utf-8"))["items"][0]
    path = tmp_path / "media-approvals.json"
    path.write_bytes(
        canonical_approval_json(
            {
                "schema_version": 2,
                "mode": "rufous-media-human-species-selections",
                "review_policy": "one-live-bird-image-per-species-v1",
                "rejections": [],
                "species_exclusions": [],
                "selections": [
                    {
                        "sha256": item["sha256"],
                        "decision": "selected",
                        "reason": SELECTION_REASON,
                        "reviewed_at": "2026-08-03",
                        "reviewed_by": "Test Human",
                        "scientific_name": item["scientific_name"],
                        "source_page_urls": [item["source_page_url"]],
                    }
                ],
            }
        )
    )
    return path


def _inaturalist_media_manifest(tmp_path: Path) -> Path:
    path = _media_manifest(tmp_path)
    payload = json.loads(path.read_text(encoding="utf-8"))
    item = payload["items"][0]
    item.update(
        {
            "provider": "inaturalist",
            "media_id": "inaturalist-123456789",
            "source_page_url": "https://www.inaturalist.org/photos/123456789",
            "source_image_url": (
                "https://inaturalist-open-data.s3.amazonaws.com/photos/123456789/large.jpg"
            ),
            "creator": "Jane Naturalist",
            "license": "CC BY-SA 4.0",
            "license_url": "https://creativecommons.org/licenses/by-sa/4.0/",
            "attribution_id": "inaturalist-attribution-123456789",
        }
    )
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def test_media_manifest_exports_only_audited_public_fields(tmp_path: Path) -> None:
    path = _media_manifest(tmp_path)

    items = load_public_media_manifest(path)["selasphorus rufus"]

    assert len(items) == 1
    assert items[0]["provider"] == "usfws"
    assert items[0]["license"] == "Public Domain"
    assert items[0]["license_url"] == "https://www.fws.gov/notices"
    assert items[0]["url"].endswith(".webp")
    assert "source_image_url" not in items[0]
    assert "hero_score" not in items[0]


def test_inaturalist_media_manifest_exports_deterministic_photo_identity(
    tmp_path: Path,
) -> None:
    path = _inaturalist_media_manifest(tmp_path)

    items = load_public_media_manifest(path)["selasphorus rufus"]

    assert len(items) == 1
    item = items[0]
    assert item["provider"] == "inaturalist"
    assert item["media_id"] == "inaturalist-123456789"
    assert item["source_url"] == "https://www.inaturalist.org/photos/123456789"
    assert item["creator"] == "Jane Naturalist"
    assert item["license"] == "CC BY-SA 4.0"
    assert item["license_url"] == "https://creativecommons.org/licenses/by-sa/4.0/"
    assert item["attribution_id"] == "inaturalist-attribution-123456789"
    assert "source_image_url" not in item


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("source_page_url", "https://www.inaturalist.org/photos/0"),
        ("source_page_url", "https://www.inaturalist.org/photos/123456789/"),
        ("source_page_url", "https://www.inaturalist.org/photos/123456789?size=large"),
        ("media_id", "inaturalist-987654321"),
        ("attribution_id", "inaturalist-attribution-987654321"),
        ("license", "CC BY 3.0"),
    ],
)
def test_inaturalist_media_manifest_fails_closed_on_nonexact_photo_contract(
    tmp_path: Path,
    field: str,
    value: str,
) -> None:
    path = _inaturalist_media_manifest(tmp_path)
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["items"][0][field] = value
    path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(PublicExportError, match="fails the public contract"):
        load_public_media_manifest(path)


def test_selected_public_projection_contains_only_one_image_per_species(
    tmp_path: Path,
) -> None:
    path = _media_manifest(tmp_path)
    payload = json.loads(path.read_text(encoding="utf-8"))
    selected = payload["items"][0]
    unselected = {
        **selected,
        "media_id": "usfws-" + "c" * 24,
        "attribution_id": "usfws-attribution-" + "d" * 24,
        "source_page_url": "https://www.fws.gov/media/rufous-hummingbird-higher-score",
        "sha256": "e" * 64,
        "url": (f"https://rufous-data.loughondata.com/rufous-media/v1/objects/ee/{'e' * 64}.webp"),
        "hero_score": 999.0,
    }
    payload["items"].append(unselected)
    payload["counts"].update(items=2, objects=2)
    path.write_text(json.dumps(payload), encoding="utf-8")

    projected = load_public_media_manifest(
        path,
        selected_sha256_by_species={"selasphorus rufus": selected["sha256"]},
    )

    assert [item["sha256"] for item in projected["selasphorus rufus"]] == [selected["sha256"]]


def test_explicit_no_safe_image_species_projects_to_silhouette_fallback(
    tmp_path: Path,
) -> None:
    path = _media_manifest(tmp_path)

    projected = load_public_media_manifest(
        path,
        selected_sha256_by_species={},
        excluded_species=frozenset({"selasphorus rufus"}),
    )

    assert projected == {}


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("license", "CC BY-NC 4.0"),
        ("creator", "Rufous Hummingbird"),
        ("scientific_name", "Not the same bird"),
        ("source_page_url", "https://evil.example/media/rufous-hummingbird"),
        ("source_page_url", "https://www.fws.gov/media/rufous-hummingbird-"),
        ("url", "https://example.r2.dev/photo.webp"),
        ("mime_type", "image/jpeg"),
        ("width", 651),
    ],
)
def test_media_manifest_fails_closed_on_unsafe_metadata(
    tmp_path: Path, field: str, value: object
) -> None:
    path = _media_manifest(tmp_path)
    payload = json.loads(path.read_text())
    payload["items"][0][field] = value
    path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(PublicExportError, match="fails the public contract"):
        load_public_media_manifest(path)


def test_database_projection_prefers_clean_species_over_accepted_name_authority(
    tmp_path: Path,
) -> None:
    database = tmp_path / "source.duckdb"
    _database(database)

    records = records_from_database(database, _gnis_places())

    assert records.species[0]["scientific_name"] == "Selasphorus rufus"


def test_database_projection_rejects_live_shaped_genus_rank_species_labels(
    tmp_path: Path,
) -> None:
    database = tmp_path / "source.duckdb"
    _database(database)

    records = records_from_database(database, _gnis_places())

    assert records.rejected["gbif_non_species_taxon"] == 2
    encoded = json.dumps(records.species)
    assert "Astur Lacepède" not in encoded
    assert "Anarhynchus Quoy & Gaimard" not in encoded
    assert "Selasphorus rufus" in encoded


def test_database_projection_is_gbif_eod_only_and_strips_personal_values(
    tmp_path: Path,
) -> None:
    database = tmp_path / "source.duckdb"
    _database(database)

    records = records_from_database(database, _gnis_places())

    assert records.rejected == {
        "gbif_non_eod_dataset": 1,
        "gbif_non_species_taxon": 2,
    }
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
        "media_source": "none",
        "media_delivery": "none",
        "audio_source": "none",
        "audio_delivery": "none",
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
    media_manifest = _media_manifest(tmp_path)

    manifest = export_public_data(
        mode="production",
        output_dir=tmp_path / "public",
        database_path=database,
        gnis_path=gnis,
        gnis_sha256=checksum,
        media_manifest_path=media_manifest,
        media_approvals_path=_media_approvals(tmp_path, media_manifest),
    )

    assert manifest["release_mode"] == "production"
    assert manifest["counts"]["observations"] == 1
    assert manifest["source_policy"]["direct_ebird"] == "excluded"
    assert audit_public_site(tmp_path / "public") == []


def test_production_export_requires_committed_human_media_approval(tmp_path: Path) -> None:
    database = tmp_path / "source.duckdb"
    _database(database)
    gnis, checksum = _gnis_file(tmp_path)
    media_manifest = _media_manifest(tmp_path)

    with pytest.raises(PublicExportError, match="--media-approvals"):
        export_public_data(
            mode="production",
            output_dir=tmp_path / "missing-approval",
            database_path=database,
            gnis_path=gnis,
            gnis_sha256=checksum,
            media_manifest_path=media_manifest,
        )

    empty_approvals = tmp_path / "empty-approvals.json"
    empty_approvals.write_bytes(
        canonical_approval_json(
            {
                "schema_version": 2,
                "mode": "rufous-media-human-species-selections",
                "review_policy": "one-live-bird-image-per-species-v1",
                "rejections": [],
                "species_exclusions": [],
                "selections": [],
            }
        )
    )
    with pytest.raises(PublicExportError, match="lack a committed human image selection"):
        export_public_data(
            mode="production",
            output_dir=tmp_path / "unapproved",
            database_path=database,
            gnis_path=gnis,
            gnis_sha256=checksum,
            media_manifest_path=media_manifest,
            media_approvals_path=empty_approvals,
        )


def test_production_export_refuses_to_drop_a_pinned_approved_media_species(
    tmp_path: Path,
) -> None:
    database = tmp_path / "source.duckdb"
    _database(database)
    gnis, checksum = _gnis_file(tmp_path)
    media_manifest = _media_manifest(tmp_path)
    approvals = json.loads(_media_approvals(tmp_path, media_manifest).read_text(encoding="utf-8"))
    manifest_payload = json.loads(media_manifest.read_text(encoding="utf-8"))
    existing = manifest_payload["items"][0]
    missing_digest = "e" * 64
    missing = {
        **existing,
        "species_code": "absent",
        "common_name": "Absent Bird",
        "scientific_name": "Avis absentia",
        "media_id": "usfws-" + "c" * 24,
        "source_page_url": "https://www.fws.gov/media/absent-bird",
        "title": "Absent Bird perched safely",
        "sha256": missing_digest,
        "url": (
            "https://rufous-data.loughondata.com/rufous-media/v1/objects/"
            f"{missing_digest[:2]}/{missing_digest}.webp"
        ),
        "attribution_id": "usfws-attribution-" + "d" * 24,
    }
    manifest_payload["items"].append(missing)
    manifest_payload["counts"] = {"items": 2, "objects": 2, "species": 2}
    media_manifest.write_text(json.dumps(manifest_payload), encoding="utf-8")

    approvals["selections"].append(
        {
            "sha256": missing_digest,
            "decision": "selected",
            "reason": SELECTION_REASON,
            "reviewed_at": "2026-08-03",
            "reviewed_by": "Test Human",
            "scientific_name": "Avis absentia",
            "source_page_urls": ["https://www.fws.gov/media/absent-bird"],
        }
    )
    approvals["selections"].sort(
        key=lambda item: (item["scientific_name"].casefold(), item["sha256"])
    )
    approval_path = tmp_path / "pinned-approvals.json"
    approval_path.write_bytes(canonical_approval_json(approvals))

    with pytest.raises(PublicExportError, match="every pinned approved media species"):
        export_public_data(
            mode="production",
            output_dir=tmp_path / "missing-pinned-species",
            database_path=database,
            gnis_path=gnis,
            gnis_sha256=checksum,
            media_manifest_path=media_manifest,
            media_approvals_path=approval_path,
        )


def test_production_audit_rejects_more_specific_occurrence_details(tmp_path: Path) -> None:
    database = tmp_path / "source.duckdb"
    _database(database)
    gnis, checksum = _gnis_file(tmp_path)
    output = tmp_path / "public"
    media_manifest = _media_manifest(tmp_path)
    manifest = export_public_data(
        mode="production",
        output_dir=output,
        database_path=database,
        gnis_path=gnis,
        gnis_sha256=checksum,
        media_manifest_path=media_manifest,
        media_approvals_path=_media_approvals(tmp_path, media_manifest),
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
    assert records.rejected == {
        "gbif_license": 1,
        "gbif_non_eod_dataset": 1,
        "gbif_non_species_taxon": 2,
    }


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


def test_public_export_never_replaces_an_arbitrary_nonempty_directory(tmp_path: Path) -> None:
    output = tmp_path / "public"
    output.mkdir()
    sentinel = output / "personal-notes.txt"
    sentinel.write_text("keep me", encoding="utf-8")

    with pytest.raises(PublicExportError, match="valid Rufous public manifest"):
        export_public_data(mode="synthetic", output_dir=output)

    assert sentinel.read_text(encoding="utf-8") == "keep me"
    assert list(output.iterdir()) == [sentinel]


def test_public_export_rejects_a_symbolic_link_output(tmp_path: Path) -> None:
    target = tmp_path / "site"
    target.mkdir()
    sentinel = target / "index.html"
    sentinel.write_text("keep me", encoding="utf-8")
    output = tmp_path / "public"
    output.symlink_to(target, target_is_directory=True)

    with pytest.raises(PublicExportError, match="symbolic link"):
        export_public_data(mode="synthetic", output_dir=output)

    assert output.is_symlink()
    assert sentinel.read_text(encoding="utf-8") == "keep me"


def test_public_export_allows_an_empty_existing_directory(tmp_path: Path) -> None:
    output = tmp_path / "public"
    output.mkdir()

    manifest = export_public_data(mode="synthetic", output_dir=output)

    assert manifest["mode"] == "public"
    assert (output / "data" / "manifest.json").is_file()


def test_public_export_never_replaces_a_tree_with_unmanifested_content(tmp_path: Path) -> None:
    output = tmp_path / "public"
    export_public_data(mode="synthetic", output_dir=output)
    extra = output / "unrelated.txt"
    extra.write_text("do not delete", encoding="utf-8")

    with pytest.raises(PublicExportError, match="exact manifest"):
        export_public_data(mode="synthetic", output_dir=output)

    assert extra.read_text(encoding="utf-8") == "do not delete"


def test_failed_public_tree_install_restores_last_good_output(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    output = tmp_path / "public"
    export_public_data(mode="synthetic", output_dir=output)
    before = {
        path.relative_to(output): path.read_bytes() for path in output.rglob("*") if path.is_file()
    }
    stage = tmp_path / "replacement-stage"
    shutil.copytree(output, stage)
    expected = public_export._validate_public_output_target(output)
    real_replace = public_export.os.replace

    def fail_install(source: object, destination: object) -> None:
        if Path(source) == stage and Path(destination) == output:
            raise OSError("simulated interrupted install")
        real_replace(source, destination)

    monkeypatch.setattr(public_export.os, "replace", fail_install)

    with pytest.raises(PublicExportError, match="atomically publish"):
        public_export._publish_public_tree(stage, output, expected=expected)

    assert {
        path.relative_to(output): path.read_bytes() for path in output.rglob("*") if path.is_file()
    } == before
    assert stage.is_dir()
    assert not list(tmp_path.glob(".public.backup-*"))
