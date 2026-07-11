from __future__ import annotations

import smtplib
import ssl
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import duckdb
import pytest
from databox.api import create_app
from databox.bird_alert_delivery import (
    BirdAlertSmtpSettings,
    _tls_context,
    deliver_next_outbox,
    send_bounded_live_verification,
)
from databox.bird_alert_outbox import (
    ALERT_SCHEMA,
    CalendarPayload,
    claim_next_outbox,
    cleanup_outbox_history,
    delivery_allowed_actions,
    ensure_outbox_tables,
    reconcile_unknown_as_delivered,
    reconcile_unknown_as_not_delivered,
    record_attempt_outcome,
    retry_terminal_delivery,
    start_send_attempt,
    suppress_event_outbox,
)
from fastapi.testclient import TestClient
from pydantic import SecretStr, ValidationError

NOW = datetime(2026, 7, 10, 12, tzinfo=UTC)


def _certificate(path: Path) -> Path:
    path.write_text("-----BEGIN CERTIFICATE-----\nTEST\n-----END CERTIFICATE-----\n")
    return path


def _settings(tmp_path: Path) -> BirdAlertSmtpSettings:
    return BirdAlertSmtpSettings(
        enabled=SecretStr("true"),
        security=SecretStr("starttls"),
        host=SecretStr("127.0.0.1"),
        port=SecretStr("1025"),
        username=SecretStr("sender@example.invalid"),
        password=SecretStr("bridge-secret"),
        organizer=SecretStr("sender@example.invalid"),
        recipient=SecretStr("recipient@example.invalid"),
        ca_file=SecretStr(str(_certificate(tmp_path / "bridge.pem"))),
    )


def _payload(sequence: int = 0) -> CalendarPayload:
    return CalendarPayload(
        species_code="target1",
        common_name="Target Bird",
        scientific_name="Avis target",
        event_uid="stable-target@local",
        sequence=sequence,
        method="REQUEST",
        dtstamp=NOW.isoformat(),
        morning_start=(NOW + timedelta(days=1)).isoformat(),
        morning_end=(NOW + timedelta(days=1, hours=2)).isoformat(),
        event_horizon_end=(NOW + timedelta(days=5)).isoformat(),
        location_id="L1",
        location_name="Public Lake",
        latitude=34.1,
        longitude=-112.1,
        confirmed_distance_miles=10,
        independent_submission_count=2,
        newest_observation_at=(NOW - timedelta(hours=1)).isoformat(),
    )


def _database(path: Path) -> duckdb.DuckDBPyConnection:
    connection = duckdb.connect(str(path))
    ensure_outbox_tables(connection)
    connection.execute(
        f"""CREATE TABLE {ALERT_SCHEMA}.event_intents (
          species_code VARCHAR PRIMARY KEY, watch_id VARCHAR, activation_generation VARCHAR,
          event_uid VARCHAR, sequence BIGINT, method VARCHAR, status VARCHAR,
          report_id VARCHAR, source_report_id VARCHAR, morning_start VARCHAR,
          morning_end VARCHAR, event_horizon_end VARCHAR, location_id VARCHAR,
          location_name VARCHAR, latitude DOUBLE, longitude DOUBLE,
          last_accepted_sequence BIGINT, last_accepted_horizon_end VARCHAR,
          last_accepted_at VARCHAR, updated_at VARCHAR
        )"""
    )
    connection.execute(
        f"""CREATE TABLE {ALERT_SCHEMA}.match_reports (
          report_id VARCHAR, species_code VARCHAR, watch_id VARCHAR,
          activation_generation VARCHAR, common_name VARCHAR, scientific_name VARCHAR,
          confirmed_location_id VARCHAR, confirmed_location_name VARCHAR,
          confirmed_latitude DOUBLE, confirmed_longitude DOUBLE,
          confirmed_distance_miles DOUBLE, independent_submission_count BIGINT,
          newest_observation_at VARCHAR, morning_start VARCHAR, morning_end VARCHAR,
          event_horizon_end VARCHAR, resolved_at VARCHAR
        )"""
    )
    _insert_pending(connection)
    return connection


