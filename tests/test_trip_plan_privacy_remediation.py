"""Atomic offline remediation for Trip Planner eBird evidence eligibility."""

from __future__ import annotations

import socket
from pathlib import Path

import duckdb
import pytest
from databox.agent_tools.persistence import ensure_birding_agent_persistence_tables
from databox.agent_tools.trip_plan_privacy_remediation import (
    inspect_trip_plan_privacy,
    remediate_trip_plan_privacy,
)


def _insert_minimal_plan(connection: duckdb.DuckDBPyConnection, plan_id: str) -> None:
    connection.execute(
        """INSERT INTO birding_agent.trip_plans (
        trip_plan_id, requested_location, window_start, window_end,
        plan_status, caveats_json, created_at, updated_at
        ) VALUES (?, 'Arizona', '2026-07-10T06:00:00', '2026-07-10T08:00:00',
                  'completed', '[]', '2026-07-10T00:00:00', '2026-07-10T00:00:00')""",
        [plan_id],
    )
    connection.execute(
        """INSERT INTO birding_agent.trip_plan_recommendations (
        recommendation_id, trip_plan_id, recommendation_group, rank_order,
        caveats_json, created_at
        ) VALUES (?, ?, 'high_likelihood', 1, '[]', '2026-07-10T00:00:00')""",
        [f"recommendation-{plan_id}", plan_id],
    )
    connection.execute(
        """INSERT INTO birding_agent.trip_plan_tool_traces (
        tool_trace_id, trip_plan_id, step_order, tool_name, tool_status,
        input_json, output_summary_json, caveats_json
        ) VALUES (?, ?, 1, 'lookup_recent_observation_evidence', 'ok', '{}', '{}', '[]')""",
        [f"trace-{plan_id}", plan_id],
    )


def _insert_ebird_evidence(
    connection: duckdb.DuckDBPyConnection,
    *,
    evidence_id: str,
    plan_id: str,
    source_record_id: str | None,
) -> None:
    connection.execute(
        """INSERT INTO birding_agent.trip_plan_evidence (
        evidence_id, trip_plan_id, source, source_table, source_record_id,
        evidence_type, status, summary_json, payload_json, caveats_json
        ) VALUES (?, ?, 'ebird', 'environmental_observations.fact_bird_observation', ?,
                  'recent_observation', 'available', '{}', '{}', '[]')""",
        [evidence_id, plan_id, source_record_id],
    )


def _database(tmp_path: Path) -> Path:
    path = tmp_path / "privacy-remediation.duckdb"
    connection = duckdb.connect(str(path))
    connection.execute("CREATE SCHEMA environmental_observations")
    connection.execute(
        """CREATE TABLE environmental_observations.fact_bird_observation (
        source_observation_id TEXT, is_valid BOOLEAN, is_reviewed BOOLEAN,
        is_location_private BOOLEAN)"""
    )
    connection.executemany(
        "INSERT INTO environmental_observations.fact_bird_observation VALUES (?, ?, ?, ?)",
        [
            ("eligible", True, True, False),
            ("private", True, True, True),
            ("invalid", False, True, False),
            ("unreviewed", True, False, False),
        ],
    )
    ensure_birding_agent_persistence_tables(connection)
    for plan_id in ("keep", "tainted-private", "tainted-quality"):
        _insert_minimal_plan(connection, plan_id)
    evidence = [
        ("e-keep", "keep", "eligible"),
        ("e-private", "tainted-private", "private"),
        ("e-invalid", "tainted-quality", "invalid"),
        ("e-unreviewed", "tainted-quality", "unreviewed"),
    ]
    for evidence_id, plan_id, source_id in evidence:
        _insert_ebird_evidence(
            connection,
            evidence_id=evidence_id,
            plan_id=plan_id,
            source_record_id=source_id,
        )
    connection.close()
    return path


def _counts(connection: duckdb.DuckDBPyConnection) -> dict[str, int]:
    return {
        table: int(connection.execute(f"SELECT COUNT(*) FROM birding_agent.{table}").fetchone()[0])
        for table in (
            "trip_plans",
            "trip_plan_recommendations",
            "trip_plan_evidence",
            "trip_plan_tool_traces",
        )
    }


