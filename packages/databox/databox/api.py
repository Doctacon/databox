"""Loopback-only HTTP API for the local Birding Trip Copilot."""

from __future__ import annotations

import asyncio
import json
import re
from collections.abc import Callable, Mapping
from datetime import datetime
from pathlib import Path
from typing import Any, Literal, cast
from urllib.parse import urlsplit

import duckdb
from fastapi import FastAPI, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field, field_validator

from databox.agent_tools.open_meteo_geocoding import (
    ArizonaLocationSuggestion,
    OpenMeteoGeocodingError,
    search_arizona_locations,
)
from databox.agents.birding_trip_planner import (
    NormalizedLocation,
    TripRequest,
    resolve_arizona_location,
    run_trip_planner_agent_async,
)
from databox.agents.cloudflare_workers_ai import (
    CLOUDFLARE_WORKERS_AI_MODEL,
    CloudflareAuthenticationError,
    CloudflareConfigurationError,
    CloudflareMalformedResponseError,
    CloudflareModelUnavailableError,
    CloudflareRateLimitError,
    CloudflareTimeoutError,
    CloudflareWorkersAIClient,
    TripPlanModelClient,
)
from databox.config.settings import PROJECT_ROOT, settings

JsonGetter = Callable[[str, Mapping[str, object]], dict[str, Any]]
JsonObject = dict[str, Any]


class LocationSelectionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    display_name: str = Field(min_length=1, max_length=300)
    latitude: float
    longitude: float
    timezone: str = Field(min_length=1, max_length=64)
    region_code: Literal["US-AZ"]


class CreateTripPlanRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    location: str = Field(min_length=1, max_length=300)
    location_selection: LocationSelectionRequest | None = None
    start_at: datetime
    duration_minutes: int = Field(gt=0, le=1440)
    skill_level: str | None = Field(default=None, max_length=64)
    constraints: str | None = Field(default=None, max_length=1000)

    @field_validator("location")
    @classmethod
    def strip_location(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("location is required")
        return stripped

    @field_validator("skill_level", "constraints")
    @classmethod
    def strip_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return value.strip() or None

    @field_validator("start_at")
    @classmethod
    def require_local_timestamp(cls, value: datetime) -> datetime:
        if value.tzinfo is not None:
            raise ValueError("start_at must be a local timestamp without a time zone")
        return value


class ErrorBody(BaseModel):
    code: str
    message: str


class ErrorResponse(BaseModel):
    error: ErrorBody


class HealthResponse(BaseModel):
    status: Literal["ready", "degraded"]
    database_ready: bool
    model_ready: bool


class LocationSuggestionResponse(BaseModel):
    display_name: str
    latitude: float
    longitude: float
    timezone: str
    region_code: Literal["US-AZ"]


class LocationSearchResponse(BaseModel):
    locations: list[LocationSuggestionResponse]


class PlanSummaryResponse(BaseModel):
    trip_plan_id: str
    requested_location: str
    normalized_location_name: str | None
    window_start: str
    window_end: str
    duration_minutes: int
    plan_status: str
    caveats: list[str]
    created_at: str
    updated_at: str


class TripPlanResponse(PlanSummaryResponse):
    latitude: float | None
    longitude: float | None
    region_code: str | None
    timezone: str | None
    skill_level: str | None
    constraints_text: str | None
    field_plan_text: str | None


class RecommendationResponse(BaseModel):
    recommendation_id: str
    species_code: str | None
    common_name: str | None
    scientific_name: str | None
    recommendation_group: str
    rank_order: int
    confidence_label: str | None
    rationale_text: str | None
    caveats: list[str]


class EvidenceResponse(BaseModel):
    evidence_id: str
    recommendation_id: str | None
    source: str
    source_table: str | None
    source_record_id: str | None
    evidence_type: str
    status: str
    retrieved_at: str | None
    summary: JsonObject
    payload: JsonObject
    caveats: list[str]


class MediaResponse(BaseModel):
    evidence_id: str
    recommendation_id: str | None
    source_record_id: str | None
    recording_id: str | None
    status: str
    species_name: str | None
    recording_type: str | None
    quality: str | None
    recordist: str | None
    license_text: str
    license_url: str | None
    source_url: str | None
    audio_url: str | None
    caveats: list[str]


class ToolTraceResponse(BaseModel):
    tool_trace_id: str
    step_order: int
    tool_name: str
    tool_status: str
    started_at: str | None
    completed_at: str | None
    input: JsonObject
    output_summary: JsonObject
    caveats: list[str]


class TripPlanDetailResponse(BaseModel):
    plan: TripPlanResponse
    recommendations: list[RecommendationResponse]
    evidence: list[EvidenceResponse]
    weather: EvidenceResponse | None
    media: list[MediaResponse]
    tool_traces: list[ToolTraceResponse]


class PlanListResponse(BaseModel):
    plans: list[PlanSummaryResponse]


def _error(code: str, message: str, status: int) -> JSONResponse:
    body = ErrorResponse(error=ErrorBody(code=code, message=message))
    return JSONResponse(status_code=status, content=body.model_dump())


def _json_value(value: object, fallback: object) -> object:
    if not isinstance(value, str):
        return fallback
    try:
        return json.loads(value)
    except (TypeError, json.JSONDecodeError):
        return fallback


def _json_object(value: object) -> JsonObject:
    parsed = _json_value(value, {})
    return cast(JsonObject, parsed) if isinstance(parsed, dict) else {}


def _json_strings(value: object) -> list[str]:
    parsed = _json_value(value, [])
    if not isinstance(parsed, list):
        return []
    return [item for item in parsed if isinstance(item, str)]


_XENO_CANTO_HOSTS = frozenset({"xeno-canto.org", "www.xeno-canto.org"})
_XENO_RECORDING_ID = re.compile(r"^(?:XC)?(\d+)$")
_XENO_SOURCE_PATH = re.compile(r"^/(\d+)/?$")
_XENO_AUDIO_PATH = re.compile(r"^/(\d+)/download/?$")
_CREATIVE_COMMONS_HOSTS = frozenset({"creativecommons.org", "www.creativecommons.org"})
_CREATIVE_COMMONS_PATH = re.compile(r"^/licenses/([a-z0-9-]+)/([0-9.]+)/?$")
_UNAVAILABLE_VALUES = frozenset({"unavailable", "not available", "none", "null", "n/a"})


def _text(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    result = value.strip()
    if not result or result.lower() in _UNAVAILABLE_VALUES:
        return None
    return result


def _canonical_digits(value: str) -> str:
    return value.lstrip("0") or "0"


def _recording_id(row: EvidenceResponse) -> str | None:
    values = (
        row.source_record_id,
        row.summary.get("source_record_id"),
        row.summary.get("recording_id"),
        row.payload.get("source_record_id"),
        row.payload.get("recording_id"),
    )
    normalized: set[str] = set()
    found = False
    for value in values:
        if value is None:
            continue
        found = True
        if not isinstance(value, str):
            return None
        match = _XENO_RECORDING_ID.fullmatch(value)
        if match is None:
            return None
        normalized.add(_canonical_digits(match.group(1)))
    return normalized.pop() if found and len(normalized) == 1 else None


def _safe_xeno_canto_url(
    value: object, *, kind: Literal["source", "audio"]
) -> tuple[str, str] | None:
    raw = _text(value)
    if raw is None:
        return None
    try:
        parsed = urlsplit(raw)
        if parsed.port is not None:
            return None
    except ValueError:
        return None
    if (
        parsed.scheme != "https"
        or parsed.hostname not in _XENO_CANTO_HOSTS
        or parsed.username is not None
        or parsed.password is not None
        or parsed.query
        or parsed.fragment
    ):
        return None
    match = (_XENO_SOURCE_PATH if kind == "source" else _XENO_AUDIO_PATH).fullmatch(parsed.path)
    if match is None:
        return None
    return raw, match.group(1)


def _media_url(
    row: EvidenceResponse, *, field: str, kind: Literal["source", "audio"]
) -> tuple[str, str] | None:
    supplied = [
        value for value in (row.summary.get(field), row.payload.get(field)) if value is not None
    ]
    if not supplied:
        return None
    validated = [_safe_xeno_canto_url(value, kind=kind) for value in supplied]
    if any(value is None for value in validated):
        return None
    safe = cast(list[tuple[str, str]], validated)
    if len({value[1] for value in safe}) != 1:
        return None
    return safe[0]


def _license(value: object) -> tuple[str, str | None]:
    raw = _text(value)
    if raw is None:
        return "License not reported", None
    candidate = f"https:{raw}" if raw.startswith("//") else raw
    try:
        parsed = urlsplit(candidate)
        if parsed.port is not None:
            return "License link unavailable", None
    except ValueError:
        return "License link unavailable", None
    if parsed.scheme or parsed.netloc:
        match = _CREATIVE_COMMONS_PATH.fullmatch(parsed.path)
        if (
            parsed.scheme == "https"
            and parsed.hostname in _CREATIVE_COMMONS_HOSTS
            and parsed.username is None
            and parsed.password is None
            and not parsed.query
            and not parsed.fragment
            and match is not None
        ):
            return f"CC {match.group(1).upper()} {match.group(2)}", candidate
        return "License link unavailable", None
    return raw, None


def _media_response(row: EvidenceResponse) -> MediaResponse:
    recording_id = _recording_id(row)
    source = _media_url(row, field="recording_url", kind="source")
    audio = _media_url(row, field="audio_file_url", kind="audio")
    source_matches = recording_id is not None and source is not None and source[1] == recording_id
    audio_matches = recording_id is not None and audio is not None and audio[1] == recording_id
    license_text, license_url = _license(row.summary.get("license") or row.payload.get("license"))
    return MediaResponse(
        evidence_id=row.evidence_id,
        recommendation_id=row.recommendation_id,
        source_record_id=row.source_record_id,
        recording_id=recording_id,
        status=row.status,
        species_name=_text(row.summary.get("english_name"))
        or _text(row.payload.get("english_name")),
        recording_type=_text(row.summary.get("recording_type"))
        or _text(row.payload.get("recording_type")),
        quality=_text(row.summary.get("quality")) or _text(row.payload.get("quality")),
        recordist=_text(row.summary.get("recordist")) or _text(row.payload.get("recordist")),
        license_text=license_text,
        license_url=license_url,
        source_url=source[0] if source_matches and source is not None else None,
        audio_url=audio[0] if audio_matches and audio is not None else None,
        caveats=row.caveats,
    )


def _rows(cursor: duckdb.DuckDBPyConnection) -> list[dict[str, Any]]:
    columns = [item[0] for item in cursor.description]
    return [dict(zip(columns, row, strict=True)) for row in cursor.fetchall()]


def _table_exists(connection: duckdb.DuckDBPyConnection, table: str) -> bool:
    schema, name = table.split(".", 1)
    row = connection.execute(
        """
        SELECT 1 FROM information_schema.tables
        WHERE table_schema = ? AND table_name = ?
        """,
        [schema, name],
    ).fetchone()
    return row is not None


def _plan_summaries(connection: duckdb.DuckDBPyConnection) -> list[PlanSummaryResponse]:
    if not _table_exists(connection, "birding_agent.trip_plans"):
        return []
    rows = _rows(
        connection.execute(
            """
            SELECT trip_plan_id, requested_location, normalized_location_name,
                   window_start, window_end, duration_minutes, plan_status,
                   caveats_json, created_at, updated_at
            FROM birding_agent.trip_plans
            ORDER BY updated_at DESC, created_at DESC
            LIMIT 100
            """
        )
    )
    for row in rows:
        row["caveats"] = _json_strings(row.pop("caveats_json", None))
    return [PlanSummaryResponse.model_validate(row) for row in rows]


def _plan_detail(
    connection: duckdb.DuckDBPyConnection, plan_id: str
) -> TripPlanDetailResponse | None:
    if not _table_exists(connection, "birding_agent.trip_plans"):
        return None
    plans = _rows(
        connection.execute(
            """
            SELECT trip_plan_id, requested_location, normalized_location_name,
                   latitude, longitude, region_code, window_start, window_end,
                   duration_minutes, skill_level, constraints_text, plan_status,
                   field_plan_text, caveats_json, created_at, updated_at
            FROM birding_agent.trip_plans
            WHERE trip_plan_id = ?
            """,
            [plan_id],
        )
    )
    if not plans:
        return None
    plan_row = plans[0]
    plan_row["caveats"] = _json_strings(plan_row.pop("caveats_json", None))
    plan_row["timezone"] = None
    plan = TripPlanResponse.model_validate(plan_row)

    recommendation_rows = _rows(
        connection.execute(
            """
            SELECT recommendation_id, species_code, common_name, scientific_name,
                   recommendation_group, rank_order, confidence_label,
                   rationale_text, caveats_json
            FROM birding_agent.trip_plan_recommendations
            WHERE trip_plan_id = ?
            ORDER BY recommendation_group, rank_order
            """,
            [plan_id],
        )
    )
    for row in recommendation_rows:
        row["caveats"] = _json_strings(row.pop("caveats_json", None))
    recommendations = [RecommendationResponse.model_validate(row) for row in recommendation_rows]

    evidence_rows = _rows(
        connection.execute(
            """
            SELECT evidence_id, recommendation_id, source, source_table,
                   source_record_id, evidence_type, status, retrieved_at,
                   summary_json, payload_json, caveats_json
            FROM birding_agent.trip_plan_evidence
            WHERE trip_plan_id = ?
            ORDER BY source, evidence_type, evidence_id
            """,
            [plan_id],
        )
    )
    for row in evidence_rows:
        row["summary"] = _json_object(row.pop("summary_json", None))
        row["payload"] = _json_object(row.pop("payload_json", None))
        row["caveats"] = _json_strings(row.pop("caveats_json", None))
    evidence = [EvidenceResponse.model_validate(row) for row in evidence_rows]

    trace_rows = _rows(
        connection.execute(
            """
            SELECT tool_trace_id, step_order, tool_name, tool_status, started_at,
                   completed_at, input_json, output_summary_json, caveats_json
            FROM birding_agent.trip_plan_tool_traces
            WHERE trip_plan_id = ?
            ORDER BY step_order
            """,
            [plan_id],
        )
    )
    for row in trace_rows:
        row["input"] = _json_object(row.pop("input_json", None))
        row["output_summary"] = _json_object(row.pop("output_summary_json", None))
        row["caveats"] = _json_strings(row.pop("caveats_json", None))
    traces = [ToolTraceResponse.model_validate(row) for row in trace_rows]

    weather = next((row for row in evidence if row.source == "open_meteo"), None)
    if weather is not None:
        weather_timezone = weather.payload.get("timezone")
        if isinstance(weather_timezone, str):
            plan.timezone = weather_timezone
    media = [
        _media_response(row)
        for row in evidence
        if row.source == "xeno_canto" and row.status == "available"
    ]
    return TripPlanDetailResponse(
        plan=plan,
        recommendations=recommendations,
        evidence=evidence,
        weather=weather,
        media=media,
        tool_traces=traces,
    )


def _is_database_busy(exc: BaseException) -> bool:
    text = str(exc).lower()
    return any(
        phrase in text for phrase in ("conflicting lock", "database is locked", "already open")
    )


def _selected_location(payload: CreateTripPlanRequest) -> NormalizedLocation | None:
    selected = payload.location_selection
    if selected is None:
        return None
    return NormalizedLocation(
        requested_location=payload.location,
        normalized_location_name=selected.display_name,
        latitude=selected.latitude,
        longitude=selected.longitude,
        region_code=selected.region_code,
        timezone=selected.timezone,
    )


def _suggestion_response(suggestion: ArizonaLocationSuggestion) -> LocationSuggestionResponse:
    return LocationSuggestionResponse(
        display_name=suggestion.display_name,
        latitude=suggestion.latitude,
        longitude=suggestion.longitude,
        timezone=suggestion.timezone,
        region_code="US-AZ",
    )


def create_app(
    *,
    database_path: str | None = None,
    model_client: TripPlanModelClient | None = None,
    weather_getter: JsonGetter | None = None,
    geocoding_getter: JsonGetter | None = None,
    static_dir: Path | None = None,
) -> FastAPI:
    """Create the local API; injected clients keep tests offline and deterministic."""

    db_path = database_path or settings.database_path
    frontend_dir = static_dir if static_dir is not None else PROJECT_ROOT / "app" / "dist"
    app = FastAPI(title="Birding Trip Copilot", docs_url="/api/docs", redoc_url=None)
    app.state.plan_lock = asyncio.Lock()

    @app.exception_handler(RequestValidationError)
    async def validation_error(_: Request, exc: RequestValidationError) -> JSONResponse:
        fields = sorted({".".join(str(part) for part in item["loc"][1:]) for item in exc.errors()})
        suffix = f": {', '.join(fields)}" if fields else ""
        return _error("invalid_request", f"Check the trip-planning inputs{suffix}", 422)

    @app.get("/api/health", response_model=HealthResponse)
    async def health() -> HealthResponse:
        database_ready = False
        try:
            if Path(db_path).exists():
                connection = duckdb.connect(db_path, read_only=True)
                connection.execute("SELECT 1")
                connection.close()
                database_ready = True
        except duckdb.Error:
            database_ready = False
        if model_client is not None:
            model_ready = model_client.model == CLOUDFLARE_WORKERS_AI_MODEL
        else:
            try:
                CloudflareWorkersAIClient.from_settings(settings)
                model_ready = True
            except CloudflareConfigurationError:
                model_ready = False
        return HealthResponse(
            status="ready" if database_ready and model_ready else "degraded",
            database_ready=database_ready,
            model_ready=model_ready,
        )

    @app.get(
        "/api/locations",
        response_model=LocationSearchResponse,
        responses={503: {"model": ErrorResponse}},
    )
    async def search_locations(
        q: str = Query(min_length=2, max_length=100),
    ) -> LocationSearchResponse | JSONResponse:
        try:
            locations = search_arizona_locations(q, http_get_json=geocoding_getter)
            return LocationSearchResponse(
                locations=[_suggestion_response(item) for item in locations]
            )
        except OpenMeteoGeocodingError:
            return _error(
                "geocoder_unavailable",
                "Location search is temporarily unavailable; enter valid Arizona coordinates",
                503,
            )

    @app.get(
        "/api/trip-plans",
        response_model=PlanListResponse,
        responses={503: {"model": ErrorResponse}},
    )
    async def list_trip_plans() -> PlanListResponse | JSONResponse:
        try:
            if not Path(db_path).exists():
                return PlanListResponse(plans=[])
            connection = duckdb.connect(db_path, read_only=True)
            plans = _plan_summaries(connection)
            connection.close()
            return PlanListResponse(plans=plans)
        except duckdb.Error as exc:
            if _is_database_busy(exc):
                return _error(
                    "database_busy", "The warehouse is refreshing; try again shortly", 503
                )
            return _error("database_unavailable", "The local warehouse is unavailable", 503)

    @app.get(
        "/api/trip-plans/{plan_id}",
        response_model=TripPlanDetailResponse,
        responses={
            400: {"model": ErrorResponse},
            404: {"model": ErrorResponse},
            503: {"model": ErrorResponse},
        },
    )
    async def get_trip_plan(plan_id: str) -> TripPlanDetailResponse | JSONResponse:
        if not plan_id or len(plan_id) > 128:
            return _error("invalid_request", "Invalid trip plan identifier", 400)
        try:
            if not Path(db_path).exists():
                return _error("not_found", "Trip plan not found", 404)
            connection = duckdb.connect(db_path, read_only=True)
            detail = _plan_detail(connection, plan_id)
            connection.close()
            if detail is None:
                return _error("not_found", "Trip plan not found", 404)
            return detail
        except duckdb.Error as exc:
            if _is_database_busy(exc):
                return _error(
                    "database_busy", "The warehouse is refreshing; try again shortly", 503
                )
            return _error("database_unavailable", "The local warehouse is unavailable", 503)

    @app.post(
        "/api/trip-plans",
        status_code=201,
        response_model=TripPlanDetailResponse,
        responses={
            400: {"model": ErrorResponse},
            409: {"model": ErrorResponse},
            422: {"model": ErrorResponse},
            429: {"model": ErrorResponse},
            500: {"model": ErrorResponse},
            503: {"model": ErrorResponse},
            504: {"model": ErrorResponse},
        },
    )
    async def create_trip_plan(
        payload: CreateTripPlanRequest,
    ) -> TripPlanDetailResponse | JSONResponse:
        try:
            resolved_location = resolve_arizona_location(
                payload.location, _selected_location(payload)
            )
        except ValueError as exc:
            return _error("invalid_location", str(exc), 400)
        if app.state.plan_lock.locked():
            return _error("planner_busy", "A trip plan is already running", 409)
        async with app.state.plan_lock:
            connection: duckdb.DuckDBPyConnection | None = None
            try:
                Path(db_path).parent.mkdir(parents=True, exist_ok=True)
                connection = duckdb.connect(db_path)
                result = await run_trip_planner_agent_async(
                    connection,
                    request=TripRequest(
                        location=payload.location,
                        start_at=payload.start_at,
                        duration_minutes=payload.duration_minutes,
                        skill_level=payload.skill_level,
                        constraints_text=payload.constraints,
                        timezone=resolved_location.timezone,
                        resolved_location=resolved_location,
                    ),
                    model_client=model_client,
                    weather_getter=weather_getter,
                )
                detail = _plan_detail(connection, result.trip_plan_id)
                if detail is None:
                    raise RuntimeError("Persisted trip plan could not be reloaded")
                return detail
            except CloudflareConfigurationError:
                return _error(
                    "model_not_configured", "Configure Cloudflare Workers AI in .env", 503
                )
            except CloudflareAuthenticationError:
                return _error(
                    "model_authentication_failed", "Cloudflare authentication failed", 503
                )
            except CloudflareRateLimitError:
                return _error("model_rate_limited", "Cloudflare rate limit reached; try later", 429)
            except CloudflareTimeoutError:
                return _error("model_timeout", "Cloudflare inference timed out; try again", 504)
            except (CloudflareMalformedResponseError, CloudflareModelUnavailableError):
                return _error("model_unavailable", "The configured model is unavailable", 503)
            except ValueError as exc:
                return _error("invalid_request", str(exc), 400)
            except duckdb.Error as exc:
                if _is_database_busy(exc):
                    return _error(
                        "database_busy", "The warehouse is refreshing; try again shortly", 503
                    )
                return _error("database_unavailable", "The local warehouse is unavailable", 503)
            except RuntimeError:
                return _error("planner_failed", "The trip planner could not complete the plan", 500)
            finally:
                if connection is not None:
                    connection.close()

    if frontend_dir.is_dir():
        assets_dir = frontend_dir / "assets"
        if assets_dir.is_dir():
            app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")

        @app.get("/{path:path}", include_in_schema=False)
        async def frontend(path: str) -> FileResponse:
            candidate = frontend_dir / path
            if path and candidate.is_file() and frontend_dir in candidate.resolve().parents:
                return FileResponse(candidate)
            return FileResponse(frontend_dir / "index.html")

    return app


app = create_app()