def _insert_pending(connection: duckdb.DuckDBPyConnection, sequence: int = 0) -> str:
    payload = _payload(sequence)
    outbox_id = f"alert_outbox_{sequence:064x}"
    connection.execute(f"DELETE FROM {ALERT_SCHEMA}.event_intents")
    connection.execute(f"DELETE FROM {ALERT_SCHEMA}.match_reports")
    connection.execute(
        f"""INSERT INTO {ALERT_SCHEMA}.match_reports VALUES
          ('report-1','target1','watch-1','generation-1','Target Bird','Avis target',
           'L1','Public Lake',34.1,-112.1,10,2,?,?,?, ?, NULL)""",
        [
            payload.newest_observation_at,
            payload.morning_start,
            payload.morning_end,
            payload.event_horizon_end,
        ],
    )
    connection.execute(
        f"""INSERT INTO {ALERT_SCHEMA}.event_intents VALUES
          ('target1','watch-1','generation-1', ?, ?, 'REQUEST', 'pending_request',
           'report-1', 'report-1', ?, ?, ?, 'L1', 'Public Lake', 34.1, -112.1,
           NULL, NULL, NULL, ?)""",
        [
            payload.event_uid,
            sequence,
            payload.morning_start,
            payload.morning_end,
            payload.event_horizon_end,
            payload.dtstamp,
        ],
    )
    connection.execute(
        f"""INSERT INTO {ALERT_SCHEMA}.alert_outbox VALUES
          (?, 'target1', 'watch-1', 'generation-1', 'report-1', ?, ?, 'REQUEST', ?, ?,
           'pending', ?, NULL, NULL, NULL, NULL, 0, ?, ?, NULL, NULL)""",
        [
            outbox_id,
            payload.event_uid,
            sequence,
            payload.canonical_json(),
            payload.payload_hash,
            NOW.isoformat(),
            NOW.isoformat(),
            NOW.isoformat(),
        ],
    )
    return outbox_id


class FakeSmtp:
    def __init__(
        self,
        events: list[str],
        *,
        login_error: Exception | None = None,
        send_error: Exception | None = None,
    ) -> None:
        self.events = events
        self.login_error = login_error
        self.send_error = send_error
        self.message: Any = None

    def ehlo(self) -> None:
        self.events.append("ehlo")

    def starttls(self, *, context: ssl.SSLContext) -> None:
        assert context.check_hostname and context.verify_mode == ssl.CERT_REQUIRED
        self.events.append("starttls")

    def login(self, user: str, password: str) -> None:
        self.events.append("login")
        if self.login_error:
            raise self.login_error

    def send_message(self, message: Any) -> dict[str, Any]:
        self.events.append("send_message")
        self.message = message
        if self.send_error:
            raise self.send_error
        return {}

    def quit(self) -> None:
        self.events.append("quit")

    def close(self) -> None:
        self.events.append("close")


def test_secret_settings_validate_loopback_exact_public_ca_and_redact(tmp_path: Path) -> None:
    configured = _settings(tmp_path)
    rendered = repr(configured) + repr(configured.runtime())
    assert "bridge-secret" not in rendered
    assert "sender@example" not in rendered
    assert "recipient@example" not in rendered
    for host in ("localhost", "192.0.2.1"):
        with pytest.raises(ValidationError, match="numeric loopback"):
            BirdAlertSmtpSettings(**{**configured.model_dump(), "host": SecretStr(host)})
    with pytest.raises(ValidationError, match="organizer"):
        BirdAlertSmtpSettings(
            **{**configured.model_dump(), "organizer": SecretStr("other@example.invalid")}
        )
    private = tmp_path / "private.pem"
    private.write_text("-----BEGIN CERTIFICATE-----\nX\n-----END CERTIFICATE-----\nPRIVATE KEY")
    with pytest.raises(ValidationError, match="public certificate"):
        BirdAlertSmtpSettings(**{**configured.model_dump(), "ca_file": SecretStr(str(private))})