def test_remediation_deletes_complete_tainted_aggregates_and_is_idempotent(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = _database(tmp_path)

    def forbidden(*_: object, **__: object) -> object:
        raise AssertionError("privacy remediation must remain offline")

    monkeypatch.setattr(socket, "create_connection", forbidden)
    connection = duckdb.connect(str(path))
    before = inspect_trip_plan_privacy(connection)
    assert before.tainted_plans == 2
    assert before.remaining_plans == 3
    assert before.unmatched_source_records == 0

    result = remediate_trip_plan_privacy(connection)
    assert result.to_dict() == {
        "tainted_plans": 2,
        "deleted_plans": 2,
        "deleted_recommendations": 2,
        "deleted_evidence": 3,
        "deleted_tool_traces": 2,
        "remaining_plans": 1,
        "unmatched_source_records": 0,
    }
    assert _counts(connection) == {
        "trip_plans": 1,
        "trip_plan_recommendations": 1,
        "trip_plan_evidence": 1,
        "trip_plan_tool_traces": 1,
    }
    assert connection.execute("SELECT trip_plan_id FROM birding_agent.trip_plans").fetchone() == (
        "keep",
    )
    assert remediate_trip_plan_privacy(connection).deleted_plans == 0
    connection.close()


def test_remediation_rolls_back_all_aggregate_deletes(tmp_path: Path) -> None:
    connection = duckdb.connect(str(_database(tmp_path)))
    before = _counts(connection)

    def fail(_: duckdb.DuckDBPyConnection) -> None:
        raise RuntimeError("injected failure")

    with pytest.raises(RuntimeError, match="injected failure"):
        remediate_trip_plan_privacy(connection, before_commit=fail)
    assert _counts(connection) == before
    assert inspect_trip_plan_privacy(connection).tainted_plans == 2
    connection.close()


def test_missing_authority_taints_plan_and_preserves_unrelated_orphan(tmp_path: Path) -> None:
    connection = duckdb.connect(str(_database(tmp_path)))
    _insert_ebird_evidence(
        connection,
        evidence_id="unmatched",
        plan_id="keep",
        source_record_id="missing-authority",
    )
    connection.execute(
        """INSERT INTO birding_agent.trip_plan_tool_traces (
        tool_trace_id, trip_plan_id, step_order, tool_name, tool_status,
        input_json, output_summary_json, caveats_json
        ) VALUES ('orphan', 'missing-plan', 1, 'tool', 'ok', '{}', '{}', '[]')"""
    )
    before = inspect_trip_plan_privacy(connection)
    assert before.unmatched_source_records == 1
    assert before.tainted_plans == 3
    result = remediate_trip_plan_privacy(connection)
    assert result.deleted_plans == 3
    assert result.unmatched_source_records == 1
    assert connection.execute(
        "SELECT COUNT(*) FROM birding_agent.trip_plan_tool_traces WHERE tool_trace_id='orphan'"
    ).fetchone() == (1,)
    assert remediate_trip_plan_privacy(connection).deleted_plans == 0
    connection.close()


def test_null_blank_missing_and_duplicate_identities_taint_rollback_and_delete(
    tmp_path: Path,
) -> None:
    connection = duckdb.connect(str(_database(tmp_path)))
    connection.executemany(
        "INSERT INTO environmental_observations.fact_bird_observation VALUES (?, ?, ?, ?)",
        [("ambiguous", True, True, False), ("ambiguous", True, True, False)],
    )
    malformed = [
        ("null-identity", None),
        ("blank-identity", "   "),
        ("missing-identity", "not-authoritative"),
        ("duplicate-identity", "ambiguous"),
    ]
    for plan_id, source_record_id in malformed:
        _insert_minimal_plan(connection, plan_id)
        _insert_ebird_evidence(
            connection,
            evidence_id=f"e-{plan_id}",
            plan_id=plan_id,
            source_record_id=source_record_id,
        )

    inspection = inspect_trip_plan_privacy(connection)
    assert inspection.unmatched_source_records == 4
    assert inspection.tainted_plans == 6
    assert inspection.remaining_plans == 7
    before = _counts(connection)

    def fail(_: duckdb.DuckDBPyConnection) -> None:
        raise RuntimeError("malformed identity rollback")

    with pytest.raises(RuntimeError, match="malformed identity rollback"):
        remediate_trip_plan_privacy(connection, before_commit=fail)
    assert _counts(connection) == before
    assert inspect_trip_plan_privacy(connection).unmatched_source_records == 4

    result = remediate_trip_plan_privacy(connection)
    assert result.unmatched_source_records == 4
    assert result.deleted_plans == 6
    assert result.remaining_plans == 1
    rerun = remediate_trip_plan_privacy(connection)
    assert rerun.deleted_plans == rerun.unmatched_source_records == 0
    connection.close()


def test_remediation_rolls_back_if_any_tainted_child_survives(tmp_path: Path) -> None:
    connection = duckdb.connect(str(_database(tmp_path)))
    before = _counts(connection)

    def inject_partial_row(db: duckdb.DuckDBPyConnection) -> None:
        db.execute(
            """INSERT INTO birding_agent.trip_plan_tool_traces (
            tool_trace_id, trip_plan_id, step_order, tool_name, tool_status,
            input_json, output_summary_json, caveats_json
            ) VALUES ('injected-orphan', 'tainted-private', 1, 'tool', 'ok', '{}', '{}', '[]')"""
        )

    with pytest.raises(ValueError, match="partial tainted"):
        remediate_trip_plan_privacy(connection, before_commit=inject_partial_row)
    assert _counts(connection) == before
    assert inspect_trip_plan_privacy(connection).tainted_plans == 2
    connection.close()
