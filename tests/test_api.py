"""Local Birding Trip Copilot HTTP API contract tests."""

from __future__ import annotations

import hashlib
import json
import socket
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import duckdb
import pytest
from databox.agent_tools.open_meteo import ELEVATION_ENDPOINT, FORECAST_ENDPOINT
from databox.agent_tools.open_meteo_geocoding import GEOCODING_ENDPOINT
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


class CountingModelClient(FakeModelClient):
    calls = 0

    def synthesize(self, request: GroundedSynthesisRequest) -> GroundedSynthesisResult:
        self.calls += 1
        return super().synthesize(request)


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
        "hourly_units": {
            "time": "iso8601",
            "temperature_2m": "°C",
            "relative_humidity_2m": "%",
            "precipitation_probability": "%",
            "precipitation": "mm",
            "weather_code": "wmo code",
            "wind_speed_10m": "km/h",
            "wind_gusts_10m": "km/h",
        },
        "hourly": {
            "time": ["2026-07-10T06:00"],
            "temperature_2m": [18.0],
            "relative_humidity_2m": [40],
            "precipitation_probability": [0],
            "precipitation": [0],
            "weather_code": [0],
            "wind_speed_10m": [5],
            "wind_gusts_10m": [9],
        },
    }


def _geocoding(endpoint: str, params: Mapping[str, object]) -> dict[str, Any]:
    assert endpoint == GEOCODING_ENDPOINT
    assert params["name"] == "Prescott"
    return {
        "results": [
            {
                "name": "Prescott",
                "admin1": "Arizona",
                "country": "United States",
                "country_code": "US",
                "latitude": 34.54002,
                "longitude": -112.4685,
                "elevation": 1638.0,
                "timezone": "America/Phoenix",
            },
            {
                "name": "Prescott",
                "admin1": "Arkansas",
                "country": "United States",
                "country_code": "US",
                "latitude": 33.80261,
                "longitude": -93.38101,
                "timezone": "America/Chicago",
            },
        ]
    }


def _empty_media(endpoint: str, params: Mapping[str, object]) -> dict[str, Any]:
    _ = params
    return {"results": []} if "gbif" in endpoint else {"recordings": []}


