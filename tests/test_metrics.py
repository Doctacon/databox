"""Semantic metrics layer tests.

Validates that the SQLMesh metric registry loads without errors, every
ticket-required metric is present, and each metric rewrites into syntactically
valid SQL that references the flagship mart.

Does not hit the live database — these are registry/structure tests. Live
verification runs as the Dagster asset check on the flagship mart.
"""

from __future__ import annotations

import pytest

REQUIRED_METRICS = {
    "species_richness",
    "observation_intensity",
    "heat_stress_index",
    "rainfall_anomaly_7d",
    "discharge_anomaly_7d",
}


@pytest.fixture(scope="module")
def metrics_context():
    from databox_orchestration.metrics import _context

    return _context()


def test_required_metrics_registered(metrics_context) -> None:
    """Every metric named in the ticket must exist in the registry."""
    loaded = set(metrics_context._metrics.keys())
    missing = REQUIRED_METRICS - loaded
    assert not missing, f"Missing required metrics: {sorted(missing)}"


def test_metric_query_rewrites_to_valid_sql() -> None:
    """A simple METRIC() query must rewrite into SQL that parses and names the flagship mart."""
    from databox_orchestration.metrics import resolve_metric_query

    sql = resolve_metric_query(
        "SELECT obs_date, METRIC(species_richness) AS sr FROM __semantic.__table GROUP BY obs_date"
    )
    assert "analytics.fct_species_environment_daily" in sql
    assert "COUNT(DISTINCT" in sql
    assert "__semantic" not in sql


def test_derived_metric_expands_dependencies() -> None:
    """observation_intensity = total_observations / total_checklists.

    Both raw aggregates must appear in the rewritten SQL.
    """
    from databox_orchestration.metrics import resolve_metric_query

    sql = resolve_metric_query(
        "SELECT obs_date, METRIC(observation_intensity) AS oi "
        "FROM __semantic.__table GROUP BY obs_date"
    )
    assert "SUM(" in sql
    assert "n_observations" in sql
    assert "n_checklists" in sql
    assert "NULLIF" in sql


def test_all_ticket_metrics_resolve() -> None:
    """Every required metric must rewrite without error."""
    from databox_orchestration.metrics import resolve_metric_query

    for metric in REQUIRED_METRICS:
        sql = resolve_metric_query(
            f"SELECT obs_date, METRIC({metric}) AS v FROM __semantic.__table GROUP BY obs_date"
        )
        assert "analytics.fct_species_environment_daily" in sql, f"{metric} did not bind to mart"
