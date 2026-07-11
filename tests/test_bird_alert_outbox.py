from __future__ import annotations

import json
import socket
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from email import policy
from email.parser import BytesParser
from pathlib import Path
from threading import Barrier
from typing import Any

import duckdb
import pytest
from databox.bird_alert_outbox import (
    ALERT_SCHEMA,
    CalendarPayload,
    build_calendar_mime,
    build_icalendar,
    claim_next_outbox,
    cleanup_outbox_history,
    enqueue_event_intent,
    ensure_outbox_tables,
    record_attempt_outcome,
    recover_expired_claims,
    start_send_attempt,
    suppress_event_outbox,
)
from databox.watched_bird_evaluator import ensure_alert_tables
from pydantic import ValidationError

NOW = datetime(2026, 7, 10, 12, tzinfo=UTC)
START = datetime(2026, 7, 11, 12, tzinfo=UTC)
END = START + timedelta(hours=2)
HORIZON = NOW + timedelta(days=5)
ORGANIZER = "alerts@example.invalid"
ATTENDEE = "birder@example.invalid"


def _database(path: Path) -> duckdb.DuckDBPyConnection:
    connection = duckdb.connect(str(path))
    connection.execute("CREATE SCHEMA birding_agent")
    connection.execute(
        """CREATE TABLE birding_agent.arizona_species_catalog (
           species_code VARCHAR, common_name VARCHAR, scientific_name VARCHAR)"""
    )
    connection.execute(
        "INSERT INTO birding_agent.arizona_species_catalog VALUES "
        "('target1','Target Bird','Avis target')"
    )
    ensure_alert_tables(connection)
    ensure_outbox_tables(connection)
    _insert_report(connection)
    return connection


def _insert_report(connection: duckdb.DuckDBPyConnection) -> None:
    connection.execute(
        f"""INSERT INTO {ALERT_SCHEMA}.match_reports (
           report_id, run_id, watch_id, activation_generation, species_code,
           common_name, scientific_name, watch_center_name,
           watch_center_latitude, watch_center_longitude, radius_miles,
           confirmed_location_id, confirmed_location_name, confirmed_latitude,
           confirmed_longitude, confirmed_distance_miles,
           independent_submission_count, newest_observation_at, clusters_json,
           morning_start, morning_end, event_horizon_end, weather_json,
           caveats_json, emphasis_ids_json, report_status, evidence_freshness_at,
           model, fact_hash, created_at, resolved_at
        ) VALUES (
          'report-1','run-1','watch-1','generation-1','target1',
          'Target Bird','Avis target','Personal Center',33.5,-112.5,100,
          'L1','Public Lake',34.1,-112.1,42.5,2,
          '2026-07-10T11:00:00+00:00','[]',?,?,?,?,
          '[\"Evidence is recent.\"]','[\"freshness\"]','ready',
          '2026-07-10T11:00:00+00:00',NULL,?, ?, NULL
        )""",
        [
            START.isoformat(),
            END.isoformat(),
            HORIZON.isoformat(),
            json.dumps({"status": "available"}),
            "f" * 64,
            NOW.isoformat(),
        ],
    )


def _insert_event(
    connection: duckdb.DuckDBPyConnection,
    *,
    sequence: int = 0,
    method: str = "REQUEST",
    status: str = "pending_request",
    report_id: str | None = "report-1",
) -> None:
    connection.execute(f"DELETE FROM {ALERT_SCHEMA}.event_intents WHERE species_code='target1'")
    connection.execute(
        f"UPDATE {ALERT_SCHEMA}.match_reports SET resolved_at=? WHERE report_id='report-1'",
        [(NOW + timedelta(minutes=1)).isoformat() if method == "CANCEL" else None],
    )
    connection.execute(
        f"""INSERT INTO {ALERT_SCHEMA}.event_intents (
          species_code, watch_id, activation_generation, event_uid, sequence,
          method, status, report_id, source_report_id, morning_start, morning_end,
          event_horizon_end, location_id, location_name, latitude, longitude,
          last_accepted_sequence, last_accepted_horizon_end, last_accepted_at,
          updated_at
        ) VALUES (
          'target1','watch-1','generation-1','stable-target@local',?,?,?, ?,
          'report-1', ?, ?, ?, 'L1', 'Public Lake',34.1,-112.1,NULL,NULL,NULL,?
        )""",
        [
            sequence,
            method,
            status,
            report_id,
            START.isoformat(),
            END.isoformat(),
            HORIZON.isoformat(),
            NOW.isoformat(),
        ],
    )


