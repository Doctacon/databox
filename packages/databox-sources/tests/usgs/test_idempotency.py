"""Idempotency test: re-running USGS load against identical fixture data
must leave the final row set unchanged.

Uses `daily_values`: write_disposition=merge,
primary_key=(site_no, parameter_cd, observation_date).
"""

from __future__ import annotations

import pytest
from databox_sources.usgs.source import usgs_source

FROZEN_NOW = "2026-02-15T00:00:00Z"


def _build_source():
    return usgs_source(state_cd="RI", parameter_cds="00060", days_back=3).with_resources(
        "daily_values"
    )


@pytest.mark.vcr
@pytest.mark.time_machine(FROZEN_NOW)
def test_usgs_daily_values_idempotent(memory_duckdb_pipeline_factory):
    pipeline = memory_duckdb_pipeline_factory(pipeline_name="usgs_idempotency")

    info_a = pipeline.run(_build_source())
    assert not info_a.has_failed_jobs

    with pipeline.sql_client() as client:
        count_a = client.execute_sql("SELECT COUNT(*) FROM daily_values")[0][0]
        pks_a = {
            (r[0], r[1], r[2])
            for r in client.execute_sql(
                "SELECT site_no, parameter_cd, observation_date FROM daily_values"
            )
        }

    info_b = pipeline.run(_build_source())
    assert not info_b.has_failed_jobs

    with pipeline.sql_client() as client:
        count_b = client.execute_sql("SELECT COUNT(*) FROM daily_values")[0][0]
        pks_b = {
            (r[0], r[1], r[2])
            for r in client.execute_sql(
                "SELECT site_no, parameter_cd, observation_date FROM daily_values"
            )
        }

    assert count_a == count_b, f"row count drifted: before={count_a} after={count_b}"
    assert pks_a == pks_b, "primary-key set drifted across reruns"
    assert pks_a, "expected at least one row to test against"
