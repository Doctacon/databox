"""Deterministic Open-Meteo Arizona geocoding tests."""

import socket
from collections.abc import Mapping
from typing import Any
from urllib.error import HTTPError, URLError

import pytest
from databox.agent_tools.open_meteo_geocoding import (
    GEOCODING_ENDPOINT,
    OpenMeteoGeocodingError,
    normalize_geocoding_query,
    search_arizona_locations,
)


def test_search_normalizes_suffix_filters_arizona_and_bounds_count() -> None:
    observed: dict[str, object] = {}

    def getter(endpoint: str, params: Mapping[str, object]) -> dict[str, Any]:
        observed.update(params)
        assert endpoint == GEOCODING_ENDPOINT
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
                    "id": 1,
                    "name": "Border Error",
                    "admin1": "Arizona",
                    "country": "United States",
                    "country_code": "US",
                    "latitude": 36.9,
                    "longitude": -114.8,
                    "timezone": "America/Phoenix",
                },
                {
                    "id": 4126226,
                    "name": "Prescott",
                    "admin1": "Arkansas",
                    "country": "United States",
                    "country_code": "US",
                    "latitude": 33.80261,
                    "longitude": -93.38101,
                    "timezone": "America/Chicago",
                },
            ]
        }

    results = search_arizona_locations(" Prescott, Arizona ", limit=100, http_get_json=getter)

    assert observed == {"name": "Prescott", "count": 5, "language": "en", "format": "json"}
    assert len(results) == 1
    assert results[0].display_name == "Prescott, Arizona, United States"
    assert results[0].region_code == "US-AZ"
    assert results[0].source_id == "open_meteo_5309842"
    assert results[0].place_type == "Arizona place"


@pytest.mark.parametrize(
    "failure",
    [
        TimeoutError("timed out"),
        socket.timeout("socket timed out"),  # noqa: UP041
        URLError("network unavailable"),
        HTTPError(GEOCODING_ENDPOINT, 503, "unavailable", {}, None),
    ],
)
def test_transport_failures_normalize_to_safe_typed_error(failure: BaseException) -> None:
    def getter(endpoint: str, params: Mapping[str, object]) -> dict[str, Any]:
        _ = endpoint, params
        raise failure

    with pytest.raises(
        OpenMeteoGeocodingError,
        match="Open-Meteo geocoding is temporarily unavailable",
    ):
        search_arizona_locations("Prescott", http_get_json=getter)


def test_short_query_does_not_call_upstream() -> None:
    def getter(endpoint: str, params: Mapping[str, object]) -> dict[str, Any]:
        raise AssertionError(f"unexpected geocoder call: {endpoint} {params}")

    assert search_arizona_locations("P", http_get_json=getter) == []
    assert normalize_geocoding_query("Prescott, AZ") == "Prescott"
