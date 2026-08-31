"""Deterministic bounded Census-derived Arizona map geometry artifact."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

ARTIFACT = Path("app/src/assets/arizona-boundaries.geojson")


def test_arizona_boundary_artifact_is_exact_compact_and_bounded() -> None:
    raw = ARTIFACT.read_bytes()
    assert len(raw) == 30_927
    assert (
        hashlib.sha256(raw).hexdigest()
        == "e326985b9f3dd3baa9c98f5cfbd7ea310588af0e43dc00e6c2a0323a0eab163b"
    )
    document = json.loads(raw)
    assert set(document) == {"type", "features"}
    assert document["type"] == "FeatureCollection"
    features = document["features"]
    assert len(features) == 16
    assert [feature["properties"] for feature in features] == [
        {"kind": "state", "geoid": "04", "name": "Arizona"},
        *[
            {"kind": "county", "geoid": geoid, "name": name}
            for geoid, name in [
                ("04001", "Apache County"),
                ("04003", "Cochise County"),
                ("04005", "Coconino County"),
                ("04007", "Gila County"),
                ("04009", "Graham County"),
                ("04011", "Greenlee County"),
                ("04012", "La Paz County"),
                ("04013", "Maricopa County"),
                ("04015", "Mohave County"),
                ("04017", "Navajo County"),
                ("04019", "Pima County"),
                ("04021", "Pinal County"),
                ("04023", "Santa Cruz County"),
                ("04025", "Yavapai County"),
                ("04027", "Yuma County"),
            ]
        ],
    ]
    for feature in features:
        assert set(feature) == {"type", "properties", "geometry"}
        assert feature["type"] == "Feature"
        assert set(feature["properties"]) == {"kind", "geoid", "name"}
        assert feature["geometry"]["type"] in {"Polygon", "MultiPolygon"}
        assert feature["properties"]["geoid"].startswith("04")
