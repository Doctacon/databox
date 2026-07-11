from __future__ import annotations

import hashlib
import json
import socket
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, Literal

import duckdb
import pytest
from databox.agents.cloudflare_workers_ai import (
    CLOUDFLARE_WORKERS_AI_MODEL,
    CloudflareMalformedResponseError,
    WatchReportSynthesisGrounding,
    WatchReportSynthesisRequest,
    WatchReportSynthesisResult,
)
from databox.api import create_app
from databox.bird_alert_outbox import (
    claim_next_outbox,
    reconcile_unknown_as_delivered,
    record_attempt_outcome,
    start_send_attempt,
)
from databox.personal_collection import ensure_tables, request_watch_cancellation
from databox.watched_bird_evaluator import (
    ALERT_SCHEMA,
    cleanup_alert_history,
    ensure_alert_tables,
    evaluate_watched_birds,
    load_watch_report,
    load_watch_reports,
    select_morning_window,
)
from fastapi.testclient import TestClient

EVALUATION_AT = datetime(2026, 7, 10, 12, tzinfo=UTC)


class FakeWatchModel:
    model = CLOUDFLARE_WORKERS_AI_MODEL

    def __init__(self, *, fail: bool = False) -> None:
        self.fail = fail
        self.requests: list[WatchReportSynthesisRequest] = []

    def synthesize_watch_report(
        self, request: WatchReportSynthesisRequest
    ) -> WatchReportSynthesisResult:
        self.requests.append(request)
        if self.fail:
            raise CloudflareMalformedResponseError("synthetic invalid response")
        return WatchReportSynthesisResult(
            emphasis_ids=["freshness", "confirmed_location", "weather"],
            grounding=WatchReportSynthesisGrounding(
                species_code=request.species_code, fact_hash=request.fact_hash
            ),
        )


def weather(url: str, params: Any) -> dict[str, Any]:
    if "elevation" in url:
        return {"elevation": [330.0]}
    start = str(params["start_date"])
    return {
        "hourly_units": {
            "temperature_2m": "°C",
            "relative_humidity_2m": "%",
            "precipitation_probability": "%",
            "precipitation": "mm",
            "wind_speed_10m": "km/h",
            "wind_gusts_10m": "km/h",
        },
        "hourly": {
            "time": [f"{start}T05:00", f"{start}T06:00"],
            "temperature_2m": [20, 21],
            "relative_humidity_2m": [40, 38],
            "precipitation_probability": [0, 0],
            "precipitation": [0, 0],
            "weather_code": [0, 0],
            "wind_speed_10m": [5, 7],
            "wind_gusts_10m": [8, 10],
        },
    }


def _create_db(path: Path) -> duckdb.DuckDBPyConnection:
    connection = duckdb.connect(str(path))
    connection.execute("CREATE SCHEMA birding_agent")
    connection.execute(
        """CREATE TABLE birding_agent.arizona_species_catalog (
        species_code VARCHAR, common_name VARCHAR, scientific_name VARCHAR,
        taxonomic_category VARCHAR)"""
    )
    connection.execute(
        "INSERT INTO birding_agent.arizona_species_catalog VALUES "
        "('target1','Target Bird','Avis target','species'),"
        "('other1','Other Bird','Avis other','species')"
    )
    connection.execute("CREATE SCHEMA environmental_observations")
    connection.execute(
        """CREATE TABLE environmental_observations.fact_bird_observation (
        source_observation_id VARCHAR, species_code VARCHAR, region_code VARCHAR,
        location_id VARCHAR, location_name VARCHAR, latitude DOUBLE, longitude DOUBLE,
        observation_datetime TIMESTAMP, loaded_at TIMESTAMP,
        bird_observation_sk VARCHAR, dlt_id VARCHAR,
        is_valid BOOLEAN, is_reviewed BOOLEAN, is_location_private BOOLEAN)"""
    )
    ensure_tables(connection)
    connection.execute(
        """INSERT INTO birding_personal.watches VALUES
        ('target1','watch-1','generation-1',TRUE,'Synthetic Center',34.0,-112.0,
         'America/Phoenix',100,'2026-07-07T12:00:00+00:00',
         '2026-07-07T12:00:00+00:00','2026-07-07T12:00:00+00:00')"""
    )
    return connection