def test_tls_context_loads_only_configured_ca_and_keeps_hostname_verification(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    loaded: list[str] = []

    class Context:
        check_hostname = False
        verify_mode = ssl.CERT_NONE

        def load_verify_locations(self, *, cafile: str) -> None:
            loaded.append(cafile)

    context = Context()
    monkeypatch.setattr(ssl, "SSLContext", lambda protocol: context)
    certificate = _certificate(tmp_path / "only-ca.pem")
    assert _tls_context(certificate) is context
    assert context.check_hostname is True and context.verify_mode == ssl.CERT_REQUIRED
    assert loaded == [str(certificate)]


def test_sender_requires_starttls_auth_then_records_explicit_acceptance(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    connection = _database(tmp_path / "accepted.duckdb")
    settings = _settings(tmp_path)
    events: list[str] = []
    fake = FakeSmtp(events)
    monkeypatch.setattr(
        "databox.bird_alert_delivery._tls_context", lambda _: ssl.create_default_context()
    )
    result = deliver_next_outbox(
        connection, settings=settings, now=NOW, smtp_factory=lambda *a, **k: fake
    )
    assert result.status == "accepted"
    assert events == ["ehlo", "starttls", "ehlo", "login", "send_message", "quit"]
    assert fake.message["From"] == "sender@example.invalid"
    assert fake.message["To"] == "recipient@example.invalid"
    assert "bridge-secret" not in fake.message.as_string()
    assert connection.execute(
        f"SELECT state, attempt_count, safe_terminal_reason FROM {ALERT_SCHEMA}.alert_outbox"
    ).fetchone() == ("accepted", 1, "smtp_bridge_accepted")
    connection.close()


def test_pre_acceptance_transient_retries_exactly_one_five_fifteen_then_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    connection = _database(tmp_path / "retry.duckdb")
    settings = _settings(tmp_path)
    monkeypatch.setattr(
        "databox.bird_alert_delivery._tls_context", lambda _: ssl.create_default_context()
    )
    moments = [
        NOW,
        NOW + timedelta(minutes=1),
        NOW + timedelta(minutes=6),
        NOW + timedelta(minutes=21),
    ]
    expected = [NOW + timedelta(minutes=1), NOW + timedelta(minutes=6), NOW + timedelta(minutes=21)]
    for index, moment in enumerate(moments):
        result = deliver_next_outbox(
            connection,
            settings=settings,
            now=moment,
            smtp_factory=lambda *a, **k: (_ for _ in ()).throw(TimeoutError()),
        )
        if index < 3:
            assert result.status == "retry_wait"
            assert result.next_attempt_at == expected[index].isoformat()
        else:
            assert result.status == "failed"
    assert connection.execute(
        f"SELECT state, attempt_count FROM {ALERT_SCHEMA}.alert_outbox"
    ).fetchone() == ("failed", 4)
    connection.close()


def test_permanent_auth_rejection_stops_and_post_send_disconnect_is_unknown(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        "databox.bird_alert_delivery._tls_context", lambda _: ssl.create_default_context()
    )
    settings = _settings(tmp_path)
    permanent = _database(tmp_path / "permanent.duckdb")
    auth = FakeSmtp([], login_error=smtplib.SMTPAuthenticationError(535, b"rejected"))
    assert (
        deliver_next_outbox(
            permanent, settings=settings, now=NOW, smtp_factory=lambda *a, **k: auth
        ).status
        == "failed"
    )
    assert permanent.execute(
        f"SELECT attempt_count FROM {ALERT_SCHEMA}.alert_outbox"
    ).fetchone() == (1,)
    permanent.close()

    unsupported = _database(tmp_path / "unsupported-starttls.duckdb")

    class MissingStartTls(FakeSmtp):
        def starttls(self, *, context: ssl.SSLContext) -> None:
            self.events.append("starttls")
            raise smtplib.SMTPNotSupportedError("missing")

    missing_starttls = MissingStartTls([])
    unsupported_result = deliver_next_outbox(
        unsupported,
        settings=settings,
        now=NOW,
        smtp_factory=lambda *a, **k: missing_starttls,
    )
    assert unsupported_result.status == "failed"
    assert unsupported.execute(
        f"SELECT state, attempt_count, next_attempt_at FROM {ALERT_SCHEMA}.alert_outbox"
    ).fetchone() == ("failed", 1, NOW.isoformat())
    unsupported.close()

    unknown = _database(tmp_path / "unknown.duckdb")
    disconnected = FakeSmtp([], send_error=TimeoutError())
    result = deliver_next_outbox(
        unknown, settings=settings, now=NOW, smtp_factory=lambda *a, **k: disconnected
    )
    assert result.status == "delivery_unknown"
    assert (
        deliver_next_outbox(
            unknown,
            settings=settings,
            now=NOW + timedelta(hours=1),
            smtp_factory=lambda *a, **k: FakeSmtp([]),
        ).status
        == "idle"
    )
    reconcile_unknown_as_delivered(unknown, outbox_id=result.outbox_id or "", now=NOW)
    reconcile_unknown_as_delivered(unknown, outbox_id=result.outbox_id or "", now=NOW)
    assert unknown.execute(f"SELECT state FROM {ALERT_SCHEMA}.alert_outbox").fetchone() == (
        "accepted",
    )
    unknown.close()


def _suppress_started_request(connection: duckdb.DuckDBPyConnection) -> str:
    outbox_id = connection.execute(
        f"SELECT outbox_id FROM {ALERT_SCHEMA}.alert_outbox WHERE sequence=0"
    ).fetchone()[0]
    claim = claim_next_outbox(connection, now=NOW)
    assert claim is not None
    start_send_attempt(connection, outbox_id=outbox_id, claim_token=claim.claim_token, now=NOW)
    suppress_event_outbox(
        connection,
        event_uid="stable-target@local",
        sequence=0,
        now=NOW + timedelta(minutes=1),
        reason="watch_inactive_after_send_started",
    )
    connection.execute(
        f"UPDATE {ALERT_SCHEMA}.match_reports SET resolved_at=? WHERE report_id='report-1'",
        [(NOW + timedelta(minutes=1)).isoformat()],
    )
    connection.execute(
        f"""UPDATE {ALERT_SCHEMA}.event_intents SET status='suppressed',
            report_id=NULL, source_report_id=NULL, morning_start=NULL,
            morning_end=NULL, event_horizon_end=NULL, location_id=NULL,
            location_name=NULL, latitude=NULL, longitude=NULL,
            last_accepted_sequence=NULL, last_accepted_horizon_end=NULL,
            last_accepted_at=NULL, updated_at=?""",
        [(NOW + timedelta(minutes=1)).isoformat()],
    )
    return str(outbox_id)


def test_suppressed_unknown_actions_terminal_without_retry_or_cancel_from_snapshot(
    tmp_path: Path,
) -> None:
    terminal = _database(tmp_path / "inactive-terminal.duckdb")
    terminal_id = _suppress_started_request(terminal)
    assert delivery_allowed_actions(terminal, outbox_id=terminal_id, now=NOW) == (
        ["mark_delivered", "mark_not_delivered"],
        False,
    )
    reconcile_unknown_as_not_delivered(terminal, outbox_id=terminal_id, now=NOW)
    reconcile_unknown_as_not_delivered(terminal, outbox_id=terminal_id, now=NOW)
    assert terminal.execute(
        f"SELECT state, safe_terminal_reason FROM {ALERT_SCHEMA}.alert_outbox"
    ).fetchone() == ("failed", "manual_mark_not_delivered")
    assert terminal.execute(
        f"SELECT count(*) FROM {ALERT_SCHEMA}.alert_outbox WHERE method='CANCEL'"
    ).fetchone() == (0,)
    terminal.close()

    delivered = _database(tmp_path / "inactive-delivered.duckdb")
    delivered_id = _suppress_started_request(delivered)
    reconcile_unknown_as_delivered(delivered, outbox_id=delivered_id, now=NOW)
    reconcile_unknown_as_delivered(delivered, outbox_id=delivered_id, now=NOW)
    rows = delivered.execute(
        f"SELECT sequence, method, state FROM {ALERT_SCHEMA}.alert_outbox ORDER BY sequence"
    ).fetchall()
    assert rows == [(0, "REQUEST", "accepted"), (1, "CANCEL", "pending")]
    cancel = CalendarPayload.model_validate_json(
        delivered.execute(
            f"SELECT payload_json FROM {ALERT_SCHEMA}.alert_outbox WHERE method='CANCEL'"
        ).fetchone()[0]
    )
    assert (cancel.event_uid, cancel.location_id, cancel.morning_start) == (
        "stable-target@local",
        "L1",
        _payload().morning_start,
    )
    snapshot = delivered.execute(
        f"""SELECT accepted_sequence, event_horizon_end, payload_hash
            FROM {ALERT_SCHEMA}.accepted_event_snapshots"""
    ).fetchone()
    assert snapshot == (0, _payload().event_horizon_end, _payload().payload_hash)
    delivered.close()


def test_suppressed_unknown_reconciliation_rolls_back_tampering_and_is_concurrent_safe(
    tmp_path: Path,
) -> None:
    tampered = _database(tmp_path / "tampered.duckdb")
    tampered_id = _suppress_started_request(tampered)
    tampered.execute(f"UPDATE {ALERT_SCHEMA}.match_reports SET confirmed_location_name='Different'")
    with pytest.raises(ValueError, match="inconsistent"):
        reconcile_unknown_as_delivered(tampered, outbox_id=tampered_id, now=NOW)
    assert tampered.execute(
        f"SELECT state FROM {ALERT_SCHEMA}.alert_outbox WHERE outbox_id=?", [tampered_id]
    ).fetchone() == ("delivery_unknown",)
    assert tampered.execute(
        f"SELECT count(*) FROM {ALERT_SCHEMA}.accepted_event_snapshots"
    ).fetchone() == (0,)
    tampered.close()

    path = tmp_path / "concurrent-reconcile.duckdb"
    setup = _database(path)
    outbox_id = _suppress_started_request(setup)
    setup.close()

    def reconcile() -> str:
        connection = duckdb.connect(str(path))
        try:
            reconcile_unknown_as_delivered(connection, outbox_id=outbox_id, now=NOW)
            return "ok"
        except duckdb.TransactionException:
            return "conflict"
        finally:
            connection.close()

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: reconcile(), range(2)))
    assert "ok" in results
    check = duckdb.connect(str(path))
    assert check.execute(
        f"SELECT count(*) FROM {ALERT_SCHEMA}.alert_outbox WHERE method='CANCEL'"
    ).fetchone() == (1,)
    assert check.execute(
        f"""SELECT count(*) FROM {ALERT_SCHEMA}.outbox_attempts
            WHERE safe_reason='manual_mark_delivered'"""
    ).fetchone() == (1,)
    check.close()


