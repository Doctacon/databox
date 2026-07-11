"""Safe local operator API for bird-alert delivery state and reconciliation."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

import duckdb
from fastapi import FastAPI, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field

from databox.bird_alert_outbox import (
    ALERT_SCHEMA,
    cleanup_outbox_history,
    delivery_allowed_actions,
    reconcile_unknown_as_delivered,
    reconcile_unknown_as_not_delivered,
    retry_terminal_delivery,
)


class DeliveryAttemptResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    attempt_number: int = Field(ge=0)
    phase: Literal[
        "send_started", "accepted", "retry_wait", "failed", "delivery_unknown", "claim_recovered"
    ]
    safe_reason: str | None = Field(default=None, max_length=64, pattern=r"^[a-z_]{1,64}$")
    occurred_at: str = Field(max_length=64)


class AlertDeliveryResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    outbox_id: str = Field(min_length=1, max_length=128)
    species_code: str = Field(pattern=r"^[A-Za-z0-9]{1,64}$")
    sequence: int = Field(ge=0)
    method: Literal["REQUEST", "CANCEL"]
    state: Literal[
        "pending",
        "claimed",
        "accepted",
        "retry_wait",
        "failed",
        "delivery_unknown",
        "cancelled",
        "superseded",
    ]
    attempt_count: int = Field(ge=0)
    next_attempt_at: str = Field(max_length=64)
    updated_at: str = Field(max_length=64)
    terminal_at: str | None = Field(default=None, max_length=64)
    safe_terminal_reason: str | None = Field(default=None, max_length=64, pattern=r"^[a-z_]{1,64}$")
    allowed_actions: list[
        Literal[
            "mark_delivered", "mark_not_delivered", "mark_not_delivered_and_retry", "retry_failed"
        ]
    ] = Field(max_length=2)
    can_retry: bool
    attempts: list[DeliveryAttemptResponse] = Field(max_length=20)


class AlertDeliveryListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    deliveries: list[AlertDeliveryResponse] = Field(max_length=1000)


class ReconciliationResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    status: Literal["accepted", "not_delivered", "retry_enqueued"]
    outbox_id: str = Field(min_length=1, max_length=128)


class CleanupResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    outbox_deleted: int = Field(ge=0)


def _error(code: str, message: str, status: int) -> JSONResponse:
    return JSONResponse(status_code=status, content={"error": {"code": code, "message": message}})


def _list_deliveries(database_path: str) -> AlertDeliveryListResponse:
    if not Path(database_path).exists():
        return AlertDeliveryListResponse(deliveries=[])
    connection = duckdb.connect(database_path, read_only=True)
    try:
        try:
            rows = connection.execute(
                f"""SELECT outbox_id, species_code, sequence, method, state,
                           attempt_count, next_attempt_at, updated_at, terminal_at,
                           safe_terminal_reason
                    FROM {ALERT_SCHEMA}.alert_outbox
                    ORDER BY updated_at DESC, outbox_id DESC LIMIT 1001"""
            ).fetchall()
        except duckdb.CatalogException:
            return AlertDeliveryListResponse(deliveries=[])
        if len(rows) > 1000:
            raise ValueError("alert delivery list exceeds its bound")
        deliveries: list[AlertDeliveryResponse] = []
        for row in rows:
            attempts = connection.execute(
                f"""SELECT attempt_number, phase, safe_reason, occurred_at
                    FROM {ALERT_SCHEMA}.outbox_attempts WHERE outbox_id=?
                    ORDER BY occurred_at DESC, attempt_id DESC LIMIT 21""",
                [row[0]],
            ).fetchall()
            if len(attempts) > 20:
                attempts = attempts[:20]
            actions, can_retry = delivery_allowed_actions(
                connection, outbox_id=str(row[0]), now=datetime.now(UTC)
            )
            deliveries.append(
                AlertDeliveryResponse(
                    outbox_id=str(row[0]),
                    species_code=str(row[1]),
                    sequence=int(row[2]),
                    method=str(row[3]),
                    state=str(row[4]),
                    attempt_count=int(row[5]),
                    next_attempt_at=str(row[6]),
                    updated_at=str(row[7]),
                    terminal_at=str(row[8]) if row[8] is not None else None,
                    safe_terminal_reason=str(row[9]) if row[9] is not None else None,
                    allowed_actions=actions,
                    can_retry=can_retry,
                    attempts=[
                        DeliveryAttemptResponse(
                            attempt_number=int(item[0]),
                            phase=str(item[1]),
                            safe_reason=str(item[2]) if item[2] is not None else None,
                            occurred_at=str(item[3]),
                        )
                        for item in attempts
                    ],
                )
            )
        return AlertDeliveryListResponse(deliveries=deliveries)
    finally:
        connection.close()


def register_bird_alert_delivery_routes(
    app: FastAPI,
    *,
    database_path: str,
    mutation_lock: asyncio.Lock,
) -> None:
    @app.get("/api/alert-deliveries", response_model=AlertDeliveryListResponse)
    async def list_alert_deliveries() -> AlertDeliveryListResponse | JSONResponse:
        try:
            return _list_deliveries(database_path)
        except (duckdb.Error, ValueError):
            return _error("database_unavailable", "Alert delivery status is unavailable", 503)

    @app.post(
        "/api/alert-deliveries/{outbox_id}/mark-delivered",
        response_model=ReconciliationResponse,
    )
    async def mark_delivered(
        outbox_id: str, confirm: bool = Query(default=False)
    ) -> ReconciliationResponse | JSONResponse:
        if not confirm:
            return _error("confirmation_required", "Confirm alert reconciliation", 409)
        if not outbox_id.startswith("alert_outbox_") or len(outbox_id) > 128:
            return _error("invalid_request", "Invalid alert delivery identity", 400)
        if mutation_lock.locked():
            return _error("delivery_busy", "Another alert operation is in progress", 409)
        async with mutation_lock:
            connection = duckdb.connect(database_path)
            try:
                reconcile_unknown_as_delivered(
                    connection, outbox_id=outbox_id, now=datetime.now(UTC)
                )
                return ReconciliationResponse(status="accepted", outbox_id=outbox_id)
            except ValueError:
                return _error("invalid_state", "Alert delivery state cannot be reconciled", 409)
            except duckdb.Error:
                return _error("database_unavailable", "Alert delivery status is unavailable", 503)
            finally:
                connection.close()

    @app.post(
        "/api/alert-deliveries/{outbox_id}/mark-not-delivered",
        response_model=ReconciliationResponse,
    )
    async def mark_not_delivered(
        outbox_id: str, confirm: bool = Query(default=False)
    ) -> ReconciliationResponse | JSONResponse:
        if not confirm:
            return _error("confirmation_required", "Confirm alert reconciliation", 409)
        if not outbox_id.startswith("alert_outbox_") or len(outbox_id) > 128:
            return _error("invalid_request", "Invalid alert delivery identity", 400)
        if mutation_lock.locked():
            return _error("delivery_busy", "Another alert operation is in progress", 409)
        async with mutation_lock:
            connection = duckdb.connect(database_path)
            try:
                reconcile_unknown_as_not_delivered(
                    connection, outbox_id=outbox_id, now=datetime.now(UTC)
                )
                return ReconciliationResponse(status="not_delivered", outbox_id=outbox_id)
            except ValueError:
                return _error("invalid_state", "Alert delivery state cannot be reconciled", 409)
            except duckdb.Error:
                return _error("database_unavailable", "Alert delivery status is unavailable", 503)
            finally:
                connection.close()

    @app.post(
        "/api/alert-deliveries/{outbox_id}/retry",
        response_model=ReconciliationResponse,
    )
    async def retry_delivery(
        outbox_id: str, confirm: bool = Query(default=False)
    ) -> ReconciliationResponse | JSONResponse:
        if not confirm:
            return _error("confirmation_required", "Confirm alert retry", 409)
        if not outbox_id.startswith("alert_outbox_") or len(outbox_id) > 128:
            return _error("invalid_request", "Invalid alert delivery identity", 400)
        if mutation_lock.locked():
            return _error("delivery_busy", "Another alert operation is in progress", 409)
        async with mutation_lock:
            connection = duckdb.connect(database_path)
            try:
                next_id = retry_terminal_delivery(
                    connection, outbox_id=outbox_id, now=datetime.now(UTC)
                )
                return ReconciliationResponse(status="retry_enqueued", outbox_id=next_id)
            except ValueError:
                return _error("invalid_state", "Alert delivery state cannot be retried", 409)
            except duckdb.Error:
                return _error("database_unavailable", "Alert delivery status is unavailable", 503)
            finally:
                connection.close()

    @app.post("/api/alert-deliveries/cleanup", response_model=CleanupResponse)
    async def cleanup_alert_deliveries(
        confirm: bool = Query(default=False),
    ) -> CleanupResponse | JSONResponse:
        if not confirm:
            return _error("confirmation_required", "Confirm alert history cleanup", 409)
        if mutation_lock.locked():
            return _error("delivery_busy", "Another alert operation is in progress", 409)
        async with mutation_lock:
            connection = duckdb.connect(database_path)
            try:
                result = cleanup_outbox_history(connection, now=datetime.now(UTC))
                return CleanupResponse(**result)
            except duckdb.Error:
                return _error("database_unavailable", "Alert delivery status is unavailable", 503)
            finally:
                connection.close()