def _downgrade_event_table(connection: duckdb.DuckDBPyConnection) -> None:
    connection.execute(
        f"""CREATE TABLE {ALERT_SCHEMA}.event_intents_legacy AS SELECT
          species_code, watch_id, activation_generation, event_uid, sequence,
          method, status, report_id, morning_start, morning_end,
          event_horizon_end, location_name, latitude, longitude,
          last_accepted_sequence, last_accepted_horizon_end, last_accepted_at,
          updated_at
        FROM {ALERT_SCHEMA}.event_intents"""
    )
    connection.execute(f"DROP TABLE {ALERT_SCHEMA}.event_intents")
    connection.execute(f"ALTER TABLE {ALERT_SCHEMA}.event_intents_legacy RENAME TO event_intents")


def _remove_event_constraints(connection: duckdb.DuckDBPyConnection) -> None:
    connection.execute(
        f"CREATE TABLE {ALERT_SCHEMA}.event_intents_unchecked AS "
        f"SELECT * FROM {ALERT_SCHEMA}.event_intents"
    )
    connection.execute(f"DROP TABLE {ALERT_SCHEMA}.event_intents")
    connection.execute(
        f"ALTER TABLE {ALERT_SCHEMA}.event_intents_unchecked RENAME TO event_intents"
    )


def _payload(method: str = "REQUEST", sequence: int = 0) -> CalendarPayload:
    return CalendarPayload(
        species_code="target1",
        common_name="Target Bird",
        scientific_name="Avis target",
        event_uid="stable-target@local",
        sequence=sequence,
        method=method,
        dtstamp=NOW.isoformat(),
        morning_start=START.isoformat(),
        morning_end=END.isoformat(),
        event_horizon_end=HORIZON.isoformat(),
        location_id="L1",
        location_name="Public Lake",
        latitude=34.1,
        longitude=-112.1,
        confirmed_distance_miles=42.5 if method == "REQUEST" else None,
        independent_submission_count=2 if method == "REQUEST" else None,
        newest_observation_at="2026-07-10T11:00:00+00:00" if method == "REQUEST" else None,
    )


def test_request_and_cancel_build_standards_calendar_and_deterministic_mime() -> None:
    request = _payload()
    calendar = build_icalendar(request, organizer=ORGANIZER, attendee=ATTENDEE)
    assert calendar.startswith("BEGIN:VCALENDAR\r\n")
    assert "METHOD:REQUEST\r\n" in calendar
    assert "UID:stable-target@local\r\n" in calendar
    assert "SEQUENCE:0\r\n" in calendar
    assert "DTSTART:20260711T120000Z\r\n" in calendar
    assert "DTEND:20260711T140000Z\r\n" in calendar
    assert f"ORGANIZER:mailto:{ORGANIZER}\r\n" in calendar
    assert f"ATTENDEE;ROLE=REQ-PARTICIPANT;RSVP=TRUE:mailto:{ATTENDEE}\r\n" in calendar
    assert "STATUS:CONFIRMED\r\n" in calendar
    assert "http://" not in calendar and "https://" not in calendar
    assert all(len(line.encode()) <= 75 for line in calendar.split("\r\n"))

    first = build_calendar_mime(request, organizer=ORGANIZER, attendee=ATTENDEE).as_bytes()
    second = build_calendar_mime(request, organizer=ORGANIZER, attendee=ATTENDEE).as_bytes()
    assert first == second
    parsed = BytesParser(policy=policy.default).parsebytes(first)
    assert parsed["From"] == ORGANIZER
    assert parsed["To"] == ATTENDEE
    calendar_part = next(
        part for part in parsed.walk() if part.get_content_type() == "text/calendar"
    )
    assert calendar_part.get_param("method") == "REQUEST"
    assert "BEGIN:VCALENDAR" in calendar_part.get_content()

    cancel = _payload("CANCEL", 1)
    cancelled = build_icalendar(cancel, organizer=ORGANIZER, attendee=ATTENDEE)
    assert "METHOD:CANCEL\r\n" in cancelled
    assert "SEQUENCE:1\r\n" in cancelled
    assert "STATUS:CANCELLED\r\n" in cancelled
    assert "UID:stable-target@local\r\n" in cancelled


