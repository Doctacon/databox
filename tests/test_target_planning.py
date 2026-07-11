from __future__ import annotations

import hashlib
import json
import socket
from datetime import datetime
from pathlib import Path
from typing import Any

import duckdb
import pytest
from databox.agents.birding_trip_planner import NormalizedLocation
from databox.agents.cloudflare_workers_ai import (
    CLOUDFLARE_WORKERS_AI_MODEL,
    CloudflareMalformedResponseError,
    TargetSynthesisGrounding,
    TargetSynthesisRequest,
    TargetSynthesisResult,
)
from databox.api import create_app
from databox.target_planning import TargetPlanner, TargetRequest, select_target_candidates
from fastapi.testclient import TestClient


class FakeTargetModel:
    model = CLOUDFLARE_WORKERS_AI_MODEL

    def __init__(self, *, fail: bool = False, force_location_action: bool = False) -> None:
        self.requests: list[TargetSynthesisRequest] = []
        self.fail = fail
        self.force_location_action = force_location_action

    def synthesize_target(self, request: TargetSynthesisRequest) -> TargetSynthesisResult:
        self.requests.append(request)
        if self.fail:
            raise CloudflareMalformedResponseError("invalid structured response")
        actions = ["review_freshness"]
        if request.candidates or self.force_location_action:
            actions = ["try_top_location", "review_freshness", "verify_access"]
        return TargetSynthesisResult(
            action_ids=actions,
            grounding=TargetSynthesisGrounding(
                species_code=request.species_code,
                requested_location=request.origin.requested_location,
                window_start=request.window_start,
                window_end=request.window_end,
                duration_minutes=request.duration_minutes,
                radius_miles=request.radius_miles,
                candidate_ids=[item.location_id for item in request.candidates],
                evidence_freshness_at=request.evidence_freshness_at,
                weather_status=request.weather.status,
                evidence_hash=request.evidence_hash,
                caveats=request.caveats,
            ),
        )


def weather(url: str, params: Any) -> dict[str, Any]:
    if "elevation" in url:
        return {"elevation": [330.0]}
    return {
        "hourly_units": {"temperature_2m": "°C", "wind_speed_10m": "km/h"},
        "hourly": {
            "time": ["2026-07-11T06:00", "2026-07-11T07:00"],
            "temperature_2m": [20.0, 21.0],
            "relative_humidity_2m": [40, 38],
            "precipitation_probability": [0, 0],
            "precipitation": [0, 0],
            "weather_code": [0, 0],
            "wind_speed_10m": [5, 7],
            "wind_gusts_10m": [8, 10],
        },
    }


def incomplete_weather(url: str, params: Any) -> dict[str, Any]:
    if "elevation" in url:
        return {"elevation": [330.0]}
    return {
        "hourly": {
            "time": ["2026-07-11T06:00", "2026-07-11T07:00"],
            "temperature_2m": [20.0, None],
        }
    }


def unavailable_weather(url: str, params: Any) -> dict[str, Any]:
    raise RuntimeError("synthetic source unavailable")


