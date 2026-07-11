"""Typed FastAPI routes for target-bird plans."""

from __future__ import annotations

import asyncio
import re
from collections.abc import Callable, Mapping
from datetime import datetime
from pathlib import Path
from typing import Any, Literal, cast

import duckdb
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    ValidationError,
    field_validator,
    model_validator,
)

from databox.agents.birding_trip_planner import NormalizedLocation, resolve_arizona_location
from databox.agents.cloudflare_workers_ai import (
    CloudflareAuthenticationError,
    CloudflareConfigurationError,
    CloudflareMalformedResponseError,
    CloudflareModelUnavailableError,
    CloudflareRateLimitError,
    CloudflareTimeoutError,
    CloudflareWorkersAIClient,
    TargetPlanModelClient,
    TargetWeatherPrompt,
)
from databox.config.settings import settings
from databox.target_planning import (
    TargetPlanner,
    TargetPlanResult,
    TargetRequest,
    list_target_plans,
    load_target_plan,
)

JsonGetter = Callable[[str, Mapping[str, object]], dict[str, Any]]


class TargetLocationSelection(BaseModel):
    model_config = ConfigDict(extra="forbid")
    display_name: str = Field(min_length=1, max_length=300)
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    timezone: str = Field(min_length=1, max_length=64)
    region_code: Literal["US-AZ"]


class CreateTargetPlanRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    species_code: str = Field(pattern=r"^[A-Za-z0-9]{1,64}$")
    location: str = Field(min_length=1, max_length=300)
    location_selection: TargetLocationSelection
    radius_miles: float = Field(ge=1, le=300, allow_inf_nan=False)
    start_at: datetime
    duration_minutes: int = Field(ge=1, le=1440)

    @field_validator("location")
    @classmethod
    def strip_location(cls, value: str) -> str:
        result = value.strip()
        if not result:
            raise ValueError("location is required")
        return result

    @field_validator("start_at")
    @classmethod
    def local_time(cls, value: datetime) -> datetime:
        if value.tzinfo is not None:
            raise ValueError("start_at must be a local timestamp without a time zone")
        return value


class TargetOriginResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    requested_location: str = Field(max_length=300)
    normalized_location_name: str = Field(max_length=300)
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    timezone: str = Field(max_length=64)
    region_code: Literal["US-AZ"]


class TargetCandidateResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    location_id: str = Field(min_length=1, max_length=128)
    location_name: str | None = Field(default=None, max_length=300)
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    observation_count: int = Field(ge=1)
    latest_observation_at: str = Field(min_length=1, max_length=64)
    distance_km: float = Field(ge=0, le=483)
    distance_miles: float = Field(ge=0, le=300)
    evidence_loaded_at: str | None = Field(default=None, max_length=64)

    @field_validator("latest_observation_at", "evidence_loaded_at")
    @classmethod
    def valid_timestamp(cls, value: str | None) -> str | None:
        if value is None:
            return None
        try:
            datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            raise ValueError("timestamp is invalid") from None
        return value


class TargetPlanResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    target_plan_id: str = Field(pattern=r"^target_[0-9a-f]{32}$")
    species_code: str = Field(pattern=r"^[A-Za-z0-9]{1,64}$")
    common_name: str | None = Field(default=None, max_length=200)
    scientific_name: str | None = Field(default=None, max_length=200)
    taxonomic_category: Literal["species", "hybrid"]
    origin: TargetOriginResponse
    radius_miles: float = Field(ge=1, le=300)
    radius_km: float = Field(ge=1.609, le=483)
    window_start: str = Field(max_length=64)
    window_end: str = Field(max_length=64)
    duration_minutes: int = Field(ge=1, le=1440)
    candidates: list[TargetCandidateResponse] = Field(max_length=10)
    weather: TargetWeatherPrompt
    action_ids: list[
        Literal[
            "try_top_location",
            "arrive_early",
            "review_freshness",
            "check_weather",
            "verify_access",
        ]
    ] = Field(min_length=1, max_length=5)
    guidance: list[str] = Field(min_length=1, max_length=5)
    caveats: list[str] = Field(max_length=20)
    evidence_freshness_at: str | None = Field(default=None, max_length=64)
    created_at: str = Field(max_length=64)

    @model_validator(mode="after")
    def validate_relationships(self) -> TargetPlanResponse:
        try:
            start = datetime.fromisoformat(self.window_start.replace("Z", "+00:00"))
            end = datetime.fromisoformat(self.window_end.replace("Z", "+00:00"))
            datetime.fromisoformat(self.created_at.replace("Z", "+00:00"))
        except ValueError:
            raise ValueError("target plan timestamp is invalid") from None
        if (end - start).total_seconds() != self.duration_minutes * 60:
            raise ValueError("target plan duration does not match its window")
        if abs(self.radius_km - self.radius_miles * 1.609344) > 0.01:
            raise ValueError("target plan radius units are inconsistent")
        if len(self.action_ids) != len(set(self.action_ids)):
            raise ValueError("target plan actions must be unique")
        if len(self.action_ids) != len(self.guidance):
            raise ValueError("target plan actions and guidance are inconsistent")
        if not self.candidates and {"try_top_location", "verify_access"}.intersection(
            self.action_ids
        ):
            raise ValueError("empty target evidence cannot select a location action")
        for candidate in self.candidates:
            if candidate.distance_miles > self.radius_miles + 0.001:
                raise ValueError("target candidate is outside the requested radius")
            if abs(candidate.distance_km - candidate.distance_miles * 1.609344) > 0.02:
                raise ValueError("target candidate distance units are inconsistent")
        expected_freshness = max(
            (
                candidate.evidence_loaded_at
                for candidate in self.candidates
                if candidate.evidence_loaded_at is not None
            ),
            default=None,
        )
        if self.evidence_freshness_at != expected_freshness:
            raise ValueError("target evidence freshness is inconsistent")
        return self


class TargetPlanListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    plans: list[TargetPlanResponse] = Field(max_length=100)


def _error(code: str, message: str, status: int) -> JSONResponse:
    return JSONResponse(status_code=status, content={"error": {"code": code, "message": message}})


def _response(result: TargetPlanResult) -> TargetPlanResponse:
    payload = result.to_dict()
    payload.pop("model")
    return TargetPlanResponse.model_validate(payload)


def register_target_planning_routes(
    app: FastAPI,
    *,
    database_path: str,
    model_client: TargetPlanModelClient | None,
    weather_getter: JsonGetter | None,
    mutation_lock: asyncio.Lock,
) -> None:
    @app.get("/api/target-plans", response_model=TargetPlanListResponse)
    async def list_plans() -> TargetPlanListResponse | JSONResponse:
        if not Path(database_path).exists():
            return TargetPlanListResponse(plans=[])
        connection = None
        try:
            connection = duckdb.connect(database_path, read_only=True)
            return TargetPlanListResponse(
                plans=[_response(item) for item in list_target_plans(connection)]
            )
        except (duckdb.Error, ValueError):
            return _error("database_unavailable", "The local target plans are unavailable", 503)
        finally:
            if connection is not None:
                connection.close()

    @app.get("/api/target-plans/{target_plan_id}", response_model=TargetPlanResponse)
    async def get_plan(target_plan_id: str) -> TargetPlanResponse | JSONResponse:
        if re.fullmatch(r"target_[0-9a-f]{32}", target_plan_id) is None:
            return _error("invalid_request", "Invalid target plan identifier", 400)
        if not Path(database_path).exists():
            return _error("not_found", "Target plan not found", 404)
        connection = None
        try:
            connection = duckdb.connect(database_path, read_only=True)
            plan = load_target_plan(connection, target_plan_id)
            return (
                _response(plan)
                if plan is not None
                else _error("not_found", "Target plan not found", 404)
            )
        except (duckdb.Error, ValueError):
            return _error("database_unavailable", "The local target plans are unavailable", 503)
        finally:
            if connection is not None:
                connection.close()

    @app.post("/api/target-plans", status_code=201, response_model=TargetPlanResponse)
    async def create_plan(payload: CreateTargetPlanRequest) -> TargetPlanResponse | JSONResponse:
        selected = NormalizedLocation(
            requested_location=payload.location,
            normalized_location_name=payload.location_selection.display_name,
            latitude=payload.location_selection.latitude,
            longitude=payload.location_selection.longitude,
            region_code=payload.location_selection.region_code,
            timezone=payload.location_selection.timezone,
        )
        try:
            origin = resolve_arizona_location(payload.location, selected)
        except ValueError as exc:
            return _error("invalid_location", str(exc), 400)
        if mutation_lock.locked():
            return _error("planner_busy", "A target plan is already running", 409)
        async with mutation_lock:
            connection = None
            try:
                Path(database_path).parent.mkdir(parents=True, exist_ok=True)
                connection = duckdb.connect(database_path)
                client = model_client or CloudflareWorkersAIClient.from_settings(settings)
                if not hasattr(client, "synthesize_target"):
                    raise CloudflareConfigurationError("Target planning model is unavailable")
                result = TargetPlanner(
                    connection,
                    model_client=cast(TargetPlanModelClient, client),
                    weather_getter=weather_getter,
                ).create(
                    TargetRequest(
                        species_code=payload.species_code,
                        origin=origin,
                        radius_miles=payload.radius_miles,
                        start_at=payload.start_at,
                        duration_minutes=payload.duration_minutes,
                    )
                )
                return _response(result)
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
            except ValidationError:
                return _error(
                    "planner_failed", "The target planner could not complete the plan", 500
                )
            except ValueError as exc:
                return _error("invalid_request", str(exc), 400)
            except duckdb.Error:
                return _error("database_unavailable", "The local warehouse is unavailable", 503)
            except Exception:
                return _error(
                    "planner_failed", "The target planner could not complete the plan", 500
                )
            finally:
                if connection is not None:
                    connection.close()
