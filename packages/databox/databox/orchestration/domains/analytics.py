"""Analytics domain — cross-domain SQLMesh marts + Soda checks.

Analytics has no dlt ingestion and no dedicated schedule; its tables are
rebuilt as part of any upstream source run via `all_pipelines`. The
`mart_cost_summary` asset has its own daily schedule so the cost page
updates even on days with no source reloads.
"""

from __future__ import annotations

from datetime import UTC, timedelta

import dagster as dg
import duckdb

from databox.config.settings import settings
from databox.orchestration._factories import SODA_DIR, freshness_checks, soda_check

sqlmesh_asset_keys = [
    dg.AssetKey(["sqlmesh", "analytics", "fct_bird_weather_daily"]),
    dg.AssetKey(["sqlmesh", "analytics", "fct_species_weather_preferences"]),
    dg.AssetKey(["sqlmesh", "analytics", "fct_species_environment_daily"]),
    dg.AssetKey(["sqlmesh", "analytics", "platform_health"]),
]

FRESHNESS_SLAS: dict[dg.AssetKey, timedelta] = {
    dg.AssetKey(["sqlmesh", "analytics", "fct_species_environment_daily"]): timedelta(hours=48),
    dg.AssetKey(["sqlmesh", "analytics", "platform_health"]): timedelta(hours=2),
}

asset_checks: list[dg.AssetChecksDefinition] = [
    soda_check(
        dg.AssetKey(["sqlmesh", "analytics", "fct_bird_weather_daily"]),
        SODA_DIR / "contracts/analytics/fct_bird_weather_daily.yaml",
    ),
    soda_check(
        dg.AssetKey(["sqlmesh", "analytics", "fct_species_weather_preferences"]),
        SODA_DIR / "contracts/analytics/fct_species_weather_preferences.yaml",
    ),
    soda_check(
        dg.AssetKey(["sqlmesh", "analytics", "platform_health"]),
        SODA_DIR / "contracts/analytics/platform_health.yaml",
    ),
    soda_check(
        dg.AssetKey(["sqlmesh", "analytics", "fct_species_environment_daily"]),
        SODA_DIR / "contracts/analytics/fct_species_environment_daily.yaml",
    ),
    soda_check(
        dg.AssetKey(["analytics", "mart_cost_summary"]),
        SODA_DIR / "contracts/analytics/mart_cost_summary.yaml",
    ),
    *freshness_checks(FRESHNESS_SLAS),
]


# MotherDuck "Standard" plan rate as of 2026-04. Forkers must update when
# MotherDuck's published per-compute-second price changes — no pricing API.
# https://motherduck.com/pricing
MOTHERDUCK_COST_PER_COMPUTE_SECOND = 0.25 / 3600  # $0.25/hour
LOOKBACK_DAYS = 30


def _motherduck_summary(con: duckdb.DuckDBPyConnection, now) -> list[tuple]:
    cutoff = (now - timedelta(days=LOOKBACK_DAYS)).isoformat()
    queries = con.execute(
        f"""
        SELECT
          DATE(start_time) AS day_date,
          COUNT(*)::BIGINT AS query_count,
          COALESCE(SUM(EXTRACT(EPOCH FROM execution_time)), 0)::DOUBLE AS compute_seconds
        FROM MD_INFORMATION_SCHEMA.QUERY_HISTORY
        WHERE start_time >= TIMESTAMP '{cutoff}'
        GROUP BY 1
        """
    ).fetchall()
    storage = {
        row[0]: row[1]
        for row in con.execute(
            f"""
            SELECT DATE(computed_ts), SUM(active_bytes)::BIGINT
            FROM MD_INFORMATION_SCHEMA.STORAGE_INFO_HISTORY
            WHERE computed_ts >= TIMESTAMP '{cutoff}'
            GROUP BY 1
            """
        ).fetchall()
    }
    rows: list[tuple] = []
    days = {q[0] for q in queries} | set(storage.keys())
    by_day = {q[0]: (q[1], q[2]) for q in queries}
    for day in sorted(days):
        qc, cs = by_day.get(day, (0, 0.0))
        rows.append(
            (
                day,
                "motherduck",
                int(qc),
                float(cs),
                int(storage.get(day, 0)),
                float(cs) * MOTHERDUCK_COST_PER_COMPUTE_SECOND,
            )
        )
    return rows


def _local_summary(now) -> list[tuple]:
    import os

    from databox.config.settings import DATA_DIR

    total_bytes = 0
    for path in DATA_DIR.glob("*.duckdb"):
        try:
            total_bytes += os.stat(path).st_size
        except OSError:
            continue
    return [(now.date(), "local", 0, 0.0, total_bytes, None)]


@dg.asset(
    name="mart_cost_summary",
    key_prefix=["analytics"],
    description=(
        "Daily MotherDuck compute/storage usage (or local DuckDB file size "
        "when backend is local). Powers docs/cost.md. Written by Dagster "
        "directly rather than via SQLMesh: the mart queries "
        "MD_INFORMATION_SCHEMA which lives outside the SQLMesh model graph."
    ),
    compute_kind="duckdb",
    group_name="analytics",
)
def mart_cost_summary(context) -> dg.MaterializeResult:
    from datetime import datetime

    con = duckdb.connect(settings.database_path)
    now = datetime.now(UTC)
    try:
        if settings.backend == "motherduck":
            try:
                rows = _motherduck_summary(con, now)
            except Exception as exc:  # noqa: BLE001
                context.log.warning(
                    f"MD_INFORMATION_SCHEMA not reachable ({exc}); "
                    "emitting single zero-row. Business plan required."
                )
                rows = [(now.date(), "motherduck", 0, 0.0, 0, 0.0)]
        else:
            rows = _local_summary(now)

        con.execute("CREATE SCHEMA IF NOT EXISTS analytics")
        con.execute(
            """
            CREATE TABLE IF NOT EXISTS analytics.mart_cost_summary (
              day_date            DATE,
              backend             VARCHAR,
              query_count         BIGINT,
              compute_seconds     DOUBLE,
              storage_bytes       BIGINT,
              motherduck_cost_usd DOUBLE
            )
            """
        )
        # Idempotent per-day upsert: delete today's backend rows, reinsert.
        con.executemany(
            "DELETE FROM analytics.mart_cost_summary WHERE day_date = ? AND backend = ?",
            [(r[0], r[1]) for r in rows],
        )
        con.executemany(
            "INSERT INTO analytics.mart_cost_summary VALUES (?, ?, ?, ?, ?, ?)",
            rows,
        )

        latest = con.execute(
            "SELECT * FROM analytics.mart_cost_summary ORDER BY day_date DESC LIMIT 1"
        ).fetchone()
    finally:
        con.close()

    if latest is None:
        return dg.MaterializeResult(metadata={"status": "empty", "rows_written": len(rows)})

    day, backend, qc, cs, sb, cost = latest
    return dg.MaterializeResult(
        metadata={
            "day_date": str(day),
            "backend": backend,
            "query_count": int(qc or 0),
            "compute_seconds": float(cs or 0.0),
            "storage_mb": round((sb or 0) / 1_048_576, 2),
            "motherduck_cost_usd": float(cost) if cost is not None else None,
            "rows_written": len(rows),
        }
    )


cost_pipeline = dg.define_asset_job(
    name="cost_daily_pipeline",
    selection=dg.AssetSelection.assets(mart_cost_summary.key),
)

cost_schedule = dg.ScheduleDefinition(job=cost_pipeline, cron_schedule="30 6 * * *")
