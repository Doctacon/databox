"""Idempotency test: re-running eBird load against identical fixture data
must leave the final row set unchanged.

Uses `recent_observations` (write_disposition=merge, primary_key=subId).
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
        pks_a = {r[0] for r in client.execute_sql("SELECT sub_id FROM recent_observations")}

    info_b = pipeline.run(_build_source())
    assert not info_b.has_failed_jobs

    with pipeline.sql_client() as client:
        snapshot_b = {
            r[0]: r[1]
            for r in client.execute_sql(
                "SELECT 'recent_observations' AS t, COUNT(*) FROM recent_observations"
            )
        }
        pks_b = {r[0] for r in client.execute_sql("SELECT sub_id FROM recent_observations")}

    assert snapshot_a == snapshot_b, (
        f"row count drifted across reruns: before={snapshot_a} after={snapshot_b}"
    )
    assert pks_a == pks_b, "primary-key set drifted across reruns"
    assert pks_a, "expected at least one row to test against"