def test_builder_rejects_injection_unbounded_payload_and_addresses() -> None:
    with pytest.raises(ValidationError, match="calendar text is invalid"):
        CalendarPayload.model_validate({**_payload().model_dump(), "location_name": "Lake\r\nEND"})
    with pytest.raises(ValueError, match="email address"):
        build_icalendar(_payload(), organizer="bad\r\nBcc:x@y.invalid", attendee=ATTENDEE)
    with pytest.raises(ValidationError):
        CalendarPayload.model_validate({**_payload().model_dump(), "event_uid": "u" * 129})
    with pytest.raises(ValidationError, match="horizon"):
        CalendarPayload.model_validate(
            {
                **_payload().model_dump(),
                "event_horizon_end": (NOW + timedelta(days=4)).isoformat(),
            }
        )


@pytest.mark.parametrize(
    ("status", "method"),
    [("pending_request", "CANCEL"), ("pending_cancel", "REQUEST")],
)
def test_enqueue_rejects_mismatched_status_method_and_rolls_back(
    tmp_path: Path, status: str, method: str
) -> None:
    connection = _database(tmp_path / f"mismatch-{status}.duckdb")
    _insert_event(connection)
    _remove_event_constraints(connection)
    connection.execute(
        f"UPDATE {ALERT_SCHEMA}.event_intents SET status=?, method=?", [status, method]
    )
    with pytest.raises(ValueError, match="status and method"):
        enqueue_event_intent(connection, "target1", now=NOW)
    assert connection.execute(
        f"SELECT status, method FROM {ALERT_SCHEMA}.event_intents"
    ).fetchone() == (status, method)
    assert connection.execute(f"SELECT count(*) FROM {ALERT_SCHEMA}.alert_outbox").fetchone() == (
        0,
    )
    connection.close()


@pytest.mark.parametrize(
    "malformation",
    [
        "cross_report",
        "missing_report",
        "species",
        "watch",
        "generation",
        "morning_start",
        "morning_end",
        "horizon",
        "location_id",
        "location_name",
        "latitude",
        "longitude",
    ],
)
def test_request_enqueue_rejects_every_report_event_relationship_mismatch(
    tmp_path: Path, malformation: str
) -> None:
    connection = _database(tmp_path / f"relation-{malformation}.duckdb")
    _insert_event(connection)
    if malformation == "cross_report":
        connection.execute(
            f"""INSERT INTO {ALERT_SCHEMA}.match_reports
                SELECT * REPLACE ('report-2' AS report_id)
                FROM {ALERT_SCHEMA}.match_reports WHERE report_id='report-1'"""
        )
        connection.execute(f"UPDATE {ALERT_SCHEMA}.event_intents SET source_report_id='report-2'")
    elif malformation == "missing_report":
        connection.execute(f"DELETE FROM {ALERT_SCHEMA}.match_reports")
    elif malformation in {"species", "watch", "generation"}:
        column = {
            "species": "species_code",
            "watch": "watch_id",
            "generation": "activation_generation",
        }[malformation]
        connection.execute(f"UPDATE {ALERT_SCHEMA}.match_reports SET {column}='other-value'")
    elif malformation in {"morning_start", "morning_end", "horizon"}:
        column = "event_horizon_end" if malformation == "horizon" else malformation
        connection.execute(
            f"UPDATE {ALERT_SCHEMA}.match_reports SET {column}='2026-07-12T00:00:00+00:00'"
        )
    elif malformation in {"location_id", "location_name"}:
        column = (
            "confirmed_location_id" if malformation == "location_id" else "confirmed_location_name"
        )
        connection.execute(
            f"UPDATE {ALERT_SCHEMA}.match_reports SET {column}='different-public-location'"
        )
    else:
        column = "confirmed_latitude" if malformation == "latitude" else "confirmed_longitude"
        connection.execute(f"UPDATE {ALERT_SCHEMA}.match_reports SET {column}=35.5")
    with pytest.raises(ValueError, match="report|linkage|inconsistent"):
        enqueue_event_intent(connection, "target1", now=NOW)
    assert connection.execute(f"SELECT count(*) FROM {ALERT_SCHEMA}.alert_outbox").fetchone() == (
        0,
    )
    connection.close()