def test_automatic_acceptance_rollback_and_newer_snapshot_precedence(tmp_path: Path) -> None:
    rollback = _database(tmp_path / "automatic-rollback.duckdb")
    first_id = rollback.execute(
        f"SELECT outbox_id FROM {ALERT_SCHEMA}.alert_outbox WHERE sequence=0"
    ).fetchone()[0]
    first_claim = claim_next_outbox(rollback, now=NOW)
    assert first_claim is not None
    start_send_attempt(rollback, outbox_id=first_id, claim_token=first_claim.claim_token, now=NOW)
    _insert_pending(rollback, sequence=1)
    rollback.execute(f"UPDATE {ALERT_SCHEMA}.match_reports SET confirmed_location_name='Tampered'")
    with pytest.raises(ValueError, match="inconsistent"):
        record_attempt_outcome(
            rollback,
            outbox_id=first_id,
            claim_token=first_claim.claim_token,
            outcome="accepted",
            now=NOW,
            safe_reason="smtp_bridge_accepted",
        )
    assert rollback.execute(
        f"SELECT state FROM {ALERT_SCHEMA}.alert_outbox WHERE outbox_id=?", [first_id]
    ).fetchone() == ("claimed",)
    assert rollback.execute(
        f"SELECT count(*) FROM {ALERT_SCHEMA}.accepted_event_snapshots"
    ).fetchone() == (0,)
    rollback.close()

    precedence = _database(tmp_path / "automatic-precedence.duckdb")
    first_id = precedence.execute(
        f"SELECT outbox_id FROM {ALERT_SCHEMA}.alert_outbox WHERE sequence=0"
    ).fetchone()[0]
    first_claim = claim_next_outbox(precedence, now=NOW)
    assert first_claim is not None
    start_send_attempt(precedence, outbox_id=first_id, claim_token=first_claim.claim_token, now=NOW)
    second_id = _insert_pending(precedence, sequence=1)
    record_attempt_outcome(
        precedence,
        outbox_id=first_id,
        claim_token=first_claim.claim_token,
        outcome="accepted",
        now=NOW,
        safe_reason="smtp_bridge_accepted",
    )
    second_claim = claim_next_outbox(precedence, now=NOW)
    assert second_claim is not None and second_claim.outbox_id == second_id
    start_send_attempt(
        precedence, outbox_id=second_id, claim_token=second_claim.claim_token, now=NOW
    )
    record_attempt_outcome(
        precedence,
        outbox_id=second_id,
        claim_token=second_claim.claim_token,
        outcome="accepted",
        now=NOW + timedelta(seconds=1),
        safe_reason="smtp_bridge_accepted",
    )
    record_attempt_outcome(
        precedence,
        outbox_id=first_id,
        claim_token=first_claim.claim_token,
        outcome="accepted",
        now=NOW + timedelta(seconds=2),
        safe_reason="smtp_bridge_accepted",
    )
    assert precedence.execute(
        f"""SELECT accepted_sequence, payload_hash
            FROM {ALERT_SCHEMA}.accepted_event_snapshots"""
    ).fetchone() == (1, _payload(sequence=1).payload_hash)
    assert precedence.execute(
        f"""SELECT sequence, status, last_accepted_sequence
            FROM {ALERT_SCHEMA}.event_intents"""
    ).fetchone() == (1, "accepted", 1)
    precedence.close()


