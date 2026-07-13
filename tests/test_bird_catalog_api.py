"""Read-only Arizona bird catalog API contract and privacy tests."""

from __future__ import annotations

import hashlib
import json
import socket
from pathlib import Path

import duckdb
import pytest
from databox.api import _BIRD_PROFILE_COLUMNS, BirdCatalogSummaryResponse, create_app
from databox.catalog_media import run_catalog_media_batch
from databox.curated_photo import INATURALIST_V1_TAXON, INATURALIST_V2_TAXA
from fastapi.testclient import TestClient
from pydantic import ValidationError

_COLUMNS = [column.strip() for column in _BIRD_PROFILE_COLUMNS.split(",")]
_DOUBLE_COLUMNS = {
    "taxonomic_order",
    "beak_length_culmen_mm",
    "beak_length_nares_mm",
    "beak_width_mm",
    "beak_depth_mm",
    "tarsus_length_mm",
    "wing_length_mm",
    "kipps_distance_mm",
    "secondary_length_mm",
    "hand_wing_index",
    "tail_length_mm",
    "mass_g",
}
_INTEGER_COLUMNS = {
    "extinct_year",
    "total_individuals",
    "female_individuals",
    "male_individuals",
    "unknown_sex_individuals",
    "complete_measures",
    "habitat_density_code",
    "migration_code",
    "source_file_id",
    "recent_public_observation_count",
    "public_location_count",
    "recent_public_notable_count",
    "gbif_occurrence_count",
    "xeno_canto_recording_count",
}
_BOOLEAN_COLUMNS = {"extinct", "inference"}
_TIMESTAMP_COLUMNS = {
    "latest_public_observation_at",
    "avonet_loaded_at",
    "species_list_loaded_at",
    "taxonomy_loaded_at",
    "ebird_observations_loaded_at",
    "gbif_loaded_at",
    "xeno_canto_loaded_at",
    "catalog_freshness_at",
}
_DATE_COLUMNS = {"gbif_latest_event_date", "xeno_canto_latest_recording_date"}


def _column_type(column: str) -> str:
    if column in _DOUBLE_COLUMNS:
        return "DOUBLE"
    if column in _INTEGER_COLUMNS:
        return "BIGINT"
    if column in _BOOLEAN_COLUMNS:
        return "BOOLEAN"
    if column in _TIMESTAMP_COLUMNS:
        return "TIMESTAMP"
    if column in _DATE_COLUMNS:
        return "DATE"
    return "VARCHAR"


def _base_row(index: int) -> dict[str, object]:
    row: dict[str, object] = dict.fromkeys(_COLUMNS)
    row.update(
        {
            "species_code": f"bird{index:03d}",
            "common_name": f"Arizona Bird {index:03d}",
            "scientific_name": f"Avis arizona{index:03d}",
            "taxonomic_category": "species" if index < 624 else "hybrid",
            "taxonomic_order": float(index),
            "order_name": "Passeriformes",
            "family_common_name": "Fixture Birds",
            "family_scientific_name": "Fixtureidae",
            "traits_status": "available" if index == 0 else "unavailable",
            "mass_g": 123.4 if index == 0 else None,
            "habitat": "Woodland" if index == 0 else None,
            "recent_public_observation_count": 0,
            "region_code": "US-AZ",
            "public_location_count": 0,
            "recent_public_notable_count": 0,
            "gbif_occurrence_count": 0,
            "xeno_canto_recording_count": 0,
        }
    )
    return row


def _database(tmp_path: Path) -> Path:
    path = tmp_path / "catalog.duckdb"
    connection = duckdb.connect(str(path))
    connection.execute("CREATE SCHEMA birding_agent")
    columns = ", ".join(f'"{column}" {_column_type(column)}' for column in _COLUMNS)
    connection.execute(f"CREATE TABLE birding_agent.arizona_species_catalog ({columns})")
    placeholders = ", ".join("?" for _ in _COLUMNS)
    for index in range(706):
        row = _base_row(index)
        connection.execute(
            f"INSERT INTO birding_agent.arizona_species_catalog VALUES ({placeholders})",
            [row[column] for column in _COLUMNS],
        )
    connection.close()
    return path