def test_pre_release_event_schema_migrates_exact_request_or_rolls_back_cancel(
    tmp_path: Path,
) -> None:
    valid = _database(tmp_path / "migration-valid.duckdb")
    _insert_event(valid)
    _downgrade_event_table(valid)
    with pytest.raises(ValueError, match="explicit transaction"):
        ensure_alert_tables(valid)
    assert valid.execute(
        """SELECT count(*) FROM information_schema.tables
           WHERE table_schema='birding_alerts'
             AND table_name='event_intents_migration'"""
    ).fetchone() == (0,)
    valid.execute("BEGIN TRANSACTION")
    ensure_alert_tables(valid, migrate_pre_release=True)
    valid.execute("COMMIT")
    assert valid.execute(
        f"SELECT source_report_id, location_id FROM {ALERT_SCHEMA}.event_intents"
    ).fetchone() == ("report-1", "L1")
    check_count = valid.execute(
        """SELECT count(*) FROM duckdb_constraints()
           WHERE schema_name='birding_alerts' AND table_name='event_intents'
             AND constraint_type='CHECK'"""
    ).fetchone()[0]
    assert check_count >= 5
    assert enqueue_event_intent(valid, "target1", now=NOW)
    valid.close()

    invalid = _database(tmp_path / "migration-invalid.duckdb")
    _insert_event(
        invalid,
        sequence=1,
        method="CANCEL",
        status="pending_cancel",
        report_id=None,
    )
    _downgrade_event_table(invalid)
    invalid.execute("BEGIN TRANSACTION")
    with pytest.raises(duckdb.ConstraintException):
        ensure_alert_tables(invalid, migrate_pre_release=True)
    invalid.execute("ROLLBACK")
    columns = {
        str(row[0])
        for row in invalid.execute(
            """SELECT column_name FROM information_schema.columns
               WHERE table_schema='birding_alerts' AND table_name='event_intents'"""
        ).fetchall()
    }
    assert not {"source_report_id", "location_id"} & columns
    assert invalid.execute(
        """SELECT count(*) FROM information_schema.tables
           WHERE table_schema='birding_alerts'
             AND table_name='event_intents_migration'"""
    ).fetchone() == (0,)
    assert invalid.execute(f"SELECT count(*) FROM {ALERT_SCHEMA}.alert_outbox").fetchone() == (0,)
    invalid.close()


def test_enqueue_replay_supersession_cancel_and_payload_privacy(tmp_path: Path) -> None:
    connection = _database(tmp_path / "outbox.duckdb")
    _insert_event(connection)
    first = enqueue_event_intent(connection, "target1", now=NOW)
    assert enqueue_event_intent(connection, "target1", now=NOW + timedelta(minutes=30)) == first
    row = connection.execute(
        f"""SELECT state, method, sequence, payload_json, payload_hash
            FROM {ALERT_SCHEMA}.alert_outbox WHERE outbox_id=?""",
        [first],
    ).fetchone()
    assert row[:3] == ("pending", "REQUEST", 0)
    assert "Personal Center" not in row[3]
    assert ORGANIZER not in row[3] and ATTENDEE not in row[3]
    assert len(row[4]) == 64

    _insert_event(connection, sequence=1)
    second = enqueue_event_intent(connection, "target1", now=NOW + timedelta(minutes=1))
    assert second != first
    assert connection.execute(
        f"SELECT state FROM {ALERT_SCHEMA}.alert_outbox WHERE outbox_id=?", [first]
    ).fetchone() == ("superseded",)

    _insert_event(
        connection,
        sequence=2,
        method="CANCEL",
        status="pending_cancel",
        report_id=None,
    )
    third = enqueue_event_intent(connection, "target1", now=NOW + timedelta(minutes=2))
    assert connection.execute(
        f"SELECT method, sequence, state FROM {ALERT_SCHEMA}.alert_outbox WHERE outbox_id=?",
        [third],
    ).fetchone() == ("CANCEL", 2, "pending")
    assert connection.execute(
        f"SELECT state FROM {ALERT_SCHEMA}.alert_outbox WHERE outbox_id=?", [second]
    ).fetchone() == ("superseded",)
    claim = claim_next_outbox(connection, now=NOW + timedelta(minutes=2))
    assert claim is not None and claim.outbox_id == third
    start_send_attempt(
        connection,
        outbox_id=third,
        claim_token=claim.claim_token,
        now=NOW + timedelta(minutes=2),
    )
    record_attempt_outcome(
        connection,
        outbox_id=third,
        claim_token=claim.claim_token,
        outcome="accepted",
        now=NOW + timedelta(minutes=3),
        safe_reason="bridge_accepted",
    )
    assert connection.execute(
        f"SELECT status, event_horizon_end, location_name FROM {ALERT_SCHEMA}.event_intents"
    ).fetchone() == ("cancelled", None, None)
    connection.close()


