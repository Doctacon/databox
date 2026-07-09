"""Deterministic DeepEval suite for the Birding Trip Copilot."""

from __future__ import annotations

import json
import os
from collections.abc import Mapping
from datetime import datetime
from typing import Any

os.environ.setdefault("CONFIDENT_OPEN_BROWSER", "false")
os.environ.setdefault("DEEPEVAL_CACHE_FOLDER", ".cache/deepeval")
os.environ.setdefault("DEEPEVAL_TELEMETRY_OPT_OUT", "true")

import duckdb
from databox.agent_tools.open_meteo import ELEVATION_ENDPOINT, FORECAST_ENDPOINT
from databox.agents.birding_trip_planner import BirdingTripPlanner, TripRequest
from databox.agents.cloudflare_workers_ai import (
    CLOUDFLARE_WORKERS_AI_MODEL,
    GroundedSynthesisRequest,
    GroundedSynthesisResult,
)
from deepeval.evaluate import assert_test
from deepeval.metrics import BaseMetric, ToolCorrectnessMetric
from deepeval.models.base_model import DeepEvalBaseLLM
from deepeval.test_case import LLMTestCase, SingleTurnParams, ToolCall

EXPECTED_TOOL_NAMES = [
    "normalize_location",
    "lookup_recent_observation_evidence",
    "lookup_gbif_occurrence_evidence",
    "fetch_open_meteo_trip_context",
    "rank_likely_species",
    "lookup_xeno_canto_media_evidence",
    "build_trip_plan_evidence",
    "synthesize_grounded_trip_plan",
    "persist_trip_plan",
]

PERSONAL_HISTORY_PHRASES = [
    "life list",
    "personal history",
    "stored history",
    "your sightings",
    "you have seen",
    "previous sightings",
]


class NoOpDeepEvalModel(DeepEvalBaseLLM):
    """No-network model placeholder for deterministic non-LLM DeepEval metrics."""

    def load_model(self, *args: object, **kwargs: object) -> NoOpDeepEvalModel:
        return self

    def generate(self, *args: object, **kwargs: object) -> str:
        raise AssertionError("The deterministic DeepEval suite must not call an LLM")

    async def a_generate(self, *args: object, **kwargs: object) -> str:
        raise AssertionError("The deterministic DeepEval suite must not call an LLM")

    def get_model_name(self, *args: object, **kwargs: object) -> str:
        return "noop-local"


NOOP_MODEL = NoOpDeepEvalModel("noop-local")


class FakeTripPlanModelClient:
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
                        item.recommendation_id for item in request.recommendations
                    ],
                    "caveats": list(request.caveats),
                },
            }
        )


class PersistedEvidenceMetric(BaseMetric):
    """Checks that persisted trip-plan artifacts include source provenance."""

    _required_params = [SingleTurnParams.ACTUAL_OUTPUT, SingleTurnParams.METADATA]  # type: ignore[assignment]

    def __init__(self, *, required_sources: set[str]) -> None:
        self.required_sources = required_sources
        self.threshold = 1.0
        self.score = None
        self.reason = None
        self.success = None
        self.async_mode = False
        self.strict_mode = True

    def measure(self, test_case: LLMTestCase, *args: object, **kwargs: object) -> float:
        metadata = test_case.metadata or {}
        observed_sources = set(metadata.get("evidence_sources", []))
        evidence_count = int(metadata.get("evidence_count", 0))
        missing = sorted(self.required_sources - observed_sources)
        has_source_ids = bool(metadata.get("has_source_record_or_payload"))
        has_plan_sections = all(
            phrase in (test_case.actual_output or "")
            for phrase in ("High-likelihood species", "Uncommon but plausible targets")
        )
        passed = not missing and evidence_count >= len(self.required_sources) and has_source_ids
        passed = passed and has_plan_sections
        self.score = 1.0 if passed else 0.0
        self.success = passed
        self.reason = (
            "Persisted evidence includes required sources, source payload/provenance, and plan "
            "sections."
            if passed
            else (
                "Missing sources="
                f"{missing}; evidence_count={evidence_count}; "
                f"has_source_record_or_payload={has_source_ids}; "
                f"has_plan_sections={has_plan_sections}."
            )
        )
        return self.score

    async def a_measure(self, test_case: LLMTestCase, *args: object, **kwargs: object) -> float:
        return self.measure(test_case, *args, **kwargs)

    def is_successful(self) -> bool:
        return bool(self.success)

    @property
    def __name__(self) -> str:
        return "Persisted Evidence Metric"


