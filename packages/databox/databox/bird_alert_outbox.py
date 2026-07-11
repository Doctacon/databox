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
          source_report_id VARCHAR NOT NULL, event_uid VARCHAR NOT NULL,
          sequence BIGINT NOT NULL, method VARCHAR NOT NULL,
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
    columns = {
        str(row[0])
        for row in connection.execute(
            """SELECT column_name FROM information_schema.columns
               WHERE table_schema=? AND table_name='alert_outbox'""",
            [ALERT_SCHEMA],
        ).fetchall()
    }
    if "source_report_id" not in columns:
        connection.execute(
            f"ALTER TABLE {ALERT_SCHEMA}.alert_outbox ADD COLUMN source_report_id VARCHAR"
        )
        connection.execute(
            f"""UPDATE {ALERT_SCHEMA}.alert_outbox AS outbox
                SET source_report_id=event.source_report_id
                FROM {ALERT_SCHEMA}.event_intents AS event
                WHERE outbox.species_code=event.species_code
                  AND outbox.event_uid=event.event_uid
                  AND outbox.sequence=event.sequence"""
        )
        unresolved = connection.execute(
            f"""SELECT count(*) FROM {ALERT_SCHEMA}.alert_outbox
                WHERE source_report_id IS NULL AND state NOT IN
                  ('accepted','failed','cancelled','superseded')"""
        ).fetchone()
        if unresolved is None or int(unresolved[0]) > 0:
            raise ValueError("existing sendable outbox rows lack exact report linkage")
    connection.execute(
        f"""
        CREATE TABLE IF NOT EXISTS {ALERT_SCHEMA}.accepted_event_snapshots (
          event_uid VARCHAR PRIMARY KEY, species_code VARCHAR NOT NULL,
          watch_id VARCHAR NOT NULL, activation_generation VARCHAR NOT NULL,
          source_report_id VARCHAR NOT NULL, accepted_sequence BIGINT NOT NULL,
          event_horizon_end VARCHAR NOT NULL, payload_json VARCHAR NOT NULL,
          payload_hash VARCHAR NOT NULL, accepted_at VARCHAR NOT NULL
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
) -> tuple[CalendarPayload, tuple[str, str, str]]:
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
    return payload, (str(event[1]), str(event[2]), str(event[8]))


def _enqueue_event_intent(
    connection: duckdb.DuckDBPyConnection, species_code: str, *, now: datetime
) -> str:
    """Enqueue one current sendable event inside the caller's transaction."""

    ensure_outbox_tables(connection)
    payload, (watch_id, activation_generation, source_report_id) = _payload_for_event(
        connection, species_code
    )
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
        f"""INSERT INTO {ALERT_SCHEMA}.alert_outbox (
          outbox_id, species_code, watch_id, activation_generation,
          source_report_id, event_uid, sequence, method, payload_json,
          payload_hash, state, next_attempt_at, claim_token, claimed_at,
          claim_expires_at, send_started_at, attempt_count, created_at,
          updated_at, terminal_at, safe_terminal_reason
        ) VALUES
            (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'pending', ?, NULL, NULL, NULL, NULL,
             0, ?, ?, NULL, NULL)""",
        [
            outbox_id,
            payload.species_code,
            watch_id,
            activation_generation,
            source_report_id,
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
                SET state=?, payload_json=CASE WHEN ?='delivery_unknown'
                    THEN payload_json ELSE '{{}}' END,
                    claim_token=NULL, claimed_at=NULL, claim_expires_at=NULL,
                    updated_at=?, terminal_at=?, safe_terminal_reason=?
                WHERE outbox_id=?""",
            [next_state, next_state, timestamp, terminal_at, reason, outbox_id],
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


def record_pre_send_outcome(
    connection: duckdb.DuckDBPyConnection,
    *,
    outbox_id: str,
    claim_token: str,
    outcome: Literal["retry_wait", "failed"],
    now: datetime,
    safe_reason: str,
    next_attempt_at: datetime | None = None,
) -> None:
    """Record a preparation failure while transmission is provably unstarted."""

    if not re.fullmatch(r"[a-z_]{1,64}", safe_reason):
        raise ValueError("outcome reason is invalid")
    if (outcome == "retry_wait") != (next_attempt_at is not None):
        raise ValueError("retry outcome scheduling is inconsistent")
    timestamp = _iso(now)
    connection.execute("BEGIN TRANSACTION")
    try:
        row = connection.execute(
            f"""SELECT attempt_count, send_started_at FROM {ALERT_SCHEMA}.alert_outbox
                WHERE outbox_id=? AND state='claimed' AND claim_token=?""",
            [outbox_id, claim_token],
        ).fetchone()
        if row is None or row[1] is not None:
            raise ValueError("outbox preparation attempt is not active")
        attempt_number = int(row[0]) + 1
        terminal_at = timestamp if outcome == "failed" else None
        connection.execute(
            f"""UPDATE {ALERT_SCHEMA}.alert_outbox SET state=?, next_attempt_at=?,
                claim_token=NULL, claimed_at=NULL, claim_expires_at=NULL,
                attempt_count=?, updated_at=?, terminal_at=?, safe_terminal_reason=?
                WHERE outbox_id=?""",
            [
                outcome,
                _iso(next_attempt_at) if next_attempt_at is not None else timestamp,
                attempt_number,
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
                attempt_number,
                claim_token,
                outcome,
                safe_reason,
                timestamp,
            ],
        )
        connection.execute("COMMIT")
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
        if row is None:
            replay = connection.execute(
                f"""SELECT outbox.state FROM {ALERT_SCHEMA}.alert_outbox AS outbox
                    WHERE outbox.outbox_id=? AND outbox.state='accepted'
                      AND EXISTS (
                        SELECT 1 FROM {ALERT_SCHEMA}.outbox_attempts AS attempt
                        WHERE attempt.outbox_id=outbox.outbox_id
                          AND attempt.claim_token=? AND attempt.phase='accepted'
                      )""",
                [outbox_id, claim_token],
            ).fetchone()
            if replay is not None and outcome == "accepted":
                connection.execute("COMMIT")
                return
            raise ValueError("outbox attempt is not active")
        if row[5] is None:
            raise ValueError("outbox attempt is not active")
        accepted_snapshot = (
            _validated_reconciliation_snapshot(connection, outbox_id)
            if outcome == "accepted"
            else None
        )
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
                if accepted_snapshot is None:
                    raise ValueError("accepted delivery snapshot is unavailable")
                _propagate_accepted_request_snapshot(connection, accepted_snapshot, now=now)
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
                connection.execute(
                    f"DELETE FROM {ALERT_SCHEMA}.accepted_event_snapshots WHERE event_uid=?",
                    [row[1]],
                )
        connection.execute("COMMIT")
    except Exception:
        connection.execute("ROLLBACK")
        raise


@dataclass(frozen=True)
class ReconciliationSnapshot:
    state: str
    outbox_id: str
    species_code: str
    watch_id: str
    activation_generation: str
    source_report_id: str
    payload: CalendarPayload
    attempt_count: int
    safe_reason: str | None


def _validated_reconciliation_snapshot(
    connection: duckdb.DuckDBPyConnection, outbox_id: str
) -> ReconciliationSnapshot:
    row = connection.execute(
        f"""SELECT state, species_code, watch_id, activation_generation,
                   source_report_id, event_uid, sequence, method, payload_json,
                   payload_hash, attempt_count, safe_terminal_reason
            FROM {ALERT_SCHEMA}.alert_outbox WHERE outbox_id=?""",
        [outbox_id],
    ).fetchone()
    if row is None or row[4] is None:
        raise ValueError("alert delivery is unavailable")
    payload = CalendarPayload.model_validate_json(str(row[8]))
    if (
        payload.payload_hash != str(row[9])
        or payload.species_code != str(row[1])
        or payload.event_uid != str(row[5])
        or payload.sequence != int(row[6])
        or payload.method != str(row[7])
    ):
        raise ValueError("alert delivery canonical identity is inconsistent")
    reports = connection.execute(
        f"""SELECT report_id, species_code, watch_id, activation_generation,
                   common_name, scientific_name, confirmed_location_id,
                   confirmed_location_name, confirmed_latitude, confirmed_longitude,
                   confirmed_distance_miles, independent_submission_count,
                   newest_observation_at, morning_start, morning_end,
                   event_horizon_end
            FROM {ALERT_SCHEMA}.match_reports WHERE report_id=? LIMIT 2""",
        [row[4]],
    ).fetchall()
    if len(reports) != 1:
        raise ValueError("alert delivery source report is unavailable or non-unique")
    report = reports[0]
    report_location_name = report[7] or f"eBird location {report[6]}"
    coherent = (
        str(report[0]) == str(row[4])
        and str(report[1]) == payload.species_code
        and str(report[2]) == str(row[2])
        and str(report[3]) == str(row[3])
        and (str(report[4]) if report[4] is not None else None) == payload.common_name
        and (str(report[5]) if report[5] is not None else None) == payload.scientific_name
        and str(report[6]) == payload.location_id
        and str(report_location_name) == payload.location_name
        and float(report[8]) == payload.latitude
        and float(report[9]) == payload.longitude
        and str(report[13]) == payload.morning_start
        and str(report[14]) == payload.morning_end
        and str(report[15]) == payload.event_horizon_end
    )
    if payload.method == "REQUEST":
        coherent = coherent and (
            float(report[10]) == payload.confirmed_distance_miles
            and int(report[11]) == payload.independent_submission_count
            and str(report[12]) == payload.newest_observation_at
        )
    if not coherent:
        raise ValueError("alert delivery and source report are inconsistent")
    return ReconciliationSnapshot(
        state=str(row[0]),
        outbox_id=outbox_id,
        species_code=payload.species_code,
        watch_id=str(row[2]),
        activation_generation=str(row[3]),
        source_report_id=str(row[4]),
        payload=payload,
        attempt_count=int(row[10]),
        safe_reason=str(row[11]) if row[11] is not None else None,
    )


def _active_retry_event(
    connection: duckdb.DuckDBPyConnection, snapshot: ReconciliationSnapshot, now: datetime
) -> bool:
    event = connection.execute(
        f"""SELECT event_uid, sequence, status, event_horizon_end, watch_id,
                   activation_generation, source_report_id, morning_start,
                   morning_end, location_id, location_name, latitude, longitude
            FROM {ALERT_SCHEMA}.event_intents WHERE species_code=?""",
        [snapshot.species_code],
    ).fetchone()
    if (
        event is None
        or str(event[0]) != snapshot.payload.event_uid
        or int(event[1]) < snapshot.payload.sequence
        or str(event[2]) not in {"pending_request", "accepted"}
        or event[3] is None
        or _parse_timestamp(str(event[3])) <= now.astimezone(UTC)
    ):
        return False
    if int(event[1]) == snapshot.payload.sequence:
        return bool(
            str(event[4]) == snapshot.watch_id
            and str(event[5]) == snapshot.activation_generation
            and str(event[6]) == snapshot.source_report_id
            and str(event[7]) == snapshot.payload.morning_start
            and str(event[8]) == snapshot.payload.morning_end
            and str(event[3]) == snapshot.payload.event_horizon_end
            and str(event[9]) == snapshot.payload.location_id
            and str(event[10]) == snapshot.payload.location_name
            and float(event[11]) == snapshot.payload.latitude
            and float(event[12]) == snapshot.payload.longitude
        )
    current = connection.execute(
        f"""SELECT outbox_id FROM {ALERT_SCHEMA}.alert_outbox
            WHERE event_uid=? AND sequence=? AND method='REQUEST' LIMIT 2""",
        [event[0], event[1]],
    ).fetchall()
    if len(current) != 1:
        return False
    current_snapshot = _validated_reconciliation_snapshot(connection, str(current[0][0]))
    return current_snapshot.payload.event_horizon_end == str(event[3])


def delivery_allowed_actions(
    connection: duckdb.DuckDBPyConnection, *, outbox_id: str, now: datetime
) -> tuple[list[str], bool]:
    state = connection.execute(
        f"SELECT state FROM {ALERT_SCHEMA}.alert_outbox WHERE outbox_id=?", [outbox_id]
    ).fetchone()
    if state is None:
        raise ValueError("alert delivery is unavailable")
    if str(state[0]) not in {"delivery_unknown", "failed"}:
        return [], False
    snapshot = _validated_reconciliation_snapshot(connection, outbox_id)
    active = _active_retry_event(connection, snapshot, now)
    if snapshot.state == "delivery_unknown":
        if active:
            return ["mark_delivered", "mark_not_delivered_and_retry"], True
        return ["mark_delivered", "mark_not_delivered"], False
    if snapshot.state == "failed" and active:
        return ["retry_failed"], True
    return [], False


def _persist_accepted_snapshot(
    connection: duckdb.DuckDBPyConnection,
    snapshot: ReconciliationSnapshot,
    *,
    now: datetime,
) -> None:
    payload = snapshot.payload
    existing = connection.execute(
        f"""SELECT accepted_sequence, payload_hash
            FROM {ALERT_SCHEMA}.accepted_event_snapshots WHERE event_uid=?""",
        [payload.event_uid],
    ).fetchone()
    if existing is not None and int(existing[0]) > payload.sequence:
        return
    if existing is not None and int(existing[0]) == payload.sequence:
        if str(existing[1]) != payload.payload_hash:
            raise ValueError("accepted event snapshot identity conflicts")
        return
    connection.execute(
        f"""INSERT OR REPLACE INTO {ALERT_SCHEMA}.accepted_event_snapshots VALUES
            (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        [
            payload.event_uid,
            snapshot.species_code,
            snapshot.watch_id,
            snapshot.activation_generation,
            snapshot.source_report_id,
            payload.sequence,
            payload.event_horizon_end,
            payload.canonical_json(),
            payload.payload_hash,
            _iso(now),
        ],
    )


def _create_cancel_from_accepted_snapshot(
    connection: duckdb.DuckDBPyConnection,
    snapshot: ReconciliationSnapshot,
    *,
    now: datetime,
    current_sequence: int,
) -> str:
    payload = snapshot.payload
    next_sequence = max(current_sequence, payload.sequence) + 1
    timestamp = _iso(now)
    connection.execute(
        f"""UPDATE {ALERT_SCHEMA}.match_reports
            SET resolved_at=COALESCE(resolved_at, ?) WHERE report_id=?""",
        [timestamp, snapshot.source_report_id],
    )
    event = connection.execute(
        f"SELECT count(*) FROM {ALERT_SCHEMA}.event_intents WHERE species_code=?",
        [snapshot.species_code],
    ).fetchone()
    values = [
        snapshot.watch_id,
        snapshot.activation_generation,
        payload.event_uid,
        next_sequence,
        snapshot.source_report_id,
        payload.morning_start,
        payload.morning_end,
        payload.event_horizon_end,
        payload.location_id,
        payload.location_name,
        payload.latitude,
        payload.longitude,
        payload.sequence,
        payload.event_horizon_end,
        timestamp,
        timestamp,
        snapshot.species_code,
    ]
    if event is not None and int(event[0]) == 1:
        connection.execute(
            f"""UPDATE {ALERT_SCHEMA}.event_intents SET watch_id=?,
                activation_generation=?, event_uid=?, sequence=?, method='CANCEL',
                status='pending_cancel', report_id=NULL, source_report_id=?,
                morning_start=?, morning_end=?, event_horizon_end=?, location_id=?,
                location_name=?, latitude=?, longitude=?, last_accepted_sequence=?,
                last_accepted_horizon_end=?, last_accepted_at=?, updated_at=?
                WHERE species_code=?""",
            values,
        )
    else:
        connection.execute(
            f"""INSERT INTO {ALERT_SCHEMA}.event_intents (
              watch_id, activation_generation, event_uid, sequence, method, status,
              report_id, source_report_id, morning_start, morning_end,
              event_horizon_end, location_id, location_name, latitude, longitude,
              last_accepted_sequence, last_accepted_horizon_end, last_accepted_at,
              updated_at, species_code
            ) VALUES (?, ?, ?, ?, 'CANCEL', 'pending_cancel', NULL, ?, ?, ?, ?,
                      ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            values,
        )
    return _enqueue_event_intent(connection, snapshot.species_code, now=now)


def enqueue_cancel_from_accepted_snapshot(
    connection: duckdb.DuckDBPyConnection,
    *,
    event_uid: str,
    now: datetime,
    in_transaction: bool = False,
) -> str | None:
    """Create one coherent greater-sequence CANCEL from the last accepted REQUEST."""

    def create() -> str | None:
        row = connection.execute(
            f"""SELECT species_code, watch_id, activation_generation,
                       source_report_id, accepted_sequence, event_horizon_end,
                       payload_json, payload_hash, accepted_at
                FROM {ALERT_SCHEMA}.accepted_event_snapshots WHERE event_uid=?""",
            [event_uid],
        ).fetchone()
        if row is None or _parse_timestamp(str(row[5])) <= now.astimezone(UTC):
            return None
        payload = CalendarPayload.model_validate_json(str(row[6]))
        if (
            payload.method != "REQUEST"
            or payload.event_uid != event_uid
            or payload.species_code != str(row[0])
            or payload.sequence != int(row[4])
            or payload.event_horizon_end != str(row[5])
            or payload.payload_hash != str(row[7])
        ):
            raise ValueError("accepted event snapshot is inconsistent")
        snapshot = ReconciliationSnapshot(
            state="accepted",
            outbox_id="accepted-snapshot",
            species_code=str(row[0]),
            watch_id=str(row[1]),
            activation_generation=str(row[2]),
            source_report_id=str(row[3]),
            payload=payload,
            attempt_count=0,
            safe_reason=None,
        )
        event = connection.execute(
            f"""SELECT sequence, event_uid, status FROM {ALERT_SCHEMA}.event_intents
                WHERE species_code=?""",
            [snapshot.species_code],
        ).fetchone()
        if event is not None and str(event[1]) != event_uid:
            raise ValueError("accepted event UID conflicts with current event")
        if event is not None and str(event[2]) in {"pending_cancel", "cancelled"}:
            existing = connection.execute(
                f"""SELECT outbox_id FROM {ALERT_SCHEMA}.alert_outbox
                    WHERE event_uid=? AND method='CANCEL' ORDER BY sequence DESC LIMIT 1""",
                [event_uid],
            ).fetchone()
            return str(existing[0]) if existing is not None else None
        current_sequence = int(event[0]) if event is not None else payload.sequence
        return _create_cancel_from_accepted_snapshot(
            connection, snapshot, now=now, current_sequence=current_sequence
        )

    if in_transaction:
        return create()
    connection.execute("BEGIN TRANSACTION")
    try:
        result = create()
        connection.execute("COMMIT")
        return result
    except Exception:
        connection.execute("ROLLBACK")
        raise


def _propagate_accepted_request_snapshot(
    connection: duckdb.DuckDBPyConnection,
    snapshot: ReconciliationSnapshot,
    *,
    now: datetime,
) -> None:
    """Persist acceptance without regressing a newer same-UID event."""

    payload = snapshot.payload
    if payload.method != "REQUEST":
        raise ValueError("accepted request propagation requires REQUEST payload")
    _persist_accepted_snapshot(connection, snapshot, now=now)
    event = connection.execute(
        f"""SELECT event_uid, sequence, status FROM {ALERT_SCHEMA}.event_intents
            WHERE species_code=?""",
        [snapshot.species_code],
    ).fetchone()
    if event is not None and str(event[0]) != payload.event_uid:
        raise ValueError("current event UID conflicts with accepted delivery")
    timestamp = _iso(now)
    if event is not None:
        connection.execute(
            f"""UPDATE {ALERT_SCHEMA}.event_intents SET
                last_accepted_sequence=CASE
                  WHEN last_accepted_sequence IS NULL OR last_accepted_sequence < ?
                  THEN ? ELSE last_accepted_sequence END,
                last_accepted_horizon_end=CASE
                  WHEN last_accepted_sequence IS NULL OR last_accepted_sequence <= ?
                  THEN ? ELSE last_accepted_horizon_end END,
                last_accepted_at=CASE
                  WHEN last_accepted_sequence IS NULL OR last_accepted_sequence <= ?
                  THEN ? ELSE last_accepted_at END,
                status=CASE WHEN sequence=? AND status='pending_request'
                  THEN 'accepted' ELSE status END,
                updated_at=CASE WHEN sequence=? AND status='pending_request'
                  THEN ? ELSE updated_at END
                WHERE species_code=? AND event_uid=? AND sequence>=?""",
            [
                payload.sequence,
                payload.sequence,
                payload.sequence,
                payload.event_horizon_end,
                payload.sequence,
                timestamp,
                payload.sequence,
                payload.sequence,
                timestamp,
                snapshot.species_code,
                payload.event_uid,
                payload.sequence,
            ],
        )
    current_status = str(event[2]) if event is not None else "suppressed"
    if (
        current_status in {"suppressed", "expired"}
        and _parse_timestamp(payload.event_horizon_end) > now.astimezone(UTC)
    ) or event is None:
        enqueue_cancel_from_accepted_snapshot(
            connection, event_uid=payload.event_uid, now=now, in_transaction=True
        )


def reconcile_unknown_as_delivered(
    connection: duckdb.DuckDBPyConnection,
    *,
    outbox_id: str,
    now: datetime,
) -> None:
    """Idempotently accept an ambiguous delivery after operator reconciliation."""

    timestamp = _iso(now)
    connection.execute("BEGIN TRANSACTION")
    try:
        snapshot = _validated_reconciliation_snapshot(connection, outbox_id)
        if snapshot.state == "accepted":
            connection.execute("COMMIT")
            return
        if snapshot.state != "delivery_unknown":
            raise ValueError("only unknown delivery can be marked delivered")
        payload = snapshot.payload
        event = connection.execute(
            f"""SELECT event_uid, sequence, status FROM {ALERT_SCHEMA}.event_intents
                WHERE species_code=?""",
            [snapshot.species_code],
        ).fetchone()
        if event is not None and str(event[0]) != payload.event_uid:
            raise ValueError("current event UID conflicts with accepted delivery")
        connection.execute(
            f"""UPDATE {ALERT_SCHEMA}.alert_outbox SET state='accepted', updated_at=?,
                terminal_at=?, safe_terminal_reason='manual_mark_delivered'
                WHERE outbox_id=?""",
            [timestamp, timestamp, outbox_id],
        )
        connection.execute(
            f"INSERT INTO {ALERT_SCHEMA}.outbox_attempts VALUES (?, ?, ?, ?, 'accepted', ?, ?)",
            [
                str(uuid.uuid4()),
                outbox_id,
                snapshot.attempt_count,
                "manual-reconciliation",
                "manual_mark_delivered",
                timestamp,
            ],
        )
        if payload.method == "REQUEST":
            _propagate_accepted_request_snapshot(connection, snapshot, now=now)
        elif event is not None and int(event[1]) == payload.sequence:
            connection.execute(
                f"""UPDATE {ALERT_SCHEMA}.event_intents SET status='cancelled',
                    report_id=NULL, source_report_id=NULL, morning_start=NULL,
                    morning_end=NULL, event_horizon_end=NULL, location_id=NULL,
                    location_name=NULL, latitude=NULL, longitude=NULL,
                    last_accepted_sequence=NULL, last_accepted_horizon_end=NULL,
                    last_accepted_at=NULL, updated_at=?
                    WHERE species_code=? AND event_uid=? AND sequence=?
                      AND status='pending_cancel'""",
                [timestamp, snapshot.species_code, payload.event_uid, payload.sequence],
            )
            connection.execute(
                f"DELETE FROM {ALERT_SCHEMA}.accepted_event_snapshots WHERE event_uid=?",
                [payload.event_uid],
            )
        connection.execute("COMMIT")
    except Exception:
        connection.execute("ROLLBACK")
        raise


def reconcile_unknown_as_not_delivered(
    connection: duckdb.DuckDBPyConnection,
    *,
    outbox_id: str,
    now: datetime,
) -> None:
    """Terminally resolve an inactive unknown without creating a retry."""

    timestamp = _iso(now)
    connection.execute("BEGIN TRANSACTION")
    try:
        snapshot = _validated_reconciliation_snapshot(connection, outbox_id)
        if snapshot.state == "failed" and snapshot.safe_reason == "manual_mark_not_delivered":
            connection.execute("COMMIT")
            return
        actions, can_retry = delivery_allowed_actions(connection, outbox_id=outbox_id, now=now)
        if snapshot.state != "delivery_unknown" or can_retry or "mark_not_delivered" not in actions:
            raise ValueError("unknown active delivery requires a new-sequence retry")
        connection.execute(
            f"""UPDATE {ALERT_SCHEMA}.alert_outbox SET state='failed', terminal_at=?,
                updated_at=?, safe_terminal_reason='manual_mark_not_delivered'
                WHERE outbox_id=?""",
            [timestamp, timestamp, outbox_id],
        )
        connection.execute(
            f"INSERT INTO {ALERT_SCHEMA}.outbox_attempts VALUES (?, ?, ?, ?, 'failed', ?, ?)",
            [
                str(uuid.uuid4()),
                outbox_id,
                snapshot.attempt_count,
                "manual-reconciliation",
                "manual_mark_not_delivered",
                timestamp,
            ],
        )
        connection.execute("COMMIT")
    except Exception:
        connection.execute("ROLLBACK")
        raise


def retry_terminal_delivery(
    connection: duckdb.DuckDBPyConnection,
    *,
    outbox_id: str,
    now: datetime,
) -> str:
    """Retry a failed/unknown delivery as a new sequence; never resend the old row."""

    timestamp = _iso(now)
    connection.execute("BEGIN TRANSACTION")
    try:
        row = connection.execute(
            f"""SELECT state, species_code, event_uid, sequence, method,
                       safe_terminal_reason, attempt_count
                FROM {ALERT_SCHEMA}.alert_outbox WHERE outbox_id=?""",
            [outbox_id],
        ).fetchone()
        if row is None:
            raise ValueError("alert delivery is unavailable")
        if str(row[5]) == "manual_retry_enqueued":
            existing = connection.execute(
                f"""SELECT outbox_id FROM {ALERT_SCHEMA}.alert_outbox
                    WHERE event_uid=? AND sequence>? ORDER BY sequence LIMIT 1""",
                [row[2], row[3]],
            ).fetchone()
            if existing is None:
                raise ValueError("manual retry state is inconsistent")
            connection.execute("COMMIT")
            return str(existing[0])
        if str(row[0]) not in {"failed", "delivery_unknown"}:
            raise ValueError("only failed or unknown delivery can be retried")
        actions, can_retry = delivery_allowed_actions(connection, outbox_id=outbox_id, now=now)
        expected_action = (
            "mark_not_delivered_and_retry" if str(row[0]) == "delivery_unknown" else "retry_failed"
        )
        if not can_retry or expected_action not in actions:
            raise ValueError("alert delivery is not retryable in its current event state")
        event = connection.execute(
            f"""SELECT sequence FROM {ALERT_SCHEMA}.event_intents
                WHERE species_code=? AND event_uid=?""",
            [row[1], row[2]],
        ).fetchone()
        if event is None or int(event[0]) < int(row[3]):
            raise ValueError("alert event state is inconsistent")
        if int(event[0]) > int(row[3]):
            existing = connection.execute(
                f"""SELECT outbox_id FROM {ALERT_SCHEMA}.alert_outbox
                    WHERE event_uid=? AND sequence=? ORDER BY outbox_id LIMIT 1""",
                [row[2], event[0]],
            ).fetchone()
            if existing is None:
                raise ValueError("advanced alert event lacks an outbox row")
            connection.execute(
                f"""UPDATE {ALERT_SCHEMA}.alert_outbox SET state='failed', terminal_at=?,
                    updated_at=?, safe_terminal_reason='manual_retry_enqueued'
                    WHERE outbox_id=?""",
                [timestamp, timestamp, outbox_id],
            )
            connection.execute(
                f"INSERT INTO {ALERT_SCHEMA}.outbox_attempts VALUES (?, ?, ?, ?, 'failed', ?, ?)",
                [
                    str(uuid.uuid4()),
                    outbox_id,
                    int(row[6]),
                    "manual-reconciliation",
                    "manual_retry_enqueued",
                    timestamp,
                ],
            )
            connection.execute("COMMIT")
            return str(existing[0])
        next_sequence = int(row[3]) + 1
        pending_status = "pending_request" if str(row[4]) == "REQUEST" else "pending_cancel"
        connection.execute(
            f"""UPDATE {ALERT_SCHEMA}.event_intents SET sequence=?, status=?
                WHERE species_code=? AND event_uid=? AND sequence=?""",
            [next_sequence, pending_status, row[1], row[2], row[3]],
        )
        connection.execute(
            f"""UPDATE {ALERT_SCHEMA}.alert_outbox SET state='failed', terminal_at=?,
                updated_at=?, safe_terminal_reason='manual_retry_enqueued'
                WHERE outbox_id=?""",
            [timestamp, timestamp, outbox_id],
        )
        connection.execute(
            f"INSERT INTO {ALERT_SCHEMA}.outbox_attempts VALUES (?, ?, ?, ?, 'failed', ?, ?)",
            [
                str(uuid.uuid4()),
                outbox_id,
                int(row[6]),
                "manual-reconciliation",
                "manual_retry_enqueued",
                timestamp,
            ],
        )
        next_id = _enqueue_event_intent(connection, str(row[1]), now=now)
        connection.execute("COMMIT")
        return next_id
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
    connection.execute(
        f"""DELETE FROM {ALERT_SCHEMA}.accepted_event_snapshots AS snapshot
            WHERE snapshot.accepted_at < ? AND NOT EXISTS (
              SELECT 1 FROM {ALERT_SCHEMA}.event_intents AS event
              WHERE event.event_uid=snapshot.event_uid
                AND event.status NOT IN ('cancelled','expired')
            )""",
        [cutoff],
    )
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
        description = f"The Rufous watched-bird event for {name} was cancelled."
        status = "CANCELLED"
    lines = [
        "BEGIN:VCALENDAR",
        "PRODID:-//Rufous//Bird Alert//EN",
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
        f"Your Rufous bird alert for {name} was {action}. Open the calendar invitation for details."
    )
    message.add_alternative(
        calendar,
        subtype="calendar",
        charset="utf-8",
        params={"method": payload.method},
    )
    message.set_boundary("databox-" + payload.payload_hash[:32])
    return message