def test_event_and_outbox_enqueue_roll_back_together(tmp_path: Path) -> None:
    connection = _database(tmp_path / "rollback.duckdb")
    connection.execute("BEGIN TRANSACTION")
    _insert_event(connection)
    enqueue_event_intent(connection, "target1", now=NOW, in_transaction=True)
    connection.execute("ROLLBACK")
    assert connection.execute(f"SELECT count(*) FROM {ALERT_SCHEMA}.event_intents").fetchone() == (
        0,
    )
    assert connection.execute(f"SELECT count(*) FROM {ALERT_SCHEMA}.alert_outbox").fetchone() == (
        0,
    )
    connection.close()


def test_atomic_claim_start_accept_and_event_state(tmp_path: Path) -> None:
    connection = _database(tmp_path / "claim.duckdb")
    _insert_event(connection)
    outbox_id = enqueue_event_intent(connection, "target1", now=NOW)
    claim = claim_next_outbox(connection, now=NOW)
    assert claim is not None and claim.outbox_id == outbox_id
    assert claim_next_outbox(connection, now=NOW) is None
    with pytest.raises(ValueError, match="not active"):
        record_attempt_outcome(
            connection,
            outbox_id=outbox_id,
            claim_token=claim.claim_token,
            outcome="accepted",
            now=NOW,
            safe_reason="bridge_accepted",
        )
    assert (
        start_send_attempt(
            connection, outbox_id=outbox_id, claim_token=claim.claim_token, now=NOW
        ).event_uid
        == "stable-target@local"
    )
    with pytest.raises(ValueError, match="not startable"):
        start_send_attempt(connection, outbox_id=outbox_id, claim_token=claim.claim_token, now=NOW)
    record_attempt_outcome(
        connection,
        outbox_id=outbox_id,
        claim_token=claim.claim_token,
        outcome="accepted",
        now=NOW + timedelta(seconds=1),
        safe_reason="bridge_accepted",
    )
    assert connection.execute(
        f"SELECT state, attempt_count FROM {ALERT_SCHEMA}.alert_outbox"
    ).fetchone() == ("accepted", 1)
    assert connection.execute(
        f"""SELECT status, last_accepted_sequence, last_accepted_at IS NOT NULL
            FROM {ALERT_SCHEMA}.event_intents"""
    ).fetchone() == ("accepted", 0, True)
    assert connection.execute(
        f"SELECT phase FROM {ALERT_SCHEMA}.outbox_attempts ORDER BY occurred_at, phase"
    ).fetchall() == [("send_started",), ("accepted",)]
    connection.close()


def test_newer_sequence_survives_acceptance_of_inflight_older_request(tmp_path: Path) -> None:
    connection = _database(tmp_path / "inflight.duckdb")
    _insert_event(connection)
    first_id = enqueue_event_intent(connection, "target1", now=NOW)
    first_claim = claim_next_outbox(connection, now=NOW)
    assert first_claim is not None
    start_send_attempt(
        connection,
        outbox_id=first_id,
        claim_token=first_claim.claim_token,
        now=NOW,
    )

    _insert_event(connection, sequence=1)
    second_id = enqueue_event_intent(connection, "target1", now=NOW + timedelta(minutes=1))
    record_attempt_outcome(
        connection,
        outbox_id=first_id,
        claim_token=first_claim.claim_token,
        outcome="accepted",
        now=NOW + timedelta(minutes=2),
        safe_reason="bridge_accepted",
    )
    assert connection.execute(
        f"SELECT state FROM {ALERT_SCHEMA}.alert_outbox WHERE outbox_id=?", [first_id]
    ).fetchone() == ("accepted",)
    assert connection.execute(
        f"SELECT sequence, status FROM {ALERT_SCHEMA}.event_intents"
    ).fetchone() == (1, "pending_request")
    assert claim_next_outbox(connection, now=NOW + timedelta(minutes=2)).outbox_id == second_id
    connection.close()


