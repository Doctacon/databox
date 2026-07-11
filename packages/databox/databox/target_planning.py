"""Atomic, evidence-grounded target-bird planning."""

from __future__ import annotations

import json
import math
import uuid
from collections.abc import Callable
from dataclasses import asdict, dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

import duckdb

from databox.agent_tools.open_meteo import JsonGetter, fetch_open_meteo_trip_context
from databox.agents.birding_trip_planner import NormalizedLocation
from databox.agents.cloudflare_workers_ai import (
    CLOUDFLARE_WORKERS_AI_MODEL,
    CloudflareMalformedResponseError,
    TargetLocationPrompt,
    TargetOriginPrompt,
    TargetPlanModelClient,
    TargetSynthesisRequest,
    TargetWeatherPrompt,
    TargetWeatherSummaryPrompt,
    TargetWeatherUnitsPrompt,
    validate_target_synthesis_grounding,
)

MILES_TO_KM = 1.609344
EARTH_RADIUS_KM = 6371.0088


class TargetPlanError(RuntimeError):
    """Safe target-planning failure."""


@dataclass(frozen=True)
class TargetRequest:
    species_code: str
    origin: NormalizedLocation
    radius_miles: float
    start_at: datetime
    duration_minutes: int

    @property
    def end_at(self) -> datetime:
        return self.start_at + timedelta(minutes=self.duration_minutes)


@dataclass(frozen=True)
class TargetCandidate:
    location_id: str
    location_name: str | None
    latitude: float
    longitude: float
    observation_count: int
    latest_observation_at: str
    distance_km: float
    distance_miles: float
    evidence_loaded_at: str | None


@dataclass(frozen=True)
class TargetPlanResult:
    target_plan_id: str
    species_code: str
    common_name: str | None
    scientific_name: str | None
    taxonomic_category: str
    origin: dict[str, Any]
    radius_miles: float
    radius_km: float
    window_start: str
    window_end: str
    duration_minutes: int
    candidates: list[TargetCandidate]
    weather: TargetWeatherPrompt
    action_ids: list[str]
    guidance: list[str]
    caveats: list[str]
    evidence_freshness_at: str | None
    model: str
    created_at: str

    def to_dict(self) -> dict[str, Any]:
        result = asdict(self)
        result["candidates"] = [asdict(item) for item in self.candidates]
        result["weather"] = self.weather.model_dump(mode="json")
        return result


_LOCATION_DEPENDENT_ACTIONS = {"try_top_location", "verify_access"}

_ACTION_TEXT = {
    "try_top_location": "Start with the highest-ranked qualifying public location.",
    "arrive_early": "Arrive before the requested window so the outing can begin on time.",
    "review_freshness": (
        "Review the evidence dates before departure; recent records do not guarantee presence."
    ),
    "check_weather": "Review the persisted weather status and caveats before departure.",
    "verify_access": "Verify current site access and posted restrictions before visiting.",
}


def _quote(value: str) -> str:
    return '"' + value.replace('"', '""') + '"'


