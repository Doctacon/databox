"""Open-Meteo trip context tool tests."""

from __future__ import annotations

import json
from collections.abc import Mapping
from datetime import datetime
from typing import Any

import duckdb
from databox.agent_tools.open_meteo import (
    ELEVATION_ENDPOINT,
    FORECAST_ENDPOINT,
    fetch_open_meteo_trip_context,
    persist_open_meteo_evidence,
)
from databox.agent_tools.persistence import ensure_birding_agent_persistence_tables


def _forecast_response() -> dict[str, Any]:
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
            "time": [
                "2026-07-09T05:00",
                "2026-07-09T06:00",
                "2026-07-09T07:00",
                "2026-07-09T08:00",
                "2026-07-09T09:00",
            ],
            "temperature_2m": [19.0, 20.0, 21.5, 23.0, 28.0],
            "relative_humidity_2m": [62, 60, 55, 50, 30],
            "precipitation_probability": [0, 5, 10, 20, 90],
            "precipitation": [0.0, 0.0, 0.1, 0.2, 4.0],
            "weather_code": [0, 0, 1, 2, 95],
            "wind_speed_10m": [3.0, 4.0, 5.5, 7.0, 18.0],
            "wind_gusts_10m": [5.0, 6.0, 8.0, 10.0, 30.0],
        },
    }


def test_fetch_open_meteo_trip_context_normalizes_window_and_units() -> None:
    calls: list[tuple[str, Mapping[str, object]]] = []

    def fake_get_json(endpoint: str, params: Mapping[str, object]) -> dict[str, Any]:
        calls.append((endpoint, params))
        if endpoint == FORECAST_ENDPOINT:
            return _forecast_response()
        if endpoint == ELEVATION_ENDPOINT:
            return {"elevation": [1642.0]}
        raise AssertionError(f"unexpected endpoint {endpoint}")

    context = fetch_open_meteo_trip_context(
        latitude=34.54,
        longitude=-112.47,
        start_at=datetime.fromisoformat("2026-07-09T06:00:00"),
        end_at=datetime.fromisoformat("2026-07-09T09:00:00"),
        timezone="America/Phoenix",
        http_get_json=fake_get_json,
    )

    assert context.status == "available"
    assert context.elevation_m == 1642.0
    assert context.units["temperature"] == "°C"
    assert context.units["precipitation"] == "mm"
    assert len(context.hourly) == 3
    assert context.hourly[0]["time"] == "2026-07-09T06:00"
    assert context.forecast_summary == {
        "temperature_2m_min": 20.0,
        "temperature_2m_max": 23.0,
        "temperature_2m_avg": 21.5,
        "relative_humidity_2m_avg": 55.0,
        "precipitation_probability_max": 20.0,
        "precipitation_sum": 0.3,
        "wind_speed_10m_max": 7.0,
        "wind_gusts_10m_max": 10.0,
        "weather_codes": [0, 1, 2],
    }
    assert not context.caveats
    assert calls[0][0] == FORECAST_ENDPOINT
    assert calls[0][1]["start_date"] == "2026-07-09"
    assert calls[0][1]["end_date"] == "2026-07-09"
    assert calls[0][1]["timezone"] == "America/Phoenix"
    assert calls[0][1]["temperature_unit"] == "celsius"
    assert calls[0][1]["wind_speed_unit"] == "kmh"
    assert calls[0][1]["precipitation_unit"] == "mm"
    assert calls[1][0] == ELEVATION_ENDPOINT


def test_provider_wind_inconsistency_preserves_values_and_persists_caveat() -> None:
    def fake_get_json(endpoint: str, params: Mapping[str, object]) -> dict[str, Any]:
        if endpoint == FORECAST_ENDPOINT:
            response = _forecast_response()
            hourly = response["hourly"]
            hourly["wind_speed_10m"] = [3.0, 23.3, 26.0, 25.0, 18.0]
            hourly["wind_gusts_10m"] = [5.0, 19.1, 21.2, 20.0, 30.0]
            return response
        return {"elevation": [1642.0]}

    context = fetch_open_meteo_trip_context(
        latitude=34.54,
        longitude=-112.47,
        start_at="2026-07-09T06:00:00",
        end_at="2026-07-09T08:00:00",
        timezone="America/Phoenix",
        http_get_json=fake_get_json,
    )

    assert [row["wind_speed_10m"] for row in context.hourly] == [23.3, 26.0]
    assert [row["wind_gusts_10m"] for row in context.hourly] == [19.1, 21.2]
    assert context.forecast_summary["wind_speed_10m_max"] == 26.0
    assert context.forecast_summary["wind_gusts_10m_max"] == 21.2
    assert context.caveats == [
        "Open-Meteo reported a lower maximum 10 m gust than maximum 10 m wind speed "
        "for this window; both source values are shown unchanged"
    ]

    con = duckdb.connect(":memory:")
    persist_open_meteo_evidence(
        con,
        context,
        trip_plan_id="trip-inconsistent-wind",
        evidence_id="evidence-inconsistent-wind",
    )
    persisted = con.execute(
        "SELECT payload_json, caveats_json FROM birding_agent.trip_plan_evidence "
        "WHERE evidence_id = ?",
        ["evidence-inconsistent-wind"],
    ).fetchone()
    assert persisted is not None
    assert json.loads(persisted[0])["forecast_summary"]["wind_speed_10m_max"] == 26.0
    assert json.loads(persisted[0])["forecast_summary"]["wind_gusts_10m_max"] == 21.2
    assert json.loads(persisted[1]) == context.caveats