def _client(path: Path) -> TestClient:
    return TestClient(create_app(database_path=str(path), static_dir=path.parent / "missing"))


def test_list_returns_all_706_stable_bounded_rows_without_network_or_writes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = _database(tmp_path)
    before = hashlib.sha256(path.read_bytes()).hexdigest()

    def network_forbidden(*_: object, **__: object) -> object:
        raise AssertionError("catalog GET must not use the network")

    monkeypatch.setattr(socket, "create_connection", network_forbidden)
    response = _client(path).get("/api/birds")

    assert response.status_code == 200
    birds = response.json()["birds"]
    assert len(birds) == 706
    assert [row["species_code"] for row in birds[:2]] == ["bird000", "bird001"]
    assert [row["taxonomic_category"] for row in birds].count("species") == 624
    assert [row["taxonomic_category"] for row in birds].count("hybrid") == 82
    assert set(birds[0]) == {
        "species_code",
        "common_name",
        "scientific_name",
        "taxonomic_category",
        "taxonomic_order",
        "order_name",
        "family_common_name",
        "family_scientific_name",
        "traits_status",
        "mass_g",
        "habitat",
        "recent_public_observation_count",
        "latest_public_observation_at",
        "photo",
        "call",
    }
    assert birds[0]["mass_g"] == 123.4
    assert birds[0]["habitat"] == "Woodland"
    assert all(row["mass_g"] is None and row["habitat"] is None for row in birds[624:])
    assert birds[0]["photo"]["status"] == birds[0]["call"]["status"] == "unavailable"
    assert birds[0]["photo"]["lookup_at"] is None
    assert birds[0]["call"]["lookup_at"] is None
    assert hashlib.sha256(path.read_bytes()).hexdigest() == before


@pytest.mark.parametrize(
    ("column", "value"),
    [
        ("mass_g", 0.0),
        ("mass_g", -1.0),
        ("mass_g", float("nan")),
        ("mass_g", float("inf")),
        ("habitat", ""),
        ("habitat", "   \t"),
        ("habitat", "x" * 201),
        ("habitat", "Woodland\nprivate detail"),
    ],
)
def test_catalog_summary_rejects_invalid_mass_and_habitat(
    tmp_path: Path, column: str, value: object
) -> None:
    path = _database(tmp_path)
    connection = duckdb.connect(str(path))
    connection.execute(
        f"UPDATE birding_agent.arizona_species_catalog SET {column}=? WHERE species_code='bird000'",
        [value],
    )
    connection.close()

    response = _client(path).get("/api/birds")
    assert response.status_code == 503
    assert response.json() == {
        "error": {
            "code": "database_unavailable",
            "message": "The local bird catalog is unavailable",
        }
    }


@pytest.mark.parametrize(
    ("species_code", "column", "value"),
    [
        ("bird001", "mass_g", 12.5),
        ("bird001", "habitat", "Woodland"),
        ("bird624", "mass_g", 12.5),
        ("bird624", "habitat", "Woodland"),
    ],
)
def test_catalog_summary_rejects_traits_on_unavailable_and_hybrid_taxa(
    tmp_path: Path, species_code: str, column: str, value: object
) -> None:
    path = _database(tmp_path)
    connection = duckdb.connect(str(path))
    connection.execute(
        f"UPDATE birding_agent.arizona_species_catalog SET {column}=? WHERE species_code=?",
        [value, species_code],
    )
    connection.close()

    response = _client(path).get("/api/birds")
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "database_unavailable"


def test_catalog_summary_model_rejects_extra_and_malformed_fields(tmp_path: Path) -> None:
    body = _client(_database(tmp_path)).get("/api/birds").json()["birds"][0]
    for key, value in (("extra", True), ("mass_g", "123.4"), ("habitat", 42)):
        malformed = {**body, key: value}
        with pytest.raises(ValidationError):
            BirdCatalogSummaryResponse.model_validate(malformed)