def create_db(path: Path) -> None:
    connection = duckdb.connect(str(path))
    connection.execute("CREATE SCHEMA birding_agent")
    connection.execute("""
        CREATE TABLE birding_agent.arizona_species_catalog (
          species_code TEXT, common_name TEXT, scientific_name TEXT, taxonomic_category TEXT
        )
    """)
    connection.execute(
        "INSERT INTO birding_agent.arizona_species_catalog VALUES "
        "('target1','Target Bird','Avis target','species'), "
        "('hybrid1','Target x Bird','Avis x target','hybrid')"
    )
    connection.execute("CREATE SCHEMA environmental_observations")
    connection.execute("""
      CREATE TABLE environmental_observations.fact_bird_observation (
        source_observation_id TEXT, species_code TEXT, region_code TEXT,
        location_id TEXT, location_name TEXT, latitude DOUBLE, longitude DOUBLE,
        observation_datetime TIMESTAMP, loaded_at TIMESTAMP,
        bird_observation_sk TEXT, dlt_id TEXT,
        is_valid BOOLEAN, is_reviewed BOOLEAN, is_location_private BOOLEAN
      )
    """)
    rows = [
        (
            "s1",
            "target1",
            "US-AZ",
            "far",
            "Far Public",
            34.2,
            -112.0,
            "2026-07-09 08:00",
            "2026-07-10",
            "b1",
            "d1",
            True,
            True,
            False,
        ),
        (
            "s2",
            "target1",
            "US-AZ",
            "near",
            "Old Name",
            34.01,
            -112.0,
            "2026-07-09 07:00",
            "2026-07-10",
            "b2",
            "d2",
            True,
            True,
            False,
        ),
        (
            "s3",
            "target1",
            "US-AZ",
            "near",
            "Near Public",
            34.011,
            -112.0,
            "2026-07-10 07:00",
            "2026-07-10",
            "b3",
            "d3",
            True,
            True,
            False,
        ),
        (
            "s3",
            "target1",
            "US-AZ",
            "near",
            "Near Public",
            34.011,
            -112.0,
            "2026-07-10 07:00",
            "2026-07-10",
            "b4",
            "d4",
            True,
            True,
            False,
        ),
        (
            "private",
            "target1",
            "US-AZ",
            "secret",
            "Secret",
            34.0,
            -112.0,
            "2026-07-10 10:00",
            "2026-07-10",
            "b5",
            "d5",
            True,
            True,
            True,
        ),
        (
            "invalid",
            "target1",
            "US-AZ",
            "invalid",
            "Invalid",
            34.0,
            -112.0,
            "2026-07-10 10:00",
            "2026-07-10",
            "b6",
            "d6",
            False,
            True,
            False,
        ),
        (
            "unreviewed",
            "target1",
            "US-AZ",
            "unreviewed",
            "Unreviewed",
            34.0,
            -112.0,
            "2026-07-10 10:00",
            "2026-07-10",
            "b7",
            "d7",
            True,
            False,
            False,
        ),
        (
            "wrong",
            "hybrid1",
            "US-AZ",
            "wrong",
            "Wrong",
            34.0,
            -112.0,
            "2026-07-10 10:00",
            "2026-07-10",
            "b8",
            "d8",
            True,
            True,
            False,
        ),
        (
            "outside",
            "target1",
            "US-AZ",
            "outside",
            "Outside",
            31.0,
            -109.0,
            "2026-07-10 10:00",
            "2026-07-10",
            "b9",
            "d9",
            True,
            True,
            False,
        ),
    ]
    connection.executemany(
        "INSERT INTO environmental_observations.fact_bird_observation "
        "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        rows,
    )
    connection.close()


@pytest.fixture
def db(tmp_path: Path) -> Path:
    path = tmp_path / "target.duckdb"
    create_db(path)
    return path


def request(species: str = "target1", radius: float = 100) -> TargetRequest:
    return TargetRequest(
        species_code=species,
        origin=NormalizedLocation("Prescott", "Prescott, AZ", 34.0, -112.0, "US-AZ"),
        radius_miles=radius,
        start_at=datetime(2026, 7, 11, 6),
        duration_minutes=120,
    )


def payload(species: str = "target1", radius: float = 100) -> dict[str, Any]:
    return {
        "species_code": species,
        "location": "Prescott, AZ",
        "location_selection": {
            "display_name": "Prescott, Arizona, United States",
            "latitude": 34.0,
            "longitude": -112.0,
            "timezone": "America/Phoenix",
            "region_code": "US-AZ",
        },
        "radius_miles": radius,
        "start_at": "2026-07-11T06:00:00",
        "duration_minutes": 120,
    }