def _client(
    tmp_path: Path,
    model: object | None = None,
    geocoding_getter: object = _geocoding,
    weather_getter: object = _weather,
) -> TestClient:
    return TestClient(
        create_app(
            database_path=str(tmp_path / "databox.duckdb"),
            model_client=model or FakeModelClient(),  # type: ignore[arg-type]
            weather_getter=weather_getter,  # type: ignore[arg-type]
            geocoding_getter=geocoding_getter,  # type: ignore[arg-type]
            media_gbif_getter=_empty_media,
            media_xeno_getter=_empty_media,
            xeno_api_key="test-key",
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
    "timezone",
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
    "photo",
    "call",
}
PHOTO_KEYS = {
    "status",
    "source_record_id",
    "species_name",
    "display_url",
    "source_url",
    "creator",
    "rights_holder",
    "publisher",
    "format",
    "license_text",
    "license_url",
    "selection_reason",
    "caveats",
}
CALL_KEYS = {
    "status",
    "source_record_id",
    "recording_id",
    "species_name",
    "geographic_scope",
    "recording_type",
    "quality",
    "recordist",
    "locality",
    "country",
    "source_url",
    "audio_url",
    "license_text",
    "license_url",
    "selection_reason",
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
MEDIA_KEYS = {
    "evidence_id",
    "recommendation_id",
    "source_record_id",
    "recording_id",
    "status",
    "species_name",
    "recording_type",
    "quality",
    "recordist",
    "license_text",
    "license_url",
    "source_url",
    "audio_url",
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
    assert all(set(row["photo"]) == PHOTO_KEYS for row in detail["recommendations"])
    assert all(set(row["call"]) == CALL_KEYS for row in detail["recommendations"])
    assert all(set(row) == EVIDENCE_KEYS for row in detail["evidence"])
    assert detail["weather"] is None or set(detail["weather"]) == EVIDENCE_KEYS
    assert all(set(row) == MEDIA_KEYS for row in detail["media"])
    assert all(set(row) == TRACE_KEYS for row in detail["tool_traces"])


def test_location_search_normalizes_query_and_returns_only_arizona(tmp_path: Path) -> None:
    client = _client(tmp_path)

    response = client.get("/api/locations", params={"q": "Prescott, Arizona"})

    assert response.status_code == 200
    assert response.json() == {
        "locations": [
            {
                "display_name": "Prescott, Arizona, United States",
                "latitude": 34.54002,
                "longitude": -112.4685,
                "timezone": "America/Phoenix",
                "region_code": "US-AZ",
            }
        ]
    }


def test_location_search_failure_is_safe_and_coordinate_fallback_remains(
    tmp_path: Path,
) -> None:
    def unavailable(endpoint: str, params: Mapping[str, object]) -> dict[str, Any]:
        _ = endpoint, params
        raise socket.timeout("private upstream detail")  # noqa: UP041

    client = _client(tmp_path, geocoding_getter=unavailable)
    failed = client.get("/api/locations", params={"q": "Prescott"})
    assert failed.status_code == 503
    assert failed.json() == {
        "error": {
            "code": "geocoder_unavailable",
            "message": (
                "Location search is temporarily unavailable; enter valid Arizona coordinates"
            ),
        }
    }
    assert "private upstream detail" not in failed.text

    created = client.post(
        "/api/trip-plans",
        json={
            "location": "34.54,-112.47",
            "start_at": "2026-07-10T06:00:00",
            "duration_minutes": 60,
        },
    )
    assert created.status_code == 201


def test_invalid_coordinates_fail_before_database_weather_or_model(tmp_path: Path) -> None:
    model = CountingModelClient()
    weather_calls = 0

    def weather(endpoint: str, params: Mapping[str, object]) -> dict[str, Any]:
        nonlocal weather_calls
        _ = endpoint, params
        weather_calls += 1
        raise AssertionError("weather must not run")

    client = _client(tmp_path, model=model, weather_getter=weather)
    payload = {
        "start_at": "2026-07-10T06:00:00",
        "duration_minutes": 60,
    }

    missing_sign = client.post("/api/trip-plans", json={**payload, "location": "34.54,112.50"})
    assert missing_sign.status_code == 400
    assert missing_sign.json()["error"]["code"] == "invalid_location"
    assert "Arizona longitudes are negative" in missing_sign.json()["error"]["message"]
    assert "34.5400,-112.5000" in missing_sign.json()["error"]["message"]

    outside = client.post("/api/trip-plans", json={**payload, "location": "40.71,-74.00"})
    assert outside.status_code == 400
    assert outside.json() == {
        "error": {
            "code": "invalid_location",
            "message": "The current bird dataset supports Arizona locations only",
        }
    }
    assert model.calls == 0
    assert weather_calls == 0
    assert not (tmp_path / "databox.duckdb").exists()


def test_selected_arizona_location_persists_name_coordinates_region_and_timezone(
    tmp_path: Path,
) -> None:
    client = _client(tmp_path)
    response = client.post(
        "/api/trip-plans",
        json={
            "location": "Prescott, Arizona, United States",
            "location_selection": {
                "display_name": "Prescott, Arizona, United States",
                "latitude": 34.54002,
                "longitude": -112.4685,
                "timezone": "America/Phoenix",
                "region_code": "US-AZ",
            },
            "start_at": "2026-07-10T06:00:00",
            "duration_minutes": 60,
        },
    )

    assert response.status_code == 201
    plan = response.json()["plan"]
    assert plan["normalized_location_name"] == "Prescott, Arizona, United States"
    assert plan["latitude"] == pytest.approx(34.54002)
    assert plan["longitude"] == pytest.approx(-112.4685)
    assert plan["region_code"] == "US-AZ"
    assert plan["timezone"] == "America/Phoenix"


def test_source_scientific_name_survives_lookup_persistence_and_api_reload(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "databox.duckdb"
    connection = duckdb.connect(str(database_path))
    connection.execute("CREATE SCHEMA birding_agent")
    connection.execute(
        """
        CREATE TABLE birding_agent.gbif_occurrence_evidence AS
        SELECT
            'gbif-western-bluebird'::TEXT AS occurrence_evidence_id,
            'raw_gbif.occurrences'::TEXT AS source_table,
            '5938231789'::TEXT AS source_record_id,
            'wesblu'::TEXT AS species_code,
            'Sialia mexicana'::TEXT AS scientific_name,
            'Sialia occidentalis Townsend, 1837'::TEXT AS source_scientific_name,
            'Sialia mexicana Swainson, 1832'::TEXT AS accepted_scientific_name,
            'Western Bluebird'::TEXT AS common_name,
            'Turdidae'::TEXT AS family,
            'Sialia'::TEXT AS genus,
            34.54::DOUBLE AS latitude,
            -112.47::DOUBLE AS longitude,
            'Prescott'::TEXT AS locality,
            'Arizona'::TEXT AS state_province,
            '2025-07-01'::TEXT AS event_date_text,
            2025::BIGINT AS year,
            7::BIGINT AS month,
            'HUMAN_OBSERVATION'::TEXT AS basis_of_record,
            'PRESENT'::TEXT AS occurrence_status,
            'CC_BY_4_0'::TEXT AS license,
            'https://www.gbif.org/occurrence/5938231789'::TEXT AS source_reference_url,
            '2026-07-09T12:00:00'::TEXT AS loaded_at,
            'Arizona'::TEXT AS _query_state_province
        """
    )
    connection.close()
    media_calls = 0

    def gbif_media(endpoint: str, params: Mapping[str, object]) -> dict[str, Any]:
        nonlocal media_calls
        media_calls += 1
        species = str(params["scientificName"])
        return {
            "results": [
                {
                    "key": 5938231789,
                    "species": species,
                    "acceptedScientificName": species,
                    "countryCode": "US",
                    "country": "United States",
                    "stateProvince": "Arizona",
                    "publishingOrgKey": "Fixture publisher",
                    "media": [
                        {
                            "type": "StillImage",
                            "format": "image/jpeg",
                            "identifier": "https://images.inaturalist.org/bluebird.jpg",
                            "license": "https://creativecommons.org/licenses/by/4.0/",
                            "creator": "Fixture Photographer",
                        }
                    ],
                }
            ]
        }

    def xeno_media(endpoint: str, params: Mapping[str, object]) -> dict[str, Any]:
        nonlocal media_calls
        media_calls += 1
        return {
            "recordings": [
                {
                    "id": "314",
                    "gen": "Sialia",
                    "sp": "mexicana",
                    "rec": "Fixture Recordist",
                    "cnt": "United States",
                    "loc": "Arizona",
                    "type": "call",
                    "q": "A",
                    "url": "https://xeno-canto.org/314",
                    "file": "https://xeno-canto.org/314/download",
                    "lic": "https://creativecommons.org/licenses/by-nc-sa/4.0/",
                }
            ]
        }

    client = TestClient(
        create_app(
            database_path=str(database_path),
            model_client=FakeModelClient(),
            weather_getter=_weather,
            geocoding_getter=_geocoding,
            media_gbif_getter=gbif_media,
            media_xeno_getter=xeno_media,
            xeno_api_key="test-key",
            static_dir=tmp_path / "missing-dist",
        )
    )

    created_response = client.post(
        "/api/trip-plans",
        json={
            "location": "34.54,-112.47",
            "start_at": "2026-07-10T06:00:00",
            "duration_minutes": 60,
        },
    )

    assert created_response.status_code == 201
    created = created_response.json()
    recommendation = next(
        row for row in created["recommendations"] if row["common_name"] == "Western Bluebird"
    )
    assert recommendation["scientific_name"] == "Sialia mexicana"
    assert recommendation["photo"] == {
        "status": "available",
        "source_record_id": "5938231789",
        "species_name": "Sialia mexicana",
        "display_url": (
            "https://api.gbif.org/v1/image/cache/500x500/occurrence/5938231789/media/"
            + hashlib.md5(
                b"https://images.inaturalist.org/bluebird.jpg", usedforsecurity=False
            ).hexdigest()
        ),
        "source_url": "https://www.gbif.org/occurrence/5938231789",
        "creator": "Fixture Photographer",
        "rights_holder": None,
        "publisher": "Fixture publisher",
        "format": "image/jpeg",
        "license_text": "CC BY 4.0",
        "license_url": "https://creativecommons.org/licenses/by/4.0/",
        "selection_reason": (
            "Exact Arizona species image with complete attribution, supported CC license, "
            "and GBIF cache URL derived from occurrence key plus identifier MD5"
        ),
        "caveats": [],
    }
    assert recommendation["call"]["status"] == "available"
    assert recommendation["call"]["recording_id"] == "314"
    assert recommendation["call"]["geographic_scope"] == "Arizona"
    assert recommendation["call"]["audio_url"] == "https://xeno-canto.org/314/download"
    assert media_calls == 2
    gbif_evidence = next(
        row
        for row in created["evidence"]
        if row["source"] == "gbif" and row["evidence_type"] == "occurrence_context"
    )
    expected_names = {
        "common_name": "Western Bluebird",
        "scientific_name": "Sialia mexicana",
        "source_scientific_name": "Sialia occidentalis Townsend, 1837",
        "accepted_scientific_name": "Sialia mexicana Swainson, 1832",
    }
    assert {key: gbif_evidence["summary"][key] for key in expected_names} == expected_names
    assert gbif_evidence["payload"]["scientific_name"] == "Sialia mexicana"
    assert (
        gbif_evidence["payload"]["source_scientific_name"] == "Sialia occidentalis Townsend, 1837"
    )
    assert gbif_evidence["payload"]["accepted_scientific_name"] == "Sialia mexicana Swainson, 1832"

    loaded = client.get(f"/api/trip-plans/{created['plan']['trip_plan_id']}")
    assert loaded.status_code == 200
    assert loaded.json()["recommendations"][0]["photo"] == recommendation["photo"]
    assert loaded.json()["recommendations"][0]["call"] == recommendation["call"]
    assert media_calls == 2
    loaded_gbif = next(
        row
        for row in loaded.json()["evidence"]
        if row["source"] == "gbif" and row["evidence_type"] == "occurrence_context"
    )
    assert loaded_gbif["summary"] == gbif_evidence["summary"]
    assert loaded_gbif["payload"] == gbif_evidence["payload"]

    persisted_photo = next(
        row for row in created["evidence"] if row["evidence_type"] == "recommendation_photo"
    )
    assert "original_media_identifier" not in persisted_photo["payload"]
    assert "original_media_identifier_md5" in persisted_photo["payload"]
    tampered_summary = dict(persisted_photo["summary"])
    tampered_summary["display_url"] = "https://api.gbif.org/v1/occurrence/search"
    connection = duckdb.connect(str(database_path))
    connection.execute(
        "UPDATE birding_agent.trip_plan_evidence SET summary_json = ? WHERE evidence_id = ?",
        [json.dumps(tampered_summary), persisted_photo["evidence_id"]],
    )
    connection.close()
    tampered = client.get(f"/api/trip-plans/{created['plan']['trip_plan_id']}")
    assert tampered.status_code == 200
    assert tampered.json()["recommendations"][0]["photo"]["status"] == "unavailable"
    assert tampered.json()["recommendations"][0]["photo"]["display_url"] is None


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
    assert created["weather"]["payload"]["forecast_summary"] == {
        "temperature_2m_min": 18.0,
        "temperature_2m_max": 18.0,
        "temperature_2m_avg": 18.0,
        "relative_humidity_2m_avg": 40.0,
        "precipitation_probability_max": 0.0,
        "precipitation_sum": 0.0,
        "wind_speed_10m_max": 5.0,
        "wind_gusts_10m_max": 9.0,
        "weather_codes": [0],
    }
    assert created["weather"]["payload"]["elevation_m"] == 1642.0
    assert {row["tool_name"] for row in created["tool_traces"]} >= {
        "synthesize_grounded_trip_plan",
        "persist_trip_plan",
    }
    assert created["media"] == []
    assert created["recommendations"] == []

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
            '{"english_name":"Mexican Jay","recording_type":"call","quality":"A",'
            '"license":"https://creativecommons.org/licenses/by/4.0/",'
            '"recording_url":"https://xeno-canto.org/1"}',
            '{"recording_id":"1","recordist":"Ada Birder",'
            '"audio_file_url":"https://xeno-canto.org/1/download"}',
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
    assert detail["media"][0] == {
        "evidence_id": "media-available",
        "recommendation_id": "rec-media",
        "source_record_id": "XC1",
        "recording_id": "1",
        "status": "available",
        "species_name": "Mexican Jay",
        "recording_type": "call",
        "quality": "A",
        "recordist": "Ada Birder",
        "license_text": "CC BY 4.0",
        "license_url": "https://creativecommons.org/licenses/by/4.0/",
        "source_url": "https://xeno-canto.org/1",
        "audio_url": "https://xeno-canto.org/1/download",
        "caveats": [],
    }
    raw_media = next(row for row in detail["evidence"] if row["evidence_id"] == "media-available")
    assert raw_media["payload"]["audio_file_url"] == "https://xeno-canto.org/1/download"


def test_media_response_sanitizes_source_and_audio_independently(tmp_path: Path) -> None:
    client = _client(tmp_path)
    created = client.post(
        "/api/trip-plans",
        json={
            "location": "34.54,-112.47",
            "start_at": "2026-07-10T06:00:00",
            "duration_minutes": 90,
        },
    ).json()
    plan_id = created["plan"]["trip_plan_id"]
    cases = [
        ("source-safe", "https://xeno-canto.org/1", "javascript:alert(1)", "CC BY 4.0"),
        ("audio-safe", "javascript:alert(1)", "https://xeno-canto.org/2/download", "CC BY 4.0"),
        (
            "credentials",
            "https://user@xeno-canto.org/3",
            "https://user@xeno-canto.org/3/download",
            "CC BY 4.0",
        ),
        (
            "port",
            "https://xeno-canto.org:443/4",
            "https://xeno-canto.org:443/4/download",
            "CC BY 4.0",
        ),
        (
            "subdomain",
            "https://media.xeno-canto.org/5",
            "https://media.xeno-canto.org/5/download",
            "CC BY 4.0",
        ),
        ("path", "https://xeno-canto.org/about", "https://xeno-canto.org/6/file.mp3", "CC BY 4.0"),
        ("sentinel", "unavailable", "not available", "CC BY 4.0"),
        ("malformed", "https://[", "https://[", "CC BY 4.0"),
        (
            "mismatch",
            "https://xeno-canto.org/99",
            "https://xeno-canto.org/99/download",
            "CC BY 4.0",
        ),
        (
            "www-safe",
            "https://www.xeno-canto.org/10",
            "https://www.xeno-canto.org/10/download",
            "//creativecommons.org/licenses/by-nc-sa/4.0/",
        ),
        (
            "unsafe-license",
            "https://xeno-canto.org/11",
            "https://xeno-canto.org/11/download",
            "https://evil.example/license",
        ),
        (
            "missing-id",
            "https://xeno-canto.org/12",
            "https://xeno-canto.org/12/download",
            "CC BY 4.0",
        ),
        ("audio-missing", "https://xeno-canto.org/13", None, "CC BY 4.0"),
        (
            "audio-unavailable",
            "https://xeno-canto.org/14",
            "unavailable",
            "CC BY 4.0",
        ),
        (
            "unknown-cc-license",
            "https://xeno-canto.org/15",
            "https://xeno-canto.org/15/download",
            "https://creativecommons.org/licenses/sampling/1.0/",
        ),
        (
            "insane-cc-version",
            "https://xeno-canto.org/16",
            "https://xeno-canto.org/16/download",
            "https://creativecommons.org/licenses/by/999.999/",
        ),
        (
            "malformed-cc-version",
            "https://xeno-canto.org/17",
            "https://xeno-canto.org/17/download",
            "https://creativecommons.org/licenses/by/4..0/",
        ),
    ]
    connection = duckdb.connect(str(tmp_path / "databox.duckdb"))
    for index, (name, source_url, audio_url, license_value) in enumerate(cases, start=1):
        recording_id = "unknown" if name == "missing-id" else str(index)
        connection.execute(
            """
            INSERT INTO birding_agent.trip_plan_evidence
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                f"media-{name}",
                plan_id,
                None,
                "xeno_canto",
                "recordings",
                f"XC{recording_id}",
                "media_context",
                "available",
                None,
                None,
                None,
                None,
                None,
                json.dumps(
                    {
                        "english_name": "Mexican Jay",
                        "recording_type": "call",
                        "quality": "A",
                        "license": license_value,
                        "recording_url": source_url,
                    }
                ),
                json.dumps(
                    {
                        "recording_id": recording_id,
                        "recordist": "Ada Birder",
                        "audio_file_url": audio_url,
                    }
                ),
                "[]",
            ],
        )
    connection.close()

    response = client.get(f"/api/trip-plans/{plan_id}")
    assert response.status_code == 200
    media = {row["evidence_id"]: row for row in response.json()["media"]}
    assert media["media-source-safe"]["recording_id"] == "1"
    assert media["media-source-safe"]["source_url"] == "https://xeno-canto.org/1"
    assert media["media-source-safe"]["audio_url"] is None
    assert media["media-audio-safe"]["recording_id"] == "2"
    assert media["media-audio-safe"]["source_url"] is None
    assert media["media-audio-safe"]["audio_url"] == "https://xeno-canto.org/2/download"
    for name in (
        "credentials",
        "port",
        "subdomain",
        "path",
        "sentinel",
        "malformed",
        "mismatch",
        "missing-id",
    ):
        assert media[f"media-{name}"]["source_url"] is None
        assert media[f"media-{name}"]["audio_url"] is None
    assert media["media-missing-id"]["recording_id"] is None
    assert media["media-www-safe"]["recording_id"] == "10"
    assert media["media-www-safe"]["source_url"] == "https://www.xeno-canto.org/10"
    assert media["media-www-safe"]["audio_url"] == "https://www.xeno-canto.org/10/download"
    assert media["media-www-safe"]["license_text"] == "CC BY-NC-SA 4.0"
    assert (
        media["media-www-safe"]["license_url"]
        == "https://creativecommons.org/licenses/by-nc-sa/4.0/"
    )
    for name in (
        "unsafe-license",
        "unknown-cc-license",
        "insane-cc-version",
        "malformed-cc-version",
    ):
        assert media[f"media-{name}"]["status"] == "unavailable"
        assert media[f"media-{name}"]["license_text"] == "License link unavailable"
        assert media[f"media-{name}"]["license_url"] is None
        assert media[f"media-{name}"]["source_url"] is None
        assert media[f"media-{name}"]["audio_url"] is None
    assert media["media-audio-missing"]["source_url"] == "https://xeno-canto.org/13"
    assert media["media-audio-missing"]["audio_url"] is None
    assert media["media-audio-unavailable"]["source_url"] == "https://xeno-canto.org/14"
    assert media["media-audio-unavailable"]["audio_url"] is None
    assert all(set(row) == MEDIA_KEYS for row in media.values())


def test_media_response_requires_one_consistent_recording_identity(tmp_path: Path) -> None:
    client = _client(tmp_path)
    created = client.post(
        "/api/trip-plans",
        json={
            "location": "34.54,-112.47",
            "start_at": "2026-07-10T06:00:00",
            "duration_minutes": 90,
        },
    ).json()
    plan_id = created["plan"]["trip_plan_id"]
    rows = [
        (
            "identifier-conflict",
            "XC1",
            {"recording_id": "1", "recording_url": "https://xeno-canto.org/1"},
            {"recording_id": "2", "audio_file_url": "https://xeno-canto.org/1/download"},
        ),
        (
            "same-id-forms",
            "XC2",
            {
                "source_record_id": "2",
                "recording_id": "XC2",
                "recording_url": "https://xeno-canto.org/2",
            },
            {
                "source_record_id": "XC002",
                "recording_id": "002",
                "audio_file_url": "https://xeno-canto.org/2/download",
            },
        ),
        (
            "url-cross-mismatch",
            "XC3",
            {"recording_id": "3", "recording_url": "https://xeno-canto.org/3"},
            {"recording_id": "XC3", "audio_file_url": "https://xeno-canto.org/4/download"},
        ),
        (
            "malformed-source-id",
            "XC4oops",
            {"recording_id": "4", "recording_url": "https://xeno-canto.org/4"},
            {"recording_id": "4", "audio_file_url": "https://xeno-canto.org/4/download"},
        ),
        (
            "malformed-summary-id",
            "XC5",
            {"recording_id": "5.0", "recording_url": "https://xeno-canto.org/5"},
            {"recording_id": "5", "audio_file_url": "https://xeno-canto.org/5/download"},
        ),
        (
            "malformed-payload-id",
            "XC6",
            {"recording_id": "6", "recording_url": "https://xeno-canto.org/6"},
            {"recording_id": "xc6", "audio_file_url": "https://xeno-canto.org/6/download"},
        ),
        (
            "non-string-id",
            "XC7",
            {"recording_id": "7", "recording_url": "https://xeno-canto.org/7"},
            {"recording_id": 7, "audio_file_url": "https://xeno-canto.org/7/download"},
        ),
    ]
    connection = duckdb.connect(str(tmp_path / "databox.duckdb"))
    for name, source_record_id, summary, payload in rows:
        summary.update({"english_name": "Mexican Jay", "license": "CC BY 4.0"})
        payload.update({"recordist": "Ada Birder"})
        connection.execute(
            """
            INSERT INTO birding_agent.trip_plan_evidence
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                f"media-{name}",
                plan_id,
                None,
                "xeno_canto",
                "recordings",
                source_record_id,
                "media_context",
                "available",
                None,
                None,
                None,
                None,
                None,
                json.dumps(summary),
                json.dumps(payload),
                "[]",
            ],
        )
    connection.close()

    response = client.get(f"/api/trip-plans/{plan_id}")
    assert response.status_code == 200
    media = {row["evidence_id"]: row for row in response.json()["media"]}

    conflicting = media["media-identifier-conflict"]
    assert conflicting["recording_id"] is None
    assert conflicting["source_url"] is None
    assert conflicting["audio_url"] is None

    consistent = media["media-same-id-forms"]
    assert consistent["recording_id"] == "2"
    assert consistent["source_url"] == "https://xeno-canto.org/2"
    assert consistent["audio_url"] == "https://xeno-canto.org/2/download"

    cross_mismatch = media["media-url-cross-mismatch"]
    assert cross_mismatch["recording_id"] == "3"
    assert cross_mismatch["source_url"] == "https://xeno-canto.org/3"
    assert cross_mismatch["audio_url"] is None

    for name in (
        "malformed-source-id",
        "malformed-summary-id",
        "malformed-payload-id",
        "non-string-id",
    ):
        malformed = media[f"media-{name}"]
        assert malformed["recording_id"] is None
        assert malformed["source_url"] is None
        assert malformed["audio_url"] is None


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