def test_fetch_open_meteo_trip_context_returns_unavailable_on_api_errors() -> None:
    def failing_get_json(endpoint: str, params: Mapping[str, object]) -> dict[str, Any]:
        raise RuntimeError(f"boom from {endpoint}")

    context = fetch_open_meteo_trip_context(
        latitude=34.54,
        longitude=-112.47,
        start_at="2026-07-09T06:00:00",
        end_at="2026-07-09T09:00:00",
        http_get_json=failing_get_json,
    )

    assert context.status == "unavailable"
    assert context.forecast_summary == {}
    assert context.hourly == []
    assert context.elevation_m is None
    assert len(context.caveats) == 2
    assert "forecast unavailable" in context.caveats[0]
    assert "elevation unavailable" in context.caveats[1]


def test_fetch_open_meteo_trip_context_returns_partial_for_empty_window() -> None:
    def fake_get_json(endpoint: str, params: Mapping[str, object]) -> dict[str, Any]:
        if endpoint == FORECAST_ENDPOINT:
            return _forecast_response()
        return {"elevation": [1642.0]}

    context = fetch_open_meteo_trip_context(
        latitude=34.54,
        longitude=-112.47,
        start_at="2026-07-09T12:00:00",
        end_at="2026-07-09T13:00:00",
        http_get_json=fake_get_json,
    )

    assert context.status == "partial"
    assert context.hourly == []
    assert context.elevation_m == 1642.0
    assert context.caveats == [
        "Open-Meteo forecast returned no hourly rows for the requested window"
    ]


def test_ensure_birding_agent_persistence_tables_creates_sql_interfaces() -> None:
    con = duckdb.connect(":memory:")

    ensure_birding_agent_persistence_tables(con)

    tables = {
        row[0]
        for row in con.execute(
            """
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = 'birding_agent'
            """
        ).fetchall()
    }
    assert tables == {
        "trip_plans",
        "trip_plan_recommendations",
        "trip_plan_evidence",
        "trip_plan_tool_traces",
    }

    evidence_columns = {
        row[0]
        for row in con.execute(
            """
            SELECT column_name
            FROM information_schema.columns
            WHERE table_schema = 'birding_agent'
              AND table_name = 'trip_plan_evidence'
            """
        ).fetchall()
    }
    assert {
        "evidence_id",
        "trip_plan_id",
        "recommendation_id",
        "source",
        "source_table",
        "source_record_id",
        "evidence_type",
        "payload_json",
    } <= evidence_columns


def test_persist_open_meteo_evidence_writes_trip_plan_artifact() -> None:
    def fake_get_json(endpoint: str, params: Mapping[str, object]) -> dict[str, Any]:
        if endpoint == FORECAST_ENDPOINT:
            return _forecast_response()
        return {"elevation": [1642.0]}

    context = fetch_open_meteo_trip_context(
        latitude=34.54,
        longitude=-112.47,
        start_at="2026-07-09T06:00:00",
        end_at="2026-07-09T09:00:00",
        http_get_json=fake_get_json,
    )
    con = duckdb.connect(":memory:")

    evidence_id = persist_open_meteo_evidence(
        con,
        context,
        trip_plan_id="trip-thumb-butte",
        evidence_id="evidence-open-meteo",
    )

    assert evidence_id == "evidence-open-meteo"
    row = con.execute(
        """
        SELECT trip_plan_id, source, evidence_type, status, summary_json, payload_json, caveats_json
        FROM birding_agent.trip_plan_evidence
        WHERE evidence_id = ?
        """,
        [evidence_id],
    ).fetchone()
    assert row is not None
    assert row[0] == "trip-thumb-butte"
    assert row[1] == "open_meteo"
    assert row[2] == "weather_elevation_context"
    assert row[3] == "available"
    summary = json.loads(row[4])
    payload = json.loads(row[5])
    caveats = json.loads(row[6])
    assert summary["elevation_m"] == 1642.0
    assert payload["source"] == "open_meteo"
    assert payload["forecast_summary"]["temperature_2m_avg"] == 21.5
    assert caveats == []