def ensure_target_tables(connection: Any, *, schema: str = "birding_agent") -> None:
    q = _quote(schema)
    connection.execute(f"CREATE SCHEMA IF NOT EXISTS {q}")
    connection.execute(
        f"""
        CREATE TABLE IF NOT EXISTS {q}.target_bird_plans (
            target_plan_id TEXT PRIMARY KEY,
            species_code TEXT NOT NULL,
            common_name TEXT,
            scientific_name TEXT,
            taxonomic_category TEXT NOT NULL,
            requested_location TEXT NOT NULL,
            normalized_location_name TEXT NOT NULL,
            origin_latitude DOUBLE NOT NULL,
            origin_longitude DOUBLE NOT NULL,
            origin_timezone TEXT NOT NULL,
            radius_miles DOUBLE NOT NULL,
            radius_km DOUBLE NOT NULL,
            window_start TEXT NOT NULL,
            window_end TEXT NOT NULL,
            duration_minutes BIGINT NOT NULL,
            weather_json TEXT NOT NULL,
            action_ids_json TEXT NOT NULL,
            guidance_json TEXT NOT NULL,
            caveats_json TEXT NOT NULL,
            evidence_freshness_at TEXT,
            model TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
        """
    )
    connection.execute(
        f"""
        CREATE TABLE IF NOT EXISTS {q}.target_bird_plan_candidates (
            target_plan_id TEXT NOT NULL,
            rank_order BIGINT NOT NULL,
            location_id TEXT NOT NULL,
            location_name TEXT,
            latitude DOUBLE NOT NULL,
            longitude DOUBLE NOT NULL,
            observation_count BIGINT NOT NULL,
            latest_observation_at TEXT NOT NULL,
            distance_km DOUBLE NOT NULL,
            distance_miles DOUBLE NOT NULL,
            evidence_loaded_at TEXT,
            PRIMARY KEY (target_plan_id, rank_order)
        )
        """
    )
    connection.execute(
        f"""
        CREATE TABLE IF NOT EXISTS {q}.target_bird_plan_tool_traces (
            target_plan_id TEXT NOT NULL,
            step_order BIGINT NOT NULL,
            tool_name TEXT NOT NULL,
            tool_status TEXT NOT NULL,
            output_summary_json TEXT NOT NULL,
            created_at TEXT NOT NULL,
            PRIMARY KEY (target_plan_id, step_order)
        )
        """
    )


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dlat = p2 - p1
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlon / 2) ** 2
    return EARTH_RADIUS_KM * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def _rows(cursor: Any) -> list[dict[str, Any]]:
    columns = [item[0] for item in cursor.description]
    return [dict(zip(columns, values, strict=True)) for values in cursor.fetchall()]


def _catalog_identity(connection: Any, species_code: str) -> dict[str, Any]:
    rows = _rows(
        connection.execute(
            """
            SELECT species_code, common_name, scientific_name, taxonomic_category
            FROM birding_agent.arizona_species_catalog
            WHERE species_code = ?
            LIMIT 2
            """,
            [species_code],
        )
    )
    if len(rows) != 1:
        raise ValueError("species_code must identify one current Arizona catalog taxon")
    return rows[0]


def select_target_candidates(
    connection: Any, request: TargetRequest, *, limit: int = 10
) -> list[TargetCandidate]:
    """Select coherent public exact-taxon clusters using true Haversine distance."""

    raw = _rows(
        connection.execute(
            """
            SELECT source_observation_id, location_id, location_name, latitude, longitude,
                   observation_datetime, loaded_at, bird_observation_sk, dlt_id
            FROM environmental_observations.fact_bird_observation
            WHERE species_code = ?
              AND region_code = 'US-AZ'
              AND is_valid IS TRUE
              AND is_reviewed IS TRUE
              AND is_location_private IS FALSE
              AND location_id IS NOT NULL
              AND latitude IS NOT NULL
              AND longitude IS NOT NULL
              AND source_observation_id IS NOT NULL
            """,
            [request.species_code],
        )
    )
    by_location: dict[str, list[dict[str, Any]]] = {}
    radius_km = request.radius_miles * MILES_TO_KM
    for row in raw:
        lat, lon = float(row["latitude"]), float(row["longitude"])
        if not (-90 <= lat <= 90 and -180 <= lon <= 180):
            continue
        distance = _haversine_km(request.origin.latitude, request.origin.longitude, lat, lon)
        if distance <= radius_km:
            row["distance_km"] = distance
            by_location.setdefault(str(row["location_id"]), []).append(row)

    candidates: list[TargetCandidate] = []
    for location_id, rows in by_location.items():
        newest = max(
            rows,
            key=lambda row: (
                str(row["observation_datetime"] or ""),
                str(row["loaded_at"] or ""),
                str(row["source_observation_id"] or ""),
                str(row["bird_observation_sk"] or ""),
                str(row["dlt_id"] or ""),
            ),
        )
        latest = str(newest["observation_datetime"])
        distance_km = float(newest["distance_km"])
        candidates.append(
            TargetCandidate(
                location_id=location_id,
                location_name=str(newest["location_name"])
                if newest["location_name"] is not None
                else None,
                latitude=float(newest["latitude"]),
                longitude=float(newest["longitude"]),
                observation_count=len({str(row["source_observation_id"]) for row in rows}),
                latest_observation_at=latest,
                distance_km=round(distance_km, 3),
                distance_miles=round(distance_km / MILES_TO_KM, 3),
                evidence_loaded_at=max(
                    (str(row["loaded_at"]) for row in rows if row["loaded_at"] is not None),
                    default=None,
                ),
            )
        )
    candidates.sort(
        key=lambda item: (
            -item.observation_count,
            _descending_timestamp_key(item.latest_observation_at),
            item.distance_km,
            item.location_name or "",
            item.location_id,
        )
    )
    return candidates[:limit]


