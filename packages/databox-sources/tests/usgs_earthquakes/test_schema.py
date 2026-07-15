"""Schema snapshot test for bounded USGS Earthquakes metadata."""

from __future__ import annotations

import pytest
from databox.orchestration.domains.usgs_earthquakes import _build_source


def _source():
    source = _build_source()
    source.add_limit(max_items=2)
    return source


@pytest.mark.vcr
def test_usgs_earthquakes_schema_snapshot(
    memory_duckdb_pipeline_factory, snapshot, normalize_schema
):
    pipeline = memory_duckdb_pipeline_factory(pipeline_name="usgs_earthquakes_schema_test")
    info = pipeline.run(_source())
    assert not info.has_failed_jobs
    assert normalize_schema(pipeline.default_schema.to_pretty_yaml()) == snapshot