def test_claim_lease_recovery_and_unknown_blocks_new_sequence(tmp_path: Path) -> None:
    connection = _database(tmp_path / "recovery.duckdb")
    _insert_event(connection)
    first_id = enqueue_event_intent(connection, "target1", now=NOW)
    first_claim = claim_next_outbox(connection, now=NOW, lease=timedelta(minutes=1))
    assert first_claim is not None
    assert recover_expired_claims(connection, now=NOW + timedelta(minutes=2)) == {
        "recovered": 1,
        "delivery_unknown": 0,
    }
    assert connection.execute(
        f"SELECT state FROM {ALERT_SCHEMA}.alert_outbox WHERE outbox_id=?", [first_id]
    ).fetchone() == ("pending",)

    second_claim = claim_next_outbox(
        connection, now=NOW + timedelta(minutes=2), lease=timedelta(minutes=1)
    )
    assert second_claim is not None and second_claim.claim_token != first_claim.claim_token
    start_send_attempt(
        connection,
        outbox_id=first_id,
        claim_token=second_claim.claim_token,
        now=NOW + timedelta(minutes=2),
    )
    assert recover_expired_claims(connection, now=NOW + timedelta(minutes=4)) == {
        "recovered": 0,
        "delivery_unknown": 1,
    }
    assert connection.execute(
        f"SELECT state FROM {ALERT_SCHEMA}.alert_outbox WHERE outbox_id=?", [first_id]
    ).fetchone() == ("delivery_unknown",)

    _insert_event(connection, sequence=1)
    enqueue_event_intent(connection, "target1", now=NOW + timedelta(minutes=5))
    assert claim_next_outbox(connection, now=NOW + timedelta(minutes=5)) is None
    connection.close()


def test_claim_naturally_expires_event_without_cancel_delivery(tmp_path: Path) -> None:
    connection = _database(tmp_path / "expiry.duckdb")
    _insert_event(connection)
    enqueue_event_intent(connection, "target1", now=NOW)
    assert claim_next_outbox(connection, now=HORIZON + timedelta(seconds=1)) is None
    assert connection.execute(
        f"SELECT status, method, sequence, report_id FROM {ALERT_SCHEMA}.event_intents"
    ).fetchone() == ("expired", "REQUEST", 0, None)
    assert connection.execute(
        f"SELECT state, method, sequence, payload_json FROM {ALERT_SCHEMA}.alert_outbox"
    ).fetchone() == ("cancelled", "REQUEST", 0, "{}")
    assert connection.execute(
        f"SELECT count(*) FROM {ALERT_SCHEMA}.alert_outbox WHERE method='CANCEL'"
    ).fetchone() == (0,)
    connection.close()


def test_retry_wait_transition_and_due_time(tmp_path: Path) -> None:
    connection = _database(tmp_path / "retry.duckdb")
    _insert_event(connection)
    outbox_id = enqueue_event_intent(connection, "target1", now=NOW)
    claim = claim_next_outbox(connection, now=NOW)
    assert claim is not None
    start_send_attempt(connection, outbox_id=outbox_id, claim_token=claim.claim_token, now=NOW)
    due = NOW + timedelta(minutes=5)
    record_attempt_outcome(
        connection,
        outbox_id=outbox_id,
        claim_token=claim.claim_token,
        outcome="retry_wait",
        now=NOW + timedelta(seconds=1),
        next_attempt_at=due,
        safe_reason="transient_pre_acceptance",
    )
    assert claim_next_outbox(connection, now=due - timedelta(seconds=1)) is None
    assert claim_next_outbox(connection, now=due) is not None
    connection.close()


