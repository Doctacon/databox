"""Unit tests for eBird dlt resources."""

from __future__ import annotations

import pytest
from databox_sources.ebird.source import ebird_source


@pytest.mark.vcr
def test_recent_observations_returns_rows():
    source = ebird_source(region_code="US-DC", max_results=50, days_back=1)
    rows = list(source.resources["recent_observations"])

    assert len(rows) > 0, "expected at least one eBird observation"

    sample = rows[0]
    for key in ("speciesCode", "subId", "obsDt", "_region_code", "_loaded_at"):
        assert key in sample, f"missing expected key '{key}' in row {sample!r}"

    assert sample["_region_code"] == "US-DC"
    if sample.get("lat") is not None:
        assert isinstance(sample["lat"], float)
    if sample.get("lng") is not None:
        assert isinstance(sample["lng"], float)
