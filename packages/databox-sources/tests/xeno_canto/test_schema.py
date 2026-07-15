"""Schema snapshot test for bounded Xeno-canto metadata."""

from __future__ import annotations

import pytest
from databox.orchestration.domains.xeno_canto import _build_source


def _source():
    return _build_source(max_records=2, per_page=2)


@pytest.mark.vcr
def test_xeno_canto_schema_snapshot(memory_duckdb_pipeline_factory, snapshot, normalize_schema):
    pipeline = memory_duckdb_pipeline_factory(pipeline_name="xeno_canto_schema_test")
    info = pipeline.run(_source())
    assert not info.has_failed_jobs
    assert normalize_schema(pipeline.default_schema.to_pretty_yaml()) == snapshot
