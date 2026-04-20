"""Schema snapshot tests for eBird dlt source.

A subset of resources (recent_observations, hotspots, species_list) is loaded
into an in-memory duckdb so we can capture the inferred schema. The full
taxonomy resource is excluded because its response body is several MB and
would dominate cassette size without adding schema coverage beyond what the
other resources give us.

If this test fails, a column was added/removed/retyped. Review the diff,
decide whether it's an intentional change, and re-run with --snapshot-update.
"""

from __future__ import annotations

import pytest
from databox_sources.ebird.source import ebird_source


@pytest.mark.vcr
def test_ebird_schema_snapshot(memory_duckdb_pipeline_factory, snapshot, normalize_schema):
    source = ebird_source(region_code="US-DC", max_results=50, days_back=1)
    source = source.with_resources("recent_observations", "hotspots", "species_list")

    pipeline = memory_duckdb_pipeline_factory(pipeline_name="ebird_schema_test")
    info = pipeline.run(source)
    assert not info.has_failed_jobs

    schema_yaml = pipeline.default_schema.to_pretty_yaml()
    assert normalize_schema(schema_yaml) == snapshot
