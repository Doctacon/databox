"""Birding Trip Copilot planner runtime tests."""

from __future__ import annotations

import json
from collections.abc import Mapping
from datetime import datetime
from pathlib import Path
from typing import Any, cast

import duckdb
import pytest
from databox.agent_tools.open_meteo import ELEVATION_ENDPOINT, FORECAST_ENDPOINT
from databox.agents.birding_trip_planner import (
    BirdingTripPlanner,
    TripRequest,
    build_root_agent,
    main,
    resolve_arizona_location,
    run_trip_planner_agent,
    run_trip_planner_agent_async,
)
from databox.agents.cloudflare_workers_ai import (
    CLOUDFLARE_WORKERS_AI_MODEL,
    CloudflareAuthenticationError,
    GroundedSynthesisRequest,
    GroundedSynthesisResult,
)


class FailingTripPlanModelClient:
    model = CLOUDFLARE_WORKERS_AI_MODEL

    def synthesize(self, request: GroundedSynthesisRequest) -> GroundedSynthesisResult:
        _ = request
        raise CloudflareAuthenticationError("Cloudflare Workers AI authentication failed")


class FakeTripPlanModelClient:
    model = CLOUDFLARE_WORKERS_AI_MODEL

    def __init__(self) -> None:
        self.requests: list[GroundedSynthesisRequest] = []

    def synthesize(self, request: GroundedSynthesisRequest) -> GroundedSynthesisResult:
        self.requests.append(request)
        return GroundedSynthesisResult.model_validate(
            {
                "action_ids": ["listen_first", "scan_habitat_edges"],
                "grounding": {
                    "requested_location": request.requested_location,
                    "window_start": request.window_start,
                    "window_end": request.window_end,
                    "duration_minutes": request.duration_minutes,
                    "recommendation_ids": [
                        item.recommendation_id for item in request.recommendations
                    ],
                    "caveats": list(request.caveats),
                },
            }
        )


def _weather_response(endpoint: str, params: Mapping[str, object]) -> dict[str, Any]:
    if endpoint == ELEVATION_ENDPOINT:
        return {"elevation": [1642.0]}
    if endpoint == FORECAST_ENDPOINT:
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
                "time": ["2026-07-09T06:00", "2026-07-09T07:00", "2026-07-09T08:00"],
                "temperature_2m": [19.0, 21.0, 23.0],
                "relative_humidity_2m": [62, 55, 48],
                "precipitation_probability": [0, 5, 10],
                "precipitation": [0.0, 0.0, 0.1],
                "weather_code": [0, 1, 2],
                "wind_speed_10m": [3.0, 5.0, 7.0],
                "wind_gusts_10m": [5.0, 8.0, 11.0],
            },
        }
    raise AssertionError(f"unexpected endpoint {endpoint}")