def test_candidates_are_exact_public_coherent_clustered_and_ranked(db: Path) -> None:
    connection = duckdb.connect(str(db))
    rows = select_target_candidates(connection, request())
    connection.close()
    assert [item.location_id for item in rows] == ["near", "far"]
    assert rows[0].observation_count == 2  # duplicate feed row/submission counts once
    assert rows[0].location_name == "Near Public"
    assert rows[0].latitude == 34.011  # coherent newest row, not independent minima
    assert not {"secret", "invalid", "unreviewed", "wrong", "outside"} & {
        item.location_id for item in rows
    }
    assert rows[0].distance_miles < rows[1].distance_miles


def test_equal_count_and_date_use_distance_then_name_and_id(db: Path) -> None:
    connection = duckdb.connect(str(db))
    connection.execute(
        "DELETE FROM environmental_observations.fact_bird_observation "
        "WHERE source_observation_id = 's2'"
    )
    connection.execute(
        "UPDATE environmental_observations.fact_bird_observation "
        "SET observation_datetime = '2026-07-10 07:00:00' "
        "WHERE source_observation_id = 's1'"
    )
    assert [item.location_id for item in select_target_candidates(connection, request())][:2] == [
        "near",
        "far",
    ]
    connection.execute(
        "UPDATE environmental_observations.fact_bird_observation "
        "SET latitude = 34.011, longitude = -112.0, location_name = 'A location' "
        "WHERE source_observation_id = 's1'"
    )
    assert [item.location_id for item in select_target_candidates(connection, request())][:2] == [
        "far",
        "near",
    ]
    connection.execute(
        "UPDATE environmental_observations.fact_bird_observation "
        "SET location_name = 'Near Public' WHERE source_observation_id = 's1'"
    )
    assert [item.location_id for item in select_target_candidates(connection, request())][:2] == [
        "far",
        "near",
    ]
    connection.close()


def test_empty_evidence_stays_empty_and_model_is_grounded(db: Path) -> None:
    connection = duckdb.connect(str(db))
    connection.execute(
        "DELETE FROM environmental_observations.fact_bird_observation "
        "WHERE species_code = 'hybrid1'"
    )
    model = FakeTargetModel()
    result = TargetPlanner(connection, model_client=model, weather_getter=weather).create(
        request("hybrid1", 1)
    )
    assert result.candidates == []
    assert result.taxonomic_category == "hybrid"
    assert "No qualifying modeled public observation" in result.caveats[0]
    assert model.requests[0].candidates == []
    assert "try_top_location" not in result.action_ids
    assert result.model == CLOUDFLARE_WORKERS_AI_MODEL
    assert (
        connection.execute("SELECT count(*) FROM birding_agent.target_bird_plans").fetchone()[0]
        == 1
    )
    connection.close()


def test_empty_evidence_rejects_location_action_before_persistence(db: Path) -> None:
    connection = duckdb.connect(str(db))
    connection.execute(
        "DELETE FROM environmental_observations.fact_bird_observation "
        "WHERE species_code = 'hybrid1'"
    )
    with pytest.raises(CloudflareMalformedResponseError, match="without candidate evidence"):
        TargetPlanner(
            connection,
            model_client=FakeTargetModel(force_location_action=True),
            weather_getter=weather,
        ).create(request("hybrid1", 1))
    assert (
        connection.execute(
            "SELECT count(*) FROM information_schema.tables "
            "WHERE table_name LIKE 'target_bird_plan%'"
        ).fetchone()[0]
        == 0
    )
    connection.close()