def _insert(
    connection: duckdb.DuckDBPyConnection,
    source_id: str | None,
    *,
    species: str = "target1",
    location_id: str | None = "L1",
    location_name: str = "Public Lake",
    latitude: float | None = 34.01,
    longitude: float | None = -112.0,
    observed: str = "2026-07-10 04:00:00",
    loaded: str = "2026-07-10 11:10:00",
    valid: bool = True,
    reviewed: bool = True,
    private: bool = False,
    suffix: str = "",
) -> None:
    connection.execute(
        "INSERT INTO environmental_observations.fact_bird_observation VALUES "
        "(?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        [
            source_id,
            species,
            "US-AZ",
            location_id,
            location_name,
            latitude,
            longitude,
            observed,
            loaded,
            f"bird-{source_id}-{suffix}",
            f"dlt-{source_id}-{suffix}",
            valid,
            reviewed,
            private,
        ],
    )


def _seed_mixed(connection: duckdb.DuckDBPyConnection) -> None:
    _insert(connection, "s1")
    _insert(connection, "s2", observed="2026-07-10 03:30:00")
    _insert(connection, "s2", observed="2026-07-10 03:30:00", suffix="duplicate")
    _insert(
        connection,
        "s3",
        location_id="L2",
        location_name="Second Public",
        latitude=34.03,
        observed="2026-07-10 03:00:00",
    )
    _insert(connection, "private", location_id="secret", location_name="Secret Home", private=True)
    _insert(connection, "invalid", valid=False)
    _insert(connection, "unreviewed", reviewed=False)
    _insert(connection, "missing", location_id=None)
    _insert(connection, "outside", latitude=36.5, longitude=-110.0)
    _insert(connection, "stale", observed="2026-07-08 00:00:00")
    _insert(connection, "pre", observed="2026-07-07 00:00:00")
    _insert(connection, "future", observed="2026-07-10 06:00:00")
    _insert(connection, "already", observed="2026-07-10 02:30:00")
    _insert(connection, "wrong", species="other1")
    _insert(connection, None)
    _insert(connection, "")
    _insert(connection, "x" * 257)
    _insert(connection, "bad-location-id", location_id="L" * 129)
    _insert(connection, "bad-location-name", location_name="N" * 301)
    _insert(connection, "bad-coordinate", latitude=float("nan"))
    ensure_alert_tables(connection)
    connection.execute(
        f"INSERT INTO {ALERT_SCHEMA}.processed_submissions VALUES "
        "('watch-1','already','target1','prior-run','2026-07-10T10:00:00+00:00')"
    )


@pytest.fixture
def db(tmp_path: Path) -> Path:
    path = tmp_path / "watch.duckdb"
    connection = _create_db(path)
    connection.close()
    return path


