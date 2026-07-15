"""Schema snapshot test for bounded GBIF occurrence metadata."""

from __future__ import annotations

import pytest
from databox.orchestration.domains.gbif import _build_source


def _source():
    return _build_source(max_records=2)


@pytest.mark.vcr
def test_gbif_schema_snapshot(memory_duckdb_pipeline_factory, snapshot, normalize_schema):
    pipeline = memory_duckdb_pipeline_factory(pipeline_name="gbif_schema_test")
    info = pipeline.run(_source())
    assert not info.has_failed_jobs
    assert normalize_schema(pipeline.default_schema.to_pretty_yaml()) == snapshot
