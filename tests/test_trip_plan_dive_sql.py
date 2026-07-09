"""SQL contract checks for the Birding Trip Copilot MotherDuck Dive."""

from __future__ import annotations

import json

import duckdb

DB = '"databox"."birding_agent"'

PLAN_LIST_SQL = f"""
  SELECT
    trip_plan_id,
    COALESCE(normalized_location_name, requested_location) AS plan_label,
    window_start,
    window_end,
    duration_minutes,
    plan_status,
    created_at
  FROM {DB}."trip_plans"
  ORDER BY created_at DESC, window_start DESC
  LIMIT 50
"""


def _plan_detail_sql(trip_plan_id: str) -> str:
    return f"""
      SELECT
        trip_plan_id,
        requested_location,
        normalized_location_name,
        latitude,
        longitude,
        region_code,
        window_start,
        window_end,
        duration_minutes,
        skill_level,
        constraints_text,
        plan_status,
        field_plan_text,
        caveats_json,
        created_at,
        updated_at
      FROM {DB}."trip_plans"
      WHERE trip_plan_id = '{trip_plan_id}'
      LIMIT 1
    """


def _recommendations_sql(trip_plan_id: str) -> str:
    return f"""
      WITH recommendations AS (
        SELECT
          r.recommendation_id,
          r.trip_plan_id,
          r.species_code,
          r.common_name,
          r.scientific_name,
          r.recommendation_group,
          r.rank_order,
          r.confidence_label,
          r.rationale_text,
          r.caveats_json,
          COUNT(e.evidence_id) AS evidence_count,
          string_agg(DISTINCT e.source, ', ') AS evidence_sources
        FROM {DB}."trip_plan_recommendations" r
        LEFT JOIN {DB}."trip_plan_evidence" e
          ON e.recommendation_id = r.recommendation_id
        WHERE r.trip_plan_id = '{trip_plan_id}'
        GROUP BY ALL
      )
      SELECT *
      FROM recommendations
      ORDER BY
        CASE recommendation_group
          WHEN 'high_likelihood' THEN 1
          WHEN 'uncommon_plausible' THEN 2
          ELSE 3
        END,
        rank_order ASC
    """


def _evidence_sql(trip_plan_id: str) -> str:
    return f"""
      SELECT
        e.evidence_id,
        e.trip_plan_id,
        e.recommendation_id,
        COALESCE(r.common_name, 'Trip-level') AS recommendation_label,
        e.source,
        e.source_table,
        e.source_record_id,
        e.evidence_type,
        e.status,
        e.latitude,
        e.longitude,
        e.window_start,
        e.window_end,
        e.retrieved_at,
        e.summary_json,
        e.payload_json,
        e.caveats_json
      FROM {DB}."trip_plan_evidence" e
      LEFT JOIN {DB}."trip_plan_recommendations" r
        ON r.recommendation_id = e.recommendation_id
      WHERE e.trip_plan_id = '{trip_plan_id}'
      ORDER BY
        CASE e.source
          WHEN 'open_meteo' THEN 1
          WHEN 'ebird' THEN 2
          WHEN 'gbif' THEN 3
          WHEN 'xeno_canto' THEN 4
          ELSE 5
        END,
        e.status DESC,
        e.retrieved_at DESC NULLS LAST
      LIMIT 200
    """


def _weather_sql(trip_plan_id: str) -> str:
    return f"""
      SELECT
        evidence_id,
        status,
        latitude,
        longitude,
        retrieved_at,
        summary_json,
        payload_json,
        caveats_json
      FROM {DB}."trip_plan_evidence"
      WHERE trip_plan_id = '{trip_plan_id}'
        AND source = 'open_meteo'
      ORDER BY retrieved_at DESC NULLS LAST
      LIMIT 1
    """


def _media_sql(trip_plan_id: str) -> str:
    return f"""
      SELECT
        e.evidence_id,
        COALESCE(
          r.common_name,
          json_extract_string(e.summary_json, '$.english_name'),
          'Media example'
        ) AS species_label,
        e.status,
        e.summary_json,
        e.payload_json,
        e.caveats_json
      FROM {DB}."trip_plan_evidence" e
      LEFT JOIN {DB}."trip_plan_recommendations" r
        ON r.recommendation_id = e.recommendation_id
      WHERE e.trip_plan_id = '{trip_plan_id}'
        AND e.source = 'xeno_canto'
      ORDER BY species_label, e.status DESC
      LIMIT 20
    """