def test_model_receives_complete_bounded_candidate_weather_and_freshness(db: Path) -> None:
    connection = duckdb.connect(str(db))
    model = FakeTargetModel()
    TargetPlanner(connection, model_client=model, weather_getter=weather).create(request())
    supplied = model.requests[0]
    assert supplied.taxonomic_category == "species"
    assert supplied.origin.normalized_location_name == "Prescott, AZ"
    candidate = supplied.candidates[0]
    assert candidate.model_dump() == {
        "location_id": "near",
        "location_name": "Near Public",
        "latitude": 34.011,
        "longitude": -112.0,
        "observation_count": 2,
        "latest_observation_at": "2026-07-10 07:00:00",
        "distance_km": candidate.distance_km,
        "distance_miles": candidate.distance_miles,
        "evidence_loaded_at": "2026-07-10 00:00:00",
    }
    assert supplied.evidence_freshness_at == "2026-07-10 00:00:00"
    assert supplied.weather.status == "available"
    assert supplied.weather.forecast_summary.temperature_2m_avg == 20.5
    assert supplied.weather.units.wind_speed == "km/h"
    assert supplied.weather.retrieved_at
    assert len(supplied.evidence_hash) == 64
    connection.close()


def test_model_failure_persists_nothing(db: Path) -> None:
    connection = duckdb.connect(str(db))
    with pytest.raises(CloudflareMalformedResponseError):
        TargetPlanner(
            connection, model_client=FakeTargetModel(fail=True), weather_getter=weather
        ).create(request())
    assert (
        connection.execute(
            "SELECT count(*) FROM information_schema.tables "
            "WHERE table_name LIKE 'target_bird_plan%'"
        ).fetchone()[0]
        == 0
    )
    connection.close()


