"""Loopback-only HTTP API for the local Birding Trip Copilot."""

from __future__ import annotations

import asyncio
import json
from collections.abc import Callable, Mapping
from datetime import datetime
from pathlib import Path
from typing import Any, Literal, cast

import duckdb
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field, field_validator

from databox.agents.birding_trip_planner import TripRequest, run_trip_planner_agent_async
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


class CreateTripPlanRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    location: str = Field(min_length=1, max_length=300)
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
    media: list[EvidenceResponse]
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
    media = [row for row in evidence if row.source == "xeno_canto" and row.status == "available"]
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


def create_app(
    *,
    database_path: str | None = None,
    model_client: TripPlanModelClient | None = None,
    weather_getter: JsonGetter | None = None,
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