def test_automatic_acceptance_concurrency_is_single_effect(tmp_path: Path) -> None:
    path = tmp_path / "automatic-concurrency.duckdb"
    setup = _database(path)
    outbox_id = setup.execute(f"SELECT outbox_id FROM {ALERT_SCHEMA}.alert_outbox").fetchone()[0]
    claim = claim_next_outbox(setup, now=NOW)
    assert claim is not None
    start_send_attempt(setup, outbox_id=outbox_id, claim_token=claim.claim_token, now=NOW)
    setup.close()

    def accept() -> str:
        connection = duckdb.connect(str(path))
        try:
            record_attempt_outcome(
                connection,
                outbox_id=outbox_id,
                claim_token=claim.claim_token,
                outcome="accepted",
                now=NOW,
                safe_reason="smtp_bridge_accepted",
            )
            return "ok"
        except duckdb.TransactionException:
            return "conflict"
        finally:
            connection.close()

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: accept(), range(2)))
    assert "ok" in results
    check = duckdb.connect(str(path))
    assert check.execute(f"SELECT state FROM {ALERT_SCHEMA}.alert_outbox").fetchone() == (
        "accepted",
    )
    assert check.execute(
        f"SELECT count(*) FROM {ALERT_SCHEMA}.outbox_attempts WHERE phase='accepted'"
    ).fetchone() == (1,)
    assert check.execute(
        f"SELECT accepted_sequence FROM {ALERT_SCHEMA}.accepted_event_snapshots"
    ).fetchone() == (0,)
    check.close()


