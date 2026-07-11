"""Read-only API for watched-bird evaluation runs and reports."""

from __future__ import annotations

import re
from datetime import datetime, timedelta
from pathlib import Path
from typing import Literal

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

from databox.agents.cloudflare_workers_ai import TargetWeatherPrompt
from databox.watched_bird_evaluator import (
    load_evaluation_runs,
    load_watch_report,
    load_watch_reports,
)


def _parse_timestamp(value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        raise ValueError("timestamp is invalid") from None
    if parsed.tzinfo is None:
        raise ValueError("timestamp must include an offset")
    return parsed


class EvaluationRunResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    run_id: str = Field(pattern=r"^watch_eval_[0-9a-f]{64}$")
    refresh_id: str = Field(min_length=1, max_length=128)
    status: Literal["running", "completed", "failed"]
    watches_evaluated: int = Field(ge=0)
    matches_created: int = Field(ge=0)
    cancellations_resolved: int = Field(ge=0)
    started_at: str = Field(min_length=1, max_length=64)
    completed_at: str | None = Field(default=None, max_length=64)
    safe_error_code: Literal["evaluation_failed"] | None = None

    @model_validator(mode="after")
    def validate_run_state(self) -> EvaluationRunResponse:
        started = _parse_timestamp(self.started_at)
        completed = _parse_timestamp(self.completed_at) if self.completed_at is not None else None
        if self.status == "running" and (completed is not None or self.safe_error_code is not None):
            raise ValueError("running evaluation state is inconsistent")
        if self.status in {"completed", "failed"} and completed is None:
            raise ValueError("terminal evaluation must have a completion time")
        if completed is not None and completed < started:
            raise ValueError("evaluation completion precedes its start")
        if self.status == "failed" and self.safe_error_code != "evaluation_failed":
            raise ValueError("failed evaluation must expose its safe error code")
        if self.status == "completed" and self.safe_error_code is not None:
            raise ValueError("completed evaluation cannot expose an error")
        return self


class EvaluationRunListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    runs: list[EvaluationRunResponse] = Field(max_length=100)


class WatchClusterResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)

    location_id: str = Field(min_length=1, max_length=128)
    location_name: str | None = Field(default=None, max_length=300)
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    independent_submission_count: int = Field(ge=1)
    latest_observation_at: str = Field(min_length=1, max_length=64)
    distance_km: float = Field(ge=0, le=483)
    distance_miles: float = Field(ge=0, le=300)
    evidence_loaded_at: str | None = Field(default=None, max_length=64)

    @field_validator("latest_observation_at")
    @classmethod
    def validate_latest_observation(cls, value: str) -> str:
        _parse_timestamp(value)
        return value

    @field_validator("evidence_loaded_at")
    @classmethod
    def validate_loaded_at(cls, value: str | None) -> str | None:
        if value is not None:
            _parse_timestamp(value)
        return value


class WatchReportResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)

    report_id: str = Field(pattern=r"^watch_report_[0-9a-f]{32}$")
    run_id: str = Field(pattern=r"^watch_eval_[0-9a-f]{64}$")
    species_code: str = Field(pattern=r"^[A-Za-z0-9]{1,64}$")
    common_name: str | None = Field(default=None, max_length=200)
    scientific_name: str | None = Field(default=None, max_length=200)
    watch_center_name: str = Field(min_length=1, max_length=300)
    watch_center_latitude: float = Field(ge=-90, le=90)
    watch_center_longitude: float = Field(ge=-180, le=180)
    radius_miles: float = Field(ge=1, le=300)
    confirmed_location_id: str = Field(min_length=1, max_length=128)
    confirmed_location_name: str | None = Field(default=None, max_length=300)
    confirmed_latitude: float = Field(ge=-90, le=90)
    confirmed_longitude: float = Field(ge=-180, le=180)
    confirmed_distance_miles: float = Field(ge=0, le=300)
    independent_submission_count: int = Field(ge=1)
    newest_observation_at: str = Field(min_length=1, max_length=64)
    clusters: list[WatchClusterResponse] = Field(min_length=1, max_length=10)
    morning_start: str = Field(min_length=1, max_length=64)
    morning_end: str = Field(min_length=1, max_length=64)
    event_horizon_end: str = Field(min_length=1, max_length=64)
    weather: TargetWeatherPrompt
    caveats: list[str] = Field(max_length=20)
    emphasis_ids: list[
        Literal["freshness", "confirmed_location", "weather", "access", "uncertainty"]
    ] = Field(min_length=1, max_length=5)
    report_status: Literal["ready", "deterministic_degraded"]
    evidence_freshness_at: str = Field(min_length=1, max_length=64)
    created_at: str = Field(min_length=1, max_length=64)
    event_uid: str | None = Field(default=None, max_length=128)
    sequence: int | None = Field(default=None, ge=0)
    event_method: Literal["REQUEST", "CANCEL"] | None = None
    event_status: (
        Literal[
            "pending_request", "pending_cancel", "accepted", "suppressed", "cancelled", "expired"
        ]
        | None
    ) = None

    @field_validator("caveats")
    @classmethod
    def validate_caveats(cls, value: list[str]) -> list[str]:
        if any(not item or len(item) > 500 for item in value):
            raise ValueError("report caveat text is invalid")
        return value

    @model_validator(mode="after")
    def validate_relationships(self) -> WatchReportResponse:
        if len({item.location_id for item in self.clusters}) != len(self.clusters):
            raise ValueError("cluster IDs must be unique")
        if len(set(self.emphasis_ids)) != len(self.emphasis_ids):
            raise ValueError("emphasis IDs must be unique")
        confirmed = self.clusters[0]
        if (
            confirmed.location_id != self.confirmed_location_id
            or confirmed.location_name != self.confirmed_location_name
            or confirmed.independent_submission_count != self.independent_submission_count
            or confirmed.latest_observation_at != self.newest_observation_at
        ):
            raise ValueError("confirmed destination must equal the top cluster")
        if self.confirmed_distance_miles != confirmed.distance_miles:
            raise ValueError("confirmed distance must equal the top cluster")
        morning_start = _parse_timestamp(self.morning_start)
        morning_end = _parse_timestamp(self.morning_end)
        horizon = _parse_timestamp(self.event_horizon_end)
        freshness = _parse_timestamp(self.evidence_freshness_at)
        created = _parse_timestamp(self.created_at)
        cluster_freshness = max(
            _parse_timestamp(item.latest_observation_at) for item in self.clusters
        )
        if morning_end - morning_start != timedelta(hours=2) or morning_end > horizon:
            raise ValueError("morning window is inconsistent")
        if horizon - created != timedelta(days=5) or morning_start <= created:
            raise ValueError("event horizon is inconsistent")
        if freshness != cluster_freshness:
            raise ValueError("evidence freshness is inconsistent")
        if any(item.distance_miles > self.radius_miles + 0.001 for item in self.clusters):
            raise ValueError("cluster lies outside the watch radius")
        event_values = (
            self.event_uid,
            self.sequence,
            self.event_method,
            self.event_status,
        )
        if any(value is None for value in event_values) and not all(
            value is None for value in event_values
        ):
            raise ValueError("event state is incomplete")
        return self


class WatchReportListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    reports: list[WatchReportResponse] = Field(max_length=100)


def _error(code: str, message: str, status: int) -> JSONResponse:
    return JSONResponse(status_code=status, content={"error": {"code": code, "message": message}})


def register_watched_bird_routes(app: FastAPI, *, database_path: str) -> None:
    @app.get("/api/watch-evaluations", response_model=EvaluationRunListResponse)
    async def evaluation_runs() -> EvaluationRunListResponse | JSONResponse:
        if not Path(database_path).exists():
            return EvaluationRunListResponse(runs=[])
        connection = None
        try:
            connection = duckdb.connect(database_path, read_only=True)
            return EvaluationRunListResponse(runs=load_evaluation_runs(connection))
        except (duckdb.Error, ValueError, ValidationError):
            return _error("database_unavailable", "Watch evaluations are unavailable", 503)
        finally:
            if connection is not None:
                connection.close()

    @app.get("/api/watch-reports", response_model=WatchReportListResponse)
    async def reports() -> WatchReportListResponse | JSONResponse:
        if not Path(database_path).exists():
            return WatchReportListResponse(reports=[])
        connection = None
        try:
            connection = duckdb.connect(database_path, read_only=True)
            return WatchReportListResponse(reports=load_watch_reports(connection))
        except (duckdb.Error, ValueError, ValidationError):
            return _error("database_unavailable", "Watch reports are unavailable", 503)
        finally:
            if connection is not None:
                connection.close()

    @app.get("/api/watch-reports/{report_id}", response_model=WatchReportResponse)
    async def report(report_id: str) -> WatchReportResponse | JSONResponse:
        if re.fullmatch(r"watch_report_[0-9a-f]{32}", report_id) is None:
            return _error("invalid_request", "Invalid watch report identifier", 400)
        if not Path(database_path).exists():
            return _error("not_found", "Watch report not found", 404)
        connection = None
        try:
            connection = duckdb.connect(database_path, read_only=True)
            value = load_watch_report(connection, report_id)
            if value is None:
                return _error("not_found", "Watch report not found", 404)
            return WatchReportResponse.model_validate(value)
        except (duckdb.Error, ValueError, ValidationError):
            return _error("database_unavailable", "Watch reports are unavailable", 503)
        finally:
            if connection is not None:
                connection.close()
