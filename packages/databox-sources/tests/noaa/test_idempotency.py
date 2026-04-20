"""Idempotency test: re-running NOAA CDO load against identical fixture data
must leave the final row set unchanged.

Uses `daily_weather` (write_disposition=merge, primary_key=(date, datatype, station)).
"""

from __future__ import annotations

import pytest
from databox_sources.noaa.source import noaa_source

FROZEN_NOW = "2026-02-15T00:00:00Z"


def _build_source():
    return noaa_source(
        location_id="FIPS:11",
        dataset_id="GHCND",
        days_back=7,
        datatypes="TMAX",
    ).with_resources("daily_weather")


@pytest.mark.vcr
@pytest.mark.time_machine(FROZEN_NOW)
def test_noaa_daily_weather_idempotent(memory_duckdb_pipeline_factory):
    pipeline = memory_duckdb_pipeline_factory(pipeline_name="noaa_idempotency")

    info_a = pipeline.run(_build_source())
    assert not info_a.has_failed_jobs

    with pipeline.sql_client() as client:
        count_a = client.execute_sql("SELECT COUNT(*) FROM daily_weather")[0][0]
        pks_a = {
            (r[0], r[1], r[2])
            for r in client.execute_sql("SELECT date, datatype, station FROM daily_weather")
        }

    info_b = pipeline.run(_build_source())
    assert not info_b.has_failed_jobs

    with pipeline.sql_client() as client:
        count_b = client.execute_sql("SELECT COUNT(*) FROM daily_weather")[0][0]
        pks_b = {
            (r[0], r[1], r[2])
            for r in client.execute_sql("SELECT date, datatype, station FROM daily_weather")
        }

    assert count_a == count_b, f"row count drifted: before={count_a} after={count_b}"
    assert pks_a == pks_b, "primary-key set drifted across reruns"
    assert pks_a, "expected at least one row to test against"
