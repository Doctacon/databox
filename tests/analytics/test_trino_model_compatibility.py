from __future__ import annotations

from datetime import date, datetime
from pathlib import Path

import duckdb
from sqlglot import parse_one

MODELS = Path(__file__).parents[2] / "transforms/main/models"


def _query(relative_path: str):
    sql = (MODELS / relative_path).read_text()
    return parse_one(sql.split(");", maxsplit=1)[1], read="duckdb")


def test_dim_species_uses_trino_safe_explicit_projection() -> None:
    trino_sql = _query("environmental_observations/dimensions/dim_species.sql").sql(dialect="trino")

    assert "EXCEPT" not in trino_sql
    assert "EXCLUDE" not in trino_sql


def test_earthquake_iso_timestamps_transpile_with_utc_microsecond_precision() -> None:
    query = _query("environmental_observations/facts/fact_earthquake_event.sql")
    trino_sql = query.sql(dialect="trino")

    assert "FROM_ISO8601_TIMESTAMP(event_time)" in trino_sql
    assert "AT_TIMEZONE" in trino_sql
    assert "TIMESTAMP(6)" in trino_sql

    expression = parse_one(
        "SELECT CAST(FROM_ISO8601_TIMESTAMP('2026-09-18T01:13:50.688000Z') "
        "AT TIME ZONE 'UTC' AS TIMESTAMP(6))",
        read="duckdb",
    )
    result = duckdb.sql(expression.sql(dialect="duckdb")).fetchone()[0]
    assert result == datetime(2026, 9, 18, 1, 13, 50, 688000)


def test_weather_iso_date_parsing_is_explicit_and_preserves_duckdb_dates() -> None:
    query = _query("environmental_observations/facts/fact_weather_observation.sql")
    expression = next(e.this for e in query.expressions if e.alias == "observation_date")
    assert "FROM_ISO8601_TIMESTAMP(date)" in expression.sql(dialect="trino")
    for raw in ("2026-08-19T00:00:00", "2026-08-19"):
        result = duckdb.sql(
            f"SELECT {expression.sql(dialect='duckdb')} FROM (SELECT ? AS date)",
            params=[raw],
        ).fetchone()[0]
        assert result == date(2026, 8, 19)


def test_platform_health_uses_iceberg_supported_timestamp_precision() -> None:
    trino_sql = _query("analytics/platform_health.sql").sql(dialect="trino")

    assert "CAST(CURRENT_TIMESTAMP AS TIMESTAMP(6))" in trino_sql
    assert "CAST(inserted_at AS TIMESTAMP(6))" in trino_sql
