"""Resource tests for the bounded USGS Earthquakes feed."""

from __future__ import annotations

import pytest
from databox.orchestration.domains.usgs_earthquakes import _build_source
from databox_sources.usgs_earthquakes.source import USGS_EARTHQUAKES_FEED


@pytest.mark.vcr
def test_events_resource_returns_feed_rows() -> None:
    source = _build_source()
    source.add_limit(max_items=2)
    rows = list(source.resources["events"])

    assert len(rows) == 2
    assert all(row["id"] for row in rows)
    assert all(row["event_time"] for row in rows)
    assert all(row["_loaded_at"] for row in rows)
    assert USGS_EARTHQUAKES_FEED.startswith("https://earthquake.usgs.gov/")
