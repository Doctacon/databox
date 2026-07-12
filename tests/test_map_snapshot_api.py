"""Strict read-only Field Map snapshot contract and privacy tests."""

from __future__ import annotations

import hashlib
import socket
from pathlib import Path

import duckdb
import pytest
from databox.api import MapEncounterResponse, create_app
from fastapi.testclient import TestClient
from pydantic import ValidationError


def _database(path: Path) -> None:
    connection = duckdb.connect(path)
    connection.execute("CREATE SCHEMA environmental_observations")
    connection.execute("CREATE SCHEMA birding_agent")
    connection.execute(
        """
        CREATE TABLE environmental_observations.fact_bird_observation (
            source_observation_id VARCHAR, species_code VARCHAR,
            observation_datetime TIMESTAMP, observation_count BIGINT,
            is_notable BOOLEAN, location_id VARCHAR, location_name VARCHAR,
            latitude DOUBLE, longitude DOUBLE, loaded_at TIMESTAMP,
            region_code VARCHAR, is_valid BOOLEAN, is_reviewed BOOLEAN,
            is_location_private BOOLEAN
        )
        """
    )
    connection.execute(
        """
        CREATE TABLE birding_agent.arizona_species_catalog (
            species_code VARCHAR, common_name VARCHAR, scientific_name VARCHAR,
            family_common_name VARCHAR, family_scientific_name VARCHAR
        )
        """
    )
    connection.execute(
        "INSERT INTO birding_agent.arizona_species_catalog VALUES (?, ?, ?, ?, ?)",
        ["abc123", "Alpha Bird", "Avis alpha", "Fixture Birds", "Fixtureidae"],
    )
    connection.close()


def _insert(path: Path, **overrides: object) -> None:
    row = {
        "source_observation_id": "S123",
        "species_code": "abc123",
        "observation_datetime": "2026-07-09 08:30:00",
        "observation_count": 2,
        "is_notable": True,
        "location_id": "L123",
        "location_name": "Public Park",
        "latitude": 34.54,
        "longitude": -112.47,
        "loaded_at": "2026-07-09 13:00:00",
        "region_code": "US-AZ",
        "is_valid": True,
        "is_reviewed": True,
        "is_location_private": False,
    }
    row.update(overrides)
    connection = duckdb.connect(path)
    columns = ", ".join(row)
    placeholders = ", ".join("?" for _ in row)
    connection.execute(
        f"INSERT INTO environmental_observations.fact_bird_observation ({columns}) "
        f"VALUES ({placeholders})",
        list(row.values()),
    )
    connection.close()


def _client(path: Path) -> TestClient:
    return TestClient(create_app(database_path=str(path)))


def test_snapshot_returns_only_bounded_safe_exact_fields(tmp_path: Path) -> None:
    path = tmp_path / "map.duckdb"
    _database(path)
    _insert(path, location_name="Trail (private)")
    response = _client(path).get("/api/map-snapshot")
    assert response.status_code == 200
    assert response.json() == {
        "snapshot_latest_observation_at": "2026-07-09T08:30:00",
        "source_freshness_at": "2026-07-09T13:00:00",
        "encounters": [
            {
                "source_observation_id": "S123",
                "species_code": "abc123",
                "common_name": "Alpha Bird",
                "scientific_name": "Avis alpha",
                "family_common_name": "Fixture Birds",
                "family_scientific_name": "Fixtureidae",
                "observation_at": "2026-07-09T08:30:00",
                "observation_count": 2,
                "notable": True,
                "location_id": "L123",
                "location_name": "Trail (private)",
                "latitude": 34.54,
                "longitude": -112.47,
                "access_warning": True,
            }
        ],
        "photos": [
            {
                "species_code": "abc123",
                "scientific_name": "Avis alpha",
                "photo": {
                    "status": "unavailable",
                    "source_record_id": None,
                    "species_name": None,
                    "display_url": None,
                    "source_url": None,
                    "creator": None,
                    "rights_holder": None,
                    "publisher": None,
                    "format": None,
                    "license_text": None,
                    "license_url": None,
                    "selection_reason": None,
                    "caveats": ["Catalog photo has not been enriched for this exact taxon"],
                    "lookup_at": None,
                },
            }
        ],
    }
    serialized = str(response.json()).lower()
    for forbidden in (
        "is_location_private",
        "email",
        "credential",
        "watch",
        "plan",
        "trace",
        "payload",
    ):
        assert forbidden not in serialized


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("region_code", None),
        ("region_code", "US-NM"),
        ("is_valid", False),
        ("is_valid", None),
        ("is_reviewed", False),
        ("is_reviewed", None),
        ("is_location_private", True),
        ("is_location_private", None),
        ("observation_count", None),
    ],
)
def test_ineligible_or_privacy_ambiguous_rows_are_excluded(
    tmp_path: Path, field: str, value: object
) -> None:
    path = tmp_path / "map.duckdb"
    _database(path)
    _insert(path, **{field: value})
    response = _client(path).get("/api/map-snapshot")
    assert response.status_code == 200
    assert response.json() == {
        "snapshot_latest_observation_at": None,
        "source_freshness_at": None,
        "encounters": [],
        "photos": [],
    }