def test_manual_unknown_or_failed_retry_advances_sequence_once(tmp_path: Path) -> None:
    connection = _database(tmp_path / "manual.duckdb")
    original = connection.execute(f"SELECT outbox_id FROM {ALERT_SCHEMA}.alert_outbox").fetchone()[
        0
    ]
    connection.execute(
        f"""UPDATE {ALERT_SCHEMA}.alert_outbox SET state='delivery_unknown',
            attempt_count=1, safe_terminal_reason='smtp_acceptance_ambiguous'"""
    )
    next_id = retry_terminal_delivery(connection, outbox_id=original, now=NOW)
    assert retry_terminal_delivery(connection, outbox_id=original, now=NOW) == next_id
    assert connection.execute(
        f"SELECT sequence, state FROM {ALERT_SCHEMA}.alert_outbox ORDER BY sequence"
    ).fetchall() == [(0, "failed"), (1, "pending")]
    assert connection.execute(
        f"SELECT sequence, event_uid FROM {ALERT_SCHEMA}.event_intents"
    ).fetchone() == (1, "stable-target@local")
    connection.close()


def test_manual_retry_releases_a_newer_already_enqueued_event(tmp_path: Path) -> None:
    connection = _database(tmp_path / "advanced.duckdb")
    original = connection.execute(
        f"SELECT outbox_id FROM {ALERT_SCHEMA}.alert_outbox WHERE sequence=0"
    ).fetchone()[0]
    connection.execute(
        f"UPDATE {ALERT_SCHEMA}.alert_outbox SET state='delivery_unknown', attempt_count=1"
    )
    newer = _insert_pending(connection, sequence=1)
    assert retry_terminal_delivery(connection, outbox_id=original, now=NOW) == newer
    assert connection.execute(
        f"SELECT sequence, state FROM {ALERT_SCHEMA}.alert_outbox ORDER BY sequence"
    ).fetchall() == [(0, "failed"), (1, "pending")]
    connection.close()