def test_catalog_get_returns_validated_persisted_media_and_fails_stale_identity_closed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    path = _database(tmp_path)
    connection = duckdb.connect(str(path))
    connection.execute(
        """UPDATE birding_agent.arizona_species_catalog
        SET scientific_name='Avis alpha' WHERE species_code='bird000'"""
    )
    connection.close()

    def curated(endpoint: str, params: dict[str, object]) -> dict[str, object]:
        if endpoint == INATURALIST_V2_TAXA:
            return {
                "results": [
                    {
                        "id": 201,
                        "name": str(params["q"]),
                        "rank": "species",
                        "is_active": True,
                    }
                ]
            }
        assert endpoint == INATURALIST_V1_TAXON.format(taxon_id=201)
        return {
            "results": [
                {
                    "id": 201,
                    "name": "Avis alpha",
                    "rank": "species",
                    "is_active": True,
                    "taxon_photos": [
                        {
                            "photo": {
                                "id": 301,
                                "license_code": "cc-by",
                                "attribution": "(c) Fixture, some rights reserved (CC BY)",
                                "url": (
                                    "https://inaturalist-open-data.s3.amazonaws.com/"
                                    "photos/301/square.jpeg"
                                ),
                                "original_dimensions": {"width": 1600, "height": 1200},
                            }
                        }
                    ],
                }
            ]
        }

    def xeno(_endpoint: str, _params: dict[str, object]) -> dict[str, object]:
        return {
            "recordings": [
                {
                    "id": "201",
                    "gen": "Avis",
                    "sp": "alpha",
                    "rec": "Fixture",
                    "cnt": "United States",
                    "loc": "Arizona",
                    "type": "call",
                    "q": "A",
                    "url": "https://xeno-canto.org/201",
                    "file": "https://xeno-canto.org/201/download",
                    "lic": "https://creativecommons.org/licenses/by/4.0/",
                }
            ]
        }

    run_catalog_media_batch(
        str(path),
        mode="apply",
        batch_size=1,
        curated_photo_getter=curated,
        before_inaturalist_request=lambda: None,
        xeno_getter=xeno,
        xeno_api_key="test",
    )
    curated_summary = {
        "species_name": "Avis alpha",
        "display_url": "https://inaturalist-open-data.s3.amazonaws.com/photos/301/large.jpeg",
        "source_url": "https://www.inaturalist.org/photos/301",
        "creator": "Fixture",
        "license_code": "CC BY 4.0",
        "license_url": "https://creativecommons.org/licenses/by/4.0/",
        "original_width": 1600,
        "original_height": 1200,
        "selection_reason": "First eligible curated iNaturalist taxon photo",
    }
    curated_payload = {
        "identity": {"taxon_id": 201, "photo_id": 301, "curated_position": 1},
        "attempted_sources": ["inaturalist"],
    }
    connection = duckdb.connect(str(path))
    connection.execute(
        """UPDATE birding_catalog_media.results SET source='inaturalist',
        source_record_id='301', summary_json=?, payload_json=?, caveats_json='[]'
        WHERE species_code='bird000' AND media_kind='photo'""",
        [json.dumps(curated_summary), json.dumps(curated_payload)],
    )
    connection.close()
    before_get = hashlib.sha256(path.read_bytes()).hexdigest()

    def network_forbidden(*_: object, **__: object) -> object:
        raise AssertionError("catalog GET must not use the network")

    monkeypatch.setattr(socket, "create_connection", network_forbidden)
    response = _client(path).get("/api/birds/bird000")
    assert response.status_code == 200
    assert hashlib.sha256(path.read_bytes()).hexdigest() == before_get
    body = response.json()
    assert body["photo"]["status"] == body["call"]["status"] == "available"
    assert body["photo"]["source_record_id"] == "301"
    assert body["photo"]["provider"] == "inaturalist"
    assert body["photo"]["original_width"] == 1600
    assert body["call"]["source_record_id"] == "201"

    connection = duckdb.connect(str(path))
    original_summary = connection.execute(
        """SELECT summary_json FROM birding_catalog_media.results
        WHERE species_code='bird000' AND media_kind='photo'"""
    ).fetchone()[0]
    for mutation in ("insufficient_dimensions", "missing_selection_reason"):
        summary = json.loads(original_summary)
        if mutation == "insufficient_dimensions":
            summary["original_width"] = 700
        else:
            summary.pop("selection_reason")
        connection.execute(
            """UPDATE birding_catalog_media.results SET summary_json=?
            WHERE species_code='bird000' AND media_kind='photo'""",
            [json.dumps(summary)],
        )
        connection.close()
        malformed_response = _client(path).get("/api/birds/bird000")
        assert malformed_response.status_code == 200
        malformed = malformed_response.json()
        assert malformed["photo"]["status"] == "unavailable", mutation
        assert malformed["photo"]["display_url"] is None
        connection = duckdb.connect(str(path))
        connection.execute(
            """UPDATE birding_catalog_media.results SET summary_json=?
            WHERE species_code='bird000' AND media_kind='photo'""",
            [original_summary],
        )
    connection.close()

    connection = duckdb.connect(str(path))
    connection.execute(
        """DELETE FROM birding_catalog_media.results
        WHERE species_code='bird000' AND media_kind='call'"""
    )
    connection.close()
    incomplete = _client(path).get("/api/birds/bird000").json()
    assert incomplete["photo"]["status"] == incomplete["call"]["status"] == "unavailable"
    run_catalog_media_batch(
        str(path),
        mode="apply",
        batch_size=1,
        curated_photo_getter=curated,
        before_inaturalist_request=lambda: None,
        xeno_getter=xeno,
        xeno_api_key="test",
    )

    connection = duckdb.connect(str(path))
    connection.execute(
        """UPDATE birding_catalog_media.results SET identity_hash='tampered'
        WHERE species_code='bird000'"""
    )
    connection.close()
    stale = _client(path).get("/api/birds/bird000").json()
    assert stale["photo"]["status"] == stale["call"]["status"] == "unavailable"
    assert stale["photo"]["display_url"] is None
    assert stale["call"]["audio_url"] is None