def _descending_timestamp_key(value: str) -> tuple[int, ...]:
    # ISO timestamps sort lexically, but this numeric inversion keeps descending
    # ordering inside a normal ascending tuple without locale dependence.
    return tuple(-ord(char) for char in value)


def _finite_number(value: object) -> float | None:
    if isinstance(value, bool) or not isinstance(value, int | float):
        return None
    result = float(value)
    return result if math.isfinite(result) else None


def normalize_target_weather(context: Any) -> TargetWeatherPrompt:
    """Reduce Open-Meteo output to one strict, bounded, persistable fact shape."""

    raw_summary = context.forecast_summary if isinstance(context.forecast_summary, dict) else {}
    numeric_fields = (
        "temperature_2m_min",
        "temperature_2m_max",
        "temperature_2m_avg",
        "relative_humidity_2m_avg",
        "precipitation_probability_max",
        "precipitation_sum",
        "wind_speed_10m_max",
        "wind_gusts_10m_max",
    )
    summary_values: dict[str, Any] = {
        key: _finite_number(raw_summary.get(key)) for key in numeric_fields
    }
    raw_codes = raw_summary.get("weather_codes")
    summary_values["weather_codes"] = (
        sorted(
            {value for value in raw_codes if isinstance(value, int) and not isinstance(value, bool)}
        )[:100]
        if isinstance(raw_codes, list)
        else []
    )
    summary = TargetWeatherSummaryPrompt.model_validate(summary_values)

    raw_units = context.units if isinstance(context.units, dict) else {}
    unit_keys = (
        "temperature",
        "relative_humidity",
        "precipitation_probability",
        "precipitation",
        "wind_speed",
        "wind_gusts",
        "elevation",
    )
    units = TargetWeatherUnitsPrompt.model_validate({key: raw_units.get(key) for key in unit_keys})
    elevation = _finite_number(context.elevation_m)
    if elevation is not None and not -500 <= elevation <= 10_000:
        elevation = None
    has_forecast = any(
        value is not None and (not isinstance(value, list) or bool(value))
        for value in summary.model_dump().values()
    )
    status: str
    if has_forecast and elevation is not None:
        status = "available"
    elif has_forecast or elevation is not None:
        status = "partial"
    else:
        status = "unavailable"
    caveats = [str(item)[:500] for item in list(context.caveats)[:10] if str(item)]
    if status != context.status and len(caveats) < 10:
        caveats.append("Weather status reflects only complete normalized forecast facts.")
    return TargetWeatherPrompt.model_validate(
        {
            "status": status,
            "retrieved_at": context.retrieved_at,
            "forecast_summary": summary,
            "units": units,
            "elevation_m": elevation,
            "caveats": caveats,
        }
    )


