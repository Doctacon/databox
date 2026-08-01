"""Unit tests for eBird dlt resources."""

from __future__ import annotations

import pytest
from databox_sources.ebird.source import ebird_source


@pytest.mark.parametrize("resource_name", ["recent_observations", "notable_observations"])
def test_observation_resources_merge_by_checklist_and_species(resource_name: str) -> None:
    resource = ebird_source().resources[resource_name]
    schema = resource.compute_table_schema()

    assert schema["write_disposition"] == "merge"
    assert {name for name, column in schema["columns"].items() if column.get("primary_key")} == {
        "subId",
        "speciesCode",
    }


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
