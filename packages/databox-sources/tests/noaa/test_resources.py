"""Unit tests for NOAA CDO dlt resources."""

from __future__ import annotations

import pytest
from databox_sources.noaa.source import noaa_source

# NOAA GHCND daily data lags by several days and the `noaa_source` builds its
# date range off `pendulum.now()`. Freeze to a past date with confirmed coverage
# so both the cassette and the replayed request URL stay stable.
FROZEN_NOW = "2026-02-15T00:00:00Z"


@pytest.mark.vcr
@pytest.mark.time_machine(FROZEN_NOW)
def test_daily_weather_returns_rows():
    source = noaa_source(
        location_id="FIPS:11",
        dataset_id="GHCND",
        days_back=7,
        datatypes="TMAX",
    )
    rows = list(source.resources["daily_weather"])

    assert len(rows) > 0, "expected at least one NOAA weather reading"

    sample = rows[0]
    for key in ("date", "datatype", "station", "value", "_location_id", "_loaded_at"):
        assert key in sample, f"missing expected key '{key}' in row {sample!r}"

    assert sample["_location_id"] == "FIPS:11"
    assert sample["datatype"] == "TMAX"
    if sample.get("value") is not None:
        assert isinstance(sample["value"], float)