def test_unknown_current_taxon_is_excluded(tmp_path: Path) -> None:
    path = tmp_path / "map.duckdb"
    _database(path)
    _insert(path, species_code="unknown")
    assert _client(path).get("/api/map-snapshot").json()["encounters"] == []


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("source_observation_id", ""),
        ("location_name", "   "),
        ("observation_count", 0),
        ("latitude", 31.2),
        ("longitude", -114.8),
        ("loaded_at", None),
    ],
)
def test_malformed_or_out_of_bounds_eligible_rows_fail_closed(
    tmp_path: Path, field: str, value: object
) -> None:
    path = tmp_path / "map.duckdb"
    _database(path)
    _insert(path, **{field: value})
    response = _client(path).get("/api/map-snapshot")
    assert response.status_code == 503
    assert response.json() == {
        "error": {"code": "database_unavailable", "message": "The local Field Map is unavailable"}
    }


def test_duplicate_evidence_identifiers_fail_closed(tmp_path: Path) -> None:
    path = tmp_path / "map.duckdb"
    _database(path)
    _insert(path)
    _insert(path, location_id="L456")
    assert _client(path).get("/api/map-snapshot").status_code == 503


def test_snapshot_never_truncates_over_the_ratified_bound(tmp_path: Path) -> None:
    path = tmp_path / "map.duckdb"
    _database(path)
    connection = duckdb.connect(path)
    connection.execute(
        """
        INSERT INTO environmental_observations.fact_bird_observation
        SELECT 'S' || i, 'abc123', TIMESTAMP '2026-07-09 08:30:00', 1, FALSE,
               'L' || i, 'Public Park', 34.54, -112.47,
               TIMESTAMP '2026-07-09 13:00:00', 'US-AZ', TRUE, TRUE, FALSE
        FROM range(10001) AS rows(i)
        """
    )
    connection.close()
    assert _client(path).get("/api/map-snapshot").status_code == 503


def test_strict_response_model_rejects_extra_relationship_and_type_attacks() -> None:
    valid = {
        "source_observation_id": "S1",
        "species_code": "abc123",
        "common_name": "Alpha",
        "scientific_name": "Avis alpha",
        "family_common_name": "Fixture",
        "family_scientific_name": "Fixtureidae",
        "observation_at": "2026-07-09T08:30:00",
        "observation_count": 1,
        "notable": False,
        "location_id": "L1",
        "location_name": "Public Park",
        "latitude": 34.54,
        "longitude": -112.47,
        "access_warning": False,
    }
    for attack in (
        {**valid, "secret": "leak"},
        {**valid, "notable": 1},
        {**valid, "common_name": None, "scientific_name": None},
        {**valid, "location_name": "Park (private)", "access_warning": False},
    ):
        with pytest.raises(ValidationError):
            MapEncounterResponse.model_validate(attack)


def test_get_is_network_free_and_does_not_change_the_database(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "map.duckdb"
    _database(path)
    _insert(path)
    before = hashlib.sha256(path.read_bytes()).hexdigest()

    def forbidden(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("network access is forbidden")

    monkeypatch.setattr(socket.socket, "connect", forbidden)
    response = _client(path).get("/api/map-snapshot")
    assert response.status_code == 200
    assert hashlib.sha256(path.read_bytes()).hexdigest() == before
