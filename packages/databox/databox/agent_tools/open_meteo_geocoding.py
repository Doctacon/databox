"""Bounded Open-Meteo geocoding for Arizona trip locations."""

from __future__ import annotations

import json
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any, Literal, cast
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import urlopen

from databox.agent_tools.arizona_boundary import is_in_arizona

GEOCODING_ENDPOINT = "https://geocoding-api.open-meteo.com/v1/search"
MAX_GEOCODING_RESULTS = 5
ARIZONA_REGION_CODE = "US-AZ"
ARIZONA_TIMEZONE = "America/Phoenix"

JsonGetter = Callable[[str, Mapping[str, object]], dict[str, Any]]


class OpenMeteoGeocodingError(RuntimeError):
    """Safe geocoder failure suitable for the local API boundary."""


@dataclass(frozen=True)
class ArizonaLocationSuggestion:
    """Stable browser-safe Arizona place suggestion."""

    display_name: str
    latitude: float
    longitude: float
    timezone: str
    region_code: str
    source: Literal["ebird_hotspot", "open_meteo"]
    source_id: str
    place_type: Literal["Birding hotspot", "Arizona place"]


def search_arizona_locations(
    query: str,
    *,
    limit: int = MAX_GEOCODING_RESULTS,
    http_get_json: JsonGetter | None = None,
) -> list[ArizonaLocationSuggestion]:
    """Return bounded Arizona place matches from Open-Meteo geocoding."""

    normalized_query = normalize_geocoding_query(query)
    if len(normalized_query) < 2:
        return []
    bounded_limit = min(max(limit, 1), MAX_GEOCODING_RESULTS)
    getter = http_get_json or _default_get_json
    try:
        response = getter(
            GEOCODING_ENDPOINT,
            {
                "name": normalized_query,
                "count": bounded_limit,
                "language": "en",
                "format": "json",
            },
        )
    except OpenMeteoGeocodingError:
        raise
    except (TimeoutError, URLError):
        raise OpenMeteoGeocodingError("Open-Meteo geocoding is temporarily unavailable") from None
    raw_results = response.get("results")
    if not isinstance(raw_results, list):
        return []

    suggestions: list[ArizonaLocationSuggestion] = []
    for raw in raw_results:
        if not isinstance(raw, dict) or not _is_arizona_result(raw):
            continue
        name = _text(raw.get("name"))
        source_id = raw.get("id")
        admin1 = _text(raw.get("admin1"))
        country = _text(raw.get("country"))
        latitude = _number(raw.get("latitude"))
        longitude = _number(raw.get("longitude"))
        timezone = ARIZONA_TIMEZONE
        if (
            not name
            or isinstance(source_id, bool)
            or not isinstance(source_id, int)
            or not 0 < source_id <= 9_999_999_999
            or latitude is None
            or longitude is None
            or not is_in_arizona(latitude, longitude)
        ):
            continue
        display_parts = [name]
        if admin1:
            display_parts.append(admin1)
        if country:
            display_parts.append(country)
        display_name = ", ".join(display_parts)
        suggestions.append(
            ArizonaLocationSuggestion(
                display_name=display_name,
                latitude=latitude,
                longitude=longitude,
                timezone=timezone,
                region_code=ARIZONA_REGION_CODE,
                source="open_meteo",
                source_id=f"open_meteo_{source_id}",
                place_type="Arizona place",
            )
        )
        if len(suggestions) >= bounded_limit:
            break
    return suggestions


def normalize_geocoding_query(query: str) -> str:
    """Use the place-name segment so `Prescott, Arizona` matches Open-Meteo."""

    return query.strip().split(",", 1)[0].strip()[:100]


def _is_arizona_result(raw: Mapping[str, object]) -> bool:
    admin1 = (_text(raw.get("admin1")) or "").casefold()
    country_code = (_text(raw.get("country_code")) or "").upper()
    country = (_text(raw.get("country")) or "").casefold()
    return admin1 == "arizona" and (country_code == "US" or country == "united states")


def _text(value: object) -> str | None:
    return value.strip() if isinstance(value, str) and value.strip() else None


def _number(value: object) -> float | None:
    if isinstance(value, bool):
        return None
    return float(value) if isinstance(value, int | float) else None


def _default_get_json(endpoint: str, params: Mapping[str, object]) -> dict[str, Any]:
    query = urlencode({key: str(value) for key, value in params.items()})
    try:
        with urlopen(f"{endpoint}?{query}", timeout=10) as response:  # noqa: S310
            body = response.read().decode("utf-8")
    except HTTPError:
        raise OpenMeteoGeocodingError("Open-Meteo geocoding is temporarily unavailable") from None
    except (TimeoutError, URLError):
        raise OpenMeteoGeocodingError("Open-Meteo geocoding is temporarily unavailable") from None
    try:
        parsed = json.loads(body)
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise OpenMeteoGeocodingError("Open-Meteo geocoding returned invalid data") from None
    if not isinstance(parsed, dict):
        raise OpenMeteoGeocodingError("Open-Meteo geocoding returned invalid data")
    return cast(dict[str, Any], parsed)
