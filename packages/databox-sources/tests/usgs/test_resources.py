"""Unit tests for USGS NWIS dlt resources."""

from __future__ import annotations

import pytest
from databox_sources.usgs.source import usgs_source

FROZEN_NOW = "2026-02-15T00:00:00Z"


@pytest.mark.vcr
@pytest.mark.time_machine(FROZEN_NOW)
def test_daily_values_returns_rows():
    source = usgs_source(state_cd="RI", parameter_cds="00060", days_back=3)
    rows = list(source.resources["daily_values"])

    assert len(rows) > 0, "expected at least one USGS daily streamflow reading"

    sample = rows[0]
    for key in (
        "site_no",
        "parameter_cd",
        "observation_date",
        "value",
        "_state_cd",
        "_loaded_at",
    ):
        assert key in sample, f"missing expected key '{key}' in row {sample!r}"

    assert sample["_state_cd"] == "RI"
    assert sample["parameter_cd"] == "00060"
    if sample.get("value") is not None:
        assert isinstance(sample["value"], float)
    if sample.get("latitude") is not None:
        assert isinstance(sample["latitude"], float)