class NoPersonalHistoryAssumptionMetric(BaseMetric):
    """Checks that the MVP does not assume a stored life list or sighting history."""

    _required_params = [SingleTurnParams.ACTUAL_OUTPUT, SingleTurnParams.METADATA]  # type: ignore[assignment]

    def __init__(self) -> None:
        self.threshold = 1.0
        self.score = None
        self.reason = None
        self.success = None
        self.async_mode = False
        self.strict_mode = True

    def measure(self, test_case: LLMTestCase, *args: object, **kwargs: object) -> float:
        metadata = test_case.metadata or {}
        text = "\n".join(
            [
                test_case.actual_output or "",
                "\n".join(str(item) for item in metadata.get("recommendation_rationales", [])),
                json.dumps(metadata.get("plan_caveats", []), sort_keys=True),
            ]
        ).lower()
        found = [phrase for phrase in PERSONAL_HISTORY_PHRASES if phrase in text]
        passed = not found and metadata.get("personalization_mode") == "no_life_list"
        self.score = 1.0 if passed else 0.0
        self.success = passed
        self.reason = (
            "No personal life-list or stored-history assumptions were observed."
            if passed
            else f"Found disallowed personal-history assumptions: {found}."
        )
        return self.score

    async def a_measure(self, test_case: LLMTestCase, *args: object, **kwargs: object) -> float:
        return self.measure(test_case, *args, **kwargs)

    def is_successful(self) -> bool:
        return bool(self.success)

    @property
    def __name__(self) -> str:
        return "No Personal History Assumption Metric"


