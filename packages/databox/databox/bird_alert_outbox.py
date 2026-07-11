"""Pure iCalendar/MIME builders and transactional bird-alert outbox state."""

from __future__ import annotations

import hashlib
import json
import re
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from email.message import EmailMessage
from email.policy import SMTP
from typing import Literal

import duckdb
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

ALERT_SCHEMA = "birding_alerts"
OUTBOX_STATES = {
    "pending",
    "claimed",
    "accepted",
    "retry_wait",
    "failed",
    "delivery_unknown",
    "cancelled",
    "superseded",
}
TERMINAL_STATES = {"accepted", "failed", "cancelled", "superseded"}
SENDABLE_STATES = {"pending", "retry_wait"}
RETENTION = timedelta(days=90)
MAX_PAYLOAD_BYTES = 32_768


def _iso(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.astimezone(UTC).isoformat()


def _parse_timestamp(value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        raise ValueError("timestamp is invalid") from None
    if parsed.tzinfo is None:
        raise ValueError("timestamp must include an offset")
    return parsed.astimezone(UTC)


def _bounded_text(value: str, *, name: str, maximum: int) -> str:
    if (
        not value
        or len(value) > maximum
        or any(ord(char) < 32 and char not in "\t\n" for char in value)
    ):
        raise ValueError(f"{name} is invalid")
    return value


class CalendarPayload(BaseModel):
    """Canonical persisted event facts; deliberately excludes email addresses."""

    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)

    species_code: str = Field(pattern=r"^[A-Za-z0-9]{1,64}$")
    common_name: str | None = Field(default=None, max_length=200)
    scientific_name: str | None = Field(default=None, max_length=200)
    event_uid: str = Field(min_length=1, max_length=128)
    sequence: int = Field(ge=0)
    method: Literal["REQUEST", "CANCEL"]
    dtstamp: str = Field(min_length=1, max_length=64)
    morning_start: str = Field(min_length=1, max_length=64)
    morning_end: str = Field(min_length=1, max_length=64)
    event_horizon_end: str = Field(min_length=1, max_length=64)
    location_id: str = Field(min_length=1, max_length=128)
    location_name: str = Field(min_length=1, max_length=300)
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    confirmed_distance_miles: float | None = Field(default=None, ge=0, le=300)
    independent_submission_count: int | None = Field(default=None, ge=1)
    newest_observation_at: str | None = Field(default=None, max_length=64)

    @field_validator("common_name", "scientific_name", "location_name")
    @classmethod
    def reject_control_text(cls, value: str | None) -> str | None:
        if value is not None:
            _bounded_text(value, name="calendar text", maximum=300)
            if any(ord(character) < 32 for character in value):
                raise ValueError("calendar field contains a control character")
        return value

    @model_validator(mode="after")
    def validate_times(self) -> CalendarPayload:
        stamp = _parse_timestamp(self.dtstamp)
        start = _parse_timestamp(self.morning_start)
        end = _parse_timestamp(self.morning_end)
        horizon = _parse_timestamp(self.event_horizon_end)
        if end - start != timedelta(hours=2) or end > horizon:
            raise ValueError("calendar window is inconsistent")
        horizon_duration = horizon - stamp
        if (
            horizon_duration <= timedelta(0)
            or horizon_duration > timedelta(days=5)
            or (self.method == "REQUEST" and horizon_duration != timedelta(days=5))
        ):
            raise ValueError("calendar horizon is inconsistent")
        if self.newest_observation_at is not None:
            _parse_timestamp(self.newest_observation_at)
        if self.method == "REQUEST" and (
            self.confirmed_distance_miles is None
            or self.independent_submission_count is None
            or self.newest_observation_at is None
        ):
            raise ValueError("calendar request lacks evidence facts")
        return self

    def canonical_json(self) -> str:
        value = json.dumps(self.model_dump(mode="json"), sort_keys=True, separators=(",", ":"))
        if len(value.encode()) > MAX_PAYLOAD_BYTES:
            raise ValueError("calendar payload exceeds its bound")
        return value

    @property
    def payload_hash(self) -> str:
        return hashlib.sha256(self.canonical_json().encode()).hexdigest()


@dataclass(frozen=True)
class ClaimedOutbox:
    outbox_id: str
    claim_token: str
    payload: CalendarPayload
    payload_hash: str
    attempt_count: int
    claim_expires_at: str


def ensure_outbox_tables(connection: duckdb.DuckDBPyConnection) -> None:
    connection.execute(f"CREATE SCHEMA IF NOT EXISTS {ALERT_SCHEMA}")
    connection.execute(
        f"""
        CREATE TABLE IF NOT EXISTS {ALERT_SCHEMA}.alert_outbox (
          outbox_id VARCHAR PRIMARY KEY, species_code VARCHAR NOT NULL,
          watch_id VARCHAR NOT NULL, activation_generation VARCHAR NOT NULL,
          event_uid VARCHAR NOT NULL, sequence BIGINT NOT NULL, method VARCHAR NOT NULL,
          payload_json VARCHAR NOT NULL, payload_hash VARCHAR NOT NULL,
          state VARCHAR NOT NULL, next_attempt_at VARCHAR NOT NULL,
          claim_token VARCHAR, claimed_at VARCHAR, claim_expires_at VARCHAR,
          send_started_at VARCHAR, attempt_count BIGINT NOT NULL,
          created_at VARCHAR NOT NULL, updated_at VARCHAR NOT NULL,
          terminal_at VARCHAR, safe_terminal_reason VARCHAR,
          UNIQUE (event_uid, sequence, method),
          CHECK (method IN ('REQUEST','CANCEL')),
          CHECK (state IN (
            'pending','claimed','accepted','retry_wait','failed',
            'delivery_unknown','cancelled','superseded'
          )),
          CHECK (attempt_count >= 0)
        )
        """
    )
    connection.execute(
        f"""
        CREATE TABLE IF NOT EXISTS {ALERT_SCHEMA}.outbox_attempts (
          attempt_id VARCHAR PRIMARY KEY, outbox_id VARCHAR NOT NULL,
          attempt_number BIGINT NOT NULL, claim_token VARCHAR NOT NULL,
          phase VARCHAR NOT NULL, safe_reason VARCHAR, occurred_at VARCHAR NOT NULL,
          CHECK (phase IN (
            'send_started','accepted','retry_wait','failed',
            'delivery_unknown','claim_recovered'
          )),
          CHECK (attempt_number >= 0)
        )
        """
    )
    connection.execute(
        f"""
        CREATE TABLE IF NOT EXISTS {ALERT_SCHEMA}.outbox_dedupe (
          outbox_id VARCHAR PRIMARY KEY, event_uid VARCHAR NOT NULL,
          sequence BIGINT NOT NULL, method VARCHAR NOT NULL,
          payload_hash VARCHAR NOT NULL, terminal_at VARCHAR NOT NULL,
          UNIQUE (event_uid, sequence, method)
        )
        """
    )


def _outbox_id(event_uid: str, sequence: int, method: str) -> str:
    return "alert_outbox_" + hashlib.sha256(f"{event_uid}|{sequence}|{method}".encode()).hexdigest()


def _payload_for_event(
    connection: duckdb.DuckDBPyConnection, species_code: str
) -> tuple[CalendarPayload, tuple[str, str]]:
    event = connection.execute(
        f"""SELECT species_code, watch_id, activation_generation, event_uid, sequence,
                   method, status, report_id, source_report_id, morning_start, morning_end,
                   event_horizon_end, location_id, location_name, latitude, longitude,
                   updated_at
            FROM {ALERT_SCHEMA}.event_intents WHERE species_code=?""",
        [species_code],
    ).fetchone()
    if event is None or str(event[0]) != species_code:
        raise ValueError("event intent is unavailable")
    expected_method = {"pending_request": "REQUEST", "pending_cancel": "CANCEL"}.get(str(event[6]))
    if expected_method is None or str(event[5]) != expected_method:
        raise ValueError("event intent status and method are not sendable")
    if any(event[index] is None for index in (8, 9, 10, 11, 12, 13, 14, 15)):
        raise ValueError("event intent lacks canonical calendar facts")
    method = str(event[5])
    if method == "REQUEST":
        if event[7] is None or str(event[7]) != str(event[8]):
            raise ValueError("request event report linkage is invalid")
    elif event[7] is not None:
        raise ValueError("cancel event must not retain an active report")
    report_rows = connection.execute(
        f"""SELECT report_id, species_code, watch_id, activation_generation,
                   common_name, scientific_name, confirmed_location_id,
                   confirmed_location_name, confirmed_latitude, confirmed_longitude,
                   confirmed_distance_miles, independent_submission_count,
                   newest_observation_at, morning_start, morning_end,
                   event_horizon_end, resolved_at
            FROM {ALERT_SCHEMA}.match_reports WHERE report_id=? LIMIT 2""",
        [event[8]],
    ).fetchall()
    if len(report_rows) != 1:
        raise ValueError("event source report is unavailable or non-unique")
    report = report_rows[0]
    expected_location_name = report[7] or f"eBird location {report[6]}"
    coherent = (
        str(report[0]) == str(event[8])
        and str(report[1]) == str(event[0])
        and str(report[2]) == str(event[1])
        and str(report[3]) == str(event[2])
        and str(report[6]) == str(event[12])
        and str(expected_location_name) == str(event[13])
        and float(report[8]) == float(event[14])
        and float(report[9]) == float(event[15])
        and str(report[13]) == str(event[9])
        and str(report[14]) == str(event[10])
        and str(report[15]) == str(event[11])
    )
    if not coherent:
        raise ValueError("event intent and source report are inconsistent")
    if (method == "REQUEST" and report[16] is not None) or (
        method == "CANCEL" and report[16] is None
    ):
        raise ValueError("event report lifecycle is inconsistent")
    payload = CalendarPayload(
        species_code=str(event[0]),
        common_name=str(report[4]) if report[4] is not None else None,
        scientific_name=str(report[5]) if report[5] is not None else None,
        event_uid=str(event[3]),
        sequence=int(event[4]),
        method=method,
        dtstamp=str(event[16]),
        morning_start=str(event[9]),
        morning_end=str(event[10]),
        event_horizon_end=str(event[11]),
        location_id=str(event[12]),
        location_name=str(event[13]),
        latitude=float(event[14]),
        longitude=float(event[15]),
        confirmed_distance_miles=float(report[10]) if method == "REQUEST" else None,
        independent_submission_count=int(report[11]) if method == "REQUEST" else None,
        newest_observation_at=str(report[12]) if method == "REQUEST" else None,
    )
    return payload, (str(event[1]), str(event[2]))


def _enqueue_event_intent(
    connection: duckdb.DuckDBPyConnection, species_code: str, *, now: datetime
) -> str:
    """Enqueue one current sendable event inside the caller's transaction."""

    ensure_outbox_tables(connection)
    payload, (watch_id, activation_generation) = _payload_for_event(connection, species_code)
    payload_json = payload.canonical_json()
    outbox_id = _outbox_id(payload.event_uid, payload.sequence, payload.method)
    existing = connection.execute(
        f"""SELECT payload_hash FROM {ALERT_SCHEMA}.alert_outbox WHERE outbox_id=?
            UNION ALL
            SELECT payload_hash FROM {ALERT_SCHEMA}.outbox_dedupe WHERE outbox_id=?""",
        [outbox_id, outbox_id],
    ).fetchall()
    if existing:
        if any(str(row[0]) != payload.payload_hash for row in existing):
            raise ValueError("event outbox identity conflicts with different facts")
        return outbox_id
    timestamp = _iso(now)
    connection.execute(
        f"""UPDATE {ALERT_SCHEMA}.alert_outbox
            SET state='superseded', terminal_at=?, updated_at=?,
                safe_terminal_reason='newer_event_sequence', claim_token=NULL,
                claimed_at=NULL, claim_expires_at=NULL
            WHERE event_uid=? AND sequence < ?
              AND (state IN ('pending','retry_wait')
                   OR (state='claimed' AND send_started_at IS NULL))""",
        [timestamp, timestamp, payload.event_uid, payload.sequence],
    )
    connection.execute(
        f"""INSERT INTO {ALERT_SCHEMA}.alert_outbox VALUES
            (?, ?, ?, ?, ?, ?, ?, ?, ?, 'pending', ?, NULL, NULL, NULL, NULL,
             0, ?, ?, NULL, NULL)""",
        [
            outbox_id,
            payload.species_code,
            watch_id,
            activation_generation,
            payload.event_uid,
            payload.sequence,
            payload.method,
            payload_json,
            payload.payload_hash,
            timestamp,
            timestamp,
            timestamp,
        ],
    )
    return outbox_id


def enqueue_event_intent(
    connection: duckdb.DuckDBPyConnection,
    species_code: str,
    *,
    now: datetime,
    in_transaction: bool = False,
) -> str:
    if in_transaction:
        return _enqueue_event_intent(connection, species_code, now=now)
    connection.execute("BEGIN TRANSACTION")
    try:
        outbox_id = _enqueue_event_intent(connection, species_code, now=now)
        connection.execute("COMMIT")
        return outbox_id
    except Exception:
        connection.execute("ROLLBACK")
        raise


def _suppress_event_outbox(
    connection: duckdb.DuckDBPyConnection,
    *,
    event_uid: str,
    sequence: int,
    now: datetime,
    reason: str,
) -> None:
    """Make a REQUEST structurally non-sendable in the caller transaction."""

    if not re.fullmatch(r"[a-z_]{1,64}", reason):
        raise ValueError("suppression reason is invalid")
    ensure_outbox_tables(connection)
    timestamp = _iso(now)
    rows = connection.execute(
        f"""SELECT outbox_id, state, claim_token, attempt_count, send_started_at
            FROM {ALERT_SCHEMA}.alert_outbox
            WHERE event_uid=? AND sequence=? AND method='REQUEST'""",
        [event_uid, sequence],
    ).fetchall()
    for outbox_id, state, claim_token, attempt_count, send_started_at in rows:
        if str(state) in TERMINAL_STATES or str(state) == "delivery_unknown":
            continue
        if str(state) == "claimed" and send_started_at is not None:
            next_state, terminal_at = "delivery_unknown", None
            phase = "delivery_unknown"
        else:
            next_state, terminal_at = "cancelled", timestamp
            phase = None
        connection.execute(
            f"""UPDATE {ALERT_SCHEMA}.alert_outbox
                SET state=?, payload_json='{{}}', claim_token=NULL, claimed_at=NULL,
                    claim_expires_at=NULL, updated_at=?, terminal_at=?, safe_terminal_reason=?
                WHERE outbox_id=?""",
            [next_state, timestamp, terminal_at, reason, outbox_id],
        )
        if phase is not None:
            connection.execute(
                f"INSERT INTO {ALERT_SCHEMA}.outbox_attempts VALUES (?, ?, ?, ?, ?, ?, ?)",
                [
                    str(uuid.uuid4()),
                    outbox_id,
                    int(attempt_count),
                    str(claim_token or "expired-claim"),
                    phase,
                    reason,
                    timestamp,
                ],
            )


def suppress_event_outbox(
    connection: duckdb.DuckDBPyConnection,
    *,
    event_uid: str,
    sequence: int,
    now: datetime,
    reason: str,
    in_transaction: bool = False,
) -> None:
    if in_transaction:
        _suppress_event_outbox(
            connection,
            event_uid=event_uid,
            sequence=sequence,
            now=now,
            reason=reason,
        )
        return
    connection.execute("BEGIN TRANSACTION")
    try:
        _suppress_event_outbox(
            connection,
            event_uid=event_uid,
            sequence=sequence,
            now=now,
            reason=reason,
        )
        connection.execute("COMMIT")
    except Exception:
        connection.execute("ROLLBACK")
        raise


def _expire_due_events(connection: duckdb.DuckDBPyConnection, *, now: datetime) -> int:
    timestamp = _iso(now)
    try:
        rows = connection.execute(
            f"""SELECT species_code, event_uid, sequence, report_id
                FROM {ALERT_SCHEMA}.event_intents
                WHERE status NOT IN ('suppressed','cancelled','expired')
                  AND event_horizon_end IS NOT NULL AND event_horizon_end <= ?""",
            [timestamp],
        ).fetchall()
    except duckdb.CatalogException:
        return 0
    for species_code, event_uid, sequence, report_id in rows:
        _suppress_event_outbox(
            connection,
            event_uid=str(event_uid),
            sequence=int(sequence),
            now=now,
            reason="natural_expiry",
        )
        if report_id is not None:
            connection.execute(
                f"""UPDATE {ALERT_SCHEMA}.match_reports
                    SET resolved_at=COALESCE(resolved_at, ?) WHERE report_id=?""",
                [timestamp, report_id],
            )
        connection.execute(
            f"""UPDATE {ALERT_SCHEMA}.event_intents SET status='expired',
                report_id=NULL, source_report_id=NULL, morning_start=NULL,
                morning_end=NULL, event_horizon_end=NULL, location_id=NULL,
                location_name=NULL, latitude=NULL, longitude=NULL,
                updated_at=? WHERE species_code=?""",
            [timestamp, species_code],
        )
    return len(rows)


def _recover_expired_claims(
    connection: duckdb.DuckDBPyConnection, *, now: datetime
) -> dict[str, int]:
    ensure_outbox_tables(connection)
    timestamp = _iso(now)
    rows = connection.execute(
        f"""SELECT outbox_id, claim_token, attempt_count, send_started_at
            FROM {ALERT_SCHEMA}.alert_outbox
            WHERE state='claimed' AND claim_expires_at <= ?
            ORDER BY outbox_id""",
        [timestamp],
    ).fetchall()
    recovered = unknown = 0
    for outbox_id, claim_token, attempt_count, send_started_at in rows:
        if send_started_at is None:
            state, reason, phase = "pending", "expired_pre_send_claim", "claim_recovered"
            recovered += 1
        else:
            state, reason, phase = (
                "delivery_unknown",
                "expired_after_send_started",
                "delivery_unknown",
            )
            unknown += 1
        connection.execute(
            f"""UPDATE {ALERT_SCHEMA}.alert_outbox SET state=?, claim_token=NULL,
                claimed_at=NULL, claim_expires_at=NULL, updated_at=?, safe_terminal_reason=?
                WHERE outbox_id=?""",
            [state, timestamp, reason, outbox_id],
        )
        connection.execute(
            f"INSERT INTO {ALERT_SCHEMA}.outbox_attempts VALUES (?, ?, ?, ?, ?, ?, ?)",
            [
                str(uuid.uuid4()),
                outbox_id,
                int(attempt_count),
                str(claim_token),
                phase,
                reason,
                timestamp,
            ],
        )
    return {"recovered": recovered, "delivery_unknown": unknown}


def recover_expired_claims(
    connection: duckdb.DuckDBPyConnection, *, now: datetime
) -> dict[str, int]:
    connection.execute("BEGIN TRANSACTION")
    try:
        result = _recover_expired_claims(connection, now=now)
        connection.execute("COMMIT")
        return result
    except Exception:
        connection.execute("ROLLBACK")
        raise


def claim_next_outbox(
    connection: duckdb.DuckDBPyConnection,
    *,
    now: datetime,
    lease: timedelta = timedelta(minutes=5),
) -> ClaimedOutbox | None:
    if lease <= timedelta(0) or lease > timedelta(hours=1):
        raise ValueError("claim lease is invalid")
    ensure_outbox_tables(connection)
    connection.execute("BEGIN TRANSACTION")
    try:
        _recover_expired_claims(connection, now=now)
        _expire_due_events(connection, now=now)
        timestamp = _iso(now)
        row = connection.execute(
            f"""SELECT outbox_id, payload_json, payload_hash, attempt_count
                FROM {ALERT_SCHEMA}.alert_outbox AS candidate
                WHERE state IN ('pending','retry_wait') AND next_attempt_at <= ?
                  AND payload_json <> '{{}}'
                  AND NOT EXISTS (
                    SELECT 1 FROM {ALERT_SCHEMA}.alert_outbox AS unresolved
                    WHERE unresolved.event_uid=candidate.event_uid
                      AND unresolved.state='delivery_unknown'
                  )
                ORDER BY next_attempt_at, created_at, outbox_id LIMIT 1""",
            [timestamp],
        ).fetchone()
        if row is None:
            connection.execute("COMMIT")
            return None
        token = str(uuid.uuid4())
        expires = _iso(now + lease)
        connection.execute(
            f"""UPDATE {ALERT_SCHEMA}.alert_outbox
                SET state='claimed', claim_token=?, claimed_at=?, claim_expires_at=?,
                    send_started_at=NULL, updated_at=?
                WHERE outbox_id=? AND state IN ('pending','retry_wait')""",
            [token, timestamp, expires, timestamp, row[0]],
        )
        claimed = connection.execute(
            f"""SELECT payload_json, payload_hash, attempt_count
                FROM {ALERT_SCHEMA}.alert_outbox
                WHERE outbox_id=? AND claim_token=? AND state='claimed'""",
            [row[0], token],
        ).fetchone()
        if claimed is None:
            connection.execute("ROLLBACK")
            return None
        payload = CalendarPayload.model_validate_json(str(claimed[0]))
        if payload.payload_hash != str(claimed[1]):
            raise ValueError("persisted calendar payload hash is invalid")
        result = ClaimedOutbox(
            outbox_id=str(row[0]),
            claim_token=token,
            payload=payload,
            payload_hash=str(claimed[1]),
            attempt_count=int(claimed[2]),
            claim_expires_at=expires,
        )
        connection.execute("COMMIT")
        return result
    except duckdb.TransactionException:
        try:
            connection.execute("ROLLBACK")
        except duckdb.TransactionException:
            pass
        return None
    except Exception:
        try:
            connection.execute("ROLLBACK")
        except duckdb.TransactionException:
            pass
        raise


def start_send_attempt(
    connection: duckdb.DuckDBPyConnection,
    *,
    outbox_id: str,
    claim_token: str,
    now: datetime,
) -> CalendarPayload:
    timestamp = _iso(now)
    connection.execute("BEGIN TRANSACTION")
    try:
        row = connection.execute(
            f"""SELECT payload_json, payload_hash, attempt_count, claim_expires_at,
                       send_started_at
                FROM {ALERT_SCHEMA}.alert_outbox
                WHERE outbox_id=? AND state='claimed' AND claim_token=?""",
            [outbox_id, claim_token],
        ).fetchone()
        if (
            row is None
            or _parse_timestamp(str(row[3])) <= now.astimezone(UTC)
            or row[4] is not None
        ):
            raise ValueError("outbox claim is not startable")
        payload = CalendarPayload.model_validate_json(str(row[0]))
        if payload.payload_hash != str(row[1]):
            raise ValueError("persisted calendar payload hash is invalid")
        attempt_number = int(row[2]) + 1
        connection.execute(
            f"""UPDATE {ALERT_SCHEMA}.alert_outbox
                SET send_started_at=?, attempt_count=?, updated_at=? WHERE outbox_id=?""",
            [timestamp, attempt_number, timestamp, outbox_id],
        )
        connection.execute(
            f"""INSERT INTO {ALERT_SCHEMA}.outbox_attempts
                VALUES (?, ?, ?, ?, 'send_started', NULL, ?)""",
            [str(uuid.uuid4()), outbox_id, attempt_number, claim_token, timestamp],
        )
        connection.execute("COMMIT")
        return payload
    except Exception:
        connection.execute("ROLLBACK")
        raise


def record_attempt_outcome(
    connection: duckdb.DuckDBPyConnection,
    *,
    outbox_id: str,
    claim_token: str,
    outcome: Literal["accepted", "retry_wait", "failed", "delivery_unknown"],
    now: datetime,
    safe_reason: str,
    next_attempt_at: datetime | None = None,
) -> None:
    if not re.fullmatch(r"[a-z_]{1,64}", safe_reason):
        raise ValueError("outcome reason is invalid")
    if (outcome == "retry_wait") != (next_attempt_at is not None):
        raise ValueError("retry outcome scheduling is inconsistent")
    timestamp = _iso(now)
    connection.execute("BEGIN TRANSACTION")
    try:
        row = connection.execute(
            f"""SELECT species_code, event_uid, sequence, method, attempt_count,
                       send_started_at
                FROM {ALERT_SCHEMA}.alert_outbox
                WHERE outbox_id=? AND state='claimed' AND claim_token=?""",
            [outbox_id, claim_token],
        ).fetchone()
        if row is None or row[5] is None:
            raise ValueError("outbox attempt is not active")
        terminal_at = timestamp if outcome in TERMINAL_STATES else None
        connection.execute(
            f"""UPDATE {ALERT_SCHEMA}.alert_outbox
                SET state=?, next_attempt_at=?, claim_token=NULL, claimed_at=NULL,
                    claim_expires_at=NULL, send_started_at=NULL, updated_at=?,
                    terminal_at=?, safe_terminal_reason=? WHERE outbox_id=?""",
            [
                outcome,
                _iso(next_attempt_at) if next_attempt_at is not None else timestamp,
                timestamp,
                terminal_at,
                safe_reason,
                outbox_id,
            ],
        )
        connection.execute(
            f"INSERT INTO {ALERT_SCHEMA}.outbox_attempts VALUES (?, ?, ?, ?, ?, ?, ?)",
            [
                str(uuid.uuid4()),
                outbox_id,
                int(row[4]),
                claim_token,
                outcome,
                safe_reason,
                timestamp,
            ],
        )
        if outcome == "accepted":
            if str(row[3]) == "REQUEST":
                event = connection.execute(
                    f"""SELECT event_horizon_end FROM {ALERT_SCHEMA}.event_intents
                        WHERE species_code=? AND event_uid=? AND sequence=?
                          AND status='pending_request'""",
                    [row[0], row[1], row[2]],
                ).fetchone()
                if event is not None:
                    connection.execute(
                        f"""UPDATE {ALERT_SCHEMA}.event_intents SET status='accepted',
                            last_accepted_sequence=sequence,
                            last_accepted_horizon_end=event_horizon_end,
                            last_accepted_at=?, updated_at=? WHERE species_code=?""",
                        [timestamp, timestamp, row[0]],
                    )
            else:
                connection.execute(
                    f"""UPDATE {ALERT_SCHEMA}.event_intents SET status='cancelled',
                        report_id=NULL, source_report_id=NULL, morning_start=NULL,
                        morning_end=NULL, event_horizon_end=NULL, location_id=NULL,
                        location_name=NULL, latitude=NULL, longitude=NULL,
                        last_accepted_sequence=NULL,
                        last_accepted_horizon_end=NULL, last_accepted_at=NULL,
                        updated_at=? WHERE species_code=? AND event_uid=? AND sequence=?
                          AND status='pending_cancel'""",
                    [timestamp, row[0], row[1], row[2]],
                )
        connection.execute("COMMIT")
    except Exception:
        connection.execute("ROLLBACK")
        raise


def _cleanup_outbox_history(
    connection: duckdb.DuckDBPyConnection, *, now: datetime
) -> dict[str, int]:
    ensure_outbox_tables(connection)
    _expire_due_events(connection, now=now)
    cutoff = _iso(now.astimezone(UTC) - RETENTION)
    rows = connection.execute(
        f"""SELECT outbox_id, event_uid, sequence, method, payload_hash, terminal_at
            FROM {ALERT_SCHEMA}.alert_outbox
            WHERE state IN ('accepted','failed','cancelled','superseded')
              AND terminal_at IS NOT NULL AND terminal_at < ?""",
        [cutoff],
    ).fetchall()
    for row in rows:
        existing = connection.execute(
            f"""SELECT payload_hash FROM {ALERT_SCHEMA}.outbox_dedupe
                WHERE outbox_id=? OR (event_uid=? AND sequence=? AND method=?)""",
            [row[0], row[1], row[2], row[3]],
        ).fetchone()
        if existing is not None and str(existing[0]) != str(row[4]):
            raise ValueError("outbox retention dedupe identity conflicts")
        connection.execute(
            f"INSERT OR IGNORE INTO {ALERT_SCHEMA}.outbox_dedupe VALUES (?, ?, ?, ?, ?, ?)",
            list(row),
        )
        connection.execute(
            f"DELETE FROM {ALERT_SCHEMA}.outbox_attempts WHERE outbox_id=?", [row[0]]
        )
        connection.execute(f"DELETE FROM {ALERT_SCHEMA}.alert_outbox WHERE outbox_id=?", [row[0]])
    return {"outbox_deleted": len(rows)}


def cleanup_outbox_history(
    connection: duckdb.DuckDBPyConnection, *, now: datetime
) -> dict[str, int]:
    connection.execute("BEGIN TRANSACTION")
    try:
        result = _cleanup_outbox_history(connection, now=now)
        connection.execute("COMMIT")
        return result
    except Exception:
        connection.execute("ROLLBACK")
        raise


def _ical_escape(value: str) -> str:
    _bounded_text(value, name="calendar text", maximum=1000)
    return value.replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,").replace("\n", "\\n")


def _fold_ical_line(value: str) -> str:
    parts: list[str] = []
    current = ""
    limit = 75
    for character in value:
        candidate = current + character
        if len(candidate.encode("utf-8")) > limit:
            parts.append(current)
            current = " " + character
            limit = 75
        else:
            current = candidate
    parts.append(current)
    return "\r\n".join(parts)


def _ical_time(value: str) -> str:
    return _parse_timestamp(value).strftime("%Y%m%dT%H%M%SZ")


def _email_address(value: str) -> str:
    if not re.fullmatch(r"[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]{1,64}@[A-Za-z0-9.-]{1,190}", value):
        raise ValueError("email address is invalid")
    return value


def build_icalendar(payload: CalendarPayload, *, organizer: str, attendee: str) -> str:
    organizer = _email_address(organizer)
    attendee = _email_address(attendee)
    name = payload.common_name or payload.scientific_name or payload.species_code
    summary = f"Bird alert: {name}"
    if payload.method == "REQUEST":
        description = (
            f"Recent reviewed public evidence for {name}.\n"
            f"Independent submissions: {payload.independent_submission_count}.\n"
            f"Newest observation: {payload.newest_observation_at}.\n"
            f"Distance: {payload.confirmed_distance_miles:.1f} miles.\n"
            "Presence is not guaranteed; verify current site access before visiting."
        )
        status = "CONFIRMED"
    else:
        description = f"The Databox watched-bird event for {name} was cancelled."
        status = "CANCELLED"
    lines = [
        "BEGIN:VCALENDAR",
        "PRODID:-//Databox//Bird Alert//EN",
        "VERSION:2.0",
        "CALSCALE:GREGORIAN",
        f"METHOD:{payload.method}",
        "X-WR-TIMEZONE:America/Phoenix",
        "BEGIN:VEVENT",
        f"UID:{_ical_escape(payload.event_uid)}",
        f"SEQUENCE:{payload.sequence}",
        f"DTSTAMP:{_ical_time(payload.dtstamp)}",
        f"DTSTART:{_ical_time(payload.morning_start)}",
        f"DTEND:{_ical_time(payload.morning_end)}",
        f"ORGANIZER:mailto:{organizer}",
        f"ATTENDEE;ROLE=REQ-PARTICIPANT;RSVP=TRUE:mailto:{attendee}",
        f"SUMMARY:{_ical_escape(summary)}",
        f"DESCRIPTION:{_ical_escape(description)}",
        f"LOCATION:{_ical_escape(payload.location_name)}",
        f"GEO:{payload.latitude:.6f};{payload.longitude:.6f}",
        f"STATUS:{status}",
        "END:VEVENT",
        "END:VCALENDAR",
    ]
    return "\r\n".join(_fold_ical_line(line) for line in lines) + "\r\n"


def build_calendar_mime(payload: CalendarPayload, *, organizer: str, attendee: str) -> EmailMessage:
    organizer = _email_address(organizer)
    attendee = _email_address(attendee)
    calendar = build_icalendar(payload, organizer=organizer, attendee=attendee)
    name = payload.common_name or payload.scientific_name or payload.species_code
    action = "cancelled" if payload.method == "CANCEL" else "updated"
    message = EmailMessage(policy=SMTP)
    message["From"] = organizer
    message["To"] = attendee
    message["Subject"] = f"Bird alert {action}: {name}"
    message["Date"] = _parse_timestamp(payload.dtstamp)
    message["Message-ID"] = (
        f"<{_outbox_id(payload.event_uid, payload.sequence, payload.method)}@local>"
    )
    message.set_content(
        f"Your Databox bird alert for {name} was {action}. "
        "Open the calendar invitation for details."
    )
    message.add_alternative(
        calendar,
        subtype="calendar",
        charset="utf-8",
        params={"method": payload.method},
    )
    message.set_boundary("databox-" + payload.payload_hash[:32])
    return message