def test_safe_operator_api_is_read_only_on_get_and_confirms_actions(tmp_path: Path) -> None:
    path = tmp_path / "api.duckdb"
    connection = _database(path)
    original = connection.execute(f"SELECT outbox_id FROM {ALERT_SCHEMA}.alert_outbox").fetchone()[
        0
    ]
    connection.execute(
        f"UPDATE {ALERT_SCHEMA}.alert_outbox SET state='delivery_unknown', attempt_count=1"
    )
    connection.close()
    client = TestClient(create_app(database_path=str(path), static_dir=tmp_path / "missing"))
    before = path.read_bytes()
    listed = client.get("/api/alert-deliveries")
    assert listed.status_code == 200
    assert path.read_bytes() == before
    serialized = listed.text
    assert listed.json()["deliveries"][0]["allowed_actions"] == [
        "mark_delivered",
        "mark_not_delivered_and_retry",
    ]
    assert listed.json()["deliveries"][0]["can_retry"] is True
    assert "payload_json" not in serialized and "recipient" not in serialized
    assert "sender@example" not in serialized and "bridge-secret" not in serialized
    assert client.post(f"/api/alert-deliveries/{original}/mark-delivered").status_code == 409
    accepted = client.post(f"/api/alert-deliveries/{original}/mark-delivered?confirm=true")
    assert accepted.status_code == 200 and accepted.json()["status"] == "accepted"

    inactive_path = tmp_path / "api-inactive.duckdb"
    inactive_connection = _database(inactive_path)
    inactive_id = _suppress_started_request(inactive_connection)
    inactive_connection.close()
    inactive_client = TestClient(
        create_app(database_path=str(inactive_path), static_dir=tmp_path / "missing-inactive")
    )
    inactive_row = inactive_client.get("/api/alert-deliveries").json()["deliveries"][0]
    assert inactive_row["allowed_actions"] == ["mark_delivered", "mark_not_delivered"]
    assert inactive_row["can_retry"] is False
    assert (
        inactive_client.post(f"/api/alert-deliveries/{inactive_id}/retry?confirm=true").status_code
        == 409
    )
    terminal = inactive_client.post(
        f"/api/alert-deliveries/{inactive_id}/mark-not-delivered?confirm=true"
    )
    assert terminal.status_code == 200 and terminal.json()["status"] == "not_delivered"