def test_persistence_failure_rolls_back_schema_and_rows(
    db: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import databox.target_planning as module

    connection = duckdb.connect(str(db))
    original = module.ensure_target_tables

    def fail_after_ddl(target: Any) -> None:
        original(target)
        raise RuntimeError("intentional")

    monkeypatch.setattr(module, "ensure_target_tables", fail_after_ddl)
    with pytest.raises(RuntimeError, match="intentional"):
        TargetPlanner(connection, model_client=FakeTargetModel(), weather_getter=weather).create(
            request()
        )
    assert (
        connection.execute(
            "SELECT count(*) FROM information_schema.tables "
            "WHERE table_name LIKE 'target_bird_plan%'"
        ).fetchone()[0]
        == 0
    )
    connection.close()


def test_api_create_and_get_are_reproducible_network_free(
    db: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    model = FakeTargetModel()
    client = TestClient(
        create_app(
            database_path=str(db),
            model_client=model,
            weather_getter=weather,
            static_dir=Path("missing"),
        )
    )
    created = client.post("/api/target-plans", json=payload())
    assert created.status_code == 201
    body = created.json()
    assert body["species_code"] == "target1"
    assert body["radius_miles"] == 100
    assert body["radius_km"] == 160.934
    assert len(body["candidates"]) == 2
    assert body["weather"]["status"] == "available"
    plan_id = body["target_plan_id"]
    before = hashlib.sha256(db.read_bytes()).hexdigest()

    def blocked(*args: Any, **kwargs: Any) -> None:
        raise AssertionError("GET must not use the network")

    monkeypatch.setattr(socket, "create_connection", blocked)
    replay = client.get(f"/api/target-plans/{plan_id}")
    listing = client.get("/api/target-plans")
    assert replay.status_code == 200 and replay.json() == body
    assert listing.status_code == 200 and listing.json()["plans"] == [body]
    assert hashlib.sha256(db.read_bytes()).hexdigest() == before
    assert len(model.requests) == 1
    assert "source_observation_id" not in replay.text
    assert "Secret" not in replay.text


def test_incomplete_weather_is_normalized_before_atomic_persistence(db: Path) -> None:
    client = TestClient(
        create_app(
            database_path=str(db),
            model_client=FakeTargetModel(),
            weather_getter=incomplete_weather,
            static_dir=Path("missing"),
        )
    )
    response = client.post("/api/target-plans", json=payload())
    assert response.status_code == 201
    body = response.json()
    assert body["weather"]["status"] == "available"
    assert body["weather"]["forecast_summary"] == {
        "temperature_2m_min": 20.0,
        "temperature_2m_max": 20.0,
        "temperature_2m_avg": 20.0,
        "relative_humidity_2m_avg": None,
        "precipitation_probability_max": None,
        "precipitation_sum": None,
        "wind_speed_10m_max": None,
        "wind_gusts_10m_max": None,
        "weather_codes": [],
    }
    replay = client.get(f"/api/target-plans/{body['target_plan_id']}")
    assert replay.status_code == 200
    assert replay.json() == body


def test_unavailable_weather_has_only_explicit_absence(db: Path) -> None:
    model = FakeTargetModel()
    connection = duckdb.connect(str(db))
    result = TargetPlanner(
        connection, model_client=model, weather_getter=unavailable_weather
    ).create(request())
    assert result.weather.status == "unavailable"
    assert result.weather.elevation_m is None
    assert all(
        value is None or value == []
        for value in result.weather.forecast_summary.model_dump().values()
    )
    assert model.requests[0].weather == result.weather
    connection.close()


@pytest.mark.parametrize(
    "field,value",
    [
        ("radius_miles", 0),
        ("radius_miles", 301),
        ("duration_minutes", 0),
        ("duration_minutes", 1441),
    ],
)
def test_api_rejects_bounds_without_model(db: Path, field: str, value: int) -> None:
    model = FakeTargetModel()
    data = payload()
    data[field] = value
    response = TestClient(
        create_app(
            database_path=str(db),
            model_client=model,
            weather_getter=weather,
            static_dir=Path("missing"),
        )
    ).post("/api/target-plans", json=data)
    assert response.status_code == 422
    assert model.requests == []


def test_get_rejects_malformed_persisted_weather_and_relationships(db: Path) -> None:
    client = TestClient(
        create_app(
            database_path=str(db),
            model_client=FakeTargetModel(),
            weather_getter=weather,
            static_dir=Path("missing"),
        )
    )
    created = client.post("/api/target-plans", json=payload()).json()
    plan_id = created["target_plan_id"]
    connection = duckdb.connect(str(db))
    malformed = created["weather"]
    del malformed["forecast_summary"]["wind_gusts_10m_max"]
    connection.execute(
        "UPDATE birding_agent.target_bird_plans SET weather_json = ? WHERE target_plan_id = ?",
        [json.dumps(malformed), plan_id],
    )
    connection.close()
    response = client.get(f"/api/target-plans/{plan_id}")
    assert response.status_code == 503
    assert response.json() == {
        "error": {
            "code": "database_unavailable",
            "message": "The local target plans are unavailable",
        }
    }


def test_api_rejects_non_arizona_and_missing_taxon(db: Path) -> None:
    model = FakeTargetModel()
    client = TestClient(
        create_app(
            database_path=str(db),
            model_client=model,
            weather_getter=weather,
            static_dir=Path("missing"),
        )
    )
    outside = payload()
    outside["location_selection"]["latitude"] = 40
    assert client.post("/api/target-plans", json=outside).status_code == 400
    missing = payload("missing")
    response = client.post("/api/target-plans", json=missing)
    assert response.status_code == 400
    assert "catalog taxon" in response.json()["error"]["message"]


def test_model_failure_api_is_safe_and_atomic(db: Path) -> None:
    client = TestClient(
        create_app(
            database_path=str(db),
            model_client=FakeTargetModel(fail=True),
            weather_getter=weather,
            static_dir=Path("missing"),
        )
    )
    response = client.post("/api/target-plans", json=payload())
    assert response.status_code == 503
    assert response.json() == {
        "error": {"code": "model_unavailable", "message": "The configured model is unavailable"}
    }
    connection = duckdb.connect(str(db))
    assert (
        connection.execute(
            "SELECT count(*) FROM information_schema.tables "
            "WHERE table_name LIKE 'target_bird_plan%'"
        ).fetchone()[0]
        == 0
    )
    connection.close()