def _traces_sql(trip_plan_id: str) -> str:
    return f"""
      SELECT
        tool_trace_id,
        step_order,
        tool_name,
        tool_status,
        started_at,
        completed_at,
        output_summary_json,
        caveats_json
      FROM {DB}."trip_plan_tool_traces"
      WHERE trip_plan_id = '{trip_plan_id}'
      ORDER BY step_order ASC
    """


def test_trip_plan_dive_queries_run_against_persisted_artifact_shape() -> None:
    con = duckdb.connect(":memory:")
    con.execute("ATTACH ':memory:' AS databox")
    con.execute("CREATE SCHEMA databox.birding_agent")
    _seed(con)

    plan_rows = con.execute(PLAN_LIST_SQL).fetchall()
    assert plan_rows[0][0] == "trip-demo"

    detail = con.execute(_plan_detail_sql("trip-demo")).fetchone()
    assert detail is not None
    assert detail[2] == "Thumb Butte, Prescott, AZ"

    recs = con.execute(_recommendations_sql("trip-demo")).fetchall()
    assert [row[5] for row in recs] == ["high_likelihood", "uncommon_plausible"]
    assert recs[0][10] == 2

    evidence = con.execute(_evidence_sql("trip-demo")).fetchall()
    assert [row[4] for row in evidence] == ["open_meteo", "ebird", "gbif", "xeno_canto"]

    weather = con.execute(_weather_sql("trip-demo")).fetchone()
    assert weather is not None
    assert json.loads(weather[5])["forecast_summary"]["temperature_2m_avg"] == 21.0

    media = con.execute(_media_sql("trip-demo")).fetchone()
    assert media is not None
    assert media[1] == "Acorn Woodpecker"

    traces = con.execute(_traces_sql("trip-demo")).fetchall()
    assert [row[2] for row in traces] == ["normalize_location", "persist_trip_plan"]


