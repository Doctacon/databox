"""Semantic metrics layer tests for the CDM fact layer."""

from __future__ import annotations

import pytest

REQUIRED_METRICS = {
    "species_richness",
    "total_observations",
    "total_observed_birds",
}


@pytest.fixture(scope="module")
def metrics_context():
    from databox.orchestration.metrics import _context

    _context.cache_clear()
    return _context()


def test_required_metrics_registered(metrics_context) -> None:
    """Every CDM metric must exist in the registry."""
    loaded = set(metrics_context._metrics.keys())
    missing = REQUIRED_METRICS - loaded
    assert not missing, f"Missing required metrics: {sorted(missing)}"


def test_metric_query_rewrites_to_cdm_fact() -> None:
    """A simple METRIC() query must rewrite against the CDM bird-observation fact."""
    from databox.orchestration.metrics import resolve_metric_query

    sql = resolve_metric_query(
        "SELECT observation_date, METRIC(species_richness) AS sr "
        "FROM __semantic.__table GROUP BY observation_date"
    )
    assert "environmental_observations.fact_bird_observation" in sql
    assert "COUNT(DISTINCT" in sql
    assert "__semantic" not in sql


def test_total_observed_birds_uses_observation_count() -> None:
    """The additive count metric must sum the CDM observation_count measure."""
    from databox.orchestration.metrics import resolve_metric_query

    sql = resolve_metric_query(
        "SELECT observation_date, METRIC(total_observed_birds) AS birds "
        "FROM __semantic.__table GROUP BY observation_date"
    )
    assert "SUM(" in sql
    assert "observation_count" in sql


def test_all_cdm_metrics_resolve() -> None:
    """Every required CDM metric must rewrite without error."""
    from databox.orchestration.metrics import resolve_metric_query

    for metric in REQUIRED_METRICS:
        sql = resolve_metric_query(
            f"SELECT observation_date, METRIC({metric}) AS v "
            "FROM __semantic.__table GROUP BY observation_date"
        )
        assert "environmental_observations.fact_bird_observation" in sql, (
            f"{metric} did not bind to the CDM fact"
        )
