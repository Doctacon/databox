"""Codegen for `transforms/main/models/analytics/platform_health.sql`.

The model is a fan-out over every source in `databox.config.sources.SOURCES`:
one `*_loads` CTE per source (joined via UNION ALL) and one `*_rows` CTE per
source that sums dlt-load row counts across that source's raw tables.

Keeping this hand-written would mean that adding a fifth source requires two
edit sites (registry + SQL). The codegen resolves that by making the registry
the sole declaration site.
"""

from __future__ import annotations

from pathlib import Path

from databox.config.sources import SOURCES, Source

TARGET = Path("transforms/main/models/analytics/platform_health.sql")
HEADER_MARKER = "-- platform-health-codegen: generated"


def _loads_cte(src: Source) -> str:
    return (
        f"{src.name}_loads AS (\n"
        f"  SELECT\n"
        f"    '{src.name}'             AS source,\n"
        f"    load_id,\n"
        f"    schema_name,\n"
        f"    status,\n"
        f"    inserted_at::TIMESTAMP AS completed_at\n"
        f"  FROM {src.raw_catalog}.main._dlt_loads\n"
        f")"
    )


def _rows_cte(src: Source) -> str:
    if not src.raw_tables:
        return (
            f"{src.name}_rows AS (\n"
            f"  SELECT CAST(NULL AS VARCHAR) AS load_id, CAST(0 AS BIGINT) AS rows WHERE 1=0\n"
            f")"
        )
    first = "    SELECT _dlt_load_id, COUNT(*) AS n FROM"
    rest = "    UNION ALL SELECT _dlt_load_id, COUNT(*) FROM"
    table_lines = [
        f"{(first if i == 0 else rest)} {src.raw_catalog}.main.{table} GROUP BY 1"
        for i, table in enumerate(src.raw_tables)
    ]
    return (
        f"{src.name}_rows AS (\n"
        "  SELECT _dlt_load_id AS load_id, SUM(n)::BIGINT AS rows FROM (\n"
        + "\n".join(table_lines)
        + "\n  ) t GROUP BY 1\n)"
    )


def render(sources: list[Source] | None = None) -> str:
    srcs = sources if sources is not None else SOURCES
    loads_ctes = ",\n".join(_loads_cte(s) for s in srcs)
    all_loads = "\n  UNION ALL ".join(f"SELECT * FROM {s.name}_loads" for s in srcs)
    rows_ctes = ",\n".join(_rows_cte(s) for s in srcs)
    all_rows = "\n  UNION ALL ".join(
        f"SELECT '{s.name}' AS source, load_id, rows FROM {s.name}_rows" for s in srcs
    )
    description = (
        "Per-source load observability — most recent dlt load id, "
        "completion time, status, and row volume. One row per source."
    )
    return (
        f"{HEADER_MARKER} — edit packages/databox/databox/quality/platform_health_codegen.py\n"
        "MODEL (\n"
        "  name analytics.platform_health,\n"
        "  kind VIEW,\n"
        f"  description '{description}',\n"
        "  grants (select_ = ['staging_reader', 'domain_reader', 'analyst'])\n"
        ");\n"
        "\n"
        f"WITH {loads_ctes},\n"
        "all_loads AS (\n"
        f"  {all_loads}\n"
        "),\n"
        f"{rows_ctes},\n"
        "all_rows AS (\n"
        f"  {all_rows}\n"
        "),\n"
        "latest_per_source AS (\n"
        "  SELECT\n"
        "    source,\n"
        "    load_id,\n"
        "    schema_name,\n"
        "    status,\n"
        "    completed_at,\n"
        "    ROW_NUMBER() OVER (PARTITION BY source ORDER BY completed_at DESC) AS rn\n"
        "  FROM all_loads\n"
        ")\n"
        "SELECT\n"
        "  l.source,\n"
        "  l.load_id,\n"
        "  l.schema_name,\n"
        "  l.status,\n"
        "  CASE WHEN l.status = 0 THEN 'success' ELSE 'failed' END AS status_label,\n"
        "  l.completed_at,\n"
        "  COALESCE(r.rows, 0) AS rows_loaded,\n"
        "  (CURRENT_TIMESTAMP - l.completed_at) AS age\n"
        "FROM latest_per_source l\n"
        "LEFT JOIN all_rows r\n"
        "  ON r.source = l.source AND r.load_id = l.load_id\n"
        "WHERE l.rn = 1\n"
        "ORDER BY l.source\n"
    )


def write(target: Path = TARGET) -> Path:
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(render())
    return target


def check_drift(target: Path = TARGET) -> bool:
    """Return True when committed SQL does not match the rendered output."""
    if not target.exists():
        return True
    return target.read_text() != render()