def test_suppression_cancels_pre_send_and_marks_started_send_unknown(tmp_path: Path) -> None:
    connection = _database(tmp_path / "suppress.duckdb")
    _insert_event(connection)
    outbox_id = enqueue_event_intent(connection, "target1", now=NOW)
    suppress_event_outbox(
        connection,
        event_uid="stable-target@local",
        sequence=0,
        now=NOW,
        reason="watch_inactive_before_acceptance",
    )
    assert connection.execute(
        f"SELECT state, payload_json FROM {ALERT_SCHEMA}.alert_outbox WHERE outbox_id=?",
        [outbox_id],
    ).fetchone() == ("cancelled", "{}")
    assert claim_next_outbox(connection, now=NOW) is None

    _insert_event(connection, sequence=1)
    second = enqueue_event_intent(connection, "target1", now=NOW + timedelta(minutes=1))
    claim = claim_next_outbox(connection, now=NOW + timedelta(minutes=1))
    assert claim is not None
    start_send_attempt(
        connection,
        outbox_id=second,
        claim_token=claim.claim_token,
        now=NOW + timedelta(minutes=1),
    )
    suppress_event_outbox(
        connection,
        event_uid="stable-target@local",
        sequence=1,
        now=NOW + timedelta(minutes=2),
        reason="watch_inactive_after_send_started",
    )
    assert connection.execute(
        f"SELECT state, payload_json FROM {ALERT_SCHEMA}.alert_outbox WHERE outbox_id=?",
        [second],
    ).fetchone() == ("delivery_unknown", "{}")
    connection.close()


def test_two_workers_cannot_claim_same_row(tmp_path: Path) -> None:
    path = tmp_path / "concurrent.duckdb"
    connection = _database(path)
    _insert_event(connection)
    enqueue_event_intent(connection, "target1", now=NOW)
    connection.close()
    barrier = Barrier(2)

    def worker() -> str | None:
        local = duckdb.connect(str(path))
        barrier.wait()
        claim = claim_next_outbox(local, now=NOW)
        local.close()
        return claim.claim_token if claim is not None else None

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(lambda _: worker(), range(2)))
    assert len([item for item in results if item is not None]) == 1


def test_retention_purges_terminal_payload_but_keeps_unknown_and_dedupe(tmp_path: Path) -> None:
    connection = _database(tmp_path / "retention.duckdb")
    _insert_event(connection)
    accepted_id = enqueue_event_intent(connection, "target1", now=NOW)
    connection.execute(
        f"""UPDATE {ALERT_SCHEMA}.alert_outbox
            SET state='accepted', terminal_at='2026-01-01T00:00:00+00:00',
                updated_at='2026-01-01T00:00:00+00:00' WHERE outbox_id=?""",
        [accepted_id],
    )
    _insert_event(connection, sequence=1)
    unknown_id = enqueue_event_intent(connection, "target1", now=NOW + timedelta(minutes=1))
    connection.execute(
        f"""UPDATE {ALERT_SCHEMA}.alert_outbox SET state='delivery_unknown',
            safe_terminal_reason='ambiguous' WHERE outbox_id=?""",
        [unknown_id],
    )
    assert cleanup_outbox_history(connection, now=NOW) == {"outbox_deleted": 1}
    assert connection.execute(
        f"SELECT outbox_id, state FROM {ALERT_SCHEMA}.alert_outbox"
    ).fetchone() == (unknown_id, "delivery_unknown")
    assert connection.execute(
        f"SELECT outbox_id, payload_hash FROM {ALERT_SCHEMA}.outbox_dedupe"
    ).fetchone() == (accepted_id, _payload().payload_hash)
    connection.close()


def test_pure_builders_and_state_machine_never_open_network(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def forbidden(*args: Any, **kwargs: Any) -> None:
        raise AssertionError("calendar/outbox mechanics must not open sockets")

    monkeypatch.setattr(socket, "create_connection", forbidden)
    connection = _database(tmp_path / "network.duckdb")
    _insert_event(connection)
    enqueue_event_intent(connection, "target1", now=NOW)
    claim = claim_next_outbox(connection, now=NOW)
    assert claim is not None
    build_calendar_mime(claim.payload, organizer=ORGANIZER, attendee=ATTENDEE).as_bytes()
    connection.close()
