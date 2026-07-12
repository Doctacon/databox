"""Strict local-first Arizona place suggestions."""

from __future__ import annotations

import math
import re
import unicodedata
from collections import Counter
from dataclasses import dataclass

import duckdb

from databox.agent_tools.arizona_boundary import is_in_arizona
from databox.agent_tools.open_meteo_geocoding import (
    ARIZONA_REGION_CODE,
    ARIZONA_TIMEZONE,
    ArizonaLocationSuggestion,
)

_SOURCE_ID = re.compile(r"^[A-Za-z0-9_-]{1,64}$")
_CONTROL = re.compile(r"[\x00-\x1f\x7f]")


@dataclass(frozen=True)
class LocalHotspotSearch:
    suggestions: list[ArizonaLocationSuggestion]
    has_exact_name: bool


def normalize_place_text(value: str) -> str:
    """Normalize case, accents, punctuation, and whitespace for matching."""

    decomposed = unicodedata.normalize("NFKD", value).casefold()
    ascii_text = "".join(
        character for character in decomposed if not unicodedata.combining(character)
    )
    return " ".join(re.findall(r"[a-z0-9]+", ascii_text))


def search_local_hotspots(
    connection: duckdb.DuckDBPyConnection,
    query: str,
    *,
    limit: int = 5,
) -> LocalHotspotSearch:
    """Return deterministic valid current Arizona hotspot matches."""

    normalized_query = normalize_place_text(query[:100])
    tokens = tuple(normalized_query.split())
    if len(normalized_query) < 2 or not tokens:
        return LocalHotspotSearch([], False)
    bounded_limit = min(max(limit, 1), 5)
    rows = connection.execute(
        """
        SELECT
            source_pipeline, source_id, location_id, location_name,
            region_code, latitude, longitude, num_checklists_all_time
        FROM environmental_observations.dim_bird_hotspot
        WHERE region_code = 'US-AZ'
        """
    ).fetchall()
    identifiers = Counter(row[2] for row in rows if isinstance(row[2], str) and row[2].strip())
    ranked: list[tuple[tuple[object, ...], ArizonaLocationSuggestion, bool]] = []
    for row in rows:
        source_pipeline, source_id, location_id, name, region, latitude, longitude, checklists = row
        if (
            source_pipeline != "ebird_api"
            or region != ARIZONA_REGION_CODE
            or not isinstance(source_id, str)
            or not isinstance(location_id, str)
            or source_id != location_id
            or _SOURCE_ID.fullmatch(location_id) is None
            or identifiers[location_id] != 1
            or not isinstance(name, str)
            or not 0 < len(name) <= 300
            or not name.strip()
            or _CONTROL.search(name) is not None
            or isinstance(latitude, bool)
            or not isinstance(latitude, int | float)
            or not math.isfinite(latitude)
            or isinstance(longitude, bool)
            or not isinstance(longitude, int | float)
            or not math.isfinite(longitude)
            or not is_in_arizona(float(latitude), float(longitude))
            or (
                checklists is not None
                and (
                    isinstance(checklists, bool)
                    or not isinstance(checklists, int)
                    or checklists < 0
                )
            )
        ):
            continue
        normalized_name = normalize_place_text(name)
        positions = tuple(normalized_name.find(token) for token in tokens)
        if any(position < 0 for position in positions):
            continue
        ends = tuple(
            position + len(token) for position, token in zip(positions, tokens, strict=True)
        )
        exact = normalized_name == normalized_query
        rank = (
            0 if exact else 1,
            0 if normalized_name.startswith(normalized_query) else 1,
            min(positions),
            max(ends) - min(positions),
            sum(positions),
            -(checklists if isinstance(checklists, int) else -1),
            normalized_name,
            location_id,
        )
        ranked.append(
            (
                rank,
                ArizonaLocationSuggestion(
                    display_name=name.strip(),
                    latitude=float(latitude),
                    longitude=float(longitude),
                    timezone=ARIZONA_TIMEZONE,
                    region_code=ARIZONA_REGION_CODE,
                    source="ebird_hotspot",
                    source_id=location_id,
                    place_type="Birding hotspot",
                ),
                exact,
            )
        )
    ranked.sort(key=lambda item: item[0])
    selected: list[tuple[tuple[object, ...], ArizonaLocationSuggestion, bool]] = []
    for item in ranked:
        candidate = item[1]
        normalized = normalize_place_text(candidate.display_name)
        if any(
            normalize_place_text(existing[1].display_name) == normalized
            and abs(existing[1].latitude - candidate.latitude) <= 0.001
            and abs(existing[1].longitude - candidate.longitude) <= 0.001
            for existing in selected
        ):
            continue
        selected.append(item)
        if len(selected) >= bounded_limit:
            break
    return LocalHotspotSearch(
        suggestions=[item[1] for item in selected],
        has_exact_name=any(item[2] for item in selected),
    )


def merge_fallback_suggestions(
    local: list[ArizonaLocationSuggestion],
    fallback: list[ArizonaLocationSuggestion],
    *,
    limit: int = 5,
) -> list[ArizonaLocationSuggestion]:
    """Merge bounded fallback rows with deterministic local-first near deduplication."""

    bounded_limit = min(max(limit, 1), 5)
    result: list[ArizonaLocationSuggestion] = []
    source_ids: set[tuple[str, str]] = set()
    for candidate in [*local, *fallback]:
        if len(result) >= bounded_limit:
            break
        if (candidate.source, candidate.source_id) in source_ids:
            continue
        normalized = normalize_place_text(candidate.display_name)
        if any(
            normalize_place_text(existing.display_name) == normalized
            and abs(existing.latitude - candidate.latitude) <= 0.001
            and abs(existing.longitude - candidate.longitude) <= 0.001
            for existing in result
        ):
            continue
        result.append(candidate)
        source_ids.add((candidate.source, candidate.source_id))
    return result
