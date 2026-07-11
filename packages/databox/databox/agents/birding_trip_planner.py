"""Google ADK-backed Birding Trip Copilot runtime.

The runtime deliberately keeps the first implementation deterministic: a custom
Google ADK ``BaseAgent`` runs bounded Python tools that gather evidence, rank
species, write tool traces, and persist the plan. ``build_root_agent`` exposes
the same tool contract for future LLM-backed orchestration without changing the
persistence interface consumed by the local product and DeepEval.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import uuid
from collections import Counter
from collections.abc import AsyncGenerator, Callable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any, cast

import duckdb
from google.adk.agents import Agent, BaseAgent
from google.adk.agents.invocation_context import InvocationContext
from google.adk.events import Event
from google.adk.runners import InMemoryRunner
from google.genai import types
from pydantic import Field

from databox.agent_tools.arizona_boundary import is_in_arizona
from databox.agent_tools.open_meteo import (
    JsonGetter,
    OpenMeteoTripContext,
    fetch_open_meteo_trip_context,
    persist_open_meteo_evidence,
)
from databox.agent_tools.persistence import (
    DuckDBConnection,
    ensure_birding_agent_persistence_tables,
)
from databox.agent_tools.recommendation_media import (
    JsonGetter as MediaJsonGetter,
)
from databox.agent_tools.recommendation_media import (
    RecommendationMediaEvidence,
    enrich_recommendation_media,
)
from databox.agents.cloudflare_workers_ai import (
    CLOUDFLARE_WORKERS_AI_MODEL,
    CloudflareWorkersAIClient,
    CloudflareWorkersAIError,
    GroundedSynthesisRequest,
    PlanActionId,
    RecommendationPrompt,
    TripPlanModelClient,
)
from databox.config.settings import settings

DEFAULT_TIMEZONE = "America/Phoenix"
DEFAULT_RADIUS_KM = 50.0

KNOWN_LOCATIONS: dict[str, tuple[str, float, float, str]] = {
    "thumb butte": ("Thumb Butte, Prescott, AZ", 34.5444, -112.5280, "US-AZ"),
    "watson lake": ("Watson Lake, Prescott, AZ", 34.5959, -112.4157, "US-AZ"),
    "prescott": ("Prescott, Arizona, United States", 34.5400, -112.4685, "US-AZ"),
    "prescott, arizona": ("Prescott, Arizona, United States", 34.5400, -112.4685, "US-AZ"),
    "prescott, az": ("Prescott, Arizona, United States", 34.5400, -112.4685, "US-AZ"),
}

_PLAN_ACTION_TEXT: dict[PlanActionId, str] = {
    "listen_first": "Begin by listening before moving through the area.",
    "scan_habitat_edges": "Scan habitat edges before changing position.",
    "move_if_quiet": "Move to the next suitable area if activity stays quiet.",
    "check_weather": "Recheck the recorded weather caveats before departure.",
    "respect_access": "Stay within marked public access and posted restrictions.",
    "review_call_examples": "Review the linked call examples before the outing.",
}


@dataclass(frozen=True)
class TripRequest:
    """Minimum user inputs for a trip-planning request."""

    location: str
    start_at: datetime
    duration_minutes: int
    skill_level: str | None = None
    constraints_text: str | None = None
    timezone: str = DEFAULT_TIMEZONE
    resolved_location: NormalizedLocation | None = None

    @property
    def end_at(self) -> datetime:
        return self.start_at + timedelta(minutes=self.duration_minutes)


@dataclass(frozen=True)
class NormalizedLocation:
    requested_location: str
    normalized_location_name: str
    latitude: float
    longitude: float
    region_code: str
    timezone: str = DEFAULT_TIMEZONE
    caveats: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class EvidenceRecord:
    source: str
    source_table: str | None
    source_record_id: str | None
    evidence_type: str
    status: str
    summary: dict[str, Any]
    payload: dict[str, Any]
    latitude: float | None = None
    longitude: float | None = None
    caveats: list[str] = field(default_factory=list)
    recommendation_id: str | None = None


@dataclass(frozen=True)
class SpeciesRecommendation:
    recommendation_id: str
    species_lookup_id: str | None
    species_code: str | None
    common_name: str | None
    scientific_name: str | None
    recommendation_group: str
    rank_order: int
    confidence_label: str
    rationale_text: str
    caveats: list[str]


@dataclass(frozen=True)
class ToolTrace:
    step_order: int
    tool_name: str
    tool_status: str
    started_at: str
    completed_at: str
    input: dict[str, Any]
    output_summary: dict[str, Any]
    caveats: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class TripPlanResult:
    trip_plan_id: str
    request: TripRequest
    location: NormalizedLocation
    weather: OpenMeteoTripContext
    recommendations: list[SpeciesRecommendation]
    evidence: list[EvidenceRecord]
    tool_traces: list[ToolTrace]
    field_plan_text: str
    caveats: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "trip_plan_id": self.trip_plan_id,
            "location": {
                "requested_location": self.location.requested_location,
                "normalized_location_name": self.location.normalized_location_name,
                "latitude": self.location.latitude,
                "longitude": self.location.longitude,
                "region_code": self.location.region_code,
                "timezone": self.location.timezone,
            },
            "window_start": self.request.start_at.isoformat(),
            "window_end": self.request.end_at.isoformat(),
            "duration_minutes": self.request.duration_minutes,
            "skill_level": self.request.skill_level,
            "constraints_text": self.request.constraints_text,
            "field_plan_text": self.field_plan_text,
            "caveats": self.caveats,
            "recommendations": [rec.__dict__ for rec in self.recommendations],
            "weather": self.weather.to_dict(),
        }


class BirdingTripPlanner:
    """Deterministic bounded-tool runtime for the first Trip Copilot slice."""

    def __init__(
        self,
        connection: DuckDBConnection,
        *,
        model_client: TripPlanModelClient,
        weather_getter: JsonGetter | None = None,
        media_gbif_getter: MediaJsonGetter | None = None,
        media_xeno_getter: MediaJsonGetter | None = None,
        xeno_api_key: str | None = None,
        now: Callable[[], datetime] | None = None,
        radius_km: float = DEFAULT_RADIUS_KM,
    ) -> None:
        if model_client.model != CLOUDFLARE_WORKERS_AI_MODEL:
            raise ValueError(f"Only {CLOUDFLARE_WORKERS_AI_MODEL} may synthesize trip plans")
        self.connection = connection
        self.model_client = model_client
        self.weather_getter = weather_getter
        self.media_gbif_getter = media_gbif_getter
        self.media_xeno_getter = media_xeno_getter
        self.xeno_api_key = xeno_api_key
        self.now = now or (lambda: datetime.now(UTC))
        self.radius_km = radius_km

    def plan_trip(self, request: TripRequest, *, trip_plan_id: str | None = None) -> TripPlanResult:
        """Run the bounded planner tools and persist a queryable trip-plan artifact."""

        if not request.location.strip():
            raise ValueError("location is required")
        if request.duration_minutes <= 0:
            raise ValueError("duration_minutes must be positive")

        location = self.normalize_location(request.location, request.resolved_location)
        ensure_birding_agent_persistence_tables(self.connection)
        plan_id = trip_plan_id or f"trip_{uuid.uuid4().hex}"
        traces: list[ToolTrace] = []

        location, trace = self._record_tool(
            step_order=1,
            tool_name="normalize_location",
            tool_input={"location": request.location},
            call=lambda: location,
            summary=lambda loc: {
                "normalized_location_name": loc.normalized_location_name,
                "latitude": loc.latitude,
                "longitude": loc.longitude,
                "region_code": loc.region_code,
            },
        )
        traces.append(trace)

        recent_rows, trace = self._record_tool(
            step_order=2,
            tool_name="lookup_recent_observation_evidence",
            tool_input={
                "latitude": location.latitude,
                "longitude": location.longitude,
                "region_code": location.region_code,
                "radius_km": self.radius_km,
            },
            call=lambda: self.lookup_recent_observation_evidence(location),
            summary=lambda rows: {"row_count": len(rows)},
        )
        traces.append(trace)

        occurrence_rows, trace = self._record_tool(
            step_order=3,
            tool_name="lookup_gbif_occurrence_evidence",
            tool_input={
                "latitude": location.latitude,
                "longitude": location.longitude,
                "region_code": location.region_code,
                "radius_km": self.radius_km,
            },
            call=lambda: self.lookup_gbif_occurrence_evidence(location),
            summary=lambda rows: {"row_count": len(rows)},
        )
        traces.append(trace)

        weather_context, trace = self._record_tool(
            step_order=4,
            tool_name="fetch_open_meteo_trip_context",
            tool_input={
                "latitude": location.latitude,
                "longitude": location.longitude,
                "window_start": request.start_at.isoformat(),
                "window_end": request.end_at.isoformat(),
                "timezone": location.timezone,
            },
            call=lambda: fetch_open_meteo_trip_context(
                latitude=location.latitude,
                longitude=location.longitude,
                start_at=request.start_at,
                end_at=request.end_at,
                timezone=location.timezone,
                http_get_json=self.weather_getter,
            ),
            summary=lambda context: {
                "status": context.status,
                "hourly_rows": len(context.hourly),
                "elevation_m": context.elevation_m,
            },
        )
        traces.append(trace)

        ranked, trace = self._record_tool(
            step_order=5,
            tool_name="rank_likely_species",
            tool_input={
                "recent_observation_rows": len(recent_rows),
                "gbif_occurrence_rows": len(occurrence_rows),
            },
            call=lambda: self.rank_likely_species(recent_rows, occurrence_rows),
            summary=lambda recs: {
                "recommendation_count": len(recs),
                "high_likelihood_count": sum(
                    rec.recommendation_group == "high_likelihood" for rec in recs
                ),
                "uncommon_plausible_count": sum(
                    rec.recommendation_group == "uncommon_plausible" for rec in recs
                ),
            },
        )
        traces.append(trace)

        media_batch, trace = self._record_tool(
            step_order=6,
            tool_name="enrich_recommendation_media",
            tool_input={"recommendation_count": len(ranked)},
            call=lambda: enrich_recommendation_media(
                ranked,
                gbif_getter=self.media_gbif_getter,
                xeno_getter=self.media_xeno_getter,
                xeno_api_key=self.xeno_api_key,
            ),
            summary=lambda batch: {
                "lookup_count": batch.lookup_count,
                "result_count": len(batch.evidence),
                "available_photos": batch.available_photos,
                "available_calls": batch.available_calls,
                "arizona_calls": batch.arizona_calls,
                "global_calls": batch.global_calls,
                "unavailable_results": sum(row.status == "unavailable" for row in batch.evidence),
                "caveat_count": len(batch.caveats),
            },
        )
        traces.append(trace)

        core_evidence, trace = self._record_tool(
            step_order=7,
            tool_name="build_trip_plan_evidence",
            tool_input={
                "recent_observation_rows": len(recent_rows),
                "gbif_occurrence_rows": len(occurrence_rows),
                "weather_status": weather_context.status,
            },
            call=lambda: self.build_evidence_records(
                recent_rows,
                occurrence_rows,
                ranked,
                weather_context,
            ),
            summary=lambda rows: {"evidence_rows": len(rows)},
        )
        traces.append(trace)
        media_evidence = [_media_evidence_record(row) for row in media_batch.evidence]
        evidence = [*core_evidence, *media_evidence]

        caveats = self._plan_caveats(location, recent_rows, occurrence_rows, weather_context)
        try:
            synthesis, trace = self._record_required_model_tool(
                step_order=8,
                request=request,
                location=location,
                weather_context=weather_context,
                recommendations=ranked,
                evidence=core_evidence,
                caveats=caveats,
            )
        except CloudflareWorkersAIError as exc:
            traces.append(cast(ToolTrace, exc.tool_trace))
            self._delete_completed_plan(plan_id)
            self._replace_tool_traces(plan_id, traces)
            raise
        traces.append(trace)
        field_plan_text = self.compose_field_plan(
            request,
            location,
            weather_context,
            ranked,
            caveats,
            synthesis.action_ids,
        )

        persistence_started = self.now().isoformat()
        try:
            self.persist_trip_plan(
                plan_id,
                request,
                location,
                weather_context,
                ranked,
                evidence,
                [*traces],
                field_plan_text,
                caveats,
            )
        except Exception:
            persistence_trace = ToolTrace(
                step_order=9,
                tool_name="persist_trip_plan",
                tool_status="unavailable",
                started_at=persistence_started,
                completed_at=self.now().isoformat(),
                input={
                    "trip_plan_id": plan_id,
                    "recommendation_count": len(ranked),
                    "evidence_count": len(evidence),
                    "trace_count": len(traces) + 1,
                },
                output_summary={"status": "failed"},
                caveats=["Trip plan persistence failed"],
            )
            self._delete_completed_plan(plan_id)
            self._replace_tool_traces(plan_id, [*traces, persistence_trace])
            raise RuntimeError("Trip plan persistence failed") from None
        traces.append(
            ToolTrace(
                step_order=9,
                tool_name="persist_trip_plan",
                tool_status="ok",
                started_at=persistence_started,
                completed_at=self.now().isoformat(),
                input={
                    "trip_plan_id": plan_id,
                    "recommendation_count": len(ranked),
                    "evidence_count": len(evidence),
                    "trace_count": len(traces) + 1,
                },
                output_summary={"trip_plan_id": plan_id, "status": "persisted"},
            )
        )
        try:
            self._replace_tool_traces(plan_id, traces)
        except Exception:
            self._delete_completed_plan(plan_id)
            raise RuntimeError("Trip plan persistence failed") from None

        return TripPlanResult(
            trip_plan_id=plan_id,
            request=request,
            location=location,
            weather=weather_context,
            recommendations=ranked,
            evidence=evidence,
            tool_traces=traces,
            field_plan_text=field_plan_text,
            caveats=caveats,
        )

    def normalize_location(
        self, location: str, resolved_location: NormalizedLocation | None = None
    ) -> NormalizedLocation:
        """Resolve and validate an Arizona coordinate, selected place, or known alias."""

        return resolve_arizona_location(location, resolved_location)

    def lookup_recent_observation_evidence(
        self, location: NormalizedLocation, *, limit: int = 200
    ) -> list[dict[str, Any]]:
        query = """
            SELECT
                observation_evidence_id,
                source_table,
                source_record_id,
                species_code,
                common_name,
                scientific_name,
                observation_datetime,
                observation_date,
                observation_count,
                count_display,
                location_name,
                region_code,
                latitude,
                longitude,
                is_notable,
                loaded_at,
                (
                    111.32 * sqrt(
                        power(COALESCE(latitude, ?) - ?, 2)
                        + power((COALESCE(longitude, ?) - ?) * cos(radians(?)), 2)
                    )
                ) AS distance_km
            FROM birding_agent.recent_observation_evidence
            WHERE is_valid IS TRUE
              AND is_reviewed IS TRUE
              AND is_location_private IS FALSE
              AND (? IS NULL OR region_code = ?)
            ORDER BY distance_km ASC, observation_datetime DESC NULLS LAST
            LIMIT ?
        """
        return _fetch_dicts(
            self.connection,
            query,
            [
                location.latitude,
                location.latitude,
                location.longitude,
                location.longitude,
                location.latitude,
                location.region_code,
                location.region_code,
                limit,
            ],
        )

    def lookup_gbif_occurrence_evidence(
        self, location: NormalizedLocation, *, limit: int = 200
    ) -> list[dict[str, Any]]:
        query = """
            SELECT
                occurrence_evidence_id,
                source_table,
                source_record_id,
                species_code,
                scientific_name,
                source_scientific_name,
                accepted_scientific_name,
                common_name,
                family,
                genus,
                latitude,
                longitude,
                locality,
                state_province,
                event_date_text,
                year,
                month,
                basis_of_record,
                occurrence_status,
                license,
                source_reference_url,
                loaded_at,
                (
                    111.32 * sqrt(
                        power(COALESCE(latitude, ?) - ?, 2)
                        + power((COALESCE(longitude, ?) - ?) * cos(radians(?)), 2)
                    )
                ) AS distance_km
            FROM birding_agent.gbif_occurrence_evidence
            WHERE (
                ? IS NULL
                OR state_province ILIKE '%Arizona%'
                OR _query_state_province = 'Arizona'
            )
            ORDER BY distance_km ASC, year DESC NULLS LAST, loaded_at DESC NULLS LAST
            LIMIT ?
        """
        return _fetch_dicts(
            self.connection,
            query,
            [
                location.latitude,
                location.latitude,
                location.longitude,
                location.longitude,
                location.latitude,
                location.region_code,
                limit,
            ],
        )

    def rank_likely_species(
        self,
        recent_rows: Sequence[Mapping[str, Any]],
        occurrence_rows: Sequence[Mapping[str, Any]],
    ) -> list[SpeciesRecommendation]:
        species: dict[str, dict[str, Any]] = {}
        for row in recent_rows:
            key = _species_key(row)
            if key is None:
                continue
            item = species.setdefault(key, _species_seed(row))
            item["recent_count"] += 1
            item["recent_observation_total"] += _count_value(row.get("observation_count"))
            if row.get("is_notable"):
                item["notable"] = True

        for row in occurrence_rows:
            key = _species_key(row)
            if key is None:
                continue
            item = species.setdefault(key, _species_seed(row))
            item["gbif_count"] += 1

        scored = sorted(
            species.values(),
            key=lambda item: (
                item["recent_count"] * 10 + item["recent_observation_total"] + item["gbif_count"],
                item.get("common_name") or item.get("scientific_name") or "",
            ),
            reverse=True,
        )

        high = [item for item in scored if item["recent_count"] > 0][:5]
        plausible = [
            item for item in scored if item["recent_count"] == 0 and item["gbif_count"] > 0
        ][:3]
        if not plausible:
            plausible = [item for item in scored if item.get("notable")][:2]

        recommendations: list[SpeciesRecommendation] = []
        rank_order = 1
        for group_name, items in (("high_likelihood", high), ("uncommon_plausible", plausible)):
            for item in items:
                recent_count = item["recent_count"]
                gbif_count = item["gbif_count"]
                confidence = (
                    "high" if recent_count >= 2 else "medium" if recent_count else "plausible"
                )
                rationale = _rationale(group_name, recent_count, gbif_count)
                caveats = (
                    [] if recent_count else ["No recent eBird evidence in the modeled local slice"]
                )
                recommendations.append(
                    SpeciesRecommendation(
                        recommendation_id=f"rec_{uuid.uuid4().hex}",
                        species_lookup_id=None,
                        species_code=cast(str | None, item.get("species_code")),
                        common_name=cast(str | None, item.get("common_name")),
                        scientific_name=cast(str | None, item.get("scientific_name")),
                        recommendation_group=group_name,
                        rank_order=rank_order,
                        confidence_label=confidence,
                        rationale_text=rationale,
                        caveats=caveats,
                    )
                )
                rank_order += 1
        return recommendations

    def build_evidence_records(
        self,
        recent_rows: Sequence[Mapping[str, Any]],
        occurrence_rows: Sequence[Mapping[str, Any]],
        recommendations: Sequence[SpeciesRecommendation],
        weather_context: OpenMeteoTripContext,
    ) -> list[EvidenceRecord]:
        rec_by_species = {_rec_key(rec): rec.recommendation_id for rec in recommendations}
        evidence: list[EvidenceRecord] = []

        for row in recent_rows[:50]:
            evidence.append(
                EvidenceRecord(
                    source="ebird",
                    source_table=_string_or_none(row.get("source_table")),
                    source_record_id=_string_or_none(row.get("source_record_id")),
                    evidence_type="recent_observation",
                    status="available",
                    latitude=_float_or_none(row.get("latitude")),
                    longitude=_float_or_none(row.get("longitude")),
                    recommendation_id=rec_by_species.get(_row_key(row)),
                    summary={
                        "common_name": row.get("common_name"),
                        "scientific_name": row.get("scientific_name"),
                        "observation_date": row.get("observation_date"),
                        "location_name": row.get("location_name"),
                        "count_display": row.get("count_display"),
                    },
                    payload=dict(row),
                )
            )
        if not recent_rows:
            evidence.append(
                _missing_evidence("ebird", "recent_observation", "No recent eBird rows found")
            )

        for row in occurrence_rows[:50]:
            evidence.append(
                EvidenceRecord(
                    source="gbif",
                    source_table=_string_or_none(row.get("source_table")),
                    source_record_id=_string_or_none(row.get("source_record_id")),
                    evidence_type="occurrence_context",
                    status="available",
                    latitude=_float_or_none(row.get("latitude")),
                    longitude=_float_or_none(row.get("longitude")),
                    recommendation_id=rec_by_species.get(_row_key(row)),
                    summary={
                        "common_name": row.get("common_name"),
                        "scientific_name": row.get("scientific_name"),
                        "source_scientific_name": row.get("source_scientific_name"),
                        "accepted_scientific_name": row.get("accepted_scientific_name"),
                        "event_date_text": row.get("event_date_text"),
                        "locality": row.get("locality"),
                        "license": row.get("license"),
                    },
                    payload=dict(row),
                )
            )
        if not occurrence_rows:
            evidence.append(_missing_evidence("gbif", "occurrence_context", "No GBIF rows found"))

        return evidence

    def compose_field_plan(
        self,
        request: TripRequest,
        location: NormalizedLocation,
        weather_context: OpenMeteoTripContext,
        recommendations: Sequence[SpeciesRecommendation],
        caveats: Sequence[str],
        action_ids: Sequence[PlanActionId],
    ) -> str:
        high = [rec for rec in recommendations if rec.recommendation_group == "high_likelihood"]
        plausible = [
            rec for rec in recommendations if rec.recommendation_group == "uncommon_plausible"
        ]
        weather_bits = _weather_sentence(weather_context)
        high_text = (
            ", ".join(self._species_label(rec) for rec in high) or "no high-likelihood species"
        )
        plausible_text = (
            ", ".join(self._species_label(rec) for rec in plausible) or "no uncommon targets"
        )
        constraint_text = (
            f" Constraints noted: {request.constraints_text}." if request.constraints_text else ""
        )
        caveat_text = " Caveats: " + "; ".join(caveats) if caveats else ""
        action_text = " ".join(_PLAN_ACTION_TEXT[action_id] for action_id in action_ids)
        return (
            f"Plan {request.duration_minutes} minutes at {location.normalized_location_name} "
            f"starting {request.start_at.isoformat()} and ending {request.end_at.isoformat()}. "
            f"{weather_bits} {action_text} "
            f"High-likelihood species: {high_text}. "
            f"Uncommon but plausible targets: {plausible_text}."
            f"{constraint_text}{caveat_text}"
        )

    def persist_trip_plan(
        self,
        trip_plan_id: str,
        request: TripRequest,
        location: NormalizedLocation,
        weather_context: OpenMeteoTripContext,
        recommendations: Sequence[SpeciesRecommendation],
        evidence: Sequence[EvidenceRecord],
        tool_traces: Sequence[ToolTrace],
        field_plan_text: str,
        caveats: Sequence[str],
    ) -> None:
        _validate_recommendation_media_cardinality(recommendations, evidence)
        ensure_birding_agent_persistence_tables(self.connection)
        self.connection.execute("BEGIN TRANSACTION")
        try:
            self._persist_trip_plan_rows(
                trip_plan_id,
                request,
                location,
                weather_context,
                recommendations,
                evidence,
                tool_traces,
                field_plan_text,
                caveats,
            )
        except Exception:
            self.connection.execute("ROLLBACK")
            raise
        self.connection.execute("COMMIT")

    def _persist_trip_plan_rows(
        self,
        trip_plan_id: str,
        request: TripRequest,
        location: NormalizedLocation,
        weather_context: OpenMeteoTripContext,
        recommendations: Sequence[SpeciesRecommendation],
        evidence: Sequence[EvidenceRecord],
        tool_traces: Sequence[ToolTrace],
        field_plan_text: str,
        caveats: Sequence[str],
    ) -> None:
        now = self.now().isoformat()
        self.connection.execute(
            "DELETE FROM birding_agent.trip_plans WHERE trip_plan_id = ?", [trip_plan_id]
        )
        self.connection.execute(
            """
            INSERT INTO birding_agent.trip_plans (
                trip_plan_id,
                requested_location,
                normalized_location_name,
                latitude,
                longitude,
                region_code,
                window_start,
                window_end,
                duration_minutes,
                skill_level,
                constraints_text,
                plan_status,
                field_plan_text,
                caveats_json,
                created_at,
                updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                trip_plan_id,
                location.requested_location,
                location.normalized_location_name,
                location.latitude,
                location.longitude,
                location.region_code,
                request.start_at.isoformat(),
                request.end_at.isoformat(),
                request.duration_minutes,
                request.skill_level,
                request.constraints_text,
                "complete",
                field_plan_text,
                json.dumps(list(caveats), sort_keys=True),
                now,
                now,
            ],
        )
        self.connection.execute(
            "DELETE FROM birding_agent.trip_plan_recommendations WHERE trip_plan_id = ?",
            [trip_plan_id],
        )
        for rec in recommendations:
            self.connection.execute(
                """
                INSERT INTO birding_agent.trip_plan_recommendations (
                    recommendation_id,
                    trip_plan_id,
                    species_lookup_id,
                    species_code,
                    common_name,
                    scientific_name,
                    recommendation_group,
                    rank_order,
                    confidence_label,
                    rationale_text,
                    caveats_json,
                    created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    rec.recommendation_id,
                    trip_plan_id,
                    rec.species_lookup_id,
                    rec.species_code,
                    rec.common_name,
                    rec.scientific_name,
                    rec.recommendation_group,
                    rec.rank_order,
                    rec.confidence_label,
                    rec.rationale_text,
                    json.dumps(rec.caveats, sort_keys=True),
                    now,
                ],
            )

        self.connection.execute(
            "DELETE FROM birding_agent.trip_plan_evidence WHERE trip_plan_id = ?", [trip_plan_id]
        )
        persist_open_meteo_evidence(
            self.connection,
            weather_context,
            trip_plan_id=trip_plan_id,
            evidence_id=f"open_meteo_{trip_plan_id}",
        )
        for row in evidence:
            self.connection.execute(
                """
                INSERT INTO birding_agent.trip_plan_evidence (
                    evidence_id,
                    trip_plan_id,
                    recommendation_id,
                    source,
                    source_table,
                    source_record_id,
                    evidence_type,
                    status,
                    latitude,
                    longitude,
                    window_start,
                    window_end,
                    retrieved_at,
                    summary_json,
                    payload_json,
                    caveats_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    f"evidence_{uuid.uuid4().hex}",
                    trip_plan_id,
                    row.recommendation_id,
                    row.source,
                    row.source_table,
                    row.source_record_id,
                    row.evidence_type,
                    row.status,
                    row.latitude,
                    row.longitude,
                    request.start_at.isoformat(),
                    request.end_at.isoformat(),
                    now,
                    json.dumps(row.summary, sort_keys=True, default=str),
                    json.dumps(row.payload, sort_keys=True, default=str),
                    json.dumps(row.caveats, sort_keys=True),
                ],
            )
        self._replace_tool_traces(trip_plan_id, tool_traces)

    def _delete_completed_plan(self, trip_plan_id: str) -> None:
        for table in (
            "trip_plan_recommendations",
            "trip_plan_evidence",
            "trip_plans",
        ):
            self.connection.execute(
                f"DELETE FROM birding_agent.{table} WHERE trip_plan_id = ?",
                [trip_plan_id],
            )

    def _replace_tool_traces(self, trip_plan_id: str, traces: Sequence[ToolTrace]) -> None:
        self.connection.execute(
            "DELETE FROM birding_agent.trip_plan_tool_traces WHERE trip_plan_id = ?", [trip_plan_id]
        )
        for trace in traces:
            self.connection.execute(
                """
                INSERT INTO birding_agent.trip_plan_tool_traces (
                    tool_trace_id,
                    trip_plan_id,
                    step_order,
                    tool_name,
                    tool_status,
                    started_at,
                    completed_at,
                    input_json,
                    output_summary_json,
                    caveats_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    f"trace_{uuid.uuid4().hex}",
                    trip_plan_id,
                    trace.step_order,
                    trace.tool_name,
                    trace.tool_status,
                    trace.started_at,
                    trace.completed_at,
                    json.dumps(trace.input, sort_keys=True, default=str),
                    json.dumps(trace.output_summary, sort_keys=True, default=str),
                    json.dumps(trace.caveats, sort_keys=True),
                ],
            )

    def _plan_caveats(
        self,
        location: NormalizedLocation,
        recent_rows: Sequence[Mapping[str, Any]],
        occurrence_rows: Sequence[Mapping[str, Any]],
        weather_context: OpenMeteoTripContext,
    ) -> list[str]:
        caveats = list(location.caveats)
        if not recent_rows:
            caveats.append("No recent eBird evidence was available for the requested location")
        if not occurrence_rows:
            caveats.append("No GBIF occurrence context was available for the requested location")
        caveats.extend(weather_context.caveats)
        return caveats

    def _record_required_model_tool(
        self,
        *,
        step_order: int,
        request: TripRequest,
        location: NormalizedLocation,
        weather_context: OpenMeteoTripContext,
        recommendations: Sequence[SpeciesRecommendation],
        evidence: Sequence[EvidenceRecord],
        caveats: Sequence[str],
    ) -> tuple[Any, ToolTrace]:
        started = self.now().isoformat()
        evidence_counts = Counter(row.source for row in evidence)
        evidence_counts["open_meteo"] += 1
        model_request = GroundedSynthesisRequest(
            requested_location=request.location,
            normalized_location_name=location.normalized_location_name,
            window_start=request.start_at.isoformat(),
            window_end=request.end_at.isoformat(),
            duration_minutes=request.duration_minutes,
            skill_level=request.skill_level,
            constraints_text=request.constraints_text,
            weather_summary={
                "status": weather_context.status,
                "elevation_m": weather_context.elevation_m,
                "hourly_rows": len(weather_context.hourly),
                "caveats": list(weather_context.caveats),
            },
            recommendations=[
                RecommendationPrompt(
                    recommendation_id=rec.recommendation_id,
                    common_name=rec.common_name,
                    scientific_name=rec.scientific_name,
                    recommendation_group=rec.recommendation_group,
                    current_rationale=rec.rationale_text,
                )
                for rec in recommendations
            ],
            caveats=list(caveats),
            evidence_source_counts=dict(sorted(evidence_counts.items())),
        )
        tool_input = {
            "model": CLOUDFLARE_WORKERS_AI_MODEL,
            "recommendation_count": len(recommendations),
            "evidence_source_counts": model_request.evidence_source_counts,
        }
        try:
            result = self.model_client.synthesize(model_request)
        except CloudflareWorkersAIError as exc:
            completed = self.now().isoformat()
            trace = ToolTrace(
                step_order=step_order,
                tool_name="synthesize_grounded_trip_plan",
                tool_status="unavailable",
                started_at=started,
                completed_at=completed,
                input=tool_input,
                output_summary={
                    "model": CLOUDFLARE_WORKERS_AI_MODEL,
                    "error_code": exc.code,
                },
                caveats=[str(exc)],
            )
            exc.tool_trace = trace
            raise
        completed = self.now().isoformat()
        return result, ToolTrace(
            step_order=step_order,
            tool_name="synthesize_grounded_trip_plan",
            tool_status="ok",
            started_at=started,
            completed_at=completed,
            input=tool_input,
            output_summary={
                "model": CLOUDFLARE_WORKERS_AI_MODEL,
                "action_ids": list(result.action_ids),
                "recommendation_count": len(result.grounding.recommendation_ids),
            },
        )

    def _record_tool(
        self,
        *,
        step_order: int,
        tool_name: str,
        tool_input: dict[str, Any],
        call: Callable[[], Any],
        summary: Callable[[Any], dict[str, Any]],
    ) -> tuple[Any, ToolTrace]:
        started = self.now().isoformat()
        caveats: list[str] = []
        try:
            result = call()
            status = "ok"
            output = summary(result)
        except Exception as exc:  # noqa: BLE001 - tool failures become explicit caveats.
            result = []
            status = "unavailable"
            caveats = [f"{tool_name} unavailable: {exc}"]
            output = {"error": str(exc)}
            if tool_name == "normalize_location":
                raise
        completed = self.now().isoformat()
        return result, ToolTrace(
            step_order=step_order,
            tool_name=tool_name,
            tool_status=status,
            started_at=started,
            completed_at=completed,
            input=tool_input,
            output_summary=output,
            caveats=caveats,
        )

    @staticmethod
    def _species_label(rec: SpeciesRecommendation) -> str:
        return rec.common_name or rec.scientific_name or rec.species_code or "unknown species"


class BirdingTripPlannerAdkAgent(BaseAgent):
    """Minimal Google ADK runtime wrapper around the deterministic planner."""

    connection: Any = Field(exclude=True)
    request: TripRequest = Field(exclude=True)
    trip_plan_id: str | None = None
    weather_getter: Any = Field(default=None, exclude=True)
    media_gbif_getter: Any = Field(default=None, exclude=True)
    media_xeno_getter: Any = Field(default=None, exclude=True)
    xeno_api_key: str | None = Field(default=None, exclude=True)
    model_client: Any = Field(exclude=True)

    async def _run_async_impl(self, ctx: InvocationContext) -> AsyncGenerator[Event, None]:
        planner = BirdingTripPlanner(
            self.connection,
            model_client=cast(TripPlanModelClient, self.model_client),
            weather_getter=self.weather_getter,
            media_gbif_getter=self.media_gbif_getter,
            media_xeno_getter=self.media_xeno_getter,
            xeno_api_key=self.xeno_api_key,
        )
        result = await asyncio.to_thread(
            planner.plan_trip,
            self.request,
            trip_plan_id=self.trip_plan_id,
        )
        yield Event(
            invocation_id=ctx.invocation_id,
            author=self.name,
            content=types.Content(
                role="model",
                parts=[types.Part(text=result.field_plan_text)],
            ),
            output=result,
        )


def build_root_agent() -> Agent:
    """Build the non-executed ADK tool-contract descriptor.

    Live model inference is owned exclusively by ``CloudflareWorkersAIClient``;
    this descriptor intentionally cannot accept an arbitrary ADK model.
    """

    return Agent(
        name="birding_trip_planner",
        model="",
        description="Evidence-backed birding trip planner for hobbyist birdwatchers.",
        instruction=(
            "Plan only birding trips. Use bounded tools for location normalization, "
            "recent eBird evidence, GBIF occurrence context, Open-Meteo weather/elevation, "
            "request-time recommendation media, ranking, and persistence. Never assume a personal "
            "life list or stored user history. Surface source-unavailable caveats."
        ),
        tools=[
            normalize_location_tool,
            lookup_recent_observation_evidence_tool,
            lookup_gbif_occurrence_evidence_tool,
            fetch_open_meteo_trip_context_tool,
            rank_likely_species_tool,
            enrich_recommendation_media_tool,
            synthesize_grounded_trip_plan_tool,
            persist_trip_plan_tool,
        ],
    )


def normalize_location_tool(location: str) -> dict[str, Any]:
    """Describe the location-normalization tool contract for ADK orchestration."""

    return {"tool": "normalize_location", "location": location}


def lookup_recent_observation_evidence_tool(latitude: float, longitude: float) -> dict[str, Any]:
    """Describe the recent eBird evidence lookup tool contract."""

    return {
        "tool": "lookup_recent_observation_evidence",
        "latitude": latitude,
        "longitude": longitude,
    }


def lookup_gbif_occurrence_evidence_tool(latitude: float, longitude: float) -> dict[str, Any]:
    """Describe the GBIF occurrence evidence lookup tool contract."""

    return {"tool": "lookup_gbif_occurrence_evidence", "latitude": latitude, "longitude": longitude}


def fetch_open_meteo_trip_context_tool(
    latitude: float,
    longitude: float,
    window_start: str,
    window_end: str,
) -> dict[str, Any]:
    """Describe the Open-Meteo context tool contract."""

    return {
        "tool": "fetch_open_meteo_trip_context",
        "latitude": latitude,
        "longitude": longitude,
        "window_start": window_start,
        "window_end": window_end,
    }


def rank_likely_species_tool() -> dict[str, Any]:
    """Describe the species-ranking tool contract."""

    return {"tool": "rank_likely_species"}


def enrich_recommendation_media_tool(recommendation_ids: list[str]) -> dict[str, Any]:
    """Describe the bounded request-time media-enrichment tool contract."""

    return {"tool": "enrich_recommendation_media", "recommendation_ids": recommendation_ids}


def synthesize_grounded_trip_plan_tool(recommendation_ids: list[str]) -> dict[str, Any]:
    """Describe the required grounded Cloudflare synthesis tool contract."""

    return {
        "tool": "synthesize_grounded_trip_plan",
        "model": CLOUDFLARE_WORKERS_AI_MODEL,
        "recommendation_ids": recommendation_ids,
    }


def persist_trip_plan_tool(trip_plan_id: str) -> dict[str, Any]:
    """Describe the trip-plan persistence tool contract."""

    return {"tool": "persist_trip_plan", "trip_plan_id": trip_plan_id}


_ADK_APP_NAME = "agents"


async def run_trip_planner_agent_async(
    connection: DuckDBConnection,
    *,
    request: TripRequest,
    trip_plan_id: str | None = None,
    weather_getter: JsonGetter | None = None,
    media_gbif_getter: MediaJsonGetter | None = None,
    media_xeno_getter: MediaJsonGetter | None = None,
    xeno_api_key: str | None = None,
    model_client: TripPlanModelClient | None = None,
) -> TripPlanResult:
    """Run one bounded trip plan without blocking the caller's event loop."""

    resolved_model_client = model_client or CloudflareWorkersAIClient.from_settings(settings)
    agent = BirdingTripPlannerAdkAgent(
        name="birding_trip_planner_runtime",
        connection=connection,
        request=request,
        trip_plan_id=trip_plan_id,
        weather_getter=weather_getter,
        media_gbif_getter=media_gbif_getter,
        media_xeno_getter=media_xeno_getter,
        xeno_api_key=xeno_api_key,
        model_client=resolved_model_client,
    )
    runner = InMemoryRunner(agent=agent, app_name=_ADK_APP_NAME)
    session_id = trip_plan_id or f"session_{uuid.uuid4().hex}"
    message = types.Content(
        role="user",
        parts=[
            types.Part(
                text=(
                    f"Plan a birding trip for {request.location} starting "
                    f"{request.start_at.isoformat()} for {request.duration_minutes} minutes."
                )
            )
        ],
    )
    await runner.session_service.create_session(
        app_name=_ADK_APP_NAME,
        user_id="local_user",
        session_id=session_id,
    )
    result: TripPlanResult | None = None
    async for event in runner.run_async(
        user_id="local_user",
        session_id=session_id,
        new_message=message,
    ):
        if result is None and isinstance(event.output, TripPlanResult):
            result = event.output
    if result is None:
        raise RuntimeError("ADK trip planner completed without producing a trip plan")
    return result


def run_trip_planner_agent(
    connection: DuckDBConnection,
    *,
    request: TripRequest,
    trip_plan_id: str | None = None,
    weather_getter: JsonGetter | None = None,
    media_gbif_getter: MediaJsonGetter | None = None,
    media_xeno_getter: MediaJsonGetter | None = None,
    xeno_api_key: str | None = None,
    model_client: TripPlanModelClient | None = None,
) -> TripPlanResult:
    """Synchronous CLI/test wrapper; async callers must use the async entry point."""

    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(
            run_trip_planner_agent_async(
                connection,
                request=request,
                trip_plan_id=trip_plan_id,
                weather_getter=weather_getter,
                media_gbif_getter=media_gbif_getter,
                media_xeno_getter=media_xeno_getter,
                xeno_api_key=xeno_api_key,
                model_client=model_client,
            )
        )
    raise RuntimeError(
        "run_trip_planner_agent cannot run inside an active event loop; "
        "await run_trip_planner_agent_async instead"
    )


def plan_trip(
    *,
    database_path: str,
    request: TripRequest,
    trip_plan_id: str | None = None,
    weather_getter: JsonGetter | None = None,
    media_gbif_getter: MediaJsonGetter | None = None,
    media_xeno_getter: MediaJsonGetter | None = None,
    xeno_api_key: str | None = None,
    model_client: TripPlanModelClient | None = None,
) -> TripPlanResult:
    """Generate and persist one trip plan against the local DuckDB database path."""

    with duckdb.connect(database_path) as connection:
        return run_trip_planner_agent(
            connection,
            request=request,
            trip_plan_id=trip_plan_id,
            weather_getter=weather_getter,
            media_gbif_getter=media_gbif_getter,
            media_xeno_getter=media_xeno_getter,
            xeno_api_key=xeno_api_key,
            model_client=model_client,
        )


def main(
    argv: Sequence[str] | None = None,
    *,
    model_client: TripPlanModelClient | None = None,
) -> int:
    parser = argparse.ArgumentParser(description="Generate a Birding Trip Copilot plan")
    parser.add_argument("--database-path", default=settings.database_path)
    parser.add_argument("--location", required=True)
    parser.add_argument("--start-at", required=True, help="ISO timestamp, local to --timezone")
    parser.add_argument("--duration-minutes", type=int, default=90)
    parser.add_argument("--skill-level")
    parser.add_argument("--constraints")
    parser.add_argument("--timezone", default=DEFAULT_TIMEZONE)
    parser.add_argument("--trip-plan-id")
    parser.add_argument(
        "--mock-open-meteo",
        action="store_true",
        help="Use deterministic sample weather/elevation context instead of live Open-Meteo HTTP",
    )
    args = parser.parse_args(argv)

    request = TripRequest(
        location=args.location,
        start_at=datetime.fromisoformat(args.start_at),
        duration_minutes=args.duration_minutes,
        skill_level=args.skill_level,
        constraints_text=args.constraints,
        timezone=args.timezone,
    )
    result = plan_trip(
        database_path=args.database_path,
        request=request,
        trip_plan_id=args.trip_plan_id,
        weather_getter=_sample_open_meteo_getter if args.mock_open_meteo else None,
        model_client=model_client,
    )
    print(json.dumps(result.to_dict(), indent=2, sort_keys=True, default=str))
    return 0


def _fetch_dicts(
    connection: DuckDBConnection, query: str, params: Sequence[object]
) -> list[dict[str, Any]]:
    cursor = connection.execute(query, list(params))
    columns = [description[0] for description in cursor.description]
    return [dict(zip(columns, row, strict=True)) for row in cursor.fetchall()]


def resolve_arizona_location(
    location: str, resolved_location: NormalizedLocation | None = None
) -> NormalizedLocation:
    """Resolve and validate an Arizona coordinate, selected place, or known alias."""

    value = location.strip()
    if resolved_location is not None:
        return _validate_arizona_location(
            NormalizedLocation(
                requested_location=location,
                normalized_location_name=resolved_location.normalized_location_name,
                latitude=resolved_location.latitude,
                longitude=resolved_location.longitude,
                region_code=resolved_location.region_code,
                timezone=resolved_location.timezone,
            )
        )

    parsed = _parse_coordinate_pair(value)
    if parsed is not None:
        lat, lon = parsed
        return _validate_arizona_location(
            NormalizedLocation(
                requested_location=location,
                normalized_location_name=f"{lat:.4f}, {lon:.4f}",
                latitude=lat,
                longitude=lon,
                region_code="US-AZ",
            )
        )

    known = KNOWN_LOCATIONS.get(value.lower())
    if known is None:
        raise ValueError(
            "Select an Arizona place suggestion, enter valid Arizona coordinates as "
            "'latitude,longitude', or use a supported local alias"
        )
    name, lat, lon, region = known
    return _validate_arizona_location(
        NormalizedLocation(
            requested_location=location,
            normalized_location_name=name,
            latitude=lat,
            longitude=lon,
            region_code=region,
        )
    )


def _validate_arizona_location(location: NormalizedLocation) -> NormalizedLocation:
    latitude = location.latitude
    longitude = location.longitude
    if longitude > 0 and is_in_arizona(latitude, -longitude):
        raise ValueError(
            "Arizona longitudes are negative; did you mean "
            f"'{latitude:.4f},{-longitude:.4f}'? Confirm the corrected coordinates "
            "before submitting"
        )
    if not is_in_arizona(latitude, longitude):
        raise ValueError("The current bird dataset supports Arizona locations only")
    if location.region_code != "US-AZ":
        raise ValueError("The current bird dataset supports Arizona locations only")
    return location


def _parse_coordinate_pair(value: str) -> tuple[float, float] | None:
    parts = [part.strip() for part in value.split(",")]
    if len(parts) != 2:
        return None
    try:
        lat = float(parts[0])
        lon = float(parts[1])
    except ValueError:
        return None
    if not -90 <= lat <= 90 or not -180 <= lon <= 180:
        raise ValueError("coordinates must be valid latitude and longitude")
    return lat, lon


def _species_key(row: Mapping[str, Any]) -> str | None:
    return _row_key(row)


def _row_key(row: Mapping[str, Any]) -> str | None:
    common = _lower_or_none(row.get("common_name")) or _lower_or_none(row.get("english_name"))
    scientific = _lower_or_none(row.get("scientific_name")) or _lower_or_none(
        row.get("accepted_scientific_name")
    )
    return common or scientific


def _rec_key(rec: SpeciesRecommendation) -> str | None:
    if rec.common_name:
        return rec.common_name.lower()
    if rec.scientific_name:
        return rec.scientific_name.lower()
    return None


def _species_seed(row: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "species_code": row.get("species_code"),
        "common_name": row.get("common_name"),
        "scientific_name": row.get("scientific_name") or row.get("accepted_scientific_name"),
        "recent_count": 0,
        "recent_observation_total": 0,
        "gbif_count": 0,
        "notable": False,
    }


def _count_value(value: object) -> int:
    if isinstance(value, bool):
        return 0
    if isinstance(value, int | float):
        return max(int(value), 0)
    return 1 if value is None else 0


def _rationale(group_name: str, recent_count: int, gbif_count: int) -> str:
    if group_name == "high_likelihood":
        return (
            f"Included because modeled local evidence has {recent_count} recent eBird "
            f"record(s) and {gbif_count} GBIF occurrence context row(s)."
        )
    return (
        "Included as uncommon-but-plausible because GBIF occurrence context exists "
        f"without recent modeled eBird evidence ({gbif_count} GBIF row(s))."
    )


def _validate_recommendation_media_cardinality(
    recommendations: Sequence[SpeciesRecommendation], evidence: Sequence[EvidenceRecord]
) -> None:
    expected = {
        (recommendation.recommendation_id, evidence_type)
        for recommendation in recommendations
        for evidence_type in ("recommendation_photo", "recommendation_call")
    }
    counts = Counter(
        (row.recommendation_id, row.evidence_type)
        for row in evidence
        if row.evidence_type in {"recommendation_photo", "recommendation_call"}
    )
    if set(counts) != expected or any(count != 1 for count in counts.values()):
        raise ValueError("Each recommendation requires exactly one photo and one call result")


def _media_evidence_record(row: RecommendationMediaEvidence) -> EvidenceRecord:
    return EvidenceRecord(
        source=row.source,
        source_table=None,
        source_record_id=row.source_record_id,
        evidence_type=row.evidence_type,
        status=row.status,
        summary=row.summary,
        payload=row.payload,
        caveats=row.caveats,
        recommendation_id=row.recommendation_id,
    )


def _missing_evidence(source: str, evidence_type: str, caveat: str) -> EvidenceRecord:
    return EvidenceRecord(
        source=source,
        source_table=None,
        source_record_id=None,
        evidence_type=evidence_type,
        status="unavailable",
        summary={"status": "unavailable", "caveat": caveat},
        payload={},
        caveats=[caveat],
    )


def _weather_sentence(context: OpenMeteoTripContext) -> str:
    if context.status == "unavailable":
        return "Open-Meteo weather/elevation context was unavailable."
    summary = context.forecast_summary
    temp = summary.get("temperature_2m_avg")
    wind = summary.get("wind_speed_10m_max")
    precip = summary.get("precipitation_probability_max")
    elevation = f" at about {context.elevation_m:.0f} m elevation" if context.elevation_m else ""
    bits = []
    if temp is not None:
        bits.append(f"avg temp {temp}°C")
    if wind is not None:
        bits.append(f"max wind {wind} km/h")
    if precip is not None:
        bits.append(f"max precip chance {precip}%")
    weather = ", ".join(bits) or f"status {context.status}"
    return f"Open-Meteo context{elevation}: {weather}."


def _lower_or_none(value: object) -> str | None:
    if isinstance(value, str) and value.strip():
        return value.strip().lower()
    return None


def _string_or_none(value: object) -> str | None:
    if value is None:
        return None
    return str(value)


def _float_or_none(value: object) -> float | None:
    if isinstance(value, bool) or value is None:
        return None
    try:
        return float(cast(float, value))
    except (TypeError, ValueError):
        return None


def _sample_open_meteo_getter(endpoint: str, params: Mapping[str, object]) -> dict[str, Any]:
    from databox.agent_tools.open_meteo import ELEVATION_ENDPOINT, FORECAST_ENDPOINT

    if endpoint == ELEVATION_ENDPOINT:
        return {"elevation": [1642.0]}
    if endpoint != FORECAST_ENDPOINT:
        raise RuntimeError(f"unexpected endpoint {endpoint}")
    start_date = str(params["start_date"])
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
                f"{start_date}T06:00",
                f"{start_date}T07:00",
                f"{start_date}T08:00",
            ],
            "temperature_2m": [19.0, 21.0, 23.0],
            "relative_humidity_2m": [62, 55, 48],
            "precipitation_probability": [0, 5, 10],
            "precipitation": [0.0, 0.0, 0.1],
            "weather_code": [0, 1, 2],
            "wind_speed_10m": [3.0, 5.0, 7.0],
            "wind_gusts_10m": [5.0, 8.0, 11.0],
        },
    }


if __name__ == "__main__":
    raise SystemExit(main())
