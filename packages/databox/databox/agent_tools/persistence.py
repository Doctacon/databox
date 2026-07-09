"""Persistence-table contract for Birding Trip Copilot artifacts."""

from __future__ import annotations

from typing import Any, Protocol


class DuckDBConnection(Protocol):
    """Small DuckDB connection protocol used by persistence helpers."""

    def execute(self, query: str, parameters: object | None = None) -> Any: ...


def ensure_birding_agent_persistence_tables(
    connection: DuckDBConnection,
    *,
    schema: str = "birding_agent",
) -> None:
    """Create the physical trip-plan persistence tables if they do not exist.

    These tables are intentionally not SQLMesh-managed models because the ADK
    planner will append/update plan artifacts at request time. SQLMesh models
    read source evidence for planning; the Dive and evals can query these stable
    physical interfaces for generated plans, recommendations, evidence, and
    tool traces.
    """

    schema_ident = _quote_identifier(schema)
    connection.execute(f"CREATE SCHEMA IF NOT EXISTS {schema_ident}")
    connection.execute(
        f"""
        CREATE TABLE IF NOT EXISTS {schema_ident}.trip_plans (
            trip_plan_id TEXT PRIMARY KEY,
            requested_location TEXT NOT NULL,
            normalized_location_name TEXT,
            latitude DOUBLE,
            longitude DOUBLE,
            region_code TEXT,
            window_start TEXT NOT NULL,
            window_end TEXT NOT NULL,
            duration_minutes BIGINT,
            skill_level TEXT,
            constraints_text TEXT,
            plan_status TEXT NOT NULL,
            field_plan_text TEXT,
            caveats_json TEXT NOT NULL DEFAULT '[]',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        """
    )
    connection.execute(
        f"""
        CREATE TABLE IF NOT EXISTS {schema_ident}.trip_plan_recommendations (
            recommendation_id TEXT PRIMARY KEY,
            trip_plan_id TEXT NOT NULL,
            species_lookup_id TEXT,
            species_code TEXT,
            common_name TEXT,
            scientific_name TEXT,
            recommendation_group TEXT NOT NULL,
            rank_order BIGINT NOT NULL,
            confidence_label TEXT,
            rationale_text TEXT,
            caveats_json TEXT NOT NULL DEFAULT '[]',
            created_at TEXT NOT NULL
        )
        """
    )
    connection.execute(
        f"""
        CREATE TABLE IF NOT EXISTS {schema_ident}.trip_plan_evidence (
            evidence_id TEXT PRIMARY KEY,
            trip_plan_id TEXT NOT NULL,
            recommendation_id TEXT,
            source TEXT NOT NULL,
            source_table TEXT,
            source_record_id TEXT,
            evidence_type TEXT NOT NULL,
            status TEXT NOT NULL,
            latitude DOUBLE,
            longitude DOUBLE,
            window_start TEXT,
            window_end TEXT,
            retrieved_at TEXT,
            summary_json TEXT NOT NULL,
            payload_json TEXT NOT NULL,
            caveats_json TEXT NOT NULL DEFAULT '[]'
        )
        """
    )
    connection.execute(
        f"""
        CREATE TABLE IF NOT EXISTS {schema_ident}.trip_plan_tool_traces (
            tool_trace_id TEXT PRIMARY KEY,
            trip_plan_id TEXT NOT NULL,
            step_order BIGINT NOT NULL,
            tool_name TEXT NOT NULL,
            tool_status TEXT NOT NULL,
            started_at TEXT,
            completed_at TEXT,
            input_json TEXT NOT NULL DEFAULT '{{}}',
            output_summary_json TEXT NOT NULL DEFAULT '{{}}',
            caveats_json TEXT NOT NULL DEFAULT '[]'
        )
        """
    )


def _quote_identifier(value: str) -> str:
    return '"' + value.replace('"', '""') + '"'