class TargetPlanner:
    def __init__(
        self,
        connection: Any,
        *,
        model_client: TargetPlanModelClient,
        weather_getter: JsonGetter | None = None,
        now: Callable[[], datetime] | None = None,
    ) -> None:
        if model_client.model != CLOUDFLARE_WORKERS_AI_MODEL:
            raise ValueError(f"Only {CLOUDFLARE_WORKERS_AI_MODEL} may synthesize target plans")
        self.connection = connection
        self.model_client = model_client
        self.weather_getter = weather_getter
        self.now = now or (lambda: datetime.now(UTC))

    def create(self, request: TargetRequest) -> TargetPlanResult:
        if not 1 <= request.radius_miles <= 300:
            raise ValueError("radius_miles must be between 1 and 300")
        if not 1 <= request.duration_minutes <= 1440:
            raise ValueError("duration_minutes must be between 1 and 1440")
        if request.start_at.tzinfo is not None:
            raise ValueError("start_at must be a local timestamp without a time zone")
        if request.origin.region_code != "US-AZ":
            raise ValueError("origin must be in Arizona")

        identity = _catalog_identity(self.connection, request.species_code)
        candidates = select_target_candidates(self.connection, request)
        weather_context = fetch_open_meteo_trip_context(
            latitude=request.origin.latitude,
            longitude=request.origin.longitude,
            start_at=request.start_at,
            end_at=request.end_at,
            timezone=request.origin.timezone,
            http_get_json=self.weather_getter,
        )
        caveats = [
            "Recent public observations do not guarantee that the target will be present.",
            "Verify current site access and posted restrictions before visiting.",
        ]
        if not candidates:
            caveats.insert(
                0,
                "No qualifying modeled public observation location exists "
                "inside the requested radius.",
            )
        weather = normalize_target_weather(weather_context)
        caveats.extend(weather.caveats)
        evidence_freshness = max(
            (item.evidence_loaded_at for item in candidates if item.evidence_loaded_at),
            default=None,
        )
        model_request = TargetSynthesisRequest(
            species_code=request.species_code,
            common_name=identity["common_name"],
            scientific_name=identity["scientific_name"],
            taxonomic_category=identity["taxonomic_category"],
            origin=TargetOriginPrompt(
                requested_location=request.origin.requested_location,
                normalized_location_name=request.origin.normalized_location_name,
                latitude=request.origin.latitude,
                longitude=request.origin.longitude,
                timezone=request.origin.timezone,
                region_code="US-AZ",
            ),
            window_start=request.start_at.isoformat(),
            window_end=request.end_at.isoformat(),
            duration_minutes=request.duration_minutes,
            radius_miles=request.radius_miles,
            evidence_freshness_at=evidence_freshness,
            weather=weather,
            candidates=[
                TargetLocationPrompt(
                    location_id=item.location_id,
                    location_name=item.location_name,
                    latitude=item.latitude,
                    longitude=item.longitude,
                    observation_count=item.observation_count,
                    latest_observation_at=item.latest_observation_at,
                    distance_km=item.distance_km,
                    distance_miles=item.distance_miles,
                    evidence_loaded_at=item.evidence_loaded_at,
                )
                for item in candidates
            ],
            caveats=caveats,
        )
        synthesis = self.model_client.synthesize_target(model_request)
        validate_target_synthesis_grounding(model_request, synthesis)
        if not candidates and _LOCATION_DEPENDENT_ACTIONS.intersection(synthesis.action_ids):
            raise CloudflareMalformedResponseError(
                "Model output selected a location action without candidate evidence"
            )
        created_at = self.now().isoformat()
        plan_id = f"target_{uuid.uuid4().hex}"
        result = TargetPlanResult(
            target_plan_id=plan_id,
            species_code=request.species_code,
            common_name=identity["common_name"],
            scientific_name=identity["scientific_name"],
            taxonomic_category=identity["taxonomic_category"],
            origin={
                "requested_location": request.origin.requested_location,
                "normalized_location_name": request.origin.normalized_location_name,
                "latitude": request.origin.latitude,
                "longitude": request.origin.longitude,
                "timezone": request.origin.timezone,
                "region_code": request.origin.region_code,
            },
            radius_miles=request.radius_miles,
            radius_km=round(request.radius_miles * MILES_TO_KM, 3),
            window_start=request.start_at.isoformat(),
            window_end=request.end_at.isoformat(),
            duration_minutes=request.duration_minutes,
            candidates=candidates,
            weather=weather,
            action_ids=list(synthesis.action_ids),
            guidance=[_ACTION_TEXT[action] for action in synthesis.action_ids],
            caveats=caveats,
            evidence_freshness_at=evidence_freshness,
            model=self.model_client.model,
            created_at=created_at,
        )
        self._persist(result)
        return result

    def _persist(self, result: TargetPlanResult) -> None:
        self.connection.execute("BEGIN TRANSACTION")
        try:
            ensure_target_tables(self.connection)
            self.connection.execute(
                """
                INSERT INTO birding_agent.target_bird_plans VALUES
                (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    result.target_plan_id,
                    result.species_code,
                    result.common_name,
                    result.scientific_name,
                    result.taxonomic_category,
                    result.origin["requested_location"],
                    result.origin["normalized_location_name"],
                    result.origin["latitude"],
                    result.origin["longitude"],
                    result.origin["timezone"],
                    result.radius_miles,
                    result.radius_km,
                    result.window_start,
                    result.window_end,
                    result.duration_minutes,
                    result.weather.model_dump_json(),
                    json.dumps(result.action_ids),
                    json.dumps(result.guidance),
                    json.dumps(result.caveats),
                    result.evidence_freshness_at,
                    result.model,
                    result.created_at,
                ],
            )
            for rank, item in enumerate(result.candidates, 1):
                self.connection.execute(
                    "INSERT INTO birding_agent.target_bird_plan_candidates "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    [
                        result.target_plan_id,
                        rank,
                        item.location_id,
                        item.location_name,
                        item.latitude,
                        item.longitude,
                        item.observation_count,
                        item.latest_observation_at,
                        item.distance_km,
                        item.distance_miles,
                        item.evidence_loaded_at,
                    ],
                )
            traces = [
                (
                    1,
                    "rank_public_target_locations",
                    "ok",
                    {"candidate_count": len(result.candidates)},
                ),
                (
                    2,
                    "fetch_open_meteo_trip_context",
                    result.weather.status,
                    {"status": result.weather.status},
                ),
                (
                    3,
                    "synthesize_target_plan",
                    "ok",
                    {"model": result.model, "action_count": len(result.action_ids)},
                ),
                (4, "persist_target_plan", "ok", {"candidate_count": len(result.candidates)}),
            ]
            for order, name, status, summary in traces:
                self.connection.execute(
                    "INSERT INTO birding_agent.target_bird_plan_tool_traces "
                    "VALUES (?, ?, ?, ?, ?, ?)",
                    [
                        result.target_plan_id,
                        order,
                        name,
                        status,
                        json.dumps(summary, sort_keys=True),
                        result.created_at,
                    ],
                )
            self.connection.execute("COMMIT")
        except Exception:
            self.connection.execute("ROLLBACK")
            raise


def load_target_plan(connection: Any, target_plan_id: str) -> TargetPlanResult | None:
    try:
        rows = _rows(
            connection.execute(
                "SELECT * FROM birding_agent.target_bird_plans WHERE target_plan_id = ?",
                [target_plan_id],
            )
        )
    except duckdb.CatalogException:
        return None
    if not rows:
        return None
    row = rows[0]
    candidate_rows = _rows(
        connection.execute(
            "SELECT * EXCLUDE (target_plan_id, rank_order) "
            "FROM birding_agent.target_bird_plan_candidates "
            "WHERE target_plan_id = ? ORDER BY rank_order",
            [target_plan_id],
        )
    )
    return TargetPlanResult(
        target_plan_id=row["target_plan_id"],
        species_code=row["species_code"],
        common_name=row["common_name"],
        scientific_name=row["scientific_name"],
        taxonomic_category=row["taxonomic_category"],
        origin={
            "requested_location": row["requested_location"],
            "normalized_location_name": row["normalized_location_name"],
            "latitude": row["origin_latitude"],
            "longitude": row["origin_longitude"],
            "timezone": row["origin_timezone"],
            "region_code": "US-AZ",
        },
        radius_miles=row["radius_miles"],
        radius_km=row["radius_km"],
        window_start=row["window_start"],
        window_end=row["window_end"],
        duration_minutes=row["duration_minutes"],
        candidates=[TargetCandidate(**item) for item in candidate_rows],
        weather=TargetWeatherPrompt.model_validate_json(row["weather_json"]),
        action_ids=json.loads(row["action_ids_json"]),
        guidance=json.loads(row["guidance_json"]),
        caveats=json.loads(row["caveats_json"]),
        evidence_freshness_at=row["evidence_freshness_at"],
        model=row["model"],
        created_at=row["created_at"],
    )


def list_target_plans(connection: Any, *, limit: int = 100) -> list[TargetPlanResult]:
    try:
        ids = connection.execute(
            "SELECT target_plan_id FROM birding_agent.target_bird_plans "
            "ORDER BY created_at DESC, target_plan_id DESC LIMIT ?",
            [limit],
        ).fetchall()
    except duckdb.CatalogException:
        return []
    return [
        plan for (plan_id,) in ids if (plan := load_target_plan(connection, plan_id)) is not None
    ]
