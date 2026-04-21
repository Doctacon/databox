"""Semantic metrics layer — resolve metric queries against the flagship mart.

Consumers request metrics by name (e.g. ``METRIC(species_richness)``) via the
special ``__semantic.__table`` placeholder; this module rewrites those queries
into executable SQL against the actual mart using SQLMesh's metric rewriter.

Example:

    from databox_orchestration.metrics import resolve_metric_query

    sql = resolve_metric_query(
        "SELECT obs_date, METRIC(species_richness) AS sr "
        "FROM __semantic.__table GROUP BY obs_date"
    )
    # -> ready-to-execute DuckDB SQL against analytics.fct_species_environment_daily

The single source of truth for metric definitions is
``transforms/main/metrics/flagship.sql``. If a metric changes there,
all consumers see the new definition immediately.
"""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

from sqlmesh import Context
from sqlmesh.core.metric.rewriter import rewrite as _metric_rewrite
from sqlmesh.core.reference import ReferenceGraph

TRANSFORMS_PATH = Path(__file__).resolve().parents[3] / "transforms" / "main"


@lru_cache(maxsize=1)
def _context() -> Context:
    return Context(
        paths=[str(TRANSFORMS_PATH)],
        gateway=os.environ.get("DATABOX_GATEWAY", "local"),
    )


def available_metrics() -> list[str]:
    """Return the list of registered metric names."""
    return sorted(_context()._metrics.keys())


def resolve_metric_query(sql: str, dialect: str = "duckdb") -> str:
    """Rewrite a metric-aware query into executable SQL.

    The query should reference metrics via ``METRIC(<name>)`` and select from
    ``__semantic.__table``. The rewriter replaces the placeholder with the
    underlying mart and expands each ``METRIC(...)`` into its registered SQL
    expression.
    """
    ctx = _context()
    graph = ReferenceGraph(ctx._models.values())
    rewritten = _metric_rewrite(sql, graph=graph, metrics=ctx._metrics, dialect=dialect)
    return rewritten.sql(dialect=dialect)