@pytest.mark.parametrize(
    "mutation", ["undersized", "duplicate", "arbitrary_category", "null_category", "625_species"]
)
def test_list_rejects_invalid_catalog_snapshots(tmp_path: Path, mutation: str) -> None:
    path = _database(tmp_path)
    connection = duckdb.connect(str(path))
    if mutation in {"undersized", "duplicate"}:
        connection.execute(
            "DELETE FROM birding_agent.arizona_species_catalog WHERE species_code = 'bird705'"
        )
    if mutation == "duplicate":
        duplicate = _base_row(705)
        duplicate["species_code"] = "bird000"
        placeholders = ", ".join("?" for _ in _COLUMNS)
        connection.execute(
            f"INSERT INTO birding_agent.arizona_species_catalog VALUES ({placeholders})",
            [duplicate[column] for column in _COLUMNS],
        )
    elif mutation == "arbitrary_category":
        connection.execute(
            "UPDATE birding_agent.arizona_species_catalog "
            "SET taxonomic_category = 'form' WHERE species_code = 'bird000'"
        )
    elif mutation == "null_category":
        connection.execute(
            "UPDATE birding_agent.arizona_species_catalog "
            "SET taxonomic_category = NULL WHERE species_code = 'bird000'"
        )
    elif mutation == "625_species":
        connection.execute(
            "UPDATE birding_agent.arizona_species_catalog "
            "SET taxonomic_category = 'species' WHERE species_code = 'bird624'"
        )
    connection.close()

    response = _client(path).get("/api/birds")

    assert response.status_code == 503
    assert response.json() == {
        "error": {
            "code": "database_unavailable",
            "message": "The local bird catalog is unavailable",
        }
    }


