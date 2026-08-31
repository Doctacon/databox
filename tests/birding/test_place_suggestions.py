"""Local-first Arizona place suggestion contract tests."""

from __future__ import annotations

import hashlib
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import duckdb
from databox.agent_tools.open_meteo_geocoding import ArizonaLocationSuggestion
from databox.api import create_app
from databox.place_suggestions import (
    merge_fallback_suggestions,
    normalize_place_text,
    search_local_hotspots,
)
from fastapi.testclient import TestClient


def _database(path: Path, rows: list[tuple[object, ...]]) -> None:
    connection = duckdb.connect(str(path))
    connection.execute("CREATE SCHEMA environmental_observations")
    connection.execute(
        """
        CREATE TABLE environmental_observations.dim_bird_hotspot (
            source_pipeline VARCHAR, source_id VARCHAR, location_id VARCHAR,
            location_name VARCHAR, region_code VARCHAR, latitude DOUBLE,
            longitude DOUBLE, num_checklists_all_time BIGINT
        )
        """
    )
    connection.executemany(
        "INSERT INTO environmental_observations.dim_bird_hotspot VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        rows,
    )
    connection.execute("CREATE TABLE private_observations(secret VARCHAR)")
    connection.execute("INSERT INTO private_observations VALUES ('never expose me')")
    connection.close()


def _row(identifier: str, name: str, checklists: int = 10) -> tuple[object, ...]:
    return (
        "ebird_api",
        identifier,
        identifier,
        name,
        "US-AZ",
        34.5822319,
        -112.4259328,
        checklists,
    )


def test_token_order_normalization_ranking_and_invalid_rows_fail_closed(tmp_path: Path) -> None:
    database = tmp_path / "places.duckdb"
    rows = [
        _row("L_WATSON", "Watson Lake and Riparian Preserve", 6662),
        _row("L_LOW", "Watson Scenic Lake", 2),
        _row("L_NEAR", "WÁTSON-LAKE AND RIPARIAN PRESERVE", 1),
        _row("L_DUP", "Watson Lake Duplicate", 100),
        _row("L_DUP", "Watson Lake Duplicate Poison", 200),
        ("wrong", "L_BAD_SOURCE", "L_BAD_SOURCE", "Watson Lake Bad", "US-AZ", 34.5, -112.4, 999),
        ("ebird_api", "L_OUT", "L_OUT", "Watson Lake Outside", "US-AZ", 40.0, -112.4, 999),
        _row("L_CONTROL", "Watson\nLake", 999),
    ]
    _database(database, rows)
    connection = duckdb.connect(str(database), read_only=True)
    try:
        forward = search_local_hotspots(connection, "  lake, WÁTSON!! ").suggestions
        reverse = search_local_hotspots(connection, "watson lake").suggestions
    finally:
        connection.close()

    assert normalize_place_text("  Lake, WÁTSON!! ") == "lake watson"
    assert [item.source_id for item in forward] == ["L_WATSON", "L_LOW"]
    assert [item.source_id for item in reverse] == ["L_WATSON", "L_LOW"]
    assert forward[0].place_type == "Birding hotspot"
    assert all(item.source == "ebird_hotspot" for item in forward)


def test_watson_local_result_avoids_upstream_and_get_is_private_read_only(tmp_path: Path) -> None:
    database = tmp_path / "places.duckdb"
    _database(database, [_row("L270303", "Watson Lake and Riparian Preserve", 6662)])
    before = hashlib.sha256(database.read_bytes()).hexdigest()
    calls = 0

    def forbidden_upstream(endpoint: str, params: Mapping[str, object]) -> dict[str, Any]:
        nonlocal calls
        calls += 1
        raise AssertionError(f"unexpected upstream call: {endpoint} {params}")

    client = TestClient(
        create_app(database_path=str(database), geocoding_getter=forbidden_upstream)
    )
    response = client.get("/api/locations", params={"q": "lake watson"})

    assert response.status_code == 200
    assert calls == 0
    assert response.json() == {
        "locations": [
            {
                "display_name": "Watson Lake and Riparian Preserve",
                "latitude": 34.5822319,
                "longitude": -112.4259328,
                "timezone": "America/Phoenix",
                "region_code": "US-AZ",
                "source": "ebird_hotspot",
                "source_id": "L270303",
                "place_type": "Birding hotspot",
            }
        ]
    }
    assert "never expose me" not in response.text
    assert hashlib.sha256(database.read_bytes()).hexdigest() == before


def test_zero_local_fallback_and_near_duplicate_local_wins(tmp_path: Path) -> None:
    database = tmp_path / "places.duckdb"
    _database(database, [_row("L270303", "Watson Lake", 10)])
    calls = 0

    def upstream(endpoint: str, params: Mapping[str, object]) -> dict[str, Any]:
        nonlocal calls
        calls += 1
        return {
            "results": [
                {
                    "id": 5309842,
                    "name": "Prescott",
                    "admin1": "Arizona",
                    "country": "United States",
                    "country_code": "US",
                    "latitude": 34.54002,
                    "longitude": -112.4685,
                    "timezone": "America/Phoenix",
                },
                {
                    "id": 5309843,
                    "name": "PRESCOTT!",
                    "admin1": "Arizona",
                    "country": "United States",
                    "country_code": "US",
                    "latitude": 34.5405,
                    "longitude": -112.468,
                    "timezone": "America/Phoenix",
                },
            ]
        }

    client = TestClient(create_app(database_path=str(database), geocoding_getter=upstream))
    local_response = client.get("/api/locations", params={"q": "Watson"})
    assert local_response.json()["locations"][0]["source"] == "ebird_hotspot"
    assert calls == 0
    fallback = client.get("/api/locations", params={"q": "Prescott"})
    assert fallback.status_code == 200
    assert fallback.json()["locations"][0]["source"] == "open_meteo"
    assert len(fallback.json()["locations"]) == 1
    assert calls == 1

    connection = duckdb.connect(str(database), read_only=True)
    try:
        local = search_local_hotspots(connection, "Watson").suggestions
    finally:
        connection.close()
    duplicate = ArizonaLocationSuggestion(
        display_name="WÁTSON-LAKE",
        latitude=34.5829,
        longitude=-112.4251,
        timezone="America/Phoenix",
        region_code="US-AZ",
        source="open_meteo",
        source_id="open_meteo_duplicate",
        place_type="Arizona place",
    )
    distinct = ArizonaLocationSuggestion(
        display_name="Watson Lake",
        latitude=34.59,
        longitude=-112.42,
        timezone="America/Phoenix",
        region_code="US-AZ",
        source="open_meteo",
        source_id="open_meteo_distinct",
        place_type="Arizona place",
    )
    merged = merge_fallback_suggestions(local, [duplicate, distinct])
    assert [item.source_id for item in merged] == ["L270303", "open_meteo_distinct"]