def test_exact_matching_clustering_morning_grounding_and_safe_api(
    db: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    connection = duckdb.connect(str(db))
    _seed_mixed(connection)
    model = FakeWatchModel()
    result = evaluate_watched_birds(
        connection,
        refresh_id="refresh-1",
        evaluation_at=EVALUATION_AT,
        weather_getter=weather,
        model_client=model,
    )
    assert result.status == "completed"
    assert (result.watches_evaluated, result.matches_created) == (1, 1)
    reports = load_watch_reports(connection)
    assert len(reports) == 1
    report = reports[0]
    assert report["confirmed_location_id"] == "L1"
    assert report["independent_submission_count"] == 2
    assert [item["location_id"] for item in report["clusters"]] == ["L1", "L2"]
    assert report["report_status"] == "ready"
    assert report["emphasis_ids"] == ["freshness", "confirmed_location", "weather"]
    assert report["weather"]["status"] == "available"
    morning_start = datetime.fromisoformat(report["morning_start"])
    morning_end = datetime.fromisoformat(report["morning_end"])
    assert morning_end - morning_start == timedelta(hours=2)
    assert morning_start.astimezone().date() >= EVALUATION_AT.date()
    supplied = model.requests[0]
    serialized_prompt = supplied.model_dump_json()
    assert "Synthetic Center" not in serialized_prompt
    assert "watch_center" not in serialized_prompt
    assert "Second Public" not in serialized_prompt
    assert supplied.confirmed_location.location_name == "Public Lake"
    assert supplied.confirmed_location.independent_submission_count == 2
    assert supplied.weather.forecast_summary.temperature_2m_avg == 20.5
    assert len(supplied.fact_hash) == 64
    diagnostics = json.loads(
        connection.execute(
            f"SELECT diagnostics_json FROM {ALERT_SCHEMA}.watch_evaluation_results"
        ).fetchone()[0]
    )
    assert diagnostics == {
        "already_processed": 1,
        "duplicate_source_row": 1,
        "future": 1,
        "invalid": 1,
        "invalid_coordinates": 1,
        "invalid_public_destination": 2,
        "invalid_submission_identity": 2,
        "missing_public_destination": 1,
        "missing_submission_identity": 1,
        "outside_radius": 1,
        "pre_activation": 1,
        "private": 1,
        "stale": 1,
        "unreviewed": 1,
    }
    assert (
        connection.execute(
            f"SELECT count(*) FROM {ALERT_SCHEMA}.processed_submissions WHERE first_run_id=?",
            [result.run_id],
        ).fetchone()[0]
        == 3
    )
    activation_state = connection.execute(
        f"""SELECT watch_id, activation_generation, last_run_id
            FROM {ALERT_SCHEMA}.watch_activation_state"""
    ).fetchone()
    assert activation_state == ("watch-1", "generation-1", result.run_id)
    event = connection.execute(
        f"SELECT event_uid, sequence, method, status FROM {ALERT_SCHEMA}.event_intents"
    ).fetchone()
    assert event[0].endswith("@local")
    assert event[1:] == (0, "REQUEST", "pending_request")
    connection.close()

    client = TestClient(create_app(database_path=str(db), static_dir=Path("missing")))
    before = hashlib.sha256(db.read_bytes()).hexdigest()

    def blocked(*args: Any, **kwargs: Any) -> None:
        raise AssertionError("GET must be network-free")

    monkeypatch.setattr(socket, "create_connection", blocked)
    run_response = client.get("/api/watch-evaluations")
    report_response = client.get(f"/api/watch-reports/{report['report_id']}")
    assert run_response.status_code == 200
    assert report_response.status_code == 200
    assert hashlib.sha256(db.read_bytes()).hexdigest() == before
    assert "Secret Home" not in report_response.text
    assert not {"watch_id", "activation_generation", "fact_hash", "model"} & set(
        report_response.json()
    )


def test_refresh_and_submission_replay_are_idempotent_and_new_evidence_updates_event(
    db: Path,
) -> None:
    connection = duckdb.connect(str(db))
    _insert(connection, "s1")
    first = evaluate_watched_birds(
        connection,
        refresh_id="same-refresh",
        evaluation_at=EVALUATION_AT,
        weather_getter=weather,
    )
    replay = evaluate_watched_birds(
        connection,
        refresh_id="same-refresh",
        evaluation_at=EVALUATION_AT,
        weather_getter=weather,
    )
    assert replay == first
    no_new = evaluate_watched_birds(
        connection,
        refresh_id="next-refresh",
        evaluation_at=EVALUATION_AT + timedelta(hours=1),
        weather_getter=weather,
    )
    assert no_new.matches_created == 0
    assert connection.execute(
        f"SELECT last_run_id FROM {ALERT_SCHEMA}.watch_activation_state"
    ).fetchone() == (no_new.run_id,)
    uid, sequence = connection.execute(
        f"SELECT event_uid, sequence FROM {ALERT_SCHEMA}.event_intents"
    ).fetchone()
    assert sequence == 0
    _insert(connection, "s2", observed="2026-07-10 05:30:00", loaded="2026-07-10 12:40:00")
    updated = evaluate_watched_birds(
        connection,
        refresh_id="new-evidence",
        evaluation_at=EVALUATION_AT + timedelta(hours=1),
        weather_getter=weather,
    )
    assert updated.matches_created == 1
    next_uid, next_sequence = connection.execute(
        f"SELECT event_uid, sequence FROM {ALERT_SCHEMA}.event_intents"
    ).fetchone()
    assert next_uid == uid
    assert next_sequence == 1
    assert (
        connection.execute(f"SELECT count(*) FROM {ALERT_SCHEMA}.match_reports").fetchone()[0] == 2
    )
    connection.close()


def test_event_activation_generation_supersession_and_natural_expiry(db: Path) -> None:
    connection = duckdb.connect(str(db))
    _insert(connection, "s1")
    first = evaluate_watched_birds(
        connection,
        refresh_id="generation-one",
        evaluation_at=EVALUATION_AT,
        weather_getter=weather,
    )
    first_report_id = connection.execute(
        f"SELECT report_id FROM {ALERT_SCHEMA}.match_reports WHERE run_id=?", [first.run_id]
    ).fetchone()[0]
    connection.execute(
        f"""UPDATE {ALERT_SCHEMA}.event_intents
            SET status='accepted', last_accepted_sequence=sequence,
                last_accepted_horizon_end=event_horizon_end,
                last_accepted_at='2026-07-10T12:05:00+00:00'"""
    )
    connection.execute(
        """UPDATE birding_personal.watches
           SET activation_generation='generation-2',
               activated_at='2026-07-10T12:01:00+00:00'"""
    )
    _insert(connection, "s2", observed="2026-07-10 05:30:00", loaded="2026-07-10 12:40:00")
    second = evaluate_watched_birds(
        connection,
        refresh_id="generation-two",
        evaluation_at=EVALUATION_AT + timedelta(hours=1),
        weather_getter=weather,
    )
    assert second.matches_created == 1
    event = connection.execute(
        f"""SELECT activation_generation, sequence, status, event_horizon_end
            FROM {ALERT_SCHEMA}.event_intents"""
    ).fetchone()
    assert event[:3] == ("generation-2", 1, "pending_request")
    assert (
        connection.execute(
            f"SELECT resolved_at FROM {ALERT_SCHEMA}.match_reports WHERE report_id=?",
            [first_report_id],
        ).fetchone()[0]
        is not None
    )
    assert load_watch_report(connection, str(first_report_id))["event_uid"] is None

    request_watch_cancellation(
        connection,
        "target1",
        reason="pause",
        watch_id="watch-1",
        activation_generation="generation-1",
    )
    stale = evaluate_watched_birds(
        connection,
        refresh_id="stale-cancellation",
        evaluation_at=EVALUATION_AT + timedelta(hours=2),
        weather_getter=weather,
    )
    assert stale.cancellations_resolved == 1
    assert connection.execute(
        f"SELECT status, sequence FROM {ALERT_SCHEMA}.event_intents"
    ).fetchone() == ("pending_request", 1)

    horizon = datetime.fromisoformat(str(event[3]))
    expired = evaluate_watched_birds(
        connection,
        refresh_id="natural-expiry",
        evaluation_at=horizon + timedelta(seconds=1),
        weather_getter=weather,
    )
    assert expired.matches_created == 0
    assert connection.execute(
        f"""SELECT status, report_id, event_horizon_end, location_name
            FROM {ALERT_SCHEMA}.event_intents"""
    ).fetchone() == ("expired", None, None, None)
    assert connection.execute(
        f"""SELECT state, payload_json FROM {ALERT_SCHEMA}.alert_outbox
            ORDER BY sequence DESC LIMIT 1"""
    ).fetchone() == ("cancelled", "{}")
    connection.close()


def test_model_failure_persists_deterministic_degraded_report(db: Path) -> None:
    connection = duckdb.connect(str(db))
    _insert(connection, "s1")
    result = evaluate_watched_birds(
        connection,
        refresh_id="degraded",
        evaluation_at=EVALUATION_AT,
        weather_getter=weather,
        model_client=FakeWatchModel(fail=True),
    )
    assert result.matches_created == 1
    report = load_watch_reports(connection)[0]
    assert report["report_status"] == "deterministic_degraded"
    assert any("enrichment was unavailable" in item for item in report["caveats"])
    assert connection.execute(
        f"SELECT model_status, model FROM {ALERT_SCHEMA}.model_traces"
    ).fetchone() == ("degraded", None)
    connection.close()


def test_match_transaction_rolls_back_and_same_refresh_resumes(
    db: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import databox.watched_bird_evaluator as module

    connection = duckdb.connect(str(db))
    _insert(connection, "s1")
    original = module._persist_match

    def fail_after_insert(*args: Any, **kwargs: Any) -> str:
        original(*args, **kwargs)
        raise RuntimeError("synthetic crash")

    monkeypatch.setattr(module, "_persist_match", fail_after_insert)
    with pytest.raises(RuntimeError, match="synthetic crash"):
        evaluate_watched_birds(
            connection,
            refresh_id="recoverable",
            evaluation_at=EVALUATION_AT,
            weather_getter=weather,
        )
    assert (
        connection.execute(f"SELECT count(*) FROM {ALERT_SCHEMA}.match_reports").fetchone()[0] == 0
    )
    assert connection.execute(
        f"SELECT status, safe_error_code FROM {ALERT_SCHEMA}.evaluation_runs"
    ).fetchone() == ("failed", "evaluation_failed")
    monkeypatch.setattr(module, "_persist_match", original)
    recovered = evaluate_watched_birds(
        connection,
        refresh_id="recoverable",
        evaluation_at=EVALUATION_AT + timedelta(minutes=1),
        weather_getter=weather,
    )
    assert recovered.status == "completed"
    assert recovered.matches_created == 1
    assert recovered.started_at == EVALUATION_AT.isoformat()
    connection.close()


@pytest.mark.parametrize("reason", ["pause", "delete"])
def test_pause_or_delete_suppresses_pending_request_without_sequence_or_replay(
    db: Path, reason: Literal["pause", "delete"]
) -> None:
    connection = duckdb.connect(str(db))
    _insert(connection, "s1")
    created = evaluate_watched_birds(
        connection,
        refresh_id=f"pending-{reason}",
        evaluation_at=EVALUATION_AT,
        weather_getter=weather,
    )
    report_id = connection.execute(
        f"SELECT report_id FROM {ALERT_SCHEMA}.event_intents"
    ).fetchone()[0]
    request_watch_cancellation(
        connection,
        "target1",
        reason=reason,
        watch_id="watch-1",
        activation_generation="generation-1",
    )
    if reason == "pause":
        connection.execute("UPDATE birding_personal.watches SET active=FALSE")
    else:
        connection.execute("DELETE FROM birding_personal.watches")
    resolved = evaluate_watched_birds(
        connection,
        refresh_id=f"suppress-{reason}",
        evaluation_at=EVALUATION_AT + timedelta(hours=1),
        weather_getter=weather,
    )
    assert resolved.cancellations_resolved == 1
    assert connection.execute(
        f"""SELECT sequence, method, status, report_id, morning_start,
                   event_horizon_end, location_name
            FROM {ALERT_SCHEMA}.event_intents"""
    ).fetchone() == (0, "REQUEST", "suppressed", None, None, None, None)
    assert connection.execute(
        f"SELECT outcome FROM {ALERT_SCHEMA}.cancellation_resolutions"
    ).fetchone() == ("request_suppressed",)
    assert connection.execute(
        f"SELECT resolved_at IS NOT NULL FROM {ALERT_SCHEMA}.match_reports WHERE report_id=?",
        [report_id],
    ).fetchone() == (True,)
    assert connection.execute(
        f"""SELECT count(*) FROM {ALERT_SCHEMA}.event_intents
            WHERE status IN ('pending_request','pending_cancel')
              AND report_id IS NOT NULL AND event_horizon_end IS NOT NULL"""
    ).fetchone() == (0,)
    assert connection.execute(
        f"SELECT state, payload_json FROM {ALERT_SCHEMA}.alert_outbox"
    ).fetchone() == ("cancelled", "{}")

    replay = evaluate_watched_birds(
        connection,
        refresh_id=f"suppress-{reason}",
        evaluation_at=EVALUATION_AT + timedelta(hours=2),
        weather_getter=weather,
    )
    assert replay == resolved
    assert replay.run_id != created.run_id
    assert connection.execute(
        f"SELECT sequence, status FROM {ALERT_SCHEMA}.event_intents"
    ).fetchone() == (0, "suppressed")
    connection.close()


def test_pause_race_before_match_commit_creates_no_sendable_event(db: Path) -> None:
    connection = duckdb.connect(str(db))
    _insert(connection, "s1")
    paused = False

    def racing_weather(url: str, params: Any) -> dict[str, Any]:
        nonlocal paused
        if not paused:
            paused = True
            request_watch_cancellation(
                connection,
                "target1",
                reason="pause",
                watch_id="watch-1",
                activation_generation="generation-1",
            )
            connection.execute("UPDATE birding_personal.watches SET active=FALSE")
        return weather(url, params)

    raced = evaluate_watched_birds(
        connection,
        refresh_id="pause-race",
        evaluation_at=EVALUATION_AT,
        weather_getter=racing_weather,
    )
    assert raced.matches_created == 0
    assert connection.execute(
        f"SELECT decision FROM {ALERT_SCHEMA}.watch_evaluation_results"
    ).fetchone() == ("activation_changed",)
    assert connection.execute(f"SELECT count(*) FROM {ALERT_SCHEMA}.event_intents").fetchone() == (
        0,
    )
    assert connection.execute(f"SELECT count(*) FROM {ALERT_SCHEMA}.match_reports").fetchone() == (
        0,
    )
    assert connection.execute(
        """SELECT count(*) FROM information_schema.tables
           WHERE table_schema='birding_alerts' AND table_name='alert_outbox'"""
    ).fetchone() == (0,)

    consumed = evaluate_watched_birds(
        connection,
        refresh_id="pause-race-resolution",
        evaluation_at=EVALUATION_AT + timedelta(hours=1),
        weather_getter=weather,
    )
    assert consumed.cancellations_resolved == 1
    assert connection.execute(
        f"SELECT outcome FROM {ALERT_SCHEMA}.cancellation_resolutions"
    ).fetchone() == ("no_accepted_active_event",)
    connection.close()


def test_pause_and_delete_handoffs_cancel_only_accepted_unexpired_events(db: Path) -> None:
    connection = duckdb.connect(str(db))
    _insert(connection, "s1")
    evaluate_watched_birds(
        connection,
        refresh_id="create-event",
        evaluation_at=EVALUATION_AT,
        weather_getter=weather,
    )
    event = connection.execute(
        f"SELECT event_uid, sequence, event_horizon_end FROM {ALERT_SCHEMA}.event_intents"
    ).fetchone()
    claim = claim_next_outbox(connection, now=EVALUATION_AT)
    assert claim is not None
    start_send_attempt(
        connection,
        outbox_id=claim.outbox_id,
        claim_token=claim.claim_token,
        now=EVALUATION_AT,
    )
    record_attempt_outcome(
        connection,
        outbox_id=claim.outbox_id,
        claim_token=claim.claim_token,
        outcome="accepted",
        now=EVALUATION_AT + timedelta(minutes=5),
        safe_reason="smtp_bridge_accepted",
    )
    request_watch_cancellation(
        connection,
        "target1",
        reason="pause",
        watch_id="watch-1",
        activation_generation="generation-1",
    )
    connection.execute("UPDATE birding_personal.watches SET active=FALSE")
    result = evaluate_watched_birds(
        connection,
        refresh_id="cancel-event",
        evaluation_at=EVALUATION_AT + timedelta(hours=1),
        weather_getter=weather,
    )
    assert result.cancellations_resolved == 1
    cancelled = connection.execute(
        f"SELECT event_uid, sequence, method, status FROM {ALERT_SCHEMA}.event_intents"
    ).fetchone()
    assert cancelled == (event[0], event[1] + 1, "CANCEL", "pending_cancel")
    assert connection.execute(
        f"""SELECT method, sequence, state FROM {ALERT_SCHEMA}.alert_outbox
            ORDER BY sequence"""
    ).fetchall() == [("REQUEST", 0, "accepted"), ("CANCEL", 1, "pending")]
    assert (
        connection.execute(
            "SELECT count(*) FROM birding_personal.watch_cancellation_requests"
        ).fetchone()[0]
        == 0
    )

    request_watch_cancellation(
        connection,
        "target1",
        reason="delete",
        watch_id="watch-1",
        activation_generation="generation-1",
    )
    already_cancelling = evaluate_watched_birds(
        connection,
        refresh_id="already-cancelling",
        evaluation_at=EVALUATION_AT + timedelta(hours=2),
        weather_getter=weather,
    )
    assert already_cancelling.cancellations_resolved == 1
    assert connection.execute(
        f"SELECT sequence, method, status FROM {ALERT_SCHEMA}.event_intents"
    ).fetchone() == (event[1] + 1, "CANCEL", "pending_cancel")
    outcomes = connection.execute(
        f"SELECT outcome FROM {ALERT_SCHEMA}.cancellation_resolutions ORDER BY resolved_at"
    ).fetchall()
    assert outcomes == [("cancel_intent",), ("no_accepted_active_event",)]
    connection.close()


def test_unknown_older_request_acceptance_survives_newer_event_then_pause_cancels_snapshot(
    db: Path,
) -> None:
    connection = duckdb.connect(str(db))
    _insert(connection, "s1", location_id="L1", location_name="First Public")
    evaluate_watched_birds(
        connection,
        refresh_id="unknown-seq0",
        evaluation_at=EVALUATION_AT,
        weather_getter=weather,
    )
    first = claim_next_outbox(connection, now=EVALUATION_AT)
    assert first is not None
    start_send_attempt(
        connection,
        outbox_id=first.outbox_id,
        claim_token=first.claim_token,
        now=EVALUATION_AT,
    )
    record_attempt_outcome(
        connection,
        outbox_id=first.outbox_id,
        claim_token=first.claim_token,
        outcome="delivery_unknown",
        now=EVALUATION_AT + timedelta(minutes=1),
        safe_reason="smtp_acceptance_ambiguous",
    )
    _insert(
        connection,
        "s2",
        location_id="L2",
        location_name="Newer Public",
        latitude=34.02,
        observed="2026-07-10 05:30:00",
        loaded="2026-07-10 12:30:00",
    )
    evaluate_watched_birds(
        connection,
        refresh_id="pending-seq1",
        evaluation_at=EVALUATION_AT + timedelta(minutes=30),
        weather_getter=weather,
    )
    assert connection.execute(
        f"SELECT sequence, status, location_id FROM {ALERT_SCHEMA}.event_intents"
    ).fetchone() == (1, "pending_request", "L2")
    reconcile_unknown_as_delivered(
        connection, outbox_id=first.outbox_id, now=EVALUATION_AT + timedelta(minutes=31)
    )
    assert connection.execute(
        f"""SELECT sequence, status, last_accepted_sequence
            FROM {ALERT_SCHEMA}.event_intents"""
    ).fetchone() == (1, "pending_request", 0)
    request_watch_cancellation(
        connection,
        "target1",
        reason="pause",
        watch_id="watch-1",
        activation_generation="generation-1",
    )
    connection.execute("UPDATE birding_personal.watches SET active=FALSE")
    evaluate_watched_birds(
        connection,
        refresh_id="pause-after-unknown-acceptance",
        evaluation_at=EVALUATION_AT + timedelta(hours=1),
        weather_getter=weather,
    )
    assert connection.execute(
        f"""SELECT sequence, method, status, location_id
            FROM {ALERT_SCHEMA}.event_intents"""
    ).fetchone() == (2, "CANCEL", "pending_cancel", "L1")
    cancel = connection.execute(
        f"""SELECT payload_json FROM {ALERT_SCHEMA}.alert_outbox
            WHERE method='CANCEL' AND sequence=2"""
    ).fetchone()[0]
    assert '"location_id":"L1"' in cancel and '"event_uid"' in cancel
    assert connection.execute(
        f"SELECT count(*) FROM {ALERT_SCHEMA}.accepted_event_snapshots"
    ).fetchone() == (1,)
    connection.close()


def test_automatic_older_acceptance_propagates_then_pause_cancels_accepted_snapshot(
    db: Path,
) -> None:
    connection = duckdb.connect(str(db))
    _insert(connection, "s1", location_id="L1", location_name="First Public")
    evaluate_watched_birds(
        connection,
        refresh_id="automatic-seq0",
        evaluation_at=EVALUATION_AT,
        weather_getter=weather,
    )
    first = claim_next_outbox(connection, now=EVALUATION_AT)
    assert first is not None
    start_send_attempt(
        connection,
        outbox_id=first.outbox_id,
        claim_token=first.claim_token,
        now=EVALUATION_AT,
    )
    _insert(
        connection,
        "s2",
        location_id="L2",
        location_name="Newer Public",
        latitude=34.02,
        observed="2026-07-10 05:30:00",
        loaded="2026-07-10 12:30:00",
    )
    evaluate_watched_birds(
        connection,
        refresh_id="automatic-pending-seq1",
        evaluation_at=EVALUATION_AT + timedelta(minutes=30),
        weather_getter=weather,
    )
    record_attempt_outcome(
        connection,
        outbox_id=first.outbox_id,
        claim_token=first.claim_token,
        outcome="accepted",
        now=EVALUATION_AT + timedelta(minutes=31),
        safe_reason="smtp_bridge_accepted",
    )
    record_attempt_outcome(
        connection,
        outbox_id=first.outbox_id,
        claim_token=first.claim_token,
        outcome="accepted",
        now=EVALUATION_AT + timedelta(minutes=31),
        safe_reason="smtp_bridge_accepted",
    )
    assert connection.execute(
        f"""SELECT sequence, status, location_id, last_accepted_sequence
            FROM {ALERT_SCHEMA}.event_intents"""
    ).fetchone() == (1, "pending_request", "L2", 0)
    request_watch_cancellation(
        connection,
        "target1",
        reason="delete",
        watch_id="watch-1",
        activation_generation="generation-1",
    )
    connection.execute("UPDATE birding_personal.watches SET active=FALSE")
    evaluate_watched_birds(
        connection,
        refresh_id="automatic-pause-after-acceptance",
        evaluation_at=EVALUATION_AT + timedelta(hours=1),
        weather_getter=weather,
    )
    assert connection.execute(
        f"""SELECT sequence, method, status, location_id
            FROM {ALERT_SCHEMA}.event_intents"""
    ).fetchone() == (2, "CANCEL", "pending_cancel", "L1")
    assert connection.execute(
        f"""SELECT count(*) FROM {ALERT_SCHEMA}.outbox_attempts
            WHERE outbox_id=? AND phase='accepted'""",
        [first.outbox_id],
    ).fetchone() == (1,)
    connection.close()


def test_read_api_rejects_malformed_persisted_rows_without_leaking_values(db: Path) -> None:
    connection = duckdb.connect(str(db))
    _insert(connection, "s1")
    evaluate_watched_birds(
        connection,
        refresh_id="api-shape",
        evaluation_at=EVALUATION_AT,
        weather_getter=weather,
    )
    report_id = str(
        connection.execute(f"SELECT report_id FROM {ALERT_SCHEMA}.match_reports").fetchone()[0]
    )
    connection.close()
    client = TestClient(create_app(database_path=str(db), static_dir=Path("missing")))
    assert client.get("/api/watch-reports/not-valid").status_code == 400
    assert client.get("/api/watch-reports/watch_report_" + "0" * 32).status_code == 404

    connection = duckdb.connect(str(db))
    connection.execute(
        f'UPDATE {ALERT_SCHEMA}.match_reports SET clusters_json=\'{{"private":"hidden"}}\''
    )
    connection.close()
    malformed = client.get(f"/api/watch-reports/{report_id}")
    assert malformed.status_code == 503
    assert "hidden" not in malformed.text
    connection = duckdb.connect(str(db))
    connection.execute(f"UPDATE {ALERT_SCHEMA}.evaluation_runs SET started_at='not-a-timestamp'")
    connection.close()
    bad_run = client.get("/api/watch-evaluations")
    assert bad_run.status_code == 503
    assert "not-a-timestamp" not in bad_run.text


@pytest.mark.parametrize("malformation", ["duplicate_clusters", "oversized_caveat"])
def test_read_api_rejects_duplicate_clusters_and_unbounded_caveats(
    db: Path, malformation: str
) -> None:
    connection = duckdb.connect(str(db))
    _insert(connection, "s1")
    evaluate_watched_birds(
        connection,
        refresh_id=f"malformed-{malformation}",
        evaluation_at=EVALUATION_AT,
        weather_getter=weather,
    )
    report_id, clusters_json = connection.execute(
        f"SELECT report_id, clusters_json FROM {ALERT_SCHEMA}.match_reports"
    ).fetchone()
    if malformation == "duplicate_clusters":
        clusters = json.loads(str(clusters_json))
        connection.execute(
            f"UPDATE {ALERT_SCHEMA}.match_reports SET clusters_json=?",
            [json.dumps([clusters[0], clusters[0]])],
        )
    else:
        connection.execute(
            f"UPDATE {ALERT_SCHEMA}.match_reports SET caveats_json=?",
            [json.dumps(["private-marker-" + "x" * 501])],
        )
    connection.close()
    client = TestClient(create_app(database_path=str(db), static_dir=Path("missing")))
    response = client.get(f"/api/watch-reports/{report_id}")
    assert response.status_code == 503
    assert "private-marker" not in response.text


def test_sunrise_is_earliest_future_window_and_retention_preserves_novelty(db: Path) -> None:
    start, end, horizon = select_morning_window(EVALUATION_AT, 34.0, -112.0)
    assert start > EVALUATION_AT
    assert end - start == timedelta(hours=2)
    assert end <= horizon

    connection = duckdb.connect(str(db))
    _insert(connection, "s1")
    evaluate_watched_birds(
        connection,
        refresh_id="old-run",
        evaluation_at=EVALUATION_AT,
        weather_getter=weather,
    )
    connection.execute(
        f"""UPDATE {ALERT_SCHEMA}.event_intents
            SET report_id=NULL, source_report_id=NULL, status='expired',
                updated_at='2026-01-01T00:00:00+00:00'"""
    )
    connection.execute(
        f"UPDATE {ALERT_SCHEMA}.match_reports SET resolved_at='2026-01-01T00:00:00+00:00'"
    )
    connection.execute(
        f"""INSERT INTO {ALERT_SCHEMA}.cancellation_resolutions VALUES
            ('old-cancel', 'old-run', 'target1', 'no_accepted_active_event',
             '2026-01-01T00:00:00+00:00')"""
    )
    connection.execute(
        f"""UPDATE {ALERT_SCHEMA}.evaluation_runs
        SET completed_at='2026-01-01T00:00:00+00:00'"""
    )
    deleted = cleanup_alert_history(connection, now=EVALUATION_AT)
    assert deleted == {"reports_deleted": 1, "runs_deleted": 1}
    assert (
        connection.execute(f"SELECT count(*) FROM {ALERT_SCHEMA}.processed_submissions").fetchone()[
            0
        ]
        == 1
    )
    assert connection.execute(
        f"SELECT count(*) FROM {ALERT_SCHEMA}.cancellation_resolutions"
    ).fetchone() == (0,)
    assert connection.execute(
        f"SELECT event_uid IS NOT NULL, sequence, location_name FROM {ALERT_SCHEMA}.event_intents"
    ).fetchone() == (True, 0, None)
    connection.close()