def test_detail_is_strict_modeled_profile_with_only_coherent_public_locations(
    tmp_path: Path,
) -> None:
    path = _database(tmp_path)
    locations = [
        {
            "location_id": "public-1",
            "location_name": "Odell Lake (private)",
            "latitude": 33.6,
            "longitude": -112.1,
            "observation_count": 11,
            "latest_observation_at": "2026-07-09T08:00:00",
            "notable_count": 2,
        }
    ]
    connection = duckdb.connect(str(path))
    connection.execute(
        """
        UPDATE birding_agent.arizona_species_catalog SET
          common_name = 'Mexican Jay', scientific_name = 'Aphelocoma wollweberi',
          family_code = 'corvid1', report_as = NULL, extinct = FALSE,
          traits_status = 'available', source_scientific_name = 'Aphelocoma wollweberi',
          avonet_family = 'Corvidae', avonet_order_name = 'Passeriformes',
          avibase_id = 'AVIBASE-56B8CE7A', total_individuals = 4,
          complete_measures = 4, wing_length_mm = 176.5, mass_g = 123.4,
          inference = TRUE, traits_inferred = 'Mass', reference_species = 'Reference bird',
          habitat = 'Woodland', habitat_density_code = 2,
          habitat_density_label = 'Semi-open', migration_code = 1,
          migration_label = 'Partial migrant', trophic_level = 'Omnivore',
          trophic_niche = 'Ground', primary_lifestyle = 'Insessorial',
          dataset_doi = '10.6084/m9.figshare.16586228.v7', dataset_version = 'v7',
          dataset_license = 'CC BY 4.0', source_file_id = 34480856,
          source_file_md5 = '1445afdcfb6df784010c2ca034544bc8',
          avonet_loaded_at = '2026-07-10 01:00:00',
          recent_public_observation_count = 11,
          latest_public_observation_at = '2026-07-09 08:00:00',
          public_location_count = 1, recent_public_notable_count = 2,
          top_public_locations_json = ?, gbif_occurrence_count = 7,
          gbif_latest_event_date = '2026-07-01', xeno_canto_recording_count = 3,
          xeno_canto_latest_recording_date = '2026-06-01', representative_recording_id = '123',
          representative_recordist = 'Fixture Birder', representative_recording_type = 'call',
          representative_recording_quality = 'A', representative_recording_license = 'CC BY 4.0',
          species_list_loaded_at = '2026-07-09', taxonomy_loaded_at = '2026-07-09',
          ebird_observations_loaded_at = '2026-07-09', gbif_loaded_at = '2026-07-09',
          xeno_canto_loaded_at = '2026-07-09', catalog_freshness_at = '2026-07-10'
        WHERE species_code = 'bird000'
        """,
        [json.dumps(locations)],
    )
    connection.close()

    response = _client(path).get("/api/birds/bird000")

    assert response.status_code == 200
    profile = response.json()
    assert profile["traits"]["morphology"] == {
        "beak_length_culmen_mm": None,
        "beak_length_nares_mm": None,
        "beak_width_mm": None,
        "beak_depth_mm": None,
        "tarsus_length_mm": None,
        "wing_length_mm": 176.5,
        "kipps_distance_mm": None,
        "secondary_length_mm": None,
        "hand_wing_index": None,
        "tail_length_mm": None,
        "mass_g": 123.4,
    }
    assert profile["arizona_activity"]["top_public_locations"] == locations
    assert profile["traits"]["provenance"]["dataset_license"] == "CC BY 4.0"
    # `is_location_private` is the privacy authority in the governed model. A
    # public tuple's name may still say `(private)` to describe site access.
    assert profile["arizona_activity"]["top_public_locations"][0]["location_name"] == (
        "Odell Lake (private)"
    )

    def response_keys(value: object) -> set[str]:
        if isinstance(value, dict):
            return set(value) | {key for nested in value.values() for key in response_keys(nested)}
        if isinstance(value, list):
            return {key for nested in value for key in response_keys(nested)}
        return set()

    keys = response_keys(profile)
    assert keys.isdisjoint(
        {
            "is_location_private",
            "location_private",
            "private_location",
            "species_sk",
            "top_public_locations_json",
            "_dlt_id",
            "_dlt_load_id",
        }
    )
    assert set(profile["arizona_activity"]["top_public_locations"][0]) == {
        "location_id",
        "location_name",
        "latitude",
        "longitude",
        "observation_count",
        "latest_observation_at",
        "notable_count",
    }


