"""Explicit POST-only API for trip-plan calendar invitations."""

from __future__ import annotations

import asyncio
import smtplib
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

import duckdb
from fastapi import FastAPI, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field

from databox.bird_alert_delivery import BirdAlertSmtpSettings, SmtpFactory
from databox.trip_plan_calendar import (
    UnsafeTripCalendarContentError,
    deliver_next_trip_outbox,
    enqueue_trip_invite,
    reconcile_trip_invite,
    trip_invite_status,
)


class TripInviteStatusResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    status: Literal[
        "not_created",
        "pending",
        "claimed",
        "retry_wait",
        "accepted",
        "failed",
        "delivery_unknown",
        "superseded",
    ]
    sequence: int | None = Field(default=None, ge=0)
    outbox_id: str | None = Field(default=None, max_length=128)
    allowed_actions: list[
        Literal[
            "send", "send_update", "retry_failed", "mark_delivered", "mark_not_delivered_and_retry"
        ]
    ] = Field(max_length=2)
    can_retry: bool
    updated_at: str | None = Field(default=None, max_length=64)
    acceptance_notice: str | None = Field(default=None, max_length=100)


class TripInviteActionResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    outbox_id: str = Field(pattern=r"^trip_outbox_[0-9a-f]{64}$")
    delivery: TripInviteStatusResponse


def _error(code: str, message: str, status: int) -> JSONResponse:
    return JSONResponse(status_code=status, content={"error": {"code": code, "message": message}})


def _status(connection: duckdb.DuckDBPyConnection, plan_id: str) -> TripInviteStatusResponse:
    value = trip_invite_status(connection, plan_id)
    value["acceptance_notice"] = (
        "Accepted by local mail bridge" if value["status"] == "accepted" else None
    )
    return TripInviteStatusResponse.model_validate(value)


