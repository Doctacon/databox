"""Idempotency test: re-running eBird load against identical fixture data
must leave the final row set unchanged.

Uses `recent_observations` with the checklist/species merge identity
(`subId`, `speciesCode`).
"""

from __future__ import annotations

import pytest
from databox_sources.ebird.source import ebird_source


def _build_source():
    return ebird_source(region_code="US-DC", max_results=50, days_back=1).with_resources(
        "recent_observations"
    )


@pytest.mark.vcr
def test_ebird_recent_observations_idempotent(memory_duckdb_pipeline_factory):
    pipeline = memory_duckdb_pipeline_factory(pipeline_name="ebird_idempotency")

    info_a = pipeline.run(_build_source())
    assert not info_a.has_failed_jobs

    with pipeline.sql_client() as client:
        snapshot_a = {
            r[0]: r[1]
            for r in client.execute_sql(
                "SELECT 'recent_observations' AS t, COUNT(*) FROM recent_observations"
            )
        }
        identities_a = {
            (r[0], r[1])
            for r in client.execute_sql("SELECT sub_id, species_code FROM recent_observations")
        }
        checklist_species = {
            r[0]: r[1]
            for r in client.execute_sql(
                """
                SELECT sub_id, COUNT(DISTINCT species_code)
                FROM recent_observations
                GROUP BY sub_id
                ORDER BY COUNT(DISTINCT species_code) DESC
                """
            )
        }

    info_b = pipeline.run(_build_source())
    assert not info_b.has_failed_jobs

    with pipeline.sql_client() as client:
        snapshot_b = {
            r[0]: r[1]
            for r in client.execute_sql(
                "SELECT 'recent_observations' AS t, COUNT(*) FROM recent_observations"
            )
        }
        identities_b = {
            (r[0], r[1])
            for r in client.execute_sql("SELECT sub_id, species_code FROM recent_observations")
        }

    assert snapshot_a == snapshot_b, (
        f"row count drifted across reruns: before={snapshot_a} after={snapshot_b}"
    )
    assert identities_a == identities_b, "primary-key set drifted across reruns"
    assert identities_a, "expected at least one row to test against"
    assert snapshot_a["recent_observations"] == len(identities_a)
    assert snapshot_b["recent_observations"] == len(identities_b)
    assert max(checklist_species.values()) >= 2, (
        "fixture must retain multiple species per checklist"
    )