class SourceUnavailableCaveatMetric(BaseMetric):
    """Checks that missing evidence families are explicit instead of silently skipped."""

    _required_params = [SingleTurnParams.METADATA]  # type: ignore[assignment]

    def __init__(self, *, unavailable_sources: set[str]) -> None:
        self.unavailable_sources = unavailable_sources
        self.threshold = 1.0
        self.score = None
        self.reason = None
        self.success = None
        self.async_mode = False
        self.strict_mode = True

    def measure(self, test_case: LLMTestCase, *args: object, **kwargs: object) -> float:
        metadata = test_case.metadata or {}
        unavailable = set(metadata.get("unavailable_evidence_sources", []))
        trace_failures = set(metadata.get("unavailable_trace_tools", []))
        caveat_text = " ".join(str(item) for item in metadata.get("plan_caveats", [])).lower()
        expected_tools = {
            "lookup_recent_observation_evidence",
            "lookup_gbif_occurrence_evidence",
        }
        missing_sources = sorted(self.unavailable_sources - unavailable)
        missing_tools = sorted(expected_tools - trace_failures)
        has_caveat_text = all(source in caveat_text for source in ("ebird", "gbif", "xeno-canto"))
        passed = not missing_sources and not missing_tools and has_caveat_text
        self.score = 1.0 if passed else 0.0
        self.success = passed
        self.reason = (
            "Unavailable evidence families were persisted and surfaced as caveats."
            if passed
            else (
                f"missing_sources={missing_sources}; missing_tools={missing_tools}; "
                f"has_caveat_text={has_caveat_text}."
            )
        )
        return self.score

    async def a_measure(self, test_case: LLMTestCase, *args: object, **kwargs: object) -> float:
        return self.measure(test_case, *args, **kwargs)

    def is_successful(self) -> bool:
        return bool(self.success)

    @property
    def __name__(self) -> str:
        return "Source Unavailable Caveat Metric"


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
            scientific_name TEXT,
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
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [
            "gbif-1",
            "raw_gbif.occurrences",
            "G1",
            "Buteo albonotatus",
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


def _expected_tool_calls() -> list[ToolCall]:
    return [ToolCall(name=name) for name in EXPECTED_TOOL_NAMES]


def _actual_tool_calls(result_tool_names: list[str]) -> list[ToolCall]:
    return [ToolCall(name=name) for name in result_tool_names]


def _metadata_for_trip(con: duckdb.DuckDBPyConnection, trip_plan_id: str) -> dict[str, object]:
    evidence_rows = con.execute(
        """
        SELECT source, status, source_record_id, payload_json
        FROM birding_agent.trip_plan_evidence
        WHERE trip_plan_id = ?
        """,
        [trip_plan_id],
    ).fetchall()
    unavailable_trace_tools = [
        row[0]
        for row in con.execute(
            """
            SELECT tool_name
            FROM birding_agent.trip_plan_tool_traces
            WHERE trip_plan_id = ? AND tool_status = 'unavailable'
            ORDER BY step_order
            """,
            [trip_plan_id],
        ).fetchall()
    ]
    model_trace_models = [
        json.loads(row[0]).get("model")
        for row in con.execute(
            """
            SELECT output_summary_json
            FROM birding_agent.trip_plan_tool_traces
            WHERE trip_plan_id = ? AND tool_name = 'synthesize_grounded_trip_plan'
            """,
            [trip_plan_id],
        ).fetchall()
    ]
    recommendation_rationales = [
        row[0]
        for row in con.execute(
            """
            SELECT rationale_text
            FROM birding_agent.trip_plan_recommendations
            WHERE trip_plan_id = ?
            ORDER BY rank_order
            """,
            [trip_plan_id],
        ).fetchall()
    ]
    return {
        "evidence_count": len(evidence_rows),
        "evidence_sources": sorted({row[0] for row in evidence_rows}),
        "unavailable_evidence_sources": sorted(
            {row[0] for row in evidence_rows if row[1] == "unavailable"}
        ),
        "has_source_record_or_payload": any(
            row[2] or json.loads(row[3] or "{}") for row in evidence_rows
        ),
        "unavailable_trace_tools": unavailable_trace_tools,
        "recommendation_rationales": recommendation_rationales,
        "model_trace_models": model_trace_models,
        "personalization_mode": "no_life_list",
    }


def test_thumb_butte_golden_trip_plan_uses_tools_and_persists_evidence() -> None:
    con = duckdb.connect(":memory:")
    _seed_planner_views(con)
    planner = BirdingTripPlanner(
        con,
        model_client=FakeTripPlanModelClient(),
        weather_getter=_weather_response,
    )

    result = planner.plan_trip(
        TripRequest(
            location="Thumb Butte",
            start_at=datetime.fromisoformat("2026-07-09T06:00:00"),
            duration_minutes=90,
            skill_level="beginner",
            constraints_text="focus on calls",
        ),
        trip_plan_id="eval-thumb-butte-golden",
    )
    metadata = _metadata_for_trip(con, result.trip_plan_id)
    metadata["plan_caveats"] = result.caveats
    assert metadata["model_trace_models"] == [CLOUDFLARE_WORKERS_AI_MODEL]

    test_case = LLMTestCase(
        name="golden-thumb-butte-morning-trip-plan",
        input="I have 90 minutes tomorrow morning near Thumb Butte. What should I try to see?",
        actual_output=result.field_plan_text,
        expected_output=(
            "An evidence-backed birding plan with targets, weather, caveats, and provenance."
        ),
        tools_called=_actual_tool_calls([trace.tool_name for trace in result.tool_traces]),
        expected_tools=_expected_tool_calls(),
        metadata=metadata,
    )

    assert_test(
        test_case,
        metrics=[
            ToolCorrectnessMetric(
                threshold=1.0,
                async_mode=False,
                strict_mode=True,
                should_exact_match=True,
                model=NOOP_MODEL,
            ),
            PersistedEvidenceMetric(required_sources={"ebird", "gbif", "open_meteo", "xeno_canto"}),
            NoPersonalHistoryAssumptionMetric(),
        ],
        run_async=False,
    )


def test_sparse_trip_plan_surfaces_unavailable_source_caveats() -> None:
    con = duckdb.connect(":memory:")
    planner = BirdingTripPlanner(
        con,
        model_client=FakeTripPlanModelClient(),
        weather_getter=_weather_response,
    )

    result = planner.plan_trip(
        TripRequest(
            location="34.54,-112.47",
            start_at=datetime.fromisoformat("2026-07-09T06:00:00"),
            duration_minutes=60,
        ),
        trip_plan_id="eval-sparse-source-caveats",
    )
    metadata = _metadata_for_trip(con, result.trip_plan_id)
    metadata["plan_caveats"] = result.caveats
    assert metadata["model_trace_models"] == [CLOUDFLARE_WORKERS_AI_MODEL]

    test_case = LLMTestCase(
        name="sparse-location-source-unavailable-caveats",
        input="I have one hour tomorrow morning at 34.54,-112.47. What should I try to see?",
        actual_output=result.field_plan_text,
        expected_output=(
            "A plan that explicitly caveats unavailable eBird, GBIF, and Xeno-canto evidence."
        ),
        tools_called=_actual_tool_calls([trace.tool_name for trace in result.tool_traces]),
        expected_tools=_expected_tool_calls(),
        metadata=metadata,
    )

    assert_test(
        test_case,
        metrics=[
            ToolCorrectnessMetric(
                threshold=1.0,
                async_mode=False,
                strict_mode=True,
                should_exact_match=True,
                model=NOOP_MODEL,
            ),
            SourceUnavailableCaveatMetric(unavailable_sources={"ebird", "gbif", "xeno_canto"}),
            NoPersonalHistoryAssumptionMetric(),
        ],
        run_async=False,
    )