def register_trip_plan_calendar_routes(
    app: FastAPI,
    *,
    database_path: str,
    mutation_lock: asyncio.Lock,
    smtp_settings: BirdAlertSmtpSettings | Callable[[], BirdAlertSmtpSettings] | None,
    smtp_factory: SmtpFactory = smtplib.SMTP,
) -> None:
    """Register safe status and confirmed actions; registration performs no SMTP work."""

    def active_settings() -> BirdAlertSmtpSettings:
        if smtp_settings is None:
            raise ValueError("SMTP is not configured")
        return smtp_settings() if callable(smtp_settings) else smtp_settings

    @app.get(
        "/api/trip-plans/{plan_id}/calendar-invite",
        response_model=TripInviteStatusResponse,
    )
    async def get_trip_invite(plan_id: str) -> TripInviteStatusResponse | JSONResponse:
        if not Path(database_path).exists():
            return _error("not_found", "Trip plan not found", 404)
        connection = duckdb.connect(database_path, read_only=True)
        try:
            plan = connection.execute(
                "SELECT 1 FROM birding_agent.trip_plans WHERE trip_plan_id=?", [plan_id]
            ).fetchone()
            if plan is None:
                return _error("not_found", "Trip plan not found", 404)
            return _status(connection, plan_id)
        except duckdb.Error:
            return _error("database_unavailable", "Trip invite status is unavailable", 503)
        finally:
            connection.close()

    @app.post(
        "/api/trip-plans/{plan_id}/calendar-invite",
        response_model=TripInviteActionResponse,
    )
    async def send_trip_invite(
        plan_id: str, confirm: bool = Query(default=False)
    ) -> TripInviteActionResponse | JSONResponse:
        if not confirm:
            return _error("confirmation_required", "Confirm calendar invitation send", 409)
        if mutation_lock.locked():
            return _error("delivery_busy", "Another calendar operation is in progress", 409)
        async with mutation_lock:
            connection = duckdb.connect(database_path)
            try:
                outbox_id = enqueue_trip_invite(connection, plan_id, now=datetime.now(UTC))
                try:
                    configured = active_settings()
                except ValueError:
                    return _error(
                        "smtp_not_configured",
                        "Calendar invitation is queued; configure the local mail bridge",
                        503,
                    )
                deliver_next_trip_outbox(
                    connection,
                    settings=configured,
                    now=datetime.now(UTC),
                    smtp_factory=smtp_factory,
                )
                return TripInviteActionResponse(
                    outbox_id=outbox_id, delivery=_status(connection, plan_id)
                )
            except UnsafeTripCalendarContentError:
                return _error(
                    "unsafe_calendar_content",
                    "Trip plan cannot be included in a calendar invitation",
                    409,
                )
            except ValueError:
                return _error("invalid_plan", "Trip plan is incomplete or changed", 409)
            except duckdb.Error:
                return _error("database_unavailable", "Trip invite could not be queued", 503)
            finally:
                connection.close()

    async def reconcile(
        outbox_id: str,
        *,
        outcome: Literal["delivered", "not_delivered", "retry_failed"],
        confirm: bool,
    ) -> TripInviteActionResponse | JSONResponse:
        if not confirm:
            return _error("confirmation_required", "Confirm calendar reconciliation", 409)
        if not outbox_id.startswith("trip_outbox_") or len(outbox_id) != 76:
            return _error("invalid_request", "Invalid trip delivery identity", 400)
        if mutation_lock.locked():
            return _error("delivery_busy", "Another calendar operation is in progress", 409)
        async with mutation_lock:
            connection = duckdb.connect(database_path)
            try:
                source = connection.execute(
                    "SELECT trip_plan_id FROM birding_calendar.trip_outbox WHERE outbox_id=?",
                    [outbox_id],
                ).fetchone()
                if source is None:
                    return _error("invalid_state", "Trip delivery state cannot be reconciled", 409)
                resulting_id = reconcile_trip_invite(
                    connection, outbox_id, outcome=outcome, now=datetime.now(UTC)
                )
                replacement = connection.execute(
                    """SELECT state FROM birding_calendar.trip_outbox
                       WHERE outbox_id=?""",
                    [resulting_id],
                ).fetchone()
                if resulting_id != outbox_id and replacement == ("pending",):
                    try:
                        configured = active_settings()
                    except ValueError:
                        return _error(
                            "smtp_not_configured",
                            "Calendar invitation is queued; configure the local mail bridge",
                            503,
                        )
                    deliver_next_trip_outbox(
                        connection,
                        settings=configured,
                        now=datetime.now(UTC),
                        smtp_factory=smtp_factory,
                    )
                return TripInviteActionResponse(
                    outbox_id=resulting_id, delivery=_status(connection, str(source[0]))
                )
            except UnsafeTripCalendarContentError:
                return _error(
                    "unsafe_calendar_content",
                    "Trip plan cannot be included in a calendar invitation",
                    409,
                )
            except (ValueError, duckdb.CatalogException):
                return _error("invalid_state", "Trip delivery state cannot be reconciled", 409)
            except duckdb.Error:
                return _error("database_unavailable", "Trip invite status is unavailable", 503)
            finally:
                connection.close()

    @app.post(
        "/api/trip-calendar-deliveries/deliver-due",
        response_model=TripInviteActionResponse,
    )
    async def deliver_due(
        confirm: bool = Query(default=False),
    ) -> TripInviteActionResponse | JSONResponse:
        """Explicit worker endpoint for pending and scheduled 1/5/15-minute retries."""

        if not confirm:
            return _error("confirmation_required", "Confirm due calendar delivery", 409)
        if mutation_lock.locked():
            return _error("delivery_busy", "Another calendar operation is in progress", 409)
        async with mutation_lock:
            connection = duckdb.connect(database_path)
            try:
                try:
                    configured = active_settings()
                except ValueError:
                    return _error("smtp_not_configured", "Configure the local mail bridge", 503)
                result = deliver_next_trip_outbox(
                    connection,
                    settings=configured,
                    now=datetime.now(UTC),
                    smtp_factory=smtp_factory,
                )
                if result.outbox_id is None:
                    return _error("no_due_delivery", "No calendar delivery is due", 409)
                source = connection.execute(
                    """SELECT trip_plan_id FROM birding_calendar.trip_outbox
                       WHERE outbox_id=?""",
                    [result.outbox_id],
                ).fetchone()
                if source is None:
                    return _error("invalid_state", "Trip delivery state is unavailable", 409)
                return TripInviteActionResponse(
                    outbox_id=result.outbox_id, delivery=_status(connection, str(source[0]))
                )
            except UnsafeTripCalendarContentError:
                return _error(
                    "unsafe_calendar_content",
                    "Trip plan cannot be included in a calendar invitation",
                    409,
                )
            except ValueError:
                return _error("invalid_state", "Trip delivery state is unavailable", 409)
            except duckdb.Error:
                return _error("database_unavailable", "Trip invite could not be delivered", 503)
            finally:
                connection.close()

    @app.post(
        "/api/trip-calendar-deliveries/{outbox_id}/mark-delivered",
        response_model=TripInviteActionResponse,
    )
    async def mark_delivered(
        outbox_id: str, confirm: bool = Query(default=False)
    ) -> TripInviteActionResponse | JSONResponse:
        return await reconcile(outbox_id, outcome="delivered", confirm=confirm)

    @app.post(
        "/api/trip-calendar-deliveries/{outbox_id}/mark-not-delivered-and-retry",
        response_model=TripInviteActionResponse,
    )
    async def mark_not_delivered(
        outbox_id: str, confirm: bool = Query(default=False)
    ) -> TripInviteActionResponse | JSONResponse:
        return await reconcile(outbox_id, outcome="not_delivered", confirm=confirm)

    @app.post(
        "/api/trip-calendar-deliveries/{outbox_id}/retry",
        response_model=TripInviteActionResponse,
    )
    async def retry_failed(
        outbox_id: str, confirm: bool = Query(default=False)
    ) -> TripInviteActionResponse | JSONResponse:
        return await reconcile(outbox_id, outcome="retry_failed", confirm=confirm)