def test_live_verification_is_one_attempt_per_kind_and_records_no_configuration(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    connection = duckdb.connect(str(tmp_path / "verification.duckdb"))
    settings = _settings(tmp_path)
    monkeypatch.setattr(
        "databox.bird_alert_delivery._tls_context", lambda _: ssl.create_default_context()
    )
    sent: list[Any] = []

    def factory(*args: Any, **kwargs: Any) -> FakeSmtp:
        client = FakeSmtp([])
        original = client.send_message

        def capture(message: Any) -> dict[str, Any]:
            sent.append(message)
            return original(message)

        client.send_message = capture  # type: ignore[method-assign]
        return client

    assert (
        send_bounded_live_verification(
            connection, settings=settings, kind="test_email", now=NOW, smtp_factory=factory
        )
        == "accepted"
    )
    with pytest.raises(ValueError, match="already attempted"):
        send_bounded_live_verification(
            connection, settings=settings, kind="test_email", now=NOW, smtp_factory=factory
        )
    assert (
        send_bounded_live_verification(
            connection, settings=settings, kind="test_invitation", now=NOW, smtp_factory=factory
        )
        == "accepted"
    )
    assert len(sent) == 2
    assert any(part.get_content_type() == "text/calendar" for part in sent[1].walk())
    rows = connection.execute(
        f"SELECT kind, state, safe_reason FROM {ALERT_SCHEMA}.smtp_verification ORDER BY kind"
    ).fetchall()
    assert rows == [
        ("test_email", "accepted", "smtp_bridge_accepted"),
        ("test_invitation", "accepted", "smtp_bridge_accepted"),
    ]
    serialized = str(rows)
    assert "sender@example" not in serialized and "bridge-secret" not in serialized
    connection.close()


def test_cleanup_keeps_unresolved_unknown_then_removes_resolved_history(tmp_path: Path) -> None:
    connection = _database(tmp_path / "cleanup.duckdb")
    outbox_id = connection.execute(f"SELECT outbox_id FROM {ALERT_SCHEMA}.alert_outbox").fetchone()[
        0
    ]
    old = NOW - timedelta(days=91)
    connection.execute(
        f"""UPDATE {ALERT_SCHEMA}.alert_outbox SET state='delivery_unknown',
            updated_at=?, terminal_at=NULL""",
        [old.isoformat()],
    )
    assert cleanup_outbox_history(connection, now=NOW)["outbox_deleted"] == 0
    reconcile_unknown_as_delivered(connection, outbox_id=outbox_id, now=old)
    assert cleanup_outbox_history(connection, now=NOW)["outbox_deleted"] == 1
    assert connection.execute(f"SELECT count(*) FROM {ALERT_SCHEMA}.outbox_dedupe").fetchone() == (
        1,
    )
    connection.close()