def _seed_planner_views(con: duckdb.DuckDBPyConnection) -> None:
    con.execute("CREATE SCHEMA IF NOT EXISTS birding_agent")
    con.execute(
        """
        CREATE TABLE birding_agent.recent_observation_evidence (
            observation_evidence_id TEXT,
            source_table TEXT,
            source_record_id TEXT,
            species_code TEXT,
            common_name TEXT,
            scientific_name TEXT,
            observation_datetime TEXT,
            observation_date TEXT,
            observation_count BIGINT,
            count_display TEXT,
            location_name TEXT,
            region_code TEXT,
            latitude DOUBLE,
            longitude DOUBLE,
            is_notable BOOLEAN,
            loaded_at TEXT
        )
        """
    )
    con.executemany(
        """
        INSERT INTO birding_agent.recent_observation_evidence
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [
            (
                "obs-1",
                "environmental_observations.fact_bird_observation",
                "S1",
                "acowoo",
                "Acorn Woodpecker",
                "Melanerpes formicivorus",
                "2026-07-08T06:30:00",
                "2026-07-08",
                3,
                "3",
                "Thumb Butte",
                "US-AZ",
                34.54,
                -112.52,
                False,
                "2026-07-08T12:00:00",
            ),
            (
                "obs-2",
                "environmental_observations.fact_bird_observation",
                "S2",
                "mexjay",
                "Mexican Jay",
                "Aphelocoma wollweberi",
                "2026-07-08T06:45:00",
                "2026-07-08",
                5,
                "5",
                "Thumb Butte",
                "US-AZ",
                34.55,
                -112.53,
                False,
                "2026-07-08T12:00:00",
            ),
        ],
    )
    con.execute(
        """
        CREATE TABLE birding_agent.gbif_occurrence_evidence (
            occurrence_evidence_id TEXT,
            source_table TEXT,
            source_record_id TEXT,
            species_code TEXT,
            scientific_name TEXT,
            source_scientific_name TEXT,
            accepted_scientific_name TEXT,
            common_name TEXT,
            family TEXT,
            genus TEXT,
            latitude DOUBLE,
            longitude DOUBLE,
            locality TEXT,
            state_province TEXT,
            event_date_text TEXT,
            year BIGINT,
            month BIGINT,
            basis_of_record TEXT,
            occurrence_status TEXT,
            license TEXT,
            source_reference_url TEXT,
            loaded_at TEXT,
            _query_state_province TEXT
        )
        """
    )
    con.execute(
        """
        INSERT INTO birding_agent.gbif_occurrence_evidence
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [
            "gbif-1",
            "raw_gbif.occurrences",
            "G1",
            "zthawk",
            "Buteo albonotatus",
            "Buteo albonotatus Kaup, 1847",
            "Buteo albonotatus",
            "Zone-tailed Hawk",
            "Accipitridae",
            "Buteo",
            34.56,
            -112.50,
            "Prescott",
            "Arizona",
            "2024-07-01",
            2024,
            7,
            "HUMAN_OBSERVATION",
            "PRESENT",
            "CC_BY_4_0",
            "https://gbif.example/occurrence/G1",
            "2026-07-08T12:00:00",
            "Arizona",
        ],
    )
    con.execute(
        """
        CREATE TABLE birding_agent.xeno_canto_media_evidence (
            media_evidence_id TEXT,
            source_table TEXT,
            source_record_id TEXT,
            recording_id TEXT,
            english_name TEXT,
            genus TEXT,
            species TEXT,
            recordist TEXT,
            country TEXT,
            locality TEXT,
            latitude DOUBLE,
            longitude DOUBLE,
            recording_type TEXT,
            recording_url TEXT,
            audio_file_url TEXT,
            license TEXT,
            quality TEXT,
            recording_date TEXT,
            loaded_at TEXT
        )
        """
    )
    con.execute(
        """
        INSERT INTO birding_agent.xeno_canto_media_evidence
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [
            "xc-1",
            "raw_xeno_canto.recordings",
            "XC1",
            "XC1",
            "Acorn Woodpecker",
            "Melanerpes",
            "formicivorus",
            "recordist",
            "United States",
            "Prescott",
            34.54,
            -112.52,
            "song",
            "https://xeno-canto.org/XC1",
            "https://xeno-canto.org/XC1/download",
            "CC BY-NC-SA 4.0",
            "A",
            "2024-07-01",
            "2026-07-08T12:00:00",
        ],
    )


def test_arizona_coordinate_validation_rejects_before_persistence_or_model() -> None:
    con = duckdb.connect(":memory:")
    model = FakeTripPlanModelClient()
    planner = BirdingTripPlanner(
        con,
        model_client=model,
        weather_getter=lambda endpoint, params: (_ for _ in ()).throw(
            AssertionError(f"weather must not run: {endpoint} {params}")
        ),
    )

    with pytest.raises(ValueError, match="Arizona longitudes are negative"):
        planner.plan_trip(
            TripRequest(
                location="34.54,112.50",
                start_at=datetime.fromisoformat("2026-07-09T06:00:00"),
                duration_minutes=60,
            )
        )

    schemas = con.execute(
        "SELECT count(*) FROM information_schema.schemata WHERE schema_name = 'birding_agent'"
    ).fetchone()
    assert schemas == (0,)
    assert model.requests == []


def test_valid_arizona_coordinate_retains_region_and_timezone() -> None:
    location = resolve_arizona_location("34.54,-112.50")

    assert location.latitude == 34.54
    assert location.longitude == -112.50
    assert location.region_code == "US-AZ"
    assert location.timezone == "America/Phoenix"
    named = resolve_arizona_location("Prescott, Arizona")
    assert named.normalized_location_name == "Prescott, Arizona, United States"
    assert named.region_code == "US-AZ"


def test_ranked_gbif_recommendations_keep_conformed_names_and_do_not_duplicate() -> None:
    planner = BirdingTripPlanner(
        duckdb.connect(":memory:"),
        model_client=FakeTripPlanModelClient(),
        weather_getter=_weather_response,
    )
    occurrence_rows = [
        {
            "species_code": "wesblu",
            "common_name": "Western Bluebird",
            "scientific_name": "Sialia mexicana",
        },
        {
            "species_code": "wesblu",
            "common_name": "Western Bluebird",
            "scientific_name": "Sialia mexicana",
        },
        {
            "species_code": "gilwoo",
            "common_name": "Gila Woodpecker",
            "scientific_name": "Melanerpes uropygialis",
        },
        {
            "species_code": "nswowl",
            "common_name": "Northern Saw-whet Owl",
            "scientific_name": "Aegolius acadicus",
        },
    ]

    recommendations = planner.rank_likely_species([], occurrence_rows)

    assert len(recommendations) == 3
    assert {
        recommendation.common_name: (
            recommendation.species_code,
            recommendation.scientific_name,
        )
        for recommendation in recommendations
    } == {
        "Western Bluebird": ("wesblu", "Sialia mexicana"),
        "Gila Woodpecker": ("gilwoo", "Melanerpes uropygialis"),
        "Northern Saw-whet Owl": ("nswowl", "Aegolius acadicus"),
    }


def test_build_root_agent_exposes_bounded_tool_contract() -> None:
    agent = build_root_agent()

    assert agent.name == "birding_trip_planner"
    tool_names = {getattr(tool, "name", getattr(tool, "__name__", "")) for tool in agent.tools}
    assert {
        "normalize_location_tool",
        "lookup_recent_observation_evidence_tool",
        "lookup_gbif_occurrence_evidence_tool",
        "fetch_open_meteo_trip_context_tool",
        "rank_likely_species_tool",
        "lookup_xeno_canto_media_evidence_tool",
        "synthesize_grounded_trip_plan_tool",
        "persist_trip_plan_tool",
    } <= tool_names
    assert "life list" in cast(str, agent.instruction)


def test_adk_runtime_persists_trip_plan_recommendations_evidence_and_traces() -> None:
    con = duckdb.connect(":memory:")
    _seed_planner_views(con)
    model_client = FakeTripPlanModelClient()

    result = run_trip_planner_agent(
        con,
        request=TripRequest(
            location="Thumb Butte",
            start_at=datetime.fromisoformat("2026-07-09T06:00:00"),
            duration_minutes=90,
            skill_level="beginner",
            constraints_text="focus on calls",
        ),
        trip_plan_id="trip-thumb-butte-test",
        weather_getter=_weather_response,
        model_client=model_client,
    )

    assert result.trip_plan_id == "trip-thumb-butte-test"
    assert len(model_client.requests) == 1
    assert model_client.requests[0].duration_minutes == 90
    assert model_client.requests[0].window_end == "2026-07-09T07:30:00"
    assert result.location.normalized_location_name == "Thumb Butte, Prescott, AZ"
    assert "High-likelihood species" in result.field_plan_text
    assert "Uncommon but plausible targets" in result.field_plan_text
    assert any(rec.common_name == "Mexican Jay" for rec in result.recommendations)
    assert any(
        rec.common_name == "Zone-tailed Hawk" and rec.recommendation_group == "uncommon_plausible"
        for rec in result.recommendations
    )
    assert all("life" not in rec.rationale_text.lower() for rec in result.recommendations)

    counts = dict(
        con.execute(
            """
            SELECT 'plans', count(*) FROM birding_agent.trip_plans
            UNION ALL
            SELECT 'recommendations', count(*) FROM birding_agent.trip_plan_recommendations
            UNION ALL SELECT 'evidence', count(*) FROM birding_agent.trip_plan_evidence
            UNION ALL SELECT 'traces', count(*) FROM birding_agent.trip_plan_tool_traces
            """
        ).fetchall()
    )
    assert counts["plans"] == 1
    assert counts["recommendations"] >= 3
    assert counts["evidence"] >= 5
    assert counts["traces"] == 9

    trace_tools = {
        row[0]
        for row in con.execute(
            "SELECT tool_name FROM birding_agent.trip_plan_tool_traces WHERE trip_plan_id = ?",
            [result.trip_plan_id],
        ).fetchall()
    }
    assert {
        "normalize_location",
        "lookup_recent_observation_evidence",
        "lookup_gbif_occurrence_evidence",
        "fetch_open_meteo_trip_context",
        "rank_likely_species",
        "lookup_xeno_canto_media_evidence",
        "build_trip_plan_evidence",
        "synthesize_grounded_trip_plan",
        "persist_trip_plan",
    } == trace_tools
    trace_statuses = {
        row[0]
        for row in con.execute(
            """
            SELECT DISTINCT tool_status
            FROM birding_agent.trip_plan_tool_traces
            WHERE trip_plan_id = ?
            """,
            [result.trip_plan_id],
        ).fetchall()
    }
    assert trace_statuses == {"ok"}
    model_trace = con.execute(
        """
        SELECT input_json, output_summary_json
        FROM birding_agent.trip_plan_tool_traces
        WHERE trip_plan_id = ? AND tool_name = 'synthesize_grounded_trip_plan'
        """,
        [result.trip_plan_id],
    ).fetchone()
    assert model_trace is not None
    assert json.loads(model_trace[0])["model"] == CLOUDFLARE_WORKERS_AI_MODEL
    assert json.loads(model_trace[1])["model"] == CLOUDFLARE_WORKERS_AI_MODEL
    assert "api_key" not in (model_trace[0] + model_trace[1]).lower()

    weather_evidence = con.execute(
        """
        SELECT status, payload_json
        FROM birding_agent.trip_plan_evidence
        WHERE source = 'open_meteo'
        """
    ).fetchone()
    assert weather_evidence is not None
    assert weather_evidence[0] == "available"
    assert json.loads(weather_evidence[1])["elevation_m"] == 1642.0


@pytest.mark.asyncio
async def test_async_adk_entry_runs_blocking_planner_without_blocking_loop() -> None:
    con = duckdb.connect(":memory:")
    _seed_planner_views(con)
    result = await run_trip_planner_agent_async(
        con,
        request=TripRequest(
            location="Thumb Butte",
            start_at=datetime.fromisoformat("2026-07-09T06:00:00"),
            duration_minutes=90,
        ),
        trip_plan_id="trip-async-test",
        weather_getter=_weather_response,
        model_client=FakeTripPlanModelClient(),
    )
    assert result.trip_plan_id == "trip-async-test"


@pytest.mark.asyncio
async def test_sync_adk_entry_rejects_active_event_loop() -> None:
    con = duckdb.connect(":memory:")
    with pytest.raises(RuntimeError, match="await run_trip_planner_agent_async"):
        run_trip_planner_agent(
            con,
            request=TripRequest(
                location="Thumb Butte",
                start_at=datetime.fromisoformat("2026-07-09T06:00:00"),
                duration_minutes=90,
            ),
            model_client=FakeTripPlanModelClient(),
        )


def test_persistence_failure_never_returns_successful_plan(monkeypatch: Any) -> None:
    con = duckdb.connect(":memory:")
    _seed_planner_views(con)
    from databox.agents.birding_trip_planner import BirdingTripPlanner

    planner = BirdingTripPlanner(
        con,
        model_client=FakeTripPlanModelClient(),
        weather_getter=_weather_response,
    )

    def fail_persistence(*args: object, **kwargs: object) -> None:
        raise duckdb.IOException("sensitive persistence detail")

    monkeypatch.setattr(planner, "persist_trip_plan", fail_persistence)
    with pytest.raises(RuntimeError, match="Trip plan persistence failed") as exc_info:
        planner.plan_trip(
            TripRequest(
                location="Thumb Butte",
                start_at=datetime.fromisoformat("2026-07-09T06:00:00"),
                duration_minutes=90,
            ),
            trip_plan_id="trip-persistence-failed",
        )
    assert "sensitive persistence detail" not in str(exc_info.value)
    assert con.execute(
        "SELECT count(*) FROM birding_agent.trip_plans "
        "WHERE trip_plan_id = 'trip-persistence-failed'"
    ).fetchone() == (0,)


def test_failed_model_call_persists_safe_trace_but_not_completed_plan() -> None:
    con = duckdb.connect(":memory:")
    _seed_planner_views(con)
    request = TripRequest(
        location="Thumb Butte",
        start_at=datetime.fromisoformat("2026-07-09T06:00:00"),
        duration_minutes=90,
    )
    run_trip_planner_agent(
        con,
        request=request,
        trip_plan_id="trip-model-failed",
        weather_getter=_weather_response,
        model_client=FakeTripPlanModelClient(),
    )

    with pytest.raises(CloudflareAuthenticationError, match="authentication failed"):
        run_trip_planner_agent(
            con,
            request=request,
            trip_plan_id="trip-model-failed",
            weather_getter=_weather_response,
            model_client=FailingTripPlanModelClient(),
        )

    for table in ("trip_plans", "trip_plan_recommendations", "trip_plan_evidence"):
        assert con.execute(
            f"SELECT count(*) FROM birding_agent.{table} WHERE trip_plan_id = 'trip-model-failed'"
        ).fetchone() == (0,)
    trace = con.execute(
        """
        SELECT tool_status, output_summary_json, caveats_json
        FROM birding_agent.trip_plan_tool_traces
        WHERE trip_plan_id = 'trip-model-failed'
          AND tool_name = 'synthesize_grounded_trip_plan'
        """
    ).fetchone()
    assert trace is not None
    assert trace[0] == "unavailable"
    assert json.loads(trace[1]) == {
        "error_code": "authentication_failed",
        "model": CLOUDFLARE_WORKERS_AI_MODEL,
    }
    assert "CF_WORKERS_AI_API_KEY" not in trace[2]


def test_adk_runtime_persists_source_unavailable_caveats_when_evidence_views_are_missing() -> None:
    con = duckdb.connect(":memory:")

    result = run_trip_planner_agent(
        con,
        request=TripRequest(
            location="34.54,-112.47",
            start_at=datetime.fromisoformat("2026-07-09T06:00:00"),
            duration_minutes=60,
        ),
        trip_plan_id="trip-sparse-test",
        weather_getter=_weather_response,
        model_client=FakeTripPlanModelClient(),
    )

    assert not result.recommendations
    assert "No recent eBird evidence" in " ".join(result.caveats)
    assert "No GBIF occurrence context" in " ".join(result.caveats)
    assert "No Xeno-canto media examples" in " ".join(result.caveats)

    statuses = con.execute(
        """
        SELECT source, status, caveats_json
        FROM birding_agent.trip_plan_evidence
        WHERE trip_plan_id = ?
        ORDER BY source
        """,
        [result.trip_plan_id],
    ).fetchall()
    assert {row[0] for row in statuses} == {"ebird", "gbif", "open_meteo", "xeno_canto"}
    assert any(row[1] == "unavailable" for row in statuses)

    failed_traces = con.execute(
        """
        SELECT tool_name
        FROM birding_agent.trip_plan_tool_traces
        WHERE trip_plan_id = ? AND tool_status = 'unavailable'
        ORDER BY step_order
        """,
        [result.trip_plan_id],
    ).fetchall()
    assert ("lookup_recent_observation_evidence",) in failed_traces
    assert ("lookup_gbif_occurrence_evidence",) in failed_traces


def test_cli_generates_sample_plan_against_duckdb_file(tmp_path: Path, capsys: Any) -> None:
    db_path = tmp_path / "planner.duckdb"
    con = duckdb.connect(str(db_path))
    _seed_planner_views(con)
    con.close()

    status = main(
        [
            "--database-path",
            str(db_path),
            "--location",
            "Thumb Butte",
            "--start-at",
            "2026-07-09T06:00:00",
            "--duration-minutes",
            "90",
            "--trip-plan-id",
            "trip-cli-test",
            "--mock-open-meteo",
        ],
        model_client=FakeTripPlanModelClient(),
    )

    assert status == 0
    output = json.loads(capsys.readouterr().out)
    assert output["trip_plan_id"] == "trip-cli-test"
    assert "High-likelihood species" in output["field_plan_text"]

    con = duckdb.connect(str(db_path), read_only=True)
    plan_count_row = con.execute("SELECT count(*) FROM birding_agent.trip_plans").fetchone()
    trace_count_row = con.execute(
        "SELECT count(*) FROM birding_agent.trip_plan_tool_traces"
    ).fetchone()
    assert plan_count_row is not None
    assert trace_count_row is not None
    assert plan_count_row[0] == 1
    assert trace_count_row[0] == 9
    con.close()
