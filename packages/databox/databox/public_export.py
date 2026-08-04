"""Build the privacy- and license-filtered static data contract for public Rufous.

The public build is deliberately separate from the local application database.  It
copies a small allowlist of fields into immutable JSON shards, never the DuckDB file.
Synthetic mode is completely offline and is the only mode used by pull requests.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
import re
import shutil
import stat
import tempfile
import unicodedata
import uuid
from collections import Counter, defaultdict
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any, Literal, cast
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo

import duckdb

from databox.agent_tools.arizona_boundary import is_in_arizona
from databox.public_media_approval import MediaApprovalError, require_visual_approvals

SCHEMA_VERSION = 1
REGION = {
    "code": "US-AZ",
    "name": "Arizona",
    "bounds": {"west": -114.82, "south": 31.33, "east": -109.04, "north": 37.01},
}
DEFAULT_TIMEZONE = "America/Phoenix"
MOUNTAIN_TIME_AMBIGUITY = {
    "south": 34.5,
    "west": -111.75,
}
MAX_GNIS_BYTES = 250 * 1024 * 1024
_SPECIES_CODE = re.compile(r"^[a-z0-9][a-z0-9-]{0,31}$")
_SHA256 = re.compile(r"^[a-f0-9]{64}$")
_PLACE_KEY = re.compile(r"[^a-z0-9]+")
_MEDIA_ID = re.compile(r"^usfws-[a-f0-9]{24}$")
_MEDIA_ATTRIBUTION_ID = re.compile(r"^usfws-attribution-[a-f0-9]{24}$")
_INATURALIST_MEDIA_ID = re.compile(r"^inaturalist-(?P<photo_id>[1-9][0-9]*)$")
_INATURALIST_ATTRIBUTION_ID = re.compile(r"^inaturalist-attribution-(?P<photo_id>[1-9][0-9]*)$")
_SCIENTIFIC_NAME = re.compile(r"^[A-Z][A-Za-z-]+ [a-z][A-Za-z-]+(?: [A-Za-z-]+)?$")
_SPECIES_BINOMIAL = re.compile(r"^[A-Z][A-Za-z-]+ [a-z][A-Za-z-]+$")
_USFWS_MEDIA_PAGE = re.compile(
    r"^https://www\.fws\.gov/media/[a-z0-9](?:[a-z0-9-]{0,238}[a-z0-9])?$"
)
_INATURALIST_PHOTO_PAGE = re.compile(
    r"^https://www\.inaturalist\.org/photos/(?P<photo_id>[1-9][0-9]*)$"
)
_PUBLIC_MEDIA_URL = re.compile(
    r"^https://rufous-data\.loughondata\.com/rufous-media/v1/objects/"
    r"(?P<shard>[a-f0-9]{2})/(?P<sha>[a-f0-9]{64})\.webp$"
)
MAX_MEDIA_MANIFEST_BYTES = 25 * 1024 * 1024
MAX_PUBLIC_ASSET_BYTES = 25 * 1024 * 1024
MAX_PUBLIC_ASSET_FILES = 20_000

_MEDIA_SOURCE_MARKERS = {
    frozenset(): "none",
    frozenset({"usfws"}): "usfws",
    frozenset({"inaturalist"}): "inaturalist",
    frozenset({"usfws", "inaturalist"}): "usfws+inaturalist",
}

_PUBLIC_MANIFEST_KEYS = frozenset(
    {
        "schema_version",
        "mode",
        "release_mode",
        "generated_at",
        "region",
        "species",
        "cells",
        "place_prefixes",
        "attribution_path",
        "source_policy",
        "license_policy",
        "counts",
        "data_version",
    }
)

GBIF_EBIRD_EOD_DATASET_KEY = "4fa7b334-ce0d-4e88-aaae-2e0c138d049e"
GBIF_EBIRD_EOD_DATASET_URL = "https://www.gbif.org/dataset/4fa7b334-ce0d-4e88-aaae-2e0c138d049e"
GBIF_EBIRD_EOD_PUBLISHER = "Cornell Lab of Ornithology"
GBIF_EBIRD_EOD_TABLE = "rufous_public.gbif_eod_occurrence"
GBIF_RUFOUS_TAXON_KEY = 2476855
GBIF_EBIRD_EOD_DISCLAIMER = (
    "No warranty either expressed or implied is made regarding the accuracy of these data."
)

ExportMode = Literal["synthetic", "production"]
JsonObject = dict[str, Any]

# This policy is intentionally narrower than what the upstream selectors accept.
# Public Rufous curates/resizes photos, so ND is not permitted either.
ALLOWED_LICENSES: dict[str, frozenset[str]] = {
    "inaturalist": frozenset({"CC0 1.0", "CC BY 4.0", "CC BY-SA 4.0"}),
    "xeno_canto": frozenset(
        {
            "CC0 1.0",
            "CC BY 1.0",
            "CC BY 2.0",
            "CC BY 2.5",
            "CC BY 3.0",
            "CC BY 4.0",
            "CC BY-SA 1.0",
            "CC BY-SA 2.0",
            "CC BY-SA 2.5",
            "CC BY-SA 3.0",
            "CC BY-SA 4.0",
        }
    ),
    "gbif": frozenset(
        {
            "CC0 1.0",
            "CC BY 1.0",
            "CC BY 2.0",
            "CC BY 2.5",
            "CC BY 3.0",
            "CC BY 4.0",
        }
    ),
    "usfws": frozenset(
        {
            "Public Domain",
            "CC0 1.0",
            "CC BY 1.0",
            "CC BY 2.0",
            "CC BY 2.5",
            "CC BY 3.0",
            "CC BY 4.0",
            "CC BY-SA 1.0",
            "CC BY-SA 2.0",
            "CC BY-SA 2.5",
            "CC BY-SA 3.0",
            "CC BY-SA 4.0",
        }
    ),
}


class PublicExportError(RuntimeError):
    """The source material cannot safely satisfy the public contract."""


@dataclass(frozen=True)
class _ValidatedPublicOutput:
    kind: str
    content_identity: str | None = None

    @property
    def state(self) -> tuple[str, str | None]:
        return self.kind, self.content_identity


@dataclass
class PublicRecords:
    species: list[JsonObject]
    observations: list[JsonObject]
    places: list[JsonObject]
    attribution_items: list[JsonObject]
    rejected: Counter[str]
    source_generated_at: str | None = None


def canonical_license(provider: str, value: object) -> tuple[str, str] | None:
    """Normalize a Creative Commons label/URL and enforce the provider allowlist."""
    if not isinstance(value, str) or not value.strip() or provider not in ALLOWED_LICENSES:
        return None
    raw = value.strip()
    if provider == "usfws" and raw == "Public Domain":
        return "Public Domain", "https://www.fws.gov/notices"
    if "://" in raw:
        try:
            parsed = urlsplit(raw)
        except ValueError:
            return None
        if (
            parsed.scheme.casefold() not in {"http", "https"}
            or parsed.hostname not in {"creativecommons.org", "www.creativecommons.org"}
            or parsed.username is not None
            or parsed.password is not None
            or parsed.port is not None
            or parsed.query
            or parsed.fragment
        ):
            return None
        match = re.fullmatch(
            r"/(?:licenses/(?P<slug>by(?:-sa|-nc|-nd|-nc-sa|-nc-nd)?)|"
            r"publicdomain/(?P<zero>zero))/(?P<version>[0-9]+(?:\.[0-9]+)?)"
            r"(?:/legalcode)?/?",
            parsed.path.casefold(),
        )
        if not match:
            return None
        slug = match.group("slug") or "cc0"
        version = match.group("version")
        code = f"CC0 {version}" if slug == "cc0" else f"CC {slug.upper()} {version}"
    else:
        normalized = re.sub(r"[-_ ]+", " ", raw.upper()).strip()
        normalized = normalized.replace("CC CC0", "CC0")
        match = re.fullmatch(
            r"(CC0|CC BY(?: SA| NC| ND| NC SA| NC ND)?) ([0-9]+(?:\.[0-9]+)?)", normalized
        )
        if not match:
            return None
        family, version = match.groups()
        code = f"{family.replace('CC BY SA', 'CC BY-SA')} {version}"
    if code not in ALLOWED_LICENSES[provider]:
        return None
    if code.startswith("CC0"):
        return code, f"https://creativecommons.org/publicdomain/zero/{code.split()[-1]}/"
    slug = code.removeprefix("CC ").rsplit(" ", 1)[0].casefold()
    return code, f"https://creativecommons.org/licenses/{slug}/{code.split()[-1]}/"


def _safe_url(value: object) -> str | None:
    if not isinstance(value, str) or not value.strip() or len(value) > 2_000:
        return None
    raw = value.strip()
    try:
        parsed = urlsplit(raw)
        if parsed.port is not None:
            return None
    except ValueError:
        return None
    if (
        parsed.scheme not in {"http", "https"}
        or not parsed.hostname
        or parsed.username is not None
        or parsed.password is not None
    ):
        return None
    return raw


def _text(value: object, *, maximum: int = 500) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text if text and len(text) <= maximum else None


def _iso(value: object) -> str | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    text = _text(value, maximum=100)
    return text


def _iso_utc(value: object) -> str | None:
    """Interpret warehouse load timestamps as UTC, including DuckDB naive values."""
    if value is None:
        return None
    if isinstance(value, datetime):
        parsed = value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)
        return parsed.isoformat()
    text = _text(value, maximum=100)
    if text is None:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    parsed = parsed.replace(tzinfo=UTC) if parsed.tzinfo is None else parsed.astimezone(UTC)
    return parsed.isoformat()


def _iso_arizona(value: object) -> str | None:
    """Reduce a source observation to its Arizona civil calendar date."""
    if value is None:
        return None
    if isinstance(value, date) and not isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, datetime):
        parsed = value
    else:
        text = _text(value, maximum=100)
        if text is None:
            return None
        try:
            parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
        except ValueError:
            return None
    zone = ZoneInfo(DEFAULT_TIMEZONE)
    localized = parsed.replace(tzinfo=zone) if parsed.tzinfo is None else parsed.astimezone(zone)
    return localized.date().isoformat()


def _parse_aware_datetime(value: str, label: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        raise PublicExportError(f"{label} must be ISO 8601") from None
    if parsed.tzinfo is None:
        raise PublicExportError(f"{label} must include a timezone")
    return parsed


def _valid_public_media_identity(
    provider: str | None,
    media_id: str | None,
    attribution_id: str | None,
    source_url: str | None,
) -> bool:
    if provider == "usfws":
        return bool(
            media_id
            and _MEDIA_ID.fullmatch(media_id)
            and attribution_id
            and _MEDIA_ATTRIBUTION_ID.fullmatch(attribution_id)
            and source_url
            and _USFWS_MEDIA_PAGE.fullmatch(source_url)
        )
    if provider != "inaturalist" or not media_id or not attribution_id or not source_url:
        return False
    media_match = _INATURALIST_MEDIA_ID.fullmatch(media_id)
    attribution_match = _INATURALIST_ATTRIBUTION_ID.fullmatch(attribution_id)
    source_match = _INATURALIST_PHOTO_PAGE.fullmatch(source_url)
    return bool(
        media_match
        and attribution_match
        and source_match
        and media_match.group("photo_id") == source_match.group("photo_id")
        and attribution_match.group("photo_id") == source_match.group("photo_id")
    )


def load_public_media_manifest(
    path: Path,
    *,
    selected_sha256_by_species: Mapping[str, str] | None = None,
    excluded_species: frozenset[str] = frozenset(),
) -> dict[str, list[JsonObject]]:
    """Revalidate prepared public media and return only the browser projection.

    The preparation manifest contains operational fields such as the upstream
    image URL and ranking score.  Neither crosses into the browser contract.
    """
    if path.is_symlink() or not path.is_file() or path.stat().st_size > MAX_MEDIA_MANIFEST_BYTES:
        raise PublicExportError("public media manifest is missing or exceeds 25 MiB")
    try:
        payload = json.loads(path.read_bytes())
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        raise PublicExportError("public media manifest is not valid UTF-8 JSON") from None
    if (
        not isinstance(payload, dict)
        or payload.get("schema_version") != 1
        or payload.get("mode") != "rufous-media-preparation"
        or not isinstance(payload.get("items"), list)
        or not payload["items"]
    ):
        raise PublicExportError("public media manifest has an invalid contract")

    ranked: dict[str, list[tuple[float, JsonObject]]] = defaultdict(list)
    identifiers: set[str] = set()
    source_identities: set[tuple[str, str]] = set()
    object_hashes: set[str] = set()
    manifest_species: set[str] = set()
    for index, raw in enumerate(payload["items"]):
        if not isinstance(raw, dict):
            raise PublicExportError(f"public media item {index} is malformed")
        provider = _text(raw.get("provider"), maximum=32) if "provider" in raw else "usfws"
        media_id = _text(raw.get("media_id"), maximum=64)
        attribution_id = _text(raw.get("attribution_id"), maximum=64)
        scientific_name = _text(raw.get("scientific_name"), maximum=200)
        common_name = _text(raw.get("common_name"), maximum=200)
        creator = _text(raw.get("creator"), maximum=500)
        title = _text(raw.get("title"), maximum=500)
        caption = _text(raw.get("caption"), maximum=2_000)
        alt_text = _text(raw.get("alt_text"), maximum=1_000)
        source_url = _text(raw.get("source_page_url"), maximum=2_000)
        url = _text(raw.get("url"), maximum=2_000)
        sha256 = _text(raw.get("sha256"), maximum=64)
        license_pair = canonical_license(provider or "", raw.get("license"))
        license_url = _text(raw.get("license_url"), maximum=2_000)
        match = _PUBLIC_MEDIA_URL.fullmatch(url) if url else None
        width = raw.get("width")
        height = raw.get("height")
        score = raw.get("hero_score")
        identity_texts = {
            value.casefold()
            for value in (common_name, scientific_name, title)
            if isinstance(value, str)
        }
        if (
            not _valid_public_media_identity(provider, media_id, attribution_id, source_url)
            or media_id in identifiers
            or not scientific_name
            or not _SCIENTIFIC_NAME.fullmatch(scientific_name)
            or not common_name
            or not creator
            or creator.casefold() in identity_texts
            or not title
            or not alt_text
            or not sha256
            or not _SHA256.fullmatch(sha256)
            or match is None
            or match.group("sha") != sha256
            or match.group("shard") != sha256[:2]
            or license_pair is None
            or license_url != license_pair[1]
            or raw.get("mime_type") != "image/webp"
            or type(width) is not int
            or type(height) is not int
            or not 1 <= width <= 650
            or not 1 <= height <= 650
            or isinstance(score, bool)
            or not isinstance(score, int | float)
            or not math.isfinite(float(score))
        ):
            raise PublicExportError(f"public media item {index} fails the public contract")
        assert provider is not None
        assert media_id is not None
        assert attribution_id is not None
        assert source_url is not None
        source_identity = (scientific_name.casefold(), f"{provider}:{source_url}")
        if source_identity in source_identities:
            raise PublicExportError("public media manifest repeats a species source page")
        identifiers.add(media_id)
        source_identities.add(source_identity)
        object_hashes.add(sha256)
        species_key = scientific_name.casefold()
        manifest_species.add(species_key)
        public_item: JsonObject = {
            "kind": "photo",
            "provider": provider,
            "media_id": media_id,
            "url": url,
            "source_url": source_url,
            "creator": creator,
            "license": license_pair[0],
            "license_url": license_pair[1],
            "attribution_id": attribution_id,
            "scientific_name": scientific_name,
            "title": title,
            "caption": caption,
            "alt_text": alt_text,
            "width": width,
            "height": height,
            "mime_type": "image/webp",
            "sha256": sha256,
        }
        if (
            selected_sha256_by_species is None
            or selected_sha256_by_species.get(species_key) == sha256
        ):
            ranked[species_key].append((float(score), public_item))

    counts = payload.get("counts")
    if (
        not isinstance(counts, dict)
        or counts.get("items") != len(payload["items"])
        or counts.get("objects") != len(object_hashes)
        or counts.get("species") != len(manifest_species)
    ):
        raise PublicExportError("public media manifest counts do not match its contents")
    if selected_sha256_by_species is not None:
        if (
            set(selected_sha256_by_species).intersection(excluded_species)
            or set(selected_sha256_by_species).union(excluded_species) != manifest_species
        ):
            raise PublicExportError(
                "public media selections and exclusions do not cover exactly the manifest species"
            )
        missing = sorted(set(selected_sha256_by_species) - set(ranked))
        if missing:
            raise PublicExportError(f"selected public media is absent for species {missing[0]}")
    public_by_species: dict[str, list[JsonObject]] = {}
    for scientific_name, items in sorted(ranked.items()):
        ordered = [
            item
            for _score, item in sorted(
                items,
                key=lambda pair: (
                    -pair[0],
                    str(pair[1]["source_url"]),
                    str(pair[1]["media_id"]),
                ),
            )
        ]
        public_by_species[scientific_name] = (
            ordered[:1] if selected_sha256_by_species is not None else ordered
        )
    return public_by_species


def attach_public_media(
    records: PublicRecords,
    media_by_scientific_name: Mapping[str, list[JsonObject]],
) -> int:
    """Attach exact-species media without broad or fuzzy taxon matching."""
    matched_keys: set[str] = set()
    attached = 0
    for species in records.species:
        scientific_name = _text(species.get("scientific_name"), maximum=200)
        key = scientific_name.casefold() if scientific_name else ""
        items = media_by_scientific_name.get(key, [])
        species["media"] = [dict(item) for item in items]
        if items:
            matched_keys.add(key)
            attached += len(items)
    unmatched = sum(
        len(items) for key, items in media_by_scientific_name.items() if key not in matched_keys
    )
    if unmatched:
        unmatched_by_provider: Counter[str] = Counter()
        for key, items in media_by_scientific_name.items():
            if key in matched_keys:
                continue
            unmatched_by_provider.update(
                str(item.get("provider"))
                for item in items
                if item.get("provider") in {"usfws", "inaturalist"}
            )
        for provider, count in unmatched_by_provider.items():
            records.rejected[f"{provider}_unmatched_species"] += count
    return attached


def _public_id(namespace: str, *parts: object) -> str:
    joined = "|".join(str(part) for part in parts)
    return hashlib.sha256(f"rufous-public-v1|{namespace}|{joined}".encode()).hexdigest()[:24]


def _place_search_key(name: str) -> str:
    value = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode().casefold()
    return _PLACE_KEY.sub("", value)


def place_prefix(name: str) -> str:
    key = _place_search_key(name)
    if not key:
        return "__"
    return (key + "_")[:2]


def cell_id(latitude: float, longitude: float) -> str:
    return f"n{math.floor(latitude)}w{abs(math.floor(longitude))}"


def cell_bounds(identifier: str) -> JsonObject:
    match = re.fullmatch(r"n([0-9]{2})w([0-9]{3})", identifier)
    if not match:
        raise PublicExportError(f"invalid public grid cell {identifier}")
    south = int(match.group(1))
    west = -int(match.group(2))
    return {"west": west, "south": south, "east": west + 1, "north": south + 1}


def _is_arizona(latitude: object, longitude: object) -> bool:
    if isinstance(latitude, bool) or isinstance(longitude, bool):
        return False
    if not isinstance(latitude, int | float) or not isinstance(longitude, int | float):
        return False
    bounds = cast(dict[str, float], REGION["bounds"])
    return bool(
        math.isfinite(float(latitude))
        and math.isfinite(float(longitude))
        and bounds["south"] <= float(latitude) <= bounds["north"]
        and bounds["west"] <= float(longitude) <= bounds["east"]
        and is_in_arizona(float(latitude), float(longitude))
    )


def _timezone_metadata(
    latitude: float,
    longitude: float,
    supplied: str | None = None,
) -> JsonObject:
    if supplied in {"America/Phoenix", "America/Denver"}:
        return {"timezone": supplied, "timezone_source": "source"}
    if (
        latitude >= MOUNTAIN_TIME_AMBIGUITY["south"]
        and longitude >= MOUNTAIN_TIME_AMBIGUITY["west"]
    ):
        return {
            "timezone": None,
            "timezone_source": "nws_or_visitor_required",
        }
    return {
        "timezone": DEFAULT_TIMEZONE,
        "timezone_source": "arizona_no_dst",
    }


def load_gnis_places(path: Path, expected_sha256: str) -> list[JsonObject]:
    """Load one pinned official GNIS text/CSV snapshot, filtering to Arizona."""
    expected = expected_sha256.strip().casefold()
    if not _SHA256.fullmatch(expected):
        raise PublicExportError("GNIS expected SHA-256 must be 64 lowercase hex characters")
    if not path.is_file() or path.stat().st_size > MAX_GNIS_BYTES:
        raise PublicExportError("GNIS snapshot is missing or exceeds the 250 MiB input limit")
    actual = hashlib.sha256(path.read_bytes()).hexdigest()
    if actual != expected:
        raise PublicExportError("GNIS snapshot SHA-256 does not match the pinned value")
    with path.open(encoding="utf-8-sig", newline="") as stream:
        header = stream.readline()
        stream.seek(0)
        delimiter = "|" if "|" in header else "\t" if "\t" in header else ","
        reader = csv.DictReader(stream, delimiter=delimiter)
        if reader.fieldnames is None:
            raise PublicExportError("GNIS snapshot has no header")
        fieldnames = {_normalized_header(item) for item in reader.fieldnames if item}
        required_groups = (
            {"FEATURE_ID", "ID"},
            {"FEATURE_NAME", "NAME"},
            {"FEATURE_CLASS", "CLASS"},
            {"STATE_ALPHA", "STATE", "STATE_NAME", "STATE_NUMERIC"},
            {"PRIM_LAT_DEC", "DEC_LAT", "LATITUDE"},
            {"PRIM_LONG_DEC", "DEC_LONG", "LONGITUDE"},
        )
        if any(not (group & fieldnames) for group in required_groups):
            raise PublicExportError("GNIS snapshot does not match the required feature schema")
        output: list[JsonObject] = []
        for raw in reader:
            row = {_normalized_header(key): value for key, value in raw.items() if key}
            state = (
                (_first(row, "STATE_ALPHA", "STATE", "STATE_NAME", "STATE_NUMERIC") or "")
                .strip()
                .casefold()
            )
            if state not in {"az", "arizona", "04", "4"}:
                continue
            name = _text(_first(row, "FEATURE_NAME", "NAME"))
            feature_id = _text(_first(row, "FEATURE_ID", "ID"), maximum=100)
            feature_class = _text(_first(row, "FEATURE_CLASS", "CLASS"), maximum=100)
            try:
                latitude = float(_first(row, "PRIM_LAT_DEC", "DEC_LAT", "LATITUDE") or "")
                longitude = float(_first(row, "PRIM_LONG_DEC", "DEC_LONG", "LONGITUDE") or "")
            except ValueError:
                continue
            if (
                not name
                or not feature_id
                or not feature_class
                or not _is_arizona(latitude, longitude)
            ):
                continue
            history = (_first(row, "HISTORY", "HISTORICAL") or "").strip().casefold()
            timezone = _text(_first(row, "TIMEZONE", "TIME_ZONE"), maximum=100)
            output.append(
                {
                    "public_id": _public_id("gnis-place", feature_id),
                    "name": name,
                    "kind": "place",
                    "source": "usgs_gnis",
                    "feature_class": feature_class,
                    "is_historical": history in {"true", "yes", "y", "1"},
                    "latitude": round(latitude, 6),
                    "longitude": round(longitude, 6),
                    **_timezone_metadata(latitude, longitude, timezone),
                }
            )
    if not output:
        raise PublicExportError("GNIS snapshot contains no valid Arizona features")
    output.sort(key=lambda item: (str(item["name"]).casefold(), str(item["public_id"])))
    return output


def _normalized_header(value: str) -> str:
    return re.sub(r"[^A-Z0-9]+", "_", value.strip().upper()).strip("_")


def _first(row: dict[str, str | None], *names: str) -> str | None:
    for name in names:
        value = row.get(name)
        if value is not None:
            return value
    return None


def synthetic_records() -> PublicRecords:
    species = [
        {
            "species_code": "annhum",
            "common_name": "Anna's Hummingbird",
            "scientific_name": "Calypte anna",
            "taxonomic_category": "species",
            "family": {"common_name": "Hummingbirds", "scientific_name": "Trochilidae"},
            "order_name": "Caprimulgiformes",
            "traits": {"habitat": "Woodland", "migration_label": "Resident"},
            "evidence": {
                "licensed_occurrence_count": 2,
                "latest_licensed_occurrence_at": "2026-01-15T07:12:00-07:00",
            },
            "media": [],
        },
        {
            "species_code": "cacwre",
            "common_name": "Cactus Wren",
            "scientific_name": "Campylorhynchus brunneicapillus",
            "taxonomic_category": "species",
            "family": {"common_name": "Wrens", "scientific_name": "Troglodytidae"},
            "order_name": "Passeriformes",
            "traits": {"habitat": "Desert", "migration_label": "Resident"},
            "evidence": {
                "licensed_occurrence_count": 1,
                "latest_licensed_occurrence_at": "2026-01-14T08:05:00-07:00",
            },
            "media": [],
        },
    ]
    observations = [
        _synthetic_observation(
            "annhum", "2026-01-15T07:12:00-07:00", "Papago Park", 33.456, -111.95, 2
        ),
        _synthetic_observation(
            "cacwre", "2026-01-14T08:05:00-07:00", "Rio Salado", 33.422, -112.0, 1
        ),
    ]
    places = [
        {
            "public_id": _public_id("synthetic-place", "papago-park"),
            "name": "Papago Park",
            "kind": "place",
            "source": "synthetic",
            "latitude": 33.456,
            "longitude": -111.95,
            "timezone": DEFAULT_TIMEZONE,
            "timezone_source": "fixture",
        },
        {
            "public_id": _public_id("synthetic-place", "madera-canyon"),
            "name": "Madera Canyon",
            "kind": "place",
            "source": "usgs_gnis",
            "feature_class": "Valley",
            "is_historical": False,
            "latitude": 31.73,
            "longitude": -110.88,
            "timezone": DEFAULT_TIMEZONE,
            "timezone_source": "fixture",
        },
    ]
    return PublicRecords(
        species=species,
        observations=observations,
        places=places,
        attribution_items=[],
        rejected=Counter(),
        source_generated_at="2026-01-15T14:12:00+00:00",
    )


def _synthetic_observation(
    species_code: str,
    observed_at: str,
    name: str,
    latitude: float,
    longitude: float,
    count: int,
) -> JsonObject:
    return {
        "public_id": _public_id("synthetic-observation", species_code, observed_at, name),
        "species_code": species_code,
        "observed_at": observed_at,
        "count": count,
        "count_display": str(count),
        "is_notable": False,
        "source": "synthetic",
        "attribution_id": "synthetic-fixtures",
        "location": {
            "name": name,
            "latitude": latitude,
            "longitude": longitude,
            "kind": "hotspot",
            "timezone": DEFAULT_TIMEZONE,
            "timezone_source": "fixture",
        },
    }


def records_from_database(database_path: Path, gnis_places: list[JsonObject]) -> PublicRecords:
    """Read only the separately modeled, licensed GBIF EOD public projection."""
    if not database_path.is_file():
        raise PublicExportError(f"public source database does not exist: {database_path}")
    for place in gnis_places:
        if place.get("source") != "usgs_gnis" or place.get("kind") != "place":
            raise PublicExportError("production place input must contain only GNIS places")
    connection = duckdb.connect(str(database_path), read_only=True)
    rejected: Counter[str] = Counter()
    try:
        _require_tables(connection, {GBIF_EBIRD_EOD_TABLE})
        species, observations, attribution, source_generated_at = _database_gbif_eod_records(
            connection, rejected
        )
    finally:
        connection.close()
    return PublicRecords(
        species=species,
        observations=observations,
        places=_dedupe_places(gnis_places),
        attribution_items=attribution,
        rejected=rejected,
        source_generated_at=source_generated_at,
    )


def _require_tables(connection: duckdb.DuckDBPyConnection, tables: set[str]) -> None:
    found = {
        f"{row[0]}.{row[1]}"
        for row in connection.execute(
            "SELECT table_schema, table_name FROM information_schema.tables"
        ).fetchall()
    }
    missing = tables - found
    if missing:
        raise PublicExportError("public source database is missing: " + ", ".join(sorted(missing)))


def _table_exists(connection: duckdb.DuckDBPyConnection, qualified: str) -> bool:
    schema, table = qualified.split(".", 1)
    return (
        connection.execute(
            "SELECT 1 FROM information_schema.tables WHERE table_schema=? AND table_name=?",
            [schema, table],
        ).fetchone()
        is not None
    )


def _database_gbif_eod_records(
    connection: duckdb.DuckDBPyConnection,
    rejected: Counter[str],
) -> tuple[list[JsonObject], list[JsonObject], list[JsonObject], str | None]:
    """Project EOD rows without observer names, locality, or source identifiers."""
    rows = connection.execute(
        f"""SELECT source_id, dataset_key, dataset_title, dataset_publisher,
          dataset_citation, dataset_doi, dataset_source_url, dataset_license,
          license, scientific_name, accepted_scientific_name, common_name,
          taxon_rank, family, order_name, accepted_taxon_key, taxon_key,
          species_key, event_date, latitude, longitude, loaded_at
        FROM {GBIF_EBIRD_EOD_TABLE}
        ORDER BY event_date DESC NULLS LAST, source_id"""
    ).fetchall()
    observations: list[JsonObject] = []
    attribution: list[JsonObject] = []
    species_by_code: dict[str, JsonObject] = {}
    species_counts: Counter[str] = Counter()
    latest_by_species: dict[str, str] = {}
    freshness: list[str] = []
    generalized_duplicates: Counter[tuple[str, str, str, str, str]] = Counter()
    for row in rows:
        source_id = _text(row[0], maximum=200)
        dataset_key = _text(row[1], maximum=100)
        dataset_title = _text(row[2])
        publisher = _text(row[3])
        dataset_citation = _text(row[4], maximum=2_000)
        dataset_doi = _text(row[5], maximum=200)
        source_url = _safe_url(row[6])
        dataset_license = canonical_license("gbif", row[7])
        occurrence_license = canonical_license("gbif", row[8])
        # The modeled ``scientific_name`` deliberately prefers GBIF's clean
        # species field. ``accepted_scientific_name`` commonly includes an
        # authority, which would break exact matching against the USFWS media
        # manifest; retain it only as a fallback for older modeled snapshots.
        scientific_name = _text(row[9]) or _text(row[10])
        common_name = _text(row[11]) or scientific_name
        taxon_rank = _text(row[12], maximum=100)
        taxon_key = _gbif_taxon_key(row[15], row[16], row[17])
        observed_at = _iso_arizona(row[18])
        if dataset_key != GBIF_EBIRD_EOD_DATASET_KEY:
            rejected["gbif_non_eod_dataset"] += 1
            continue
        if (
            taxon_rank is None
            or taxon_rank.casefold() != "species"
            or scientific_name is None
            or _SPECIES_BINOMIAL.fullmatch(scientific_name) is None
        ):
            # Some EOD records pair a species vernacular name with a genus-rank
            # GBIF match such as ``Astur Lacepède, 1799``. Publishing those as
            # species would misidentify observations and make exact media
            # matching impossible, so keep one explicit fail-closed count.
            rejected["gbif_non_species_taxon"] += 1
            continue
        if (
            not source_id
            or not common_name
            or not taxon_key
            or not observed_at
            or not _is_arizona(row[19], row[20])
        ):
            rejected["gbif_ineligible"] += 1
            continue
        if not occurrence_license or not dataset_license:
            rejected["gbif_license"] += 1
            continue
        if (
            not dataset_title
            or publisher != GBIF_EBIRD_EOD_PUBLISHER
            or not dataset_citation
            or not dataset_doi
            or source_url is None
        ):
            rejected["gbif_attribution"] += 1
            continue
        source_url_lower = source_url.casefold()
        if "/occurrence/" in source_url_lower or "ebird.org/checklist/" in source_url_lower:
            rejected["gbif_record_level_attribution"] += 1
            continue
        license_code, license_url = occurrence_license
        species_code = f"gbif-{taxon_key}"
        if not _SPECIES_CODE.fullmatch(species_code):
            rejected["gbif_taxon_key"] += 1
            continue
        attribution_id = _public_id("gbif-eod-attribution", dataset_key, license_code)
        latitude = float(row[19])
        longitude = float(row[20])
        generalized_latitude = round(latitude, 2)
        generalized_longitude = round(longitude, 2)
        generalized_key = (
            species_code,
            observed_at,
            f"{generalized_latitude:.2f}",
            f"{generalized_longitude:.2f}",
            attribution_id,
        )
        duplicate_ordinal = generalized_duplicates[generalized_key]
        generalized_duplicates[generalized_key] += 1
        observations.append(
            {
                # This identifier is derived only from fields already present in
                # the generalized public row. Raw GBIF identifiers never become
                # a stable correlation handle in the static artifact.
                "public_id": _public_id(
                    "gbif-eod-generalized-observation",
                    *generalized_key,
                    duplicate_ordinal,
                ),
                "species_code": species_code,
                "observed_at": observed_at,
                "count": None,
                "count_display": "occurrence",
                "is_notable": False,
                "source": "gbif",
                "attribution_id": attribution_id,
                "location": {
                    # Even publicly supplied locality labels can identify a home,
                    # nest, or other sensitive site. Only a generic label crosses
                    # the public boundary alongside rounded coordinates.
                    "name": "Generalized Arizona occurrence",
                    "latitude": generalized_latitude,
                    "longitude": generalized_longitude,
                    "kind": "generalized",
                    **_timezone_metadata(latitude, longitude),
                },
            }
        )
        attribution.append(
            {
                "attribution_id": attribution_id,
                "provider": "gbif",
                # Dataset-level publisher attribution deliberately replaces the
                # occurrence's recorded_by observer identity.
                "creator": publisher,
                "source_url": source_url,
                "license": license_code,
                "license_url": license_url,
                "dataset_title": dataset_title,
                "dataset_key": dataset_key,
                "publisher": publisher,
                "dataset_citation": dataset_citation,
                "dataset_doi": dataset_doi,
            }
        )
        if species_code not in species_by_code:
            species_by_code[species_code] = {
                "species_code": species_code,
                "common_name": common_name,
                "scientific_name": scientific_name,
                "taxonomic_category": taxon_rank,
                "family": {
                    "common_name": None,
                    "scientific_name": _text(row[13]),
                },
                "order_name": _text(row[14]),
                "traits": {},
                "evidence": {},
                "media": [],
            }
        species_counts[species_code] += 1
        previous = latest_by_species.get(species_code)
        if previous is None or observed_at > previous:
            latest_by_species[species_code] = observed_at
        loaded_at = _iso_utc(row[21])
        if loaded_at:
            freshness.append(loaded_at)
    species = []
    for code in sorted(species_by_code):
        item = species_by_code[code]
        item["evidence"] = {
            "licensed_occurrence_count": species_counts[code],
            "latest_licensed_occurrence_at": latest_by_species[code],
        }
        species.append(item)
    return (
        species,
        observations,
        _dedupe_attribution(attribution),
        max(freshness) if freshness else None,
    )


def _gbif_taxon_key(*values: object) -> str | None:
    for value in values:
        if isinstance(value, bool):
            continue
        if isinstance(value, int) or (isinstance(value, str) and value.strip().isdigit()):
            return str(value).strip()
    return None


def _dedupe_attribution(items: list[JsonObject]) -> list[JsonObject]:
    by_id = {str(item["attribution_id"]): item for item in items}
    return [by_id[key] for key in sorted(by_id)]


def _dedupe_places(items: list[JsonObject]) -> list[JsonObject]:
    by_key: dict[tuple[str, float, float], JsonObject] = {}
    for item in items:
        key = (
            _place_search_key(str(item["name"])),
            round(float(item["latitude"]), 4),
            round(float(item["longitude"]), 4),
        )
        previous = by_key.get(key)
        if previous is None:
            by_key[key] = item
    return sorted(
        by_key.values(),
        key=lambda item: (
            str(item["name"]).casefold(),
            str(item["public_id"]),
        ),
    )


def _media_source_marker(records: PublicRecords) -> str:
    providers: set[str] = set()
    for species in records.species:
        media = species.get("media")
        if not isinstance(media, list):
            raise PublicExportError("species media must be an array")
        for item in media:
            if not isinstance(item, dict) or item.get("provider") not in {
                "usfws",
                "inaturalist",
            }:
                raise PublicExportError("species media has an unsupported public provider")
            providers.add(str(item["provider"]))
    marker = _MEDIA_SOURCE_MARKERS.get(frozenset(providers))
    if marker is None:  # pragma: no cover - bounded above, retained as a fail-closed invariant
        raise PublicExportError("species media provider combination is unsupported")
    return marker


def build_public_assets(
    records: PublicRecords,
    *,
    mode: ExportMode,
    gnis_sha256: str | None,
    generated_at: str | None = None,
) -> dict[str, JsonObject]:
    """Construct every static JSON file in memory before touching the output."""
    generated = generated_at or records.source_generated_at or datetime.now(UTC).isoformat()
    _parse_aware_datetime(generated, "generated_at")
    species_by_code = {str(item["species_code"]): item for item in records.species}
    if len(species_by_code) != len(records.species) or not species_by_code:
        raise PublicExportError("public species codes must be non-empty and unique")

    assets: dict[str, JsonObject] = {}
    species_summaries: list[JsonObject] = []
    for code in sorted(species_by_code):
        if not _SPECIES_CODE.fullmatch(code):
            raise PublicExportError(f"unsafe species code: {code!r}")
        row = species_by_code[code]
        media = row.get("media")
        if not isinstance(media, list):
            raise PublicExportError(f"species {code!r} has malformed media")
        path = f"data/species/{code}.json"
        assets[path] = {"schema_version": SCHEMA_VERSION, **row}
        species_summaries.append(
            {
                "species_code": code,
                "common_name": row["common_name"],
                "scientific_name": row["scientific_name"],
                "profile_path": f"/{path}",
                "hero_photo": media[0] if media else None,
                "photo_count": len(media),
            }
        )

    observations_by_cell: dict[str, list[JsonObject]] = defaultdict(list)
    for observation in records.observations:
        if observation.get("species_code") not in species_by_code:
            raise PublicExportError("observation references an unknown species")
        location = observation.get("location")
        if not isinstance(location, dict) or not _is_arizona(
            location.get("latitude"), location.get("longitude")
        ):
            raise PublicExportError("observation has an invalid Arizona location")
        identifier = cell_id(float(location["latitude"]), float(location["longitude"]))
        observations_by_cell[identifier].append(observation)
    cell_summaries: list[JsonObject] = []
    for identifier in sorted(observations_by_cell):
        rows = sorted(
            observations_by_cell[identifier],
            key=lambda item: (str(item.get("observed_at") or ""), str(item["public_id"])),
            reverse=True,
        )
        path = f"data/cells/{identifier}.json"
        bounds = cell_bounds(identifier)
        assets[path] = {
            "schema_version": SCHEMA_VERSION,
            "cell_id": identifier,
            "bounds": bounds,
            "observations": rows,
        }
        cell_summaries.append(
            {
                "cell_id": identifier,
                "path": f"/{path}",
                "observation_count": len(rows),
                "bounds": bounds,
            }
        )

    places_by_prefix: dict[str, list[JsonObject]] = defaultdict(list)
    for place in records.places:
        if not _is_arizona(place.get("latitude"), place.get("longitude")):
            raise PublicExportError("place shard contains a location outside Arizona")
        places_by_prefix[place_prefix(str(place["name"]))].append(place)
    place_summaries: list[JsonObject] = []
    for prefix in sorted(places_by_prefix):
        rows = sorted(
            places_by_prefix[prefix],
            key=lambda item: (str(item["name"]).casefold(), str(item["public_id"])),
        )
        path = f"data/places/{prefix}.json"
        assets[path] = {"schema_version": SCHEMA_VERSION, "prefix": prefix, "places": rows}
        place_summaries.append({"prefix": prefix, "path": f"/{path}", "count": len(rows)})

    media_source = _media_source_marker(records)
    sources = _attribution_sources(mode, gnis_sha256, records)
    attribution_items = _dedupe_attribution(records.attribution_items)
    attribution: JsonObject = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": generated,
        "sources": sources,
        "items": attribution_items,
    }
    assets["data/attribution.json"] = attribution
    license_policy = {
        "version": 1,
        "allowed": {provider: sorted(values) for provider, values in ALLOWED_LICENSES.items()},
        "rejected_counts": dict(sorted(records.rejected.items())),
    }
    manifest: JsonObject = {
        "schema_version": SCHEMA_VERSION,
        "mode": "public",
        "release_mode": mode,
        "generated_at": generated,
        "region": REGION,
        "species": species_summaries,
        "cells": cell_summaries,
        "place_prefixes": place_summaries,
        "attribution_path": "/data/attribution.json",
        "source_policy": {
            "direct_ebird": "excluded",
            "occurrence_source": "synthetic" if mode == "synthetic" else "gbif",
            "gbif_dataset_key": (None if mode == "synthetic" else GBIF_EBIRD_EOD_DATASET_KEY),
            "coverage": "fictional_fixture" if mode == "synthetic" else "bounded_sample",
            "required_taxon_key": None if mode == "synthetic" else GBIF_RUFOUS_TAXON_KEY,
            "media_source": media_source,
            "media_delivery": "none" if media_source == "none" else "immutable_r2",
        },
        "license_policy": license_policy,
        "counts": {
            "species": len(species_summaries),
            "observations": len(records.observations),
            "places": len(records.places),
            "attribution_items": len(attribution_items),
            "media_items": sum(int(item["photo_count"]) for item in species_summaries),
            "species_with_media": sum(
                1 for item in species_summaries if int(item["photo_count"]) > 0
            ),
        },
    }
    assets["data/manifest.json"] = manifest
    manifest["data_version"] = semantic_data_version(assets)
    return assets


def _attribution_sources(
    mode: ExportMode,
    gnis_sha256: str | None,
    records: PublicRecords,
) -> list[JsonObject]:
    census_boundary: JsonObject = {
        "provider": "us_census_tigerweb",
        "title": "U.S. Census Bureau TIGERweb States boundary",
        "url": "https://tigerweb.geo.census.gov/arcgis/rest/services/TIGERweb/State_County/MapServer/0",
        "license": "U.S. Government public domain",
        "license_url": None,
        "credit": (
            "Arizona boundary generalized from January 1, 2025 TIGERweb data. "
            "This product is not endorsed or certified by the Census Bureau."
        ),
    }
    if mode == "synthetic":
        return [
            {
                "provider": "synthetic",
                "title": "Rufous fictional test fixtures",
                "url": "https://loughondata.com/projects/rufous/",
                "license": "Not production data",
                "license_url": None,
                "credit": "Generated solely for offline tests and previews.",
            },
            census_boundary,
            *_media_attribution_sources(records),
        ]
    if not gnis_sha256 or not _SHA256.fullmatch(gnis_sha256):
        raise PublicExportError("production attribution requires the pinned GNIS SHA-256")
    sources: list[JsonObject] = [
        {
            "provider": "gbif_ebird_eod",
            "title": "EOD – eBird Observation Dataset",
            "url": GBIF_EBIRD_EOD_DATASET_URL,
            "license": "CC BY 4.0",
            "license_url": "https://creativecommons.org/licenses/by/4.0/",
            "credit": (
                "Cornell Lab of Ornithology, EOD – eBird Observation Dataset, "
                "accessed through GBIF.org."
            ),
            "modifications": (
                "Rufous selected Arizona records, removed observer and locality fields, "
                "reduced event timestamps to day-level dates, rounded coordinates to 0.01°, "
                "used generalized location labels, and grouped occurrences into static grid "
                "cells."
            ),
            "disclaimer": GBIF_EBIRD_EOD_DISCLAIMER,
            "dataset_key": GBIF_EBIRD_EOD_DATASET_KEY,
        },
        {
            "provider": "usgs_gnis",
            "title": "Geographic Names Information System",
            "url": "https://www.usgs.gov/us-board-on-geographic-names/download-gnis-data",
            "license": "U.S. Government public domain",
            "license_url": None,
            "credit": "U.S. Geological Survey; pinned snapshot SHA-256 " + gnis_sha256,
            "snapshot_sha256": gnis_sha256,
        },
        census_boundary,
    ]
    sources.extend(_media_attribution_sources(records))
    return sources


def _media_attribution_sources(records: PublicRecords) -> list[JsonObject]:
    providers = {
        "xeno_canto" for item in records.attribution_items if item.get("provider") == "xeno_canto"
    }
    providers.update(
        str(item.get("provider"))
        for species in records.species
        for item in species.get("media", [])
        if isinstance(item, dict)
    )
    provider_sources: dict[str, JsonObject] = {
        "inaturalist": {
            "provider": "inaturalist",
            "title": "iNaturalist",
            "url": "https://www.inaturalist.org/",
            "license": "Per-item Creative Commons license",
            "license_url": None,
            "credit": "Individual creators are credited on each media item.",
            "modifications": (
                "Rufous resized, re-encoded, and stripped metadata from reviewed web display "
                "copies; each credit links to the original iNaturalist photo page."
            ),
        },
        "xeno_canto": {
            "provider": "xeno_canto",
            "title": "Xeno-canto",
            "url": "https://xeno-canto.org/",
            "license": "Per-item Creative Commons license",
            "license_url": None,
            "credit": "Individual recordists are credited on each audio item.",
        },
        "usfws": {
            "provider": "usfws",
            "title": "U.S. Fish and Wildlife Service Media Library",
            "url": "https://www.fws.gov/search/images",
            "license": "Per-item Public Domain or Creative Commons license",
            "license_url": "https://www.fws.gov/notices",
            "credit": "Individual creators are credited beside each image.",
            "modifications": (
                "Rufous resized, re-encoded, and stripped metadata from web display copies; "
                "each credit links to the original USFWS media page."
            ),
        },
    }
    return [provider_sources[provider] for provider in sorted(providers & provider_sources.keys())]


def semantic_data_version(assets: Mapping[str, object]) -> str:
    """Hash the complete public contract while ignoring generation timestamps.

    The application manifest participates in the identity.  Its ``data_version``
    field is the one deliberate self-reference, so only that field is removed
    from the canonical manifest before hashing.  ``generated_at`` is removed
    recursively from every JSON document so rebuilding identical source data at
    a later time remains a semantic no-op.
    """
    semantic: dict[str, object] = {}
    for path, payload in sorted(assets.items()):
        canonical = _without_volatile_fields(payload)
        if path == "data/manifest.json":
            if not isinstance(canonical, dict):
                raise PublicExportError("data/manifest.json must be a JSON object")
            canonical = {key: value for key, value in canonical.items() if key != "data_version"}
        semantic[path] = canonical
    encoded = json.dumps(semantic, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(encoded.encode()).hexdigest()


def _without_volatile_fields(value: object) -> object:
    if isinstance(value, dict):
        return {
            key: _without_volatile_fields(item)
            for key, item in value.items()
            if key not in {"generated_at"}
        }
    if isinstance(value, list):
        return [_without_volatile_fields(item) for item in value]
    return value


def write_public_assets(output_dir: Path, assets: dict[str, JsonObject]) -> None:
    """Safely replace one dedicated Rufous build directory with encoded assets."""
    if output_dir.is_symlink():
        raise PublicExportError("public export output must not be a symbolic link")
    output = output_dir.resolve()
    existing_output = _validate_public_output_target(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix=f".{output.name}-", dir=output.parent))
    try:
        for relative, payload in assets.items():
            if relative.startswith("/") or ".." in Path(relative).parts:
                raise PublicExportError(f"unsafe public asset path: {relative}")
            destination = temporary / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            encoded = (
                json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
                + "\n"
            ).encode()
            if len(encoded) > MAX_PUBLIC_ASSET_BYTES:
                raise PublicExportError(f"public asset exceeds 25 MiB: {relative}")
            with destination.open("xb") as stream:
                stream.write(encoded)
                stream.flush()
                os.fsync(stream.fileno())
        _validate_public_output_target(temporary)
        _publish_public_tree(temporary, output, expected=existing_output)
    finally:
        if temporary.exists():
            shutil.rmtree(temporary)


def _validate_public_output_target(output: Path) -> _ValidatedPublicOutput:
    if output in {Path(output.anchor), output.parent, Path.cwd().resolve(), Path.home().resolve()}:
        raise PublicExportError("refusing unsafe public export output directory")
    if not output.exists():
        return _ValidatedPublicOutput(kind="absent")
    try:
        output_stat = output.lstat()
    except OSError as exc:
        raise PublicExportError("existing public export output could not be inspected") from exc
    if output.is_symlink() or not stat.S_ISDIR(output_stat.st_mode):
        raise PublicExportError("existing public export output must be a real directory")
    try:
        if next(output.iterdir(), None) is None:
            return _ValidatedPublicOutput(kind="empty")
    except OSError as exc:
        raise PublicExportError("existing public export output could not be inspected") from exc
    content_identity = _validate_existing_public_output(output)
    return _ValidatedPublicOutput(kind="rufous-public", content_identity=content_identity)


def _validate_existing_public_output(output: Path) -> str:
    try:
        manifest, manifest_bytes = _read_public_json(output / "data" / "manifest.json")
    except PublicExportError as exc:
        raise PublicExportError(
            "refusing to replace a non-empty directory without a valid Rufous public manifest"
        ) from exc
    if (
        set(manifest) != _PUBLIC_MANIFEST_KEYS
        or manifest.get("schema_version") != SCHEMA_VERSION
        or manifest.get("mode") != "public"
        or manifest.get("release_mode") not in {"synthetic", "production"}
        or manifest.get("region") != REGION
        or not isinstance(manifest.get("data_version"), str)
        or _SHA256.fullmatch(manifest["data_version"]) is None
    ):
        raise PublicExportError(
            "refusing to replace a non-empty directory without a valid Rufous public manifest"
        )
    expected_files = _public_manifest_paths(manifest)
    _validate_public_output_inventory(output, expected_files)
    assets: dict[str, JsonObject] = {"data/manifest.json": manifest}
    encoded_by_path = {"data/manifest.json": manifest_bytes}
    for relative in sorted(expected_files - {Path("data/manifest.json")}):
        payload, encoded = _read_public_json(output / relative)
        assets[relative.as_posix()] = payload
        encoded_by_path[relative.as_posix()] = encoded
    if semantic_data_version(assets) != manifest["data_version"]:
        raise PublicExportError("existing Rufous public output does not match its data version")
    digest = hashlib.sha256()
    for asset_path, encoded in sorted(encoded_by_path.items()):
        digest.update(asset_path.encode())
        digest.update(b"\0")
        digest.update(encoded)
        digest.update(b"\0")
    return digest.hexdigest()


def _public_manifest_paths(manifest: Mapping[str, object]) -> set[Path]:
    expected = {Path("data/manifest.json")}

    def add_path(raw: object, label: str) -> None:
        if not isinstance(raw, str) or not raw.startswith("/data/") or not raw.endswith(".json"):
            raise PublicExportError(f"existing Rufous public manifest has an invalid {label}")
        relative = Path(raw.removeprefix("/"))
        if (
            relative.is_absolute()
            or ".." in relative.parts
            or any(part in {"", "."} for part in relative.parts)
            or any(not re.fullmatch(r"[A-Za-z0-9._-]+", part) for part in relative.parts)
        ):
            raise PublicExportError(f"existing Rufous public manifest has an unsafe {label}")
        if relative in expected:
            raise PublicExportError("existing Rufous public manifest repeats an asset path")
        expected.add(relative)

    add_path(manifest.get("attribution_path"), "attribution path")
    for collection, path_field in (
        ("species", "profile_path"),
        ("cells", "path"),
        ("place_prefixes", "path"),
    ):
        rows = manifest.get(collection)
        if not isinstance(rows, list):
            raise PublicExportError(
                f"existing Rufous public manifest has a malformed {collection} list"
            )
        for row in rows:
            if not isinstance(row, dict):
                raise PublicExportError(
                    f"existing Rufous public manifest has a malformed {collection} item"
                )
            add_path(row.get(path_field), f"{collection} path")
    if len(expected) > MAX_PUBLIC_ASSET_FILES:
        raise PublicExportError("existing Rufous public output exceeds the file-count limit")
    return expected


def _validate_public_output_inventory(output: Path, expected_files: set[Path]) -> None:
    expected_directories: set[Path] = set()
    for relative in expected_files:
        parent = relative.parent
        while parent != Path("."):
            expected_directories.add(parent)
            parent = parent.parent
    actual_files: set[Path] = set()
    actual_directories: set[Path] = set()

    def walk_error(exc: OSError) -> None:
        raise PublicExportError("existing public export output could not be inspected") from exc

    for root, directories, files in os.walk(output, topdown=True, onerror=walk_error):
        root_path = Path(root)
        for name in directories:
            child = root_path / name
            try:
                child_stat = child.lstat()
            except OSError as exc:
                raise PublicExportError(
                    "existing public export output could not be inspected"
                ) from exc
            if child.is_symlink() or not stat.S_ISDIR(child_stat.st_mode):
                raise PublicExportError(
                    "existing public export output contains an unsafe directory"
                )
            actual_directories.add(child.relative_to(output))
        for name in files:
            child = root_path / name
            try:
                child_stat = child.lstat()
            except OSError as exc:
                raise PublicExportError(
                    "existing public export output could not be inspected"
                ) from exc
            if child.is_symlink() or not stat.S_ISREG(child_stat.st_mode):
                raise PublicExportError("existing public export output contains an unsafe file")
            actual_files.add(child.relative_to(output))
    if actual_files != expected_files or actual_directories != expected_directories:
        raise PublicExportError("existing public export output does not match its exact manifest")


def _read_public_json(path: Path) -> tuple[JsonObject, bytes]:
    try:
        file_stat = path.lstat()
    except OSError as exc:
        raise PublicExportError(
            "existing Rufous public output is missing a required asset"
        ) from exc
    if (
        path.is_symlink()
        or not stat.S_ISREG(file_stat.st_mode)
        or file_stat.st_size > MAX_PUBLIC_ASSET_BYTES
    ):
        raise PublicExportError("existing Rufous public output contains an unsafe asset")
    try:
        encoded = path.read_bytes()
        payload: object = json.loads(encoded)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise PublicExportError("existing Rufous public output contains invalid JSON") from exc
    if not isinstance(payload, dict):
        raise PublicExportError("existing Rufous public output asset must be a JSON object")
    return payload, encoded


def _publish_public_tree(
    stage: Path,
    output: Path,
    *,
    expected: _ValidatedPublicOutput,
) -> None:
    current = _validate_public_output_target(output)
    if current.state != expected.state:
        raise PublicExportError("public export output changed while replacement was being built")
    _fsync_tree_directories(stage)
    backup: Path | None = None
    if output.exists():
        backup = output.with_name(f".{output.name}.backup-{uuid.uuid4().hex}")
        try:
            os.replace(output, backup)
            _fsync_directory(output.parent)
        except OSError as exc:
            raise PublicExportError("could not preserve the previous public export") from exc
    try:
        os.replace(stage, output)
        _fsync_directory(output.parent)
    except OSError as exc:
        if backup is not None and backup.exists():
            try:
                os.replace(backup, output)
                _fsync_directory(output.parent)
            except OSError as restore_exc:
                raise PublicExportError(
                    "could not publish the public export or restore its preserved backup"
                ) from restore_exc
        raise PublicExportError("could not atomically publish the public export") from exc
    if backup is not None:
        try:
            shutil.rmtree(backup)
        except OSError:
            pass


def _fsync_directory(path: Path) -> None:
    try:
        descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
    except OSError:
        return
    try:
        os.fsync(descriptor)
    except OSError:
        pass
    finally:
        os.close(descriptor)


def _fsync_tree_directories(root: Path) -> None:
    for directory, _children, _files in os.walk(root, topdown=False):
        _fsync_directory(Path(directory))


def export_public_data(
    *,
    mode: ExportMode,
    output_dir: Path,
    database_path: Path | None = None,
    gnis_path: Path | None = None,
    gnis_sha256: str | None = None,
    media_manifest_path: Path | None = None,
    media_approvals_path: Path | None = None,
    generated_at: str | None = None,
) -> JsonObject:
    if mode == "synthetic":
        records = synthetic_records()
        pinned_sha = None
    else:
        if (
            database_path is None
            or gnis_path is None
            or not gnis_sha256
            or media_manifest_path is None
            or media_approvals_path is None
        ):
            raise PublicExportError(
                "production export requires --database, --gnis, --gnis-sha256, "
                "--media-manifest, and --media-approvals"
            )
        pinned_sha = gnis_sha256.strip().casefold()
        records = records_from_database(database_path, load_gnis_places(gnis_path, pinned_sha))
    if media_manifest_path is not None:
        selected_media: Mapping[str, str] | None = None
        excluded_media: frozenset[str] = frozenset()
        if mode == "production":
            assert media_approvals_path is not None
            try:
                media_plan = require_visual_approvals(media_manifest_path, media_approvals_path)
            except MediaApprovalError as exc:
                raise PublicExportError(f"public media visual approval failed: {exc}") from None
            selected_media = media_plan.selected_sha256_by_species
            excluded_media = media_plan.excluded_species
        attached = attach_public_media(
            records,
            load_public_media_manifest(
                media_manifest_path,
                selected_sha256_by_species=selected_media,
                excluded_species=excluded_media,
            ),
        )
        if mode == "production":
            rufous = next(
                (
                    species
                    for species in records.species
                    if str(species.get("scientific_name", "")).casefold() == "selasphorus rufus"
                ),
                None,
            )
            if attached == 0 or rufous is None or not rufous.get("media"):
                raise PublicExportError(
                    "production media must include an exact Rufous Hummingbird image"
                )
    assets = build_public_assets(
        records,
        mode=mode,
        gnis_sha256=pinned_sha,
        generated_at=generated_at,
    )
    write_public_assets(output_dir, assets)
    return assets["data/manifest.json"]


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=("synthetic", "production"), required=True)
    parser.add_argument("--output", type=Path, default=Path("build/rufous-public-data"))
    parser.add_argument("--database", type=Path)
    parser.add_argument("--gnis", type=Path)
    parser.add_argument("--gnis-sha256")
    parser.add_argument("--media-manifest", type=Path)
    parser.add_argument("--media-approvals", type=Path)
    parser.add_argument("--generated-at")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    try:
        manifest = export_public_data(
            mode=cast(ExportMode, args.mode),
            output_dir=args.output,
            database_path=args.database,
            gnis_path=args.gnis,
            gnis_sha256=args.gnis_sha256,
            media_manifest_path=args.media_manifest,
            media_approvals_path=args.media_approvals,
            generated_at=args.generated_at,
        )
    except (OSError, PublicExportError, duckdb.Error) as exc:
        print(f"Rufous public export failed: {exc}")
        return 1
    print(
        "Rufous public export complete: "
        f"mode={manifest['release_mode']} data_version={manifest['data_version']} "
        f"species={manifest['counts']['species']} observations={manifest['counts']['observations']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
