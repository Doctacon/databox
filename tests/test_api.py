"""Local Birding Trip Copilot HTTP API contract tests."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any

import duckdb
import pytest
from databox.agent_tools.open_meteo import ELEVATION_ENDPOINT, FORECAST_ENDPOINT
from databox.agents.cloudflare_workers_ai import (
    CLOUDFLARE_WORKERS_AI_MODEL,
    CloudflareModelUnavailableError,
    CloudflareTimeoutError,
    GroundedSynthesisRequest,
    GroundedSynthesisResult,
)
from databox.api import create_app
from databox.config.settings import settings
from fastapi.testclient import TestClient
from pydantic import SecretStr


class FakeModelClient:
    model = CLOUDFLARE_WORKERS_AI_MODEL

    def synthesize(self, request: GroundedSynthesisRequest) -> GroundedSynthesisResult:
        return GroundedSynthesisResult.model_validate(
            {
                "action_ids": ["listen_first", "check_weather"],
                "grounding": {
                    "requested_location": request.requested_location,
                    "window_start": request.window_start,
                    "window_end": request.window_end,
                    "duration_minutes": request.duration_minutes,
                    "recommendation_ids": [
                        row.recommendation_id for row in request.recommendations
                    ],
                    "caveats": request.caveats,
                },
            }
        )


class WrongModelClient(FakeModelClient):
    model = "arbitrary-model"


class UnavailableModelClient:
    model = CLOUDFLARE_WORKERS_AI_MODEL

    def synthesize(self, request: GroundedSynthesisRequest) -> GroundedSynthesisResult:
        _ = request
        raise CloudflareModelUnavailableError("untrusted provider details")


class TimeoutModelClient:
    model = CLOUDFLARE_WORKERS_AI_MODEL

    def synthesize(self, request: GroundedSynthesisRequest) -> GroundedSynthesisResult:
        _ = request
        raise CloudflareTimeoutError("Cloudflare Workers AI request timed out")


def _weather(endpoint: str, params: Mapping[str, object]) -> dict[str, Any]:
    if endpoint == ELEVATION_ENDPOINT:
        return {"elevation": [1642.0]}
    assert endpoint == FORECAST_ENDPOINT
    return {
        "hourly_units": {"time": "iso8601", "temperature_2m": "°C"},
        "hourly": {
            "time": ["2026-07-10T06:00"],
            "temperature_2m": [18.0],
            "relative_humidity_2m": [40],
            "precipitation_probability": [0],
            "precipitation": [0],
            "weather_code": [0],
            "wind_speed_10m": [5],
        },
    }


def _client(tmp_path: Path, model: object | None = None) -> TestClient:
    return TestClient(
        create_app(
            database_path=str(tmp_path / "databox.duckdb"),
            model_client=model or FakeModelClient(),  # type: ignore[arg-type]
            weather_getter=_weather,
            static_dir=tmp_path / "missing-dist",
        )
    )


PLAN_SUMMARY_KEYS = {
    "trip_plan_id",
    "requested_location",
    "normalized_location_name",
    "window_start",
    "window_end",
    "duration_minutes",
    "plan_status",
    "caveats",
    "created_at",
    "updated_at",
}
PLAN_KEYS = PLAN_SUMMARY_KEYS | {
    "latitude",
    "longitude",
    "region_code",
    "skill_level",
    "constraints_text",
    "field_plan_text",
}
RECOMMENDATION_KEYS = {
    "recommendation_id",
    "species_code",
    "common_name",
    "scientific_name",
    "recommendation_group",
    "rank_order",
    "confidence_label",
    "rationale_text",
    "caveats",
}
EVIDENCE_KEYS = {
    "evidence_id",
    "recommendation_id",
    "source",
    "source_table",
    "source_record_id",
    "evidence_type",
    "status",
    "retrieved_at",
    "summary",
    "payload",
    "caveats",
}
TRACE_KEYS = {
    "tool_trace_id",
    "step_order",
    "tool_name",
    "tool_status",
    "started_at",
    "completed_at",
    "input",
    "output_summary",
    "caveats",
}


def _assert_detail_contract(detail: dict[str, Any]) -> None:
    assert set(detail) == {"plan", "recommendations", "evidence", "weather", "media", "tool_traces"}
    assert set(detail["plan"]) == PLAN_KEYS
    assert all(set(row) == RECOMMENDATION_KEYS for row in detail["recommendations"])
    assert all(set(row) == EVIDENCE_KEYS for row in detail["evidence"])
    assert detail["weather"] is None or set(detail["weather"]) == EVIDENCE_KEYS
    assert all(set(row) == EVIDENCE_KEYS for row in detail["media"])
    assert all(set(row) == TRACE_KEYS for row in detail["tool_traces"])


def test_create_list_and_reload_persisted_trip_plan(tmp_path: Path) -> None:
    client = _client(tmp_path)
    response = client.post(
        "/api/trip-plans",
        json={
            "location": "34.54,-112.47",
            "start_at": "2026-07-10T06:00:00",
            "duration_minutes": 90,
            "skill_level": "beginner",
            "constraints": "focus on calls",
        },
    )
    assert response.status_code == 201
    created = response.json()
    _assert_detail_contract(created)
    plan_id = created["plan"]["trip_plan_id"]
    assert created["plan"]["plan_status"] == "complete"
    assert "High-likelihood species" in created["plan"]["field_plan_text"]
    assert created["weather"]["source"] == "open_meteo"
    assert {row["tool_name"] for row in created["tool_traces"]} >= {
        "synthesize_grounded_trip_plan",
        "persist_trip_plan",
    }
    assert created["media"] == []
    assert any(
        row["source"] == "xeno_canto" and row["status"] == "unavailable"
        for row in created["evidence"]
    )

    listed = client.get("/api/trip-plans")
    assert listed.status_code == 200
    list_body = listed.json()
    assert set(list_body) == {"plans"}
    assert set(list_body["plans"][0]) == PLAN_SUMMARY_KEYS
    assert list_body["plans"][0]["trip_plan_id"] == plan_id
    loaded = client.get(f"/api/trip-plans/{plan_id}")
    assert loaded.status_code == 200
    assert loaded.json() == created

    connection = duckdb.connect(str(tmp_path / "databox.duckdb"))
    connection.execute(
        """
        INSERT INTO birding_agent.trip_plan_recommendations
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [
            "rec-media",
            plan_id,
            None,
            "mexjay",
            "Mexican Jay",
            "Aphelocoma wollweberi",
            "high_likelihood",
            1,
            "high",
            "Recent evidence",
            "[]",
            "2026-07-09T12:00:00",
        ],
    )
    connection.execute(
        """
        INSERT INTO birding_agent.trip_plan_evidence
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [
            "media-available",
            plan_id,
            "rec-media",
            "xeno_canto",
            "recordings",
            "XC1",
            "media_context",
            "available",
            None,
            None,
            None,
            None,
            None,
            '{"english_name":"Mexican Jay","license":"CC BY 4.0",'
            '"recording_url":"https://xeno-canto.org/1"}',
            '{"recordist":"Ada Birder"}',
            "[]",
        ],
    )
    connection.close()

    detail_response = client.get(f"/api/trip-plans/{plan_id}")
    assert detail_response.status_code == 200
    detail = detail_response.json()
    _assert_detail_contract(detail)
    assert len(detail["recommendations"]) == 1
    assert len(detail["media"]) == 1
    assert detail["media"][0]["payload"]["recordist"] == "Ada Birder"
    assert all(row["status"] == "available" for row in detail["media"])


def test_validation_and_model_failures_are_stable_and_safe(tmp_path: Path) -> None:
    client = _client(tmp_path)
    invalid = client.post(
        "/api/trip-plans",
        json={"location": " ", "start_at": "not-a-date", "duration_minutes": 0},
    )
    assert invalid.status_code == 422
    assert invalid.json() == {
        "error": {
            "code": "invalid_request",
            "message": "Check the trip-planning inputs: duration_minutes, location, start_at",
        }
    }
    assert "traceback" not in invalid.text.lower()

    zoned = client.post(
        "/api/trip-plans",
        json={
            "location": "34.54,-112.47",
            "start_at": "2026-07-10T06:00:00Z",
            "duration_minutes": 60,
        },
    )
    assert zoned.status_code == 422
    assert zoned.json()["error"]["code"] == "invalid_request"

    extra = client.post(
        "/api/trip-plans",
        json={
            "location": "34.54,-112.47",
            "start_at": "2026-07-10T06:00:00",
            "duration_minutes": 60,
            "unexpected": "rejected",
        },
    )
    assert extra.status_code == 422
    assert extra.json()["error"]["code"] == "invalid_request"

    timed_out = _client(tmp_path, TimeoutModelClient()).post(
        "/api/trip-plans",
        json={
            "location": "34.54,-112.47",
            "start_at": "2026-07-10T06:00:00",
            "duration_minutes": 60,
        },
    )
    assert timed_out.status_code == 504
    assert timed_out.json() == {
        "error": {"code": "model_timeout", "message": "Cloudflare inference timed out; try again"}
    }
    assert "CF_WORKERS" not in timed_out.text

    unavailable = _client(tmp_path, UnavailableModelClient()).post(
        "/api/trip-plans",
        json={
            "location": "34.54,-112.47",
            "start_at": "2026-07-10T06:00:00",
            "duration_minutes": 60,
        },
    )
    assert unavailable.status_code == 503
    assert unavailable.json() == {
        "error": {
            "code": "model_unavailable",
            "message": "The configured model is unavailable",
        }
    }
    assert "untrusted provider details" not in unavailable.text


@pytest.mark.parametrize(
    ("account_id", "model_base_url"),
    [
        ("account-123", "https://arbitrary.example/client/v4"),
        ("account id is malformed", CLOUDFLARE_WORKERS_AI_MODEL),
    ],
)
def test_health_rejects_invalid_cloudflare_configuration(
    tmp_path: Path, monkeypatch, account_id: str, model_base_url: str
) -> None:
    database_path = tmp_path / "databox.duckdb"
    duckdb.connect(str(database_path)).close()
    monkeypatch.setattr(settings, "cf_workers_ai_api_key", SecretStr("configured-token"))
    monkeypatch.setattr(settings, "cf_workers_ai_account_id", account_id)
    monkeypatch.setattr(settings, "cf_workers_ai_model_base_url", model_base_url)
    client = TestClient(
        create_app(database_path=str(database_path), static_dir=tmp_path / "missing-dist")
    )

    assert client.get("/api/health").json() == {
        "status": "degraded",
        "database_ready": True,
        "model_ready": False,
    }


@pytest.mark.parametrize(
    "model_base_url",
    [
        CLOUDFLARE_WORKERS_AI_MODEL,
        "https://api.cloudflare.com/client/v4/accounts/{account_id}/ai/v1",
    ],
)
def test_health_accepts_strict_cloudflare_configuration(
    tmp_path: Path, monkeypatch, model_base_url: str
) -> None:
    database_path = tmp_path / "databox.duckdb"
    duckdb.connect(str(database_path)).close()
    monkeypatch.setattr(settings, "cf_workers_ai_api_key", SecretStr("configured-token"))
    monkeypatch.setattr(settings, "cf_workers_ai_account_id", "account-123")
    monkeypatch.setattr(settings, "cf_workers_ai_model_base_url", model_base_url)
    client = TestClient(
        create_app(database_path=str(database_path), static_dir=tmp_path / "missing-dist")
    )

    assert client.get("/api/health").json() == {
        "status": "ready",
        "database_ready": True,
        "model_ready": True,
    }


@pytest.mark.parametrize(
    ("model_client", "expected_status", "expected_ready"),
    [
        (FakeModelClient(), "ready", True),
        (WrongModelClient(), "degraded", False),
    ],
)
def test_health_requires_injected_client_allowlisted_model(
    tmp_path: Path,
    model_client: object,
    expected_status: str,
    expected_ready: bool,
) -> None:
    database_path = tmp_path / "databox.duckdb"
    duckdb.connect(str(database_path)).close()
    client = TestClient(
        create_app(
            database_path=str(database_path),
            model_client=model_client,  # type: ignore[arg-type]
            static_dir=tmp_path / "missing-dist",
        )
    )

    assert client.get("/api/health").json() == {
        "status": expected_status,
        "database_ready": True,
        "model_ready": expected_ready,
    }


def test_missing_plan_empty_history_health_and_database_busy(tmp_path: Path, monkeypatch) -> None:
    client = _client(tmp_path)
    assert client.get("/api/trip-plans").json() == {"plans": []}
    missing = client.get("/api/trip-plans/missing")
    assert missing.status_code == 404
    assert missing.json() == {"error": {"code": "not_found", "message": "Trip plan not found"}}
    health = client.get("/api/health").json()
    assert set(health) == {"status", "database_ready", "model_ready"}
    assert health["status"] in {"ready", "degraded"}
    assert type(health["database_ready"]) is bool
    assert type(health["model_ready"]) is bool
    assert "token" not in str(health).lower()

    real_connect = duckdb.connect
    connection = real_connect(str(tmp_path / "databox.duckdb"))
    connection.close()

    def busy(*args: object, **kwargs: object) -> Any:
        raise duckdb.IOException("Could not set lock on file: conflicting lock")

    monkeypatch.setattr(duckdb, "connect", busy)
    response = client.get("/api/trip-plans")
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "database_busy"
    monkeypatch.setattr(duckdb, "connect", real_connect)
