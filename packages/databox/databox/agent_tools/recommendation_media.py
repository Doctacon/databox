"""Bounded request-time photo and call selection for fixed recommendations.

Discovery is server-side metadata-only. The default transport reads at most one
MiB of JSON with a ten-second timeout; tests and callers may inject independent
GBIF and Xeno-canto getters. Media bytes are never requested or stored.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any, Literal, Protocol, cast
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlsplit
from urllib.request import Request, urlopen

from dotenv import load_dotenv

load_dotenv()

GBIF_OCCURRENCE_SEARCH = "https://api.gbif.org/v1/occurrence/search"
XENO_CANTO_RECORDINGS = "https://xeno-canto.org/api/3/recordings"
MAX_CANDIDATES = 50
MAX_RESPONSE_BYTES = 1_048_576
HTTP_TIMEOUT_SECONDS = 10.0
GBIF_IMAGE_SIZE = "500x500"

JsonGetter = Callable[[str, Mapping[str, object]], dict[str, Any]]
MediaStatus = Literal["available", "unavailable"]
MediaEvidenceType = Literal["recommendation_photo", "recommendation_call"]

_GBIF_IMAGE_CACHE_PATH = re.compile(
    r"^/v1/image/cache/(500x500)/occurrence/([1-9][0-9]*)/media/([0-9a-f]{32})$"
)
_XENO_HOSTS = frozenset({"xeno-canto.org", "www.xeno-canto.org"})
_CC_HOSTS = frozenset({"creativecommons.org", "www.creativecommons.org"})
_CC_URL = re.compile(r"^/licenses/([a-z0-9-]+)/([0-9]+(?:\.[0-9]+)?)/?$")
_CC_ZERO_URL = re.compile(r"^/publicdomain/zero/([0-9]+(?:\.[0-9]+)?)/?$")
_CC_STANDARD_SLUGS = frozenset({"by", "by-sa", "by-nc", "by-nc-sa"})
_CC_AUDIO_ND_SLUGS = frozenset({"by-nd", "by-nc-nd"})
_CC_STANDARD_VERSIONS = frozenset({"1.0", "2.0", "2.5", "3.0", "4.0"})
_ID = re.compile(r"^(?:XC)?([0-9]+)$", re.IGNORECASE)
_IMAGE_FORMATS = frozenset({"image/jpeg", "image/png", "image/webp"})


class RecommendationIdentity(Protocol):
    recommendation_id: str
    scientific_name: str | None


@dataclass(frozen=True)
class RecommendationMediaEvidence:
    recommendation_id: str
    source: Literal["gbif", "xeno_canto"]
    source_record_id: str | None
    evidence_type: Literal["recommendation_photo", "recommendation_call"]
    status: MediaStatus
    summary: dict[str, Any]
    payload: dict[str, Any]
    caveats: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class RecommendationMediaBatch:
    evidence: list[RecommendationMediaEvidence]
    lookup_count: int
    available_photos: int
    available_calls: int
    arizona_calls: int
    global_calls: int
    caveats: list[str] = field(default_factory=list)


def enrich_recommendation_media(
    recommendations: Sequence[RecommendationIdentity],
    *,
    gbif_getter: JsonGetter | None = None,
    xeno_getter: JsonGetter | None = None,
    xeno_api_key: str | None = None,
    evidence_types: frozenset[MediaEvidenceType] = frozenset(
        {"recommendation_photo", "recommendation_call"}
    ),
) -> RecommendationMediaBatch:
    """Select requested typed media results for every fixed recommendation."""

    if not evidence_types or not evidence_types <= {
        "recommendation_photo",
        "recommendation_call",
    }:
        raise ValueError("Unsupported recommendation media evidence type set")
    resolved_gbif = gbif_getter or _get_json
    resolved_xeno = xeno_getter or _get_json
    api_key = xeno_api_key if xeno_api_key is not None else os.getenv("XENO_CANTO_API_KEY")
    evidence: list[RecommendationMediaEvidence] = []
    lookup_count = 0

    for recommendation in recommendations:
        scientific_name = _normalize_species(recommendation.scientific_name)
        if scientific_name is None:
            if "recommendation_photo" in evidence_types:
                evidence.append(
                    _unavailable(
                        recommendation.recommendation_id,
                        "gbif",
                        "recommendation_photo",
                        "A conformed binomial scientific name is required for exact photo lookup",
                    )
                )
            if "recommendation_call" in evidence_types:
                evidence.append(
                    _unavailable(
                        recommendation.recommendation_id,
                        "xeno_canto",
                        "recommendation_call",
                        "A conformed binomial scientific name is required for exact call lookup",
                    )
                )
            continue

        if "recommendation_photo" in evidence_types:
            photo, attempted = _lookup_photo(
                recommendation.recommendation_id,
                scientific_name,
                resolved_gbif,
            )
            evidence.append(photo)
            lookup_count += attempted

        if "recommendation_call" in evidence_types:
            call, attempted = _lookup_call(
                recommendation.recommendation_id,
                scientific_name,
                resolved_xeno,
                api_key,
            )
            evidence.append(call)
            lookup_count += attempted

    return RecommendationMediaBatch(
        evidence=evidence,
        lookup_count=lookup_count,
        available_photos=sum(
            row.evidence_type == "recommendation_photo" and row.status == "available"
            for row in evidence
        ),
        available_calls=sum(
            row.evidence_type == "recommendation_call" and row.status == "available"
            for row in evidence
        ),
        arizona_calls=sum(
            row.evidence_type == "recommendation_call"
            and row.summary.get("geographic_scope") == "Arizona"
            for row in evidence
        ),
        global_calls=sum(
            row.evidence_type == "recommendation_call"
            and row.summary.get("geographic_scope") == "Global example"
            for row in evidence
        ),
        caveats=sorted({caveat for row in evidence for caveat in row.caveats}),
    )


def _lookup_photo(
    recommendation_id: str,
    scientific_name: str,
    getter: JsonGetter,
) -> tuple[RecommendationMediaEvidence, int]:
    params: dict[str, object] = {
        "scientificName": scientific_name,
        "country": "US",
        "stateProvince": "Arizona",
        "mediaType": "StillImage",
        "limit": MAX_CANDIDATES,
        "offset": 0,
    }
    try:
        payload = getter(GBIF_OCCURRENCE_SEARCH, params)
        candidates = _gbif_candidates(payload, scientific_name)
    except Exception:  # noqa: BLE001 - upstream failures become typed unavailable evidence.
        return (
            _unavailable(
                recommendation_id,
                "gbif",
                "recommendation_photo",
                "GBIF photo lookup was unavailable or malformed",
            ),
            1,
        )
    if not candidates:
        return (
            _unavailable(
                recommendation_id,
                "gbif",
                "recommendation_photo",
                "No eligible exact-species Arizona GBIF photo was found",
            ),
            1,
        )
    selected = min(candidates, key=lambda item: item[0])[1]
    selected["recommendation_id"] = recommendation_id
    return RecommendationMediaEvidence(**selected), 1


def _gbif_candidates(
    payload: Mapping[str, Any], scientific_name: str
) -> list[tuple[tuple[object, ...], dict[str, Any]]]:
    results = payload.get("results")
    if not isinstance(results, list):
        raise ValueError("GBIF response is missing results")
    candidates: list[tuple[tuple[object, ...], dict[str, Any]]] = []
    for occurrence in results[:MAX_CANDIDATES]:
        if not isinstance(occurrence, dict):
            continue
        occurrence_id = _integer_id(occurrence.get("key"))
        identity = _occurrence_species(occurrence)
        media_rows = occurrence.get("media")
        if (
            occurrence_id is None
            or identity != scientific_name
            or not _is_arizona_gbif_occurrence(occurrence)
            or not isinstance(media_rows, list)
        ):
            continue
        source_url = f"https://www.gbif.org/occurrence/{occurrence_id}"
        publisher = _text(occurrence.get("publishingOrgKey")) or _text(
            occurrence.get("institutionCode")
        )
        for media in media_rows[:MAX_CANDIDATES]:
            if not isinstance(media, dict):
                continue
            candidate = _gbif_media(
                media,
                occurrence_id=occurrence_id,
                species=scientific_name,
                source_url=source_url,
                publisher=publisher,
            )
            if candidate is not None:
                candidates.append(candidate)
    return candidates


def _gbif_media(
    media: Mapping[str, Any],
    *,
    occurrence_id: str,
    species: str,
    source_url: str,
    publisher: str | None,
) -> tuple[tuple[object, ...], dict[str, Any]] | None:
    if _text(media.get("type")) != "StillImage":
        return None
    image_format = (_text(media.get("format")) or "").lower()
    if image_format not in _IMAGE_FORMATS:
        return None
    identifier = _safe_https_provenance_url(media.get("identifier"))
    if identifier is None:
        return None
    creator = _text(media.get("creator"))
    rights_holder = _text(media.get("rightsHolder"))
    if creator is None and rights_holder is None:
        return None
    license_info = parse_creative_commons_license(media.get("license"), allow_audio_nd=False)
    if license_info is None:
        return None
    license_code, license_url, _ = license_info
    identifier_md5 = _identifier_md5(identifier)
    display_url = safe_gbif_photo_url(
        _gbif_cache_url(occurrence_id, identifier_md5),
        occurrence_id=occurrence_id,
        original_identifier=identifier,
    )
    if display_url is None:
        return None
    media_id = f"{occurrence_id}:{identifier_md5}"
    selection_reason = (
        "Exact Arizona species image with complete attribution, supported CC license, "
        "and GBIF cache URL derived from occurrence key plus identifier MD5"
    )
    summary = {
        "kind": "photo",
        "species_name": species,
        "creator": creator,
        "rights_holder": rights_holder,
        "publisher": publisher,
        "format": image_format,
        "license_code": license_code,
        "license_url": license_url,
        "source_url": source_url,
        "display_url": display_url,
        "selection_reason": selection_reason,
        "geographic_scope": "Arizona",
    }
    payload = {
        "gbif_occurrence_id": occurrence_id,
        "gbif_media_id": media_id,
        "normalized_species": species,
        "original_media_identifier": identifier,
        "original_media_identifier_md5": identifier_md5,
    }
    rank = (
        0 if creator and rights_holder else 1,
        int(occurrence_id),
        identifier_md5,
        identifier,
        creator or "",
        rights_holder or "",
        publisher or "",
        image_format,
        license_code,
        license_url,
        source_url,
    )
    return rank, {
        "source": "gbif",
        "source_record_id": occurrence_id,
        "evidence_type": "recommendation_photo",
        "status": "available",
        "summary": summary,
        "payload": payload,
        "caveats": [],
    }


def _lookup_call(
    recommendation_id: str,
    scientific_name: str,
    getter: JsonGetter,
    api_key: str | None,
) -> tuple[RecommendationMediaEvidence, int]:
    if not api_key:
        return (
            _unavailable(
                recommendation_id,
                "xeno_canto",
                "recommendation_call",
                "Xeno-canto call lookup is not configured",
            ),
            0,
        )
    genus, species = scientific_name.split()
    attempts = 0
    for scope, query in (
        ("Arizona", f'gen:"{genus}" sp:"{species}" cnt:"United States" loc:"Arizona"'),
        ("Global example", f'gen:"{genus}" sp:"{species}"'),
    ):
        attempts += 1
        try:
            payload = getter(
                XENO_CANTO_RECORDINGS,
                {"query": query, "page": 1, "per_page": MAX_CANDIDATES, "key": api_key},
            )
            candidates = _xeno_candidates(payload, scientific_name, scope)
        except Exception:  # noqa: BLE001 - bounded fallback remains safe and non-fatal.
            candidates = []
        if candidates:
            selected = min(candidates, key=lambda item: item[0])[1]
            selected["recommendation_id"] = recommendation_id
            return RecommendationMediaEvidence(**selected), attempts
    return (
        _unavailable(
            recommendation_id,
            "xeno_canto",
            "recommendation_call",
            "No eligible exact-species Xeno-canto call was found",
        ),
        attempts,
    )


def _xeno_candidates(
    payload: Mapping[str, Any], scientific_name: str, scope: str
) -> list[tuple[tuple[object, ...], dict[str, Any]]]:
    rows = payload.get("recordings")
    if not isinstance(rows, list):
        raise ValueError("Xeno-canto response is missing recordings")
    candidates: list[tuple[tuple[object, ...], dict[str, Any]]] = []
    for row in rows[:MAX_CANDIDATES]:
        if not isinstance(row, dict):
            continue
        recording_id = _integer_id(row.get("id"))
        species = _normalize_species(f"{_text(row.get('gen')) or ''} {_text(row.get('sp')) or ''}")
        recordist = _text(row.get("rec"))
        if (
            recording_id is None
            or species != scientific_name
            or recordist is None
            or (scope == "Arizona" and not _is_arizona_xeno_recording(row))
        ):
            continue
        source_url = _safe_xeno_url(row.get("url"), recording_id, audio=False)
        audio_url = _safe_xeno_url(row.get("file"), recording_id, audio=True)
        license_info = parse_creative_commons_license(row.get("lic"), allow_audio_nd=True)
        if source_url is None or audio_url is None or license_info is None:
            continue
        license_code, license_url, _ = license_info
        recording_type = _text(row.get("type"))
        quality = (_text(row.get("q")) or "").upper()
        type_rank = _call_type_rank(recording_type)
        quality_rank = {letter: index for index, letter in enumerate("ABCDE")}.get(quality, 9)
        selection_reason = (
            f"Exact-species {scope} recording; call type, quality, then recording ID ranking"
        )
        locality = _text(row.get("loc"))
        country = _text(row.get("cnt"))
        summary = {
            "kind": "call",
            "species_name": scientific_name,
            "geographic_scope": scope,
            "recording_type": recording_type,
            "quality": quality or None,
            "recordist": recordist,
            "locality": locality,
            "country": country,
            "license_code": license_code,
            "license_url": license_url,
            "source_url": source_url,
            "audio_url": audio_url,
            "selection_reason": selection_reason,
        }
        payload = {
            "recording_id": recording_id,
            "normalized_species": scientific_name,
        }
        candidates.append(
            (
                (
                    type_rank,
                    quality_rank,
                    int(recording_id),
                    scientific_name,
                    (recording_type or "").casefold(),
                    quality,
                    recordist.casefold(),
                    (country or "").casefold(),
                    (locality or "").casefold(),
                    recording_type or "",
                    recordist,
                    country or "",
                    locality or "",
                    source_url,
                    audio_url,
                    license_code,
                    license_url,
                ),
                {
                    "source": "xeno_canto",
                    "source_record_id": recording_id,
                    "evidence_type": "recommendation_call",
                    "status": "available",
                    "summary": summary,
                    "payload": payload,
                    "caveats": [],
                },
            )
        )
    return candidates


def _unavailable(
    recommendation_id: str,
    source: Literal["gbif", "xeno_canto"],
    evidence_type: Literal["recommendation_photo", "recommendation_call"],
    caveat: str,
) -> RecommendationMediaEvidence:
    return RecommendationMediaEvidence(
        recommendation_id=recommendation_id,
        source=source,
        source_record_id=None,
        evidence_type=evidence_type,
        status="unavailable",
        summary={"kind": "photo" if source == "gbif" else "call", "status": "unavailable"},
        payload={},
        caveats=[caveat],
    )


def _occurrence_species(row: Mapping[str, Any]) -> str | None:
    values = [
        value
        for value in (row.get("species"), row.get("acceptedScientificName"))
        if value is not None
    ]
    normalized = {_normalize_species(value) for value in values}
    normalized.discard(None)
    if len(normalized) != 1:
        return None
    return normalized.pop()


def _normalize_species(value: object) -> str | None:
    text = _text(value)
    if text is None:
        return None
    words = text.split()
    if len(words) < 2:
        return None
    genus, species = words[:2]
    if not genus.isalpha() or not species.replace("-", "").isalpha():
        return None
    return f"{genus.lower().capitalize()} {species.lower()}"


def parse_creative_commons_license(
    value: object, *, allow_audio_nd: bool
) -> tuple[str, str, bool] | None:
    """Parse only ratified Creative Commons families and real version numbers."""

    raw = _text(value)
    if raw is None:
        return None
    candidate = f"https:{raw}" if raw.startswith("//") else raw
    slug: str | None = None
    version: str | None = None
    is_zero = False
    if candidate.startswith("http"):
        try:
            parsed = urlsplit(candidate)
            if parsed.port is not None:
                return None
        except ValueError:
            return None
        if (
            parsed.scheme not in {"http", "https"}
            or parsed.hostname not in _CC_HOSTS
            or parsed.username is not None
            or parsed.password is not None
            or parsed.query
            or parsed.fragment
        ):
            return None
        match = _CC_URL.fullmatch(parsed.path)
        zero = _CC_ZERO_URL.fullmatch(parsed.path)
        if match:
            slug, version = match.groups()
        elif zero:
            version = zero.group(1)
            is_zero = True
        else:
            return None
    else:
        zero_enum = re.fullmatch(r"CC0_([0-9]+)_([0-9]+)", raw.upper())
        zero_text = re.fullmatch(r"CC0\s+([0-9]+(?:\.[0-9]+)?)", raw.upper())
        enum_match = re.fullmatch(
            r"CC_(BY|BY_SA|BY_NC|BY_NC_SA|BY_ND|BY_NC_ND)_([0-9]+)_([0-9]+)",
            raw.upper(),
        )
        text_match = re.fullmatch(
            r"CC\s+(BY|BY-SA|BY-NC|BY-NC-SA|BY-ND|BY-NC-ND)\s+([0-9]+(?:\.[0-9]+)?)",
            raw.upper(),
        )
        if zero_enum:
            version = f"{zero_enum.group(1)}.{zero_enum.group(2)}"
            is_zero = True
        elif zero_text:
            version = zero_text.group(1)
            is_zero = True
        elif enum_match:
            slug = enum_match.group(1).replace("_", "-").lower()
            version = f"{enum_match.group(2)}.{enum_match.group(3)}"
        elif text_match:
            slug = text_match.group(1).lower()
            version = text_match.group(2)
        else:
            return None
    if is_zero:
        if version != "1.0":
            return None
        return (
            "CC0 1.0",
            "https://creativecommons.org/publicdomain/zero/1.0/",
            False,
        )
    if slug is None or version not in _CC_STANDARD_VERSIONS:
        return None
    allowed_slugs = _CC_STANDARD_SLUGS | (_CC_AUDIO_ND_SLUGS if allow_audio_nd else frozenset())
    if slug not in allowed_slugs:
        return None
    return (
        f"CC {slug.upper()} {version}",
        f"https://creativecommons.org/licenses/{slug}/{version}/",
        slug in _CC_AUDIO_ND_SLUGS,
    )


def safe_gbif_photo_url(
    value: object, *, occurrence_id: str, original_identifier: object
) -> str | None:
    """Validate the exact GBIF cache path and its occurrence-key/MD5 relation."""

    raw = _text(value)
    identifier = _safe_https_provenance_url(original_identifier)
    if raw is None or identifier is None or not occurrence_id.isdigit():
        return None
    try:
        parsed = urlsplit(raw)
        if parsed.port is not None:
            return None
    except ValueError:
        return None
    if (
        parsed.scheme != "https"
        or parsed.hostname != "api.gbif.org"
        or parsed.username is not None
        or parsed.password is not None
        or parsed.query
        or parsed.fragment
    ):
        return None
    match = _GBIF_IMAGE_CACHE_PATH.fullmatch(parsed.path)
    if match is None:
        return None
    size, path_occurrence_id, identifier_md5 = match.groups()
    if (
        size != GBIF_IMAGE_SIZE
        or path_occurrence_id != str(int(occurrence_id))
        or identifier_md5 != _identifier_md5(identifier)
    ):
        return None
    return raw


def _identifier_md5(identifier: str) -> str:
    return hashlib.md5(identifier.encode("utf-8"), usedforsecurity=False).hexdigest()


def _gbif_cache_url(occurrence_id: str, identifier_md5: str) -> str:
    return (
        f"https://api.gbif.org/v1/image/cache/{GBIF_IMAGE_SIZE}/occurrence/"
        f"{occurrence_id}/media/{identifier_md5}"
    )


def _safe_https_provenance_url(value: object) -> str | None:
    raw = _text(value)
    if raw is None:
        return None
    try:
        parsed = urlsplit(raw)
        if parsed.port is not None:
            return None
    except ValueError:
        return None
    if (
        parsed.scheme != "https"
        or parsed.hostname is None
        or parsed.username is not None
        or parsed.password is not None
        or parsed.fragment
    ):
        return None
    return raw


def _is_arizona_gbif_occurrence(row: Mapping[str, Any]) -> bool:
    countries = {
        value.casefold()
        for value in (_text(row.get("countryCode")), _text(row.get("country")))
        if value is not None
    }
    state = (_text(row.get("stateProvince")) or "").casefold()
    return (
        bool(countries)
        and countries <= {"us", "united states", "united states of america"}
        and state == "arizona"
    )


def _is_arizona_xeno_recording(row: Mapping[str, Any]) -> bool:
    country = (_text(row.get("cnt")) or "").casefold()
    locality = (_text(row.get("loc")) or "").casefold()
    return country == "united states" and re.search(r"\barizona\b", locality) is not None


def _safe_url(value: object, hosts: frozenset[str]) -> str | None:
    raw = _text(value)
    if raw is None:
        return None
    candidate = f"https:{raw}" if raw.startswith("//") else raw
    try:
        parsed = urlsplit(candidate)
        if parsed.port is not None:
            return None
    except ValueError:
        return None
    if (
        parsed.scheme != "https"
        or parsed.hostname not in hosts
        or parsed.username is not None
        or parsed.password is not None
        or not parsed.path.startswith("/")
        or parsed.fragment
    ):
        return None
    return candidate


def _safe_xeno_url(value: object, recording_id: str, *, audio: bool) -> str | None:
    candidate = _safe_url(value, _XENO_HOSTS)
    if candidate is None:
        return None
    parsed = urlsplit(candidate)
    expected = f"/{recording_id}/download" if audio else f"/{recording_id}"
    if parsed.path.rstrip("/") != expected or parsed.query:
        return None
    return candidate


def _integer_id(value: object) -> str | None:
    if isinstance(value, bool):
        return None
    raw = str(value) if isinstance(value, int) else _text(value)
    if raw is None:
        return None
    match = _ID.fullmatch(raw)
    return str(int(match.group(1))) if match else None


def _call_type_rank(value: str | None) -> int:
    if value is None:
        return 2
    tokens = {token.strip().lower() for token in re.split(r"[,;/]", value)}
    if any("call" in token for token in tokens):
        return 0
    if "song" in tokens:
        return 1
    return 2


def _text(value: object) -> str | None:
    return value.strip() if isinstance(value, str) and value.strip() else None


def _get_json(endpoint: str, params: Mapping[str, object]) -> dict[str, Any]:
    """Read one bounded JSON object using the fixed HTTPS discovery endpoints."""

    if endpoint not in {GBIF_OCCURRENCE_SEARCH, XENO_CANTO_RECORDINGS}:
        raise ValueError("unsupported recommendation-media endpoint")
    url = f"{endpoint}?{urlencode(params)}"
    request = Request(url, headers={"Accept": "application/json", "User-Agent": "databox/1"})
    transport_failed = False
    body = b""
    try:
        with urlopen(request, timeout=HTTP_TIMEOUT_SECONDS) as response:  # noqa: S310
            declared = response.headers.get("Content-Length")
            if declared is not None and int(declared) > MAX_RESPONSE_BYTES:
                raise ValueError("recommendation-media response is too large")
            body = response.read(MAX_RESPONSE_BYTES + 1)
    except (TimeoutError, HTTPError, URLError, OSError, ValueError):
        transport_failed = True
    if transport_failed or len(body) > MAX_RESPONSE_BYTES:
        raise RuntimeError("recommendation-media discovery failed") from None
    payload: object = None
    try:
        payload = json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        pass
    if not isinstance(payload, dict):
        raise RuntimeError("recommendation-media discovery failed") from None
    return cast(dict[str, Any], payload)
