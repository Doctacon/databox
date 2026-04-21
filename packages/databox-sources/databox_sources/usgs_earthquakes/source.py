"""USGS Earthquake Hazards Program source pipeline using dlt.

Data: rolling 24-hour summary of all detected earthquakes worldwide.
No API key required.

Feed: https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/all_day.geojson
Schema doc: https://earthquake.usgs.gov/earthquakes/feed/v1.0/geojson.php
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

import dlt
import pendulum
from dlt.sources.helpers import requests as dlt_requests

from databox_sources._logging import get_logger

log = get_logger("databox_sources.usgs_earthquakes")

USGS_EARTHQUAKES_FEED = "https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/all_day.geojson"


def _flatten_feature(feature: dict[str, Any], loaded_at: str) -> dict[str, Any]:
    props = feature.get("properties", {}) or {}
    geom = feature.get("geometry", {}) or {}
    coords = geom.get("coordinates") or [None, None, None]
    lon, lat, depth = (coords + [None, None, None])[:3]

    def _ms_to_iso(ms: int | None) -> str | None:
        if ms is None:
            return None
        return pendulum.from_timestamp(ms / 1000).to_iso8601_string()

    return {
        "id": feature.get("id"),
        "magnitude": props.get("mag"),
        "magnitude_type": props.get("magType"),
        "place": props.get("place"),
        "title": props.get("title"),
        "event_time": _ms_to_iso(props.get("time")),
        "event_updated_at": _ms_to_iso(props.get("updated")),
        "longitude": lon,
        "latitude": lat,
        "depth_km": depth,
        "status": props.get("status"),
        "tsunami_flag": props.get("tsunami"),
        "significance": props.get("sig"),
        "event_type": props.get("type"),
        "alert": props.get("alert"),
        "url": props.get("url"),
        "_loaded_at": loaded_at,
    }


@dlt.source
def usgs_earthquakes_source() -> Any:
    loaded_at = pendulum.now().isoformat()

    @dlt.resource(
        primary_key="id",
        write_disposition="merge",
        columns={
            "id": {"data_type": "text"},
            "magnitude": {"data_type": "double"},
            "magnitude_type": {"data_type": "text"},
            "place": {"data_type": "text"},
            "title": {"data_type": "text"},
            "event_time": {"data_type": "text"},
            "event_updated_at": {"data_type": "text"},
            "longitude": {"data_type": "double"},
            "latitude": {"data_type": "double"},
            "depth_km": {"data_type": "double"},
            "status": {"data_type": "text"},
            "tsunami_flag": {"data_type": "bigint"},
            "significance": {"data_type": "bigint"},
            "event_type": {"data_type": "text"},
            "alert": {"data_type": "text"},
            "url": {"data_type": "text"},
            "_loaded_at": {"data_type": "timestamp"},
        },
    )
    def events() -> Iterator[dict[str, Any]]:
        response = dlt_requests.get(
            USGS_EARTHQUAKES_FEED, headers={"Accept": "application/geo+json"}
        )
        response.raise_for_status()
        data = response.json()
        features = data.get("features", [])
        log.info("events_fetched", count=len(features))
        for feature in features:
            if feature.get("id"):
                yield _flatten_feature(feature, loaded_at)

    return [events]
