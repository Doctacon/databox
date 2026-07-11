"""Offline atomic remediation for saved plans influenced by ineligible eBird rows."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import asdict, dataclass
from typing import Any

import duckdb

_SCHEMA = "birding_agent"
_TABLES = (
    "trip_plans",
    "trip_plan_recommendations",
    "trip_plan_evidence",
    "trip_plan_tool_traces",
)


@dataclass(frozen=True)
class RemediationResult:
    tainted_plans: int
    deleted_plans: int
    deleted_recommendations: int
    deleted_evidence: int
    deleted_tool_traces: int
    remaining_plans: int
    unmatched_source_records: int

    def to_dict(self) -> dict[str, int]:
        return asdict(self)


def _table_presence(connection: duckdb.DuckDBPyConnection) -> set[str]:
    rows = connection.execute(
        """SELECT table_name FROM information_schema.tables
        WHERE table_schema = ? AND table_name IN (?, ?, ?, ?)""",
        [_SCHEMA, *_TABLES],
    ).fetchall()
    return {str(row[0]) for row in rows}


def _require_complete_contract(connection: duckdb.DuckDBPyConnection) -> bool:
    present = _table_presence(connection)
    if not present:
        return False
    if present != set(_TABLES):
        raise ValueError("trip plan persistence contract is incomplete")
    return True


def _unmatched_count(connection: duckdb.DuckDBPyConnection) -> int:
    row = connection.execute(
        """
        WITH authority_counts AS (
          SELECT source_observation_id, COUNT(*) AS identity_count
          FROM environmental_observations.fact_bird_observation
          WHERE source_observation_id IS NOT NULL
          GROUP BY source_observation_id
        ), unresolved AS (
          SELECT CASE
            WHEN persisted.source_record_id IS NULL THEN 'null:'
            WHEN TRIM(persisted.source_record_id) = '' THEN 'blank:'
            WHEN COALESCE(authority.identity_count, 0) = 0
              THEN 'missing:' || persisted.source_record_id
            WHEN authority.identity_count <> 1
              THEN 'ambiguous:' || persisted.source_record_id
          END AS unresolved_identity
          FROM birding_agent.trip_plan_evidence AS persisted
          LEFT JOIN authority_counts AS authority
            ON authority.source_observation_id = persisted.source_record_id
          WHERE persisted.source = 'ebird'
            AND persisted.evidence_type = 'recent_observation'
        )
        SELECT COUNT(DISTINCT unresolved_identity)
        FROM unresolved
        WHERE unresolved_identity IS NOT NULL
        """
    ).fetchone()
    assert row is not None
    return int(row[0])


def _tainted_plan_count(connection: duckdb.DuckDBPyConnection) -> int:
    row = connection.execute(
        """
        WITH authority_counts AS (
          SELECT source_observation_id, COUNT(*) AS identity_count
          FROM environmental_observations.fact_bird_observation
          WHERE source_observation_id IS NOT NULL
          GROUP BY source_observation_id
        )
        SELECT COUNT(DISTINCT persisted.trip_plan_id)
        FROM birding_agent.trip_plan_evidence AS persisted
        LEFT JOIN authority_counts AS authority
          ON authority.source_observation_id = persisted.source_record_id
        WHERE persisted.source = 'ebird'
          AND persisted.evidence_type = 'recent_observation'
          AND (
            persisted.source_record_id IS NULL
            OR TRIM(persisted.source_record_id) = ''
            OR COALESCE(authority.identity_count, 0) <> 1
            OR EXISTS (
              SELECT 1
              FROM environmental_observations.fact_bird_observation AS fact
              WHERE fact.source_observation_id = persisted.source_record_id
                AND (
                  fact.is_valid IS NOT TRUE
                  OR fact.is_reviewed IS NOT TRUE
                  OR fact.is_location_private IS NOT FALSE
                )
            )
          )
        """
    ).fetchone()
    assert row is not None
    return int(row[0])


def _scalar_count(connection: duckdb.DuckDBPyConnection, query: str) -> int:
    row = connection.execute(query).fetchone()
    assert row is not None
    return int(row[0])


def inspect_trip_plan_privacy(
    connection: duckdb.DuckDBPyConnection,
) -> RemediationResult:
    """Return aggregate-only counts without writing or exposing source identities."""

    if not _require_complete_contract(connection):
        return RemediationResult(0, 0, 0, 0, 0, 0, 0)
    unmatched = _unmatched_count(connection)
    tainted = _tainted_plan_count(connection)
    remaining = _scalar_count(connection, "SELECT COUNT(*) FROM birding_agent.trip_plans")
    return RemediationResult(tainted, 0, 0, 0, 0, remaining, unmatched)


def _count_for_tainted(connection: duckdb.DuckDBPyConnection, table: str) -> int:
    row = connection.execute(
        f"""SELECT COUNT(*) FROM birding_agent.{table}
        WHERE trip_plan_id IN (SELECT trip_plan_id FROM remediation_tainted_plans)"""
    ).fetchone()
    assert row is not None
    return int(row[0])


def _remaining_tainted_children(connection: duckdb.DuckDBPyConnection) -> int:
    return sum(
        _scalar_count(
            connection,
            f"""SELECT COUNT(*) FROM birding_agent.{table}
            WHERE trip_plan_id IN (
              SELECT trip_plan_id FROM remediation_tainted_plans
            )""",
        )
        for table in _TABLES[1:]
    )


def remediate_trip_plan_privacy(
    connection: duckdb.DuckDBPyConnection,
    *,
    before_commit: Callable[[duckdb.DuckDBPyConnection], Any] | None = None,
) -> RemediationResult:
    """Delete complete tainted plan aggregates in one fail-closed transaction."""

    connection.execute("BEGIN TRANSACTION")
    try:
        if not _require_complete_contract(connection):
            connection.execute("COMMIT")
            return RemediationResult(0, 0, 0, 0, 0, 0, 0)
        unmatched = _unmatched_count(connection)
        connection.execute(
            """
            CREATE OR REPLACE TEMP TABLE remediation_tainted_plans AS
            WITH authority_counts AS (
              SELECT source_observation_id, COUNT(*) AS identity_count
              FROM environmental_observations.fact_bird_observation
              WHERE source_observation_id IS NOT NULL
              GROUP BY source_observation_id
            )
            SELECT DISTINCT persisted.trip_plan_id
            FROM birding_agent.trip_plan_evidence AS persisted
            LEFT JOIN authority_counts AS authority
              ON authority.source_observation_id = persisted.source_record_id
            WHERE persisted.source = 'ebird'
              AND persisted.evidence_type = 'recent_observation'
              AND (
                persisted.source_record_id IS NULL
                OR TRIM(persisted.source_record_id) = ''
                OR COALESCE(authority.identity_count, 0) <> 1
                OR EXISTS (
                  SELECT 1
                  FROM environmental_observations.fact_bird_observation AS fact
                  WHERE fact.source_observation_id = persisted.source_record_id
                    AND (
                      fact.is_valid IS NOT TRUE
                      OR fact.is_reviewed IS NOT TRUE
                      OR fact.is_location_private IS NOT FALSE
                    )
                )
              )
            """
        )
        counts = {
            "plans": _count_for_tainted(connection, "trip_plans"),
            "recommendations": _count_for_tainted(connection, "trip_plan_recommendations"),
            "evidence": _count_for_tainted(connection, "trip_plan_evidence"),
            "tool_traces": _count_for_tainted(connection, "trip_plan_tool_traces"),
        }
        connection.execute(
            """DELETE FROM birding_agent.trip_plan_tool_traces
            WHERE trip_plan_id IN (SELECT trip_plan_id FROM remediation_tainted_plans)"""
        )
        connection.execute(
            """DELETE FROM birding_agent.trip_plan_evidence
            WHERE trip_plan_id IN (SELECT trip_plan_id FROM remediation_tainted_plans)"""
        )
        connection.execute(
            """DELETE FROM birding_agent.trip_plan_recommendations
            WHERE trip_plan_id IN (SELECT trip_plan_id FROM remediation_tainted_plans)"""
        )
        connection.execute(
            """DELETE FROM birding_agent.trip_plans
            WHERE trip_plan_id IN (SELECT trip_plan_id FROM remediation_tainted_plans)"""
        )
        if before_commit is not None:
            before_commit(connection)
        if _remaining_tainted_children(connection):
            raise ValueError("trip plan remediation would leave partial tainted rows")
        remaining = _scalar_count(connection, "SELECT COUNT(*) FROM birding_agent.trip_plans")
        connection.execute("COMMIT")
        return RemediationResult(
            tainted_plans=counts["plans"],
            deleted_plans=counts["plans"],
            deleted_recommendations=counts["recommendations"],
            deleted_evidence=counts["evidence"],
            deleted_tool_traces=counts["tool_traces"],
            remaining_plans=remaining,
            unmatched_source_records=unmatched,
        )
    except Exception:
        connection.execute("ROLLBACK")
        raise