def test_sparse_hybrid_and_taxonomy_drift_profiles_remain_available(tmp_path: Path) -> None:
    path = _database(tmp_path)
    client = _client(path)

    hybrid = client.get("/api/birds/bird624")
    drift = client.get("/api/birds/bird023")

    assert hybrid.status_code == drift.status_code == 200
    assert hybrid.json()["taxonomic_category"] == "hybrid"
    assert hybrid.json()["traits"]["status"] == "unavailable"
    assert drift.json()["traits"]["status"] == "unavailable"
    assert drift.json()["arizona_activity"]["top_public_locations"] == []
    assert drift.json()["gbif"]["occurrence_count"] == 0
    assert drift.json()["xeno_canto"]["recording_count"] == 0


def test_bird_pages_have_deterministic_responsive_layout_contract() -> None:
    styles = (Path(__file__).parents[1] / "app" / "src" / "styles.css").read_text(encoding="utf-8")

    assert "@media (max-width: 1100px)" in styles
    assert ".species-grid, .bird-catalog-grid { grid-template-columns: repeat(2" in styles
    assert "@media (max-width: 820px)" in styles
    assert (
        ".catalog-profile-media-grid { display: grid; grid-template-columns: minmax(0, 1fr);"
        in styles
    )
    assert ".bird-profile-main { display: grid; grid-template-columns: minmax(0, 1fr);" in styles
    assert "minmax(240px" not in styles
    assert "@media (max-width: 540px)" in styles
    mobile_grid = (
        ".summary-grid, .details-list, .species-grid, .bird-catalog-grid, "
        ".catalog-controls, .inline-collection-form, .map-controls { "
        "grid-template-columns: minmax(0, 1fr); }"
    )
    assert mobile_grid in styles
    assert ".site-header nav { order: 3; width: 100%; display: grid;" in styles
    assert ".button-row { align-items: stretch; flex-direction: column; }" in styles


def test_static_frontend_fallback_serves_direct_bird_routes(tmp_path: Path) -> None:
    static_dir = tmp_path / "dist"
    static_dir.mkdir()
    (static_dir / "index.html").write_text("<main>local app shell</main>")
    client = TestClient(
        create_app(database_path=str(tmp_path / "missing.duckdb"), static_dir=static_dir)
    )

    assert client.get("/birds").text == "<main>local app shell</main>"
    assert client.get("/birds/bird000").text == "<main>local app shell</main>"
    assert client.get("/map").text == "<main>local app shell</main>"
    assert client.get("/my-birds").text == "<main>local app shell</main>"


def test_invalid_not_found_busy_and_malformed_location_states_are_safe(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = _database(tmp_path)
    client = _client(path)
    assert client.get("/api/birds/not-valid").json() == {
        "error": {"code": "invalid_request", "message": "Invalid bird species code"}
    }
    missing = client.get("/api/birds/nope")
    assert missing.status_code == 404
    assert missing.json()["error"]["code"] == "not_found"

    connection = duckdb.connect(str(path))
    connection.execute(
        """
        UPDATE birding_agent.arizona_species_catalog
        SET top_public_locations_json = '[]x'
        WHERE species_code = 'bird000'
        """
    )
    connection.close()
    malformed = client.get("/api/birds/bird000")
    assert malformed.status_code == 503
    assert malformed.json()["error"]["code"] == "database_unavailable"
    assert "[]x" not in malformed.text

    def busy(*_: object, **__: object) -> object:
        raise duckdb.IOException("Conflicting lock: /private/path")

    monkeypatch.setattr("databox.api.duckdb.connect", busy)
    locked = client.get("/api/birds")
    assert locked.status_code == 503
    assert locked.json() == {
        "error": {
            "code": "database_busy",
            "message": "The warehouse is refreshing; try again shortly",
        }
    }
    assert "/private/path" not in locked.text