def _seed(con: duckdb.DuckDBPyConnection) -> None:
    con.execute(
        """
        CREATE TABLE databox.birding_agent.trip_plans (
            trip_plan_id TEXT,
            requested_location TEXT,
            normalized_location_name TEXT,
            latitude DOUBLE,
            longitude DOUBLE,
            region_code TEXT,
            window_start TEXT,
            window_end TEXT,
            duration_minutes BIGINT,
            skill_level TEXT,
            constraints_text TEXT,
            plan_status TEXT,
            field_plan_text TEXT,
            caveats_json TEXT,
            created_at TEXT,
            updated_at TEXT
        )
        """
    )
    con.execute(
        """
        INSERT INTO databox.birding_agent.trip_plans
        VALUES ('trip-demo', 'Thumb Butte', 'Thumb Butte, Prescott, AZ', 34.5444, -112.528,
                'US-AZ', '2026-07-09T06:00:00', '2026-07-09T07:30:00', 90,
                'beginner', 'focus on calls', 'complete',
                'Start at first light; listen for Acorn Woodpecker and watch for Zone-tailed Hawk.',
                '[]', '2026-07-09T00:00:00', '2026-07-09T00:00:00')
        """
    )
    con.execute(
        """
        CREATE TABLE databox.birding_agent.trip_plan_recommendations (
            recommendation_id TEXT,
            trip_plan_id TEXT,
            species_lookup_id TEXT,
            species_code TEXT,
            common_name TEXT,
            scientific_name TEXT,
            recommendation_group TEXT,
            rank_order BIGINT,
            confidence_label TEXT,
            rationale_text TEXT,
            caveats_json TEXT,
            created_at TEXT
        )
        """
    )
    con.executemany(
        """
        INSERT INTO databox.birding_agent.trip_plan_recommendations
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [
            (
                "rec-acorn",
                "trip-demo",
                "species-acorn",
                "acowoo",
                "Acorn Woodpecker",
                "Melanerpes formicivorus",
                "high_likelihood",
                1,
                "high",
                "Recent local evidence and media are available.",
                "[]",
                "2026-07-09T00:00:00",
            ),
            (
                "rec-zone",
                "trip-demo",
                "species-zone",
                "zothaw",
                "Zone-tailed Hawk",
                "Buteo albonotatus",
                "uncommon_plausible",
                1,
                "moderate",
                "GBIF occurrence context makes this plausible but uncommon.",
                "[]",
                "2026-07-09T00:00:00",
            ),
        ],
    )
    con.execute(
        """
        CREATE TABLE databox.birding_agent.trip_plan_evidence (
            evidence_id TEXT,
            trip_plan_id TEXT,
            recommendation_id TEXT,
            source TEXT,
            source_table TEXT,
            source_record_id TEXT,
            evidence_type TEXT,
            status TEXT,
            latitude DOUBLE,
            longitude DOUBLE,
            window_start TEXT,
            window_end TEXT,
            retrieved_at TEXT,
            summary_json TEXT,
            payload_json TEXT,
            caveats_json TEXT
        )
        """
    )
    con.executemany(
        """
        INSERT INTO databox.birding_agent.trip_plan_evidence
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [
            (
                "ev-weather",
                "trip-demo",
                None,
                "open_meteo",
                None,
                "ev-weather",
                "weather_elevation_context",
                "available",
                34.5444,
                -112.528,
                "2026-07-09T06:00:00",
                "2026-07-09T07:30:00",
                "2026-07-09T00:00:00",
                json.dumps({"forecast_summary": {"temperature_2m_avg": 21.0}, "elevation_m": 1642}),
                json.dumps({"forecast_summary": {"temperature_2m_avg": 21.0}, "elevation_m": 1642}),
                "[]",
            ),
            (
                "ev-ebird",
                "trip-demo",
                "rec-acorn",
                "ebird",
                "birding_agent.recent_observation_evidence",
                "S1",
                "recent_observation",
                "available",
                34.54,
                -112.52,
                "2026-07-09T06:00:00",
                "2026-07-09T07:30:00",
                "2026-07-09T00:00:00",
                json.dumps({"common_name": "Acorn Woodpecker", "observation_date": "2026-07-08"}),
                "{}",
                "[]",
            ),
            (
                "ev-gbif",
                "trip-demo",
                "rec-zone",
                "gbif",
                "birding_agent.gbif_occurrence_evidence",
                "G1",
                "occurrence_context",
                "available",
                34.56,
                -112.5,
                "2026-07-09T06:00:00",
                "2026-07-09T07:30:00",
                "2026-07-09T00:00:00",
                json.dumps({"common_name": "Zone-tailed Hawk", "license": "CC_BY_4_0"}),
                "{}",
                "[]",
            ),
            (
                "ev-xc",
                "trip-demo",
                "rec-acorn",
                "xeno_canto",
                "birding_agent.xeno_canto_media_evidence",
                "XC1",
                "media_context",
                "available",
                34.54,
                -112.52,
                "2026-07-09T06:00:00",
                "2026-07-09T07:30:00",
                "2026-07-09T00:00:00",
                json.dumps(
                    {
                        "english_name": "Acorn Woodpecker",
                        "recording_url": "https://xeno-canto.org/XC1",
                        "license": "CC BY-NC-SA 4.0",
                    }
                ),
                "{}",
                "[]",
            ),
        ],
    )
    con.execute(
        """
        CREATE TABLE databox.birding_agent.trip_plan_tool_traces (
            tool_trace_id TEXT,
            trip_plan_id TEXT,
            step_order BIGINT,
            tool_name TEXT,
            tool_status TEXT,
            started_at TEXT,
            completed_at TEXT,
            input_json TEXT,
            output_summary_json TEXT,
            caveats_json TEXT
        )
        """
    )
    con.executemany(
        """
        INSERT INTO databox.birding_agent.trip_plan_tool_traces
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [
            (
                "trace-1",
                "trip-demo",
                1,
                "normalize_location",
                "ok",
                "2026-07-09T00:00:00",
                "2026-07-09T00:00:01",
                "{}",
                json.dumps({"normalized_location_name": "Thumb Butte, Prescott, AZ"}),
                "[]",
            ),
            (
                "trace-2",
                "trip-demo",
                8,
                "persist_trip_plan",
                "ok",
                "2026-07-09T00:00:07",
                "2026-07-09T00:00:08",
                "{}",
                json.dumps({"status": "persisted"}),
                "[]",
            ),
        ],
    )
