"""Fail-closed iNaturalist taxon-photo discovery for missing public birds.

The caller owns the missing-species set.  This source only preserves candidates
whose exact active species identity, creator, dimensions, URLs, and commercial
Creative Commons license can all be established from the curated taxon-photo
shortlist.  It never downloads image bytes and does not use a credential.
"""

from __future__ import annotations

import hashlib
import json
import re
import threading
import time
from collections.abc import Iterator, Mapping, Sequence
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlsplit

import dlt
import pendulum
from dlt.sources.helpers import requests as dlt_requests

from databox_sources._logging import get_logger

log = get_logger("databox_sources.inaturalist")

INATURALIST_V2_TAXA_URL = "https://api.inaturalist.org/v2/taxa"
INATURALIST_V1_TAXON_URL = "https://api.inaturalist.org/v1/taxa/{taxon_id}"
INATURALIST_MAX_TARGET_SPECIES = 500
INATURALIST_MAX_CURATED_PHOTOS = 20
INATURALIST_REQUEST_MAX_ATTEMPTS = 3
INATURALIST_REQUEST_TIMEOUT_SECONDS = 10
INATURALIST_RETRY_BASE_SECONDS = 1.0
INATURALIST_RETRY_MAX_SECONDS = 8.0
INATURALIST_MAX_RESPONSE_BYTES = 1 * 1024 * 1024
INATURALIST_RESPONSE_CHUNK_BYTES = 64 * 1024
INATURALIST_MIN_LONG_EDGE = 1_000
INATURALIST_MIN_SHORT_EDGE = 750
INATURALIST_MAX_EDGE = 100_000
INATURALIST_USER_AGENT = "loughondata.com Rufous bird-media showcase (connor@loughondata.com)"

_SPECIES_CODE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,99}$")
_SCIENTIFIC_NAME = re.compile(r"^[A-Z][A-Za-z-]+ [a-z][A-Za-z-]+$")
_PHOTO_PATH = re.compile(
    r"^/photos/([1-9][0-9]*)/(?:square|small|medium|large|original)\."
    r"(jpg|jpeg|png|webp)$",
    re.IGNORECASE,
)
_SOURCE_PAGE_PATH = re.compile(r"^/photos/([1-9][0-9]*)$")
# Audited against iNaturalist's official Shared::LicenseModule::CC_VERSION.
# Keep this reviewed local constant: release safety must not depend on mutable
# GitHub source at runtime. CC0 has its own fixed 1.0 public-domain version.
INATURALIST_SHARED_CC_VERSION = "4.0"
_SAFE_LICENSES = {
    "cc0": ("CC0 1.0", "https://creativecommons.org/publicdomain/zero/1.0/"),
    "cc-by": (
        f"CC BY {INATURALIST_SHARED_CC_VERSION}",
        f"https://creativecommons.org/licenses/by/{INATURALIST_SHARED_CC_VERSION}/",
    ),
    "cc-by-sa": (
        f"CC BY-SA {INATURALIST_SHARED_CC_VERSION}",
        f"https://creativecommons.org/licenses/by-sa/{INATURALIST_SHARED_CC_VERSION}/",
    ),
}
_RETRYABLE_STATUS_CODES = frozenset({429, 500, 502, 503, 504})
_UNTRUSTWORTHY_CREATORS = frozenset(
    {"anonymous", "author unknown", "creator unknown", "inat staff", "inaturalist", "unknown"}
)
_UNTRUSTWORTHY_CREATOR_WORD = re.compile(r"(?:^|[^a-z])(anonymous|unknown)(?:[^a-z]|$)")
_HTTP_SESSION = dlt_requests.Session(
    timeout=INATURALIST_REQUEST_TIMEOUT_SECONDS,
    raise_for_status=False,
)
_http_get = _HTTP_SESSION.get

_RUN_COLUMNS: Any = {
    "run_id": {"data_type": "text"},
    "status": {"data_type": "text"},
    "target_species_count": {"data_type": "bigint"},
    "exact_species_count": {"data_type": "bigint"},
    "species_with_candidates": {"data_type": "bigint"},
    "curated_photos_inspected": {"data_type": "bigint"},
    "eligible_candidate_count": {"data_type": "bigint"},
    "request_count": {"data_type": "bigint"},
    "max_curated_photos": {"data_type": "bigint"},
    "request_max_attempts": {"data_type": "bigint"},
    "started_at": {"data_type": "timestamp"},
    "completed_at": {"data_type": "timestamp"},
    "_loaded_at": {"data_type": "timestamp"},
}

_SPECIES_COLUMNS: Any = {
    "run_id": {"data_type": "text"},
    "species_code": {"data_type": "text"},
    "target_common_name": {"data_type": "text"},
    "target_scientific_name": {"data_type": "text"},
    "taxon_id": {"data_type": "bigint"},
    "identity_status": {"data_type": "text"},
    "curated_photo_count": {"data_type": "bigint"},
    "curated_photos_inspected": {"data_type": "bigint"},
    "eligible_candidate_count": {"data_type": "bigint"},
    "rejection_counts_json": {"data_type": "text"},
    "_loaded_at": {"data_type": "timestamp"},
}

_PHOTO_COLUMNS: Any = {
    "run_id": {"data_type": "text"},
    "species_code": {"data_type": "text"},
    "target_common_name": {"data_type": "text"},
    "target_scientific_name": {"data_type": "text"},
    "taxon_id": {"data_type": "bigint"},
    "photo_id": {"data_type": "bigint"},
    "curated_position": {"data_type": "bigint"},
    "source_page_url": {"data_type": "text"},
    "source_image_original_url": {"data_type": "text"},
    "source_image_large_url": {"data_type": "text"},
    "creator": {"data_type": "text"},
    "license_code": {"data_type": "text"},
    "license_url": {"data_type": "text"},
    "original_width": {"data_type": "bigint"},
    "original_height": {"data_type": "bigint"},
    "_loaded_at": {"data_type": "timestamp"},
}


@dataclass(frozen=True)
class MissingSpecies:
    species_code: str
    common_name: str
    scientific_name: str


@dataclass(frozen=True)
class _Snapshot:
    run: dict[str, Any]
    species_results: tuple[dict[str, Any], ...]
    candidates: tuple[dict[str, Any], ...]


class _RetryableRequestError(RuntimeError):
    """A bounded provider request can be attempted again."""


def _clean_text(value: object, *, maximum: int) -> str | None:
    if not isinstance(value, str):
        return None
    text = " ".join(value.split())
    if (
        not text
        or len(text) > maximum
        or "<" in text
        or ">" in text
        or any(ord(character) < 32 for character in text)
    ):
        return None
    return text


def _positive_int(value: object) -> int | None:
    return value if isinstance(value, int) and not isinstance(value, bool) and value > 0 else None


def _normalize_targets(
    missing_species: Sequence[Mapping[str, str]] | None,
) -> tuple[MissingSpecies, ...]:
    if not missing_species:
        return ()
    if len(missing_species) > INATURALIST_MAX_TARGET_SPECIES:
        raise ValueError(
            f"iNaturalist supports at most {INATURALIST_MAX_TARGET_SPECIES} missing species"
        )
    output: list[MissingSpecies] = []
    seen_codes: set[str] = set()
    seen_names: set[str] = set()
    for row in missing_species:
        if not isinstance(row, Mapping):
            raise ValueError("iNaturalist missing species target is malformed")
        species_code = _clean_text(row.get("species_code"), maximum=100)
        common_name = _clean_text(row.get("common_name"), maximum=300)
        scientific_name = _clean_text(row.get("scientific_name"), maximum=300)
        if species_code is None or not _SPECIES_CODE.fullmatch(species_code):
            raise ValueError("iNaturalist missing species_code is invalid")
        if common_name is None:
            raise ValueError("iNaturalist missing common_name is invalid")
        if scientific_name is None or not _SCIENTIFIC_NAME.fullmatch(scientific_name):
            raise ValueError("iNaturalist requires an exact binomial scientific name")
        folded_name = scientific_name.casefold()
        if species_code in seen_codes or folded_name in seen_names:
            raise ValueError("iNaturalist missing species targets are duplicated")
        seen_codes.add(species_code)
        seen_names.add(folded_name)
        output.append(MissingSpecies(species_code, common_name, scientific_name))
    return tuple(output)


def _endpoint_is_safe(endpoint: str) -> bool:
    if endpoint == INATURALIST_V2_TAXA_URL:
        return True
    return bool(re.fullmatch(r"https://api\.inaturalist\.org/v1/taxa/[1-9][0-9]*", endpoint))


def _response_url_is_safe(value: object, endpoint: str) -> bool:
    if not isinstance(value, str):
        return False
    try:
        actual = urlsplit(value)
        expected = urlsplit(endpoint)
        if actual.port is not None:
            return False
    except ValueError:
        return False
    return bool(
        actual.scheme == expected.scheme == "https"
        and actual.hostname == expected.hostname == "api.inaturalist.org"
        and actual.path == expected.path
        and actual.username is None
        and actual.password is None
        and not actual.fragment
    )


def _response_body(response: Any) -> bytes:
    declared = response.headers.get("Content-Length")
    try:
        if declared is not None:
            declared_size = int(declared)
            if declared_size < 0:
                raise RuntimeError("iNaturalist metadata Content-Length is malformed")
            if declared_size > INATURALIST_MAX_RESPONSE_BYTES:
                raise RuntimeError("iNaturalist metadata response exceeds the byte limit")
    except (TypeError, ValueError):
        raise RuntimeError("iNaturalist metadata Content-Length is malformed") from None
    body = bytearray()
    for chunk in response.iter_content(chunk_size=INATURALIST_RESPONSE_CHUNK_BYTES):
        if not isinstance(chunk, bytes):
            raise RuntimeError("iNaturalist metadata response yielded a non-byte chunk")
        body.extend(chunk)
        if len(body) > INATURALIST_MAX_RESPONSE_BYTES:
            raise RuntimeError("iNaturalist metadata response exceeds the byte limit")
    return bytes(body)


def _request_json(
    endpoint: str, params: Mapping[str, object], *, max_attempts: int
) -> tuple[dict[str, Any], int]:
    if not _endpoint_is_safe(endpoint):
        raise ValueError("unsupported iNaturalist API endpoint")
    for attempt in range(1, max_attempts + 1):
        try:
            # Use a plain Session, not dlt's retrying global client.  This loop
            # is the sole request-attempt authority and therefore the bound is
            # exact rather than multiplied by an implicit transport retry.
            response = _http_get(
                endpoint,
                params=dict(params),
                headers={"Accept": "application/json", "User-Agent": INATURALIST_USER_AGENT},
                timeout=INATURALIST_REQUEST_TIMEOUT_SECONDS,
                stream=True,
                allow_redirects=False,
            )
            try:
                status_code = int(response.status_code)
                if status_code in _RETRYABLE_STATUS_CODES:
                    raise _RetryableRequestError(f"iNaturalist returned HTTP {status_code}")
                if status_code != 200:
                    raise RuntimeError(f"iNaturalist returned HTTP {status_code}")
                if not _response_url_is_safe(response.url, endpoint):
                    raise RuntimeError("iNaturalist metadata response origin changed")
                body = _response_body(response)
            finally:
                close = getattr(response, "close", None)
                if callable(close):
                    close()
            payload = json.loads(body.decode("utf-8"))
            if not isinstance(payload, dict):
                raise RuntimeError("iNaturalist metadata response is not an object")
            return payload, attempt
        except _RetryableRequestError:
            if attempt == max_attempts:
                raise RuntimeError(
                    f"iNaturalist request failed after {max_attempts} attempts"
                ) from None
        except dlt_requests.RequestException:
            if attempt == max_attempts:
                raise RuntimeError(
                    f"iNaturalist request failed after {max_attempts} attempts"
                ) from None
        except (UnicodeDecodeError, json.JSONDecodeError):
            raise RuntimeError("iNaturalist metadata response is malformed") from None
        time.sleep(
            min(
                INATURALIST_RETRY_BASE_SECONDS * (2 ** (attempt - 1)),
                INATURALIST_RETRY_MAX_SECONDS,
            )
        )
    raise AssertionError("bounded iNaturalist retry loop exited unexpectedly")


def _exact_taxon_id(payload: Mapping[str, Any], scientific_name: str) -> int | None:
    rows = payload.get("results")
    if not isinstance(rows, list) or len(rows) > INATURALIST_MAX_CURATED_PHOTOS:
        raise RuntimeError("iNaturalist taxon-search schema is malformed")
    exact: list[int] = []
    for row in rows:
        if not isinstance(row, dict):
            raise RuntimeError("iNaturalist taxon-search row is malformed")
        taxon_id = _positive_int(row.get("id"))
        if (
            row.get("name") == scientific_name
            and row.get("rank") == "species"
            and row.get("is_active") is True
            and taxon_id is not None
        ):
            exact.append(taxon_id)
    return exact[0] if len(exact) == 1 else None


def _taxon_photos(
    payload: Mapping[str, Any], *, scientific_name: str, taxon_id: int
) -> list[object] | None:
    rows = payload.get("results")
    if not isinstance(rows, list) or len(rows) != 1 or not isinstance(rows[0], dict):
        raise RuntimeError("iNaturalist taxon-detail schema is malformed")
    row = rows[0]
    if (
        _positive_int(row.get("id")) != taxon_id
        or row.get("name") != scientific_name
        or row.get("rank") != "species"
        or row.get("is_active") is not True
    ):
        return None
    photos = row.get("taxon_photos")
    if not isinstance(photos, list):
        raise RuntimeError("iNaturalist curated-photo schema is malformed")
    return photos


def _strict_sized_photo_url(value: object, *, photo_id: int, size: str) -> str | None:
    if not isinstance(value, str) or len(value) > 2_000:
        return None
    try:
        parsed = urlsplit(value)
        if parsed.port is not None:
            return None
    except ValueError:
        return None
    if (
        parsed.scheme != "https"
        or parsed.hostname != "inaturalist-open-data.s3.amazonaws.com"
        or parsed.username is not None
        or parsed.password is not None
        or parsed.query
        or parsed.fragment
    ):
        return None
    match = _PHOTO_PATH.fullmatch(parsed.path)
    if (
        match is None
        or int(match.group(1)) != photo_id
        or parsed.path.split("/")[-1].split(".", 1)[0].casefold() != size
    ):
        return None
    return value


def _strict_photo_urls(
    original_value: object, large_value: object, *, photo_id: int
) -> tuple[str, str] | None:
    original = _strict_sized_photo_url(original_value, photo_id=photo_id, size="original")
    large = _strict_sized_photo_url(large_value, photo_id=photo_id, size="large")
    return (original, large) if original is not None and large is not None else None


def _safe_source_page(photo_id: int) -> str:
    value = f"https://www.inaturalist.org/photos/{photo_id}"
    parsed = urlsplit(value)
    match = _SOURCE_PAGE_PATH.fullmatch(parsed.path)
    assert (
        parsed.scheme == "https"
        and parsed.hostname == "www.inaturalist.org"
        and match is not None
        and int(match.group(1)) == photo_id
    )
    return value


def _credible_creator(value: object) -> str | None:
    creator = _clean_text(value, maximum=500)
    if (
        creator is None
        or len(creator) < 2
        or creator.casefold() in _UNTRUSTWORTHY_CREATORS
        or _UNTRUSTWORTHY_CREATOR_WORD.search(creator.casefold())
    ):
        return None
    return creator


def _credible_dimensions(value: object) -> tuple[int, int] | None:
    if not isinstance(value, dict):
        return None
    width = _positive_int(value.get("width"))
    height = _positive_int(value.get("height"))
    if (
        width is None
        or height is None
        or max(width, height) > INATURALIST_MAX_EDGE
        or max(width, height) < INATURALIST_MIN_LONG_EDGE
        or min(width, height) < INATURALIST_MIN_SHORT_EDGE
    ):
        return None
    return width, height


def _candidate(
    raw: object,
    *,
    target: MissingSpecies,
    taxon_id: int,
    position: int,
    run_id: str,
    loaded_at: str,
) -> tuple[dict[str, Any] | None, str]:
    if not isinstance(raw, dict) or not isinstance(raw.get("photo"), dict):
        return None, "malformed"
    photo = raw["photo"]
    photo_id = _positive_int(photo.get("id"))
    if photo_id is None:
        return None, "malformed"
    license_info = (
        _SAFE_LICENSES.get(photo.get("license_code").casefold())
        if isinstance(photo.get("license_code"), str)
        else None
    )
    if license_info is None:
        return None, "license"
    creator = _credible_creator(photo.get("attribution"))
    if creator is None:
        return None, "creator"
    dimensions = _credible_dimensions(photo.get("original_dimensions"))
    if dimensions is None:
        return None, "dimensions"
    # Use the exact provider-returned objects. Deriving the original extension
    # from a thumbnail URL can invent a non-existent S3 key.
    urls = _strict_photo_urls(
        photo.get("original_url"),
        photo.get("large_url"),
        photo_id=photo_id,
    )
    if urls is None:
        return None, "url"
    original_url, large_url = urls
    license_code, license_url = license_info
    return (
        {
            "run_id": run_id,
            "species_code": target.species_code,
            "target_common_name": target.common_name,
            "target_scientific_name": target.scientific_name,
            "taxon_id": taxon_id,
            "photo_id": photo_id,
            "curated_position": position,
            "source_page_url": _safe_source_page(photo_id),
            "source_image_original_url": original_url,
            "source_image_large_url": large_url,
            "creator": creator,
            "license_code": license_code,
            "license_url": license_url,
            "original_width": dimensions[0],
            "original_height": dimensions[1],
            "_loaded_at": loaded_at,
        },
        "eligible",
    )


def _fetch_snapshot(
    targets: tuple[MissingSpecies, ...],
    *,
    run_id: str,
    loaded_at: str,
    request_max_attempts: int,
) -> _Snapshot:
    started_at = pendulum.now("UTC").isoformat()
    species_results: list[dict[str, Any]] = []
    candidates: list[dict[str, Any]] = []
    request_count = 0
    exact_species_count = 0
    inspected_count = 0
    for target in targets:
        search, attempts = _request_json(
            INATURALIST_V2_TAXA_URL,
            {
                "q": target.scientific_name,
                "rank": "species",
                "fields": "id,name,rank,is_active",
                "per_page": INATURALIST_MAX_CURATED_PHOTOS,
            },
            max_attempts=request_max_attempts,
        )
        request_count += attempts
        taxon_id = _exact_taxon_id(search, target.scientific_name)
        photos: list[object] | None = None
        if taxon_id is not None:
            detail, attempts = _request_json(
                INATURALIST_V1_TAXON_URL.format(taxon_id=taxon_id),
                {},
                max_attempts=request_max_attempts,
            )
            request_count += attempts
            photos = _taxon_photos(
                detail, scientific_name=target.scientific_name, taxon_id=taxon_id
            )
        if taxon_id is None or photos is None:
            species_results.append(
                {
                    "run_id": run_id,
                    "species_code": target.species_code,
                    "target_common_name": target.common_name,
                    "target_scientific_name": target.scientific_name,
                    "taxon_id": taxon_id,
                    "identity_status": "unavailable",
                    "curated_photo_count": 0,
                    "curated_photos_inspected": 0,
                    "eligible_candidate_count": 0,
                    "rejection_counts_json": "{}",
                    "_loaded_at": loaded_at,
                }
            )
            continue
        exact_species_count += 1
        inspected = photos[:INATURALIST_MAX_CURATED_PHOTOS]
        inspected_count += len(inspected)
        target_candidates: list[dict[str, Any]] = []
        rejection_counts: dict[str, int] = {}
        seen_photo_ids: set[int] = set()
        for position, raw in enumerate(inspected, start=1):
            item, outcome = _candidate(
                raw,
                target=target,
                taxon_id=taxon_id,
                position=position,
                run_id=run_id,
                loaded_at=loaded_at,
            )
            if item is not None and item["photo_id"] not in seen_photo_ids:
                seen_photo_ids.add(item["photo_id"])
                target_candidates.append(item)
            elif item is not None:
                outcome = "duplicate"
            if outcome != "eligible":
                rejection_counts[outcome] = rejection_counts.get(outcome, 0) + 1
        candidates.extend(target_candidates)
        species_results.append(
            {
                "run_id": run_id,
                "species_code": target.species_code,
                "target_common_name": target.common_name,
                "target_scientific_name": target.scientific_name,
                "taxon_id": taxon_id,
                "identity_status": "exact_active_species",
                "curated_photo_count": len(photos),
                "curated_photos_inspected": len(inspected),
                "eligible_candidate_count": len(target_candidates),
                "rejection_counts_json": json.dumps(
                    rejection_counts, sort_keys=True, separators=(",", ":")
                ),
                "_loaded_at": loaded_at,
            }
        )
    run = {
        "run_id": run_id,
        "status": "complete",
        "target_species_count": len(targets),
        "exact_species_count": exact_species_count,
        "species_with_candidates": len({item["species_code"] for item in candidates}),
        "curated_photos_inspected": inspected_count,
        "eligible_candidate_count": len(candidates),
        "request_count": request_count,
        "max_curated_photos": INATURALIST_MAX_CURATED_PHOTOS,
        "request_max_attempts": request_max_attempts,
        "started_at": started_at,
        "completed_at": pendulum.now("UTC").isoformat(),
        "_loaded_at": loaded_at,
    }
    return _Snapshot(run, tuple(species_results), tuple(candidates))


@dlt.source
def inaturalist_public_photo_source(
    missing_species: Sequence[Mapping[str, str]] | None = None,
    request_max_attempts: int = INATURALIST_REQUEST_MAX_ATTEMPTS,
    run_id: str | None = None,
    loaded_at: str | None = None,
) -> Any:
    """Return an auditable candidate snapshot for caller-proven missing species."""
    targets = _normalize_targets(missing_species)
    if not 1 <= request_max_attempts <= INATURALIST_REQUEST_MAX_ATTEMPTS:
        raise ValueError(
            "iNaturalist request_max_attempts must be between 1 and "
            f"{INATURALIST_REQUEST_MAX_ATTEMPTS}"
        )
    effective_loaded_at = loaded_at or pendulum.now("UTC").isoformat()
    target_identity = [(target.species_code, target.scientific_name) for target in targets]
    effective_run_id = (
        run_id or hashlib.sha256(f"{effective_loaded_at}|{target_identity}".encode()).hexdigest()
    )
    cached: _Snapshot | None = None
    lock = threading.Lock()

    def snapshot() -> _Snapshot:
        nonlocal cached
        if not targets:
            raise ValueError("iNaturalist missing_species must be supplied by the caller")
        if cached is None:
            with lock:
                if cached is None:
                    cached = _fetch_snapshot(
                        targets,
                        run_id=effective_run_id,
                        loaded_at=effective_loaded_at,
                        request_max_attempts=request_max_attempts,
                    )
        return cached

    @dlt.resource(primary_key="run_id", write_disposition="merge", columns=_RUN_COLUMNS)
    def photo_discovery_runs() -> Iterator[dict[str, Any]]:
        yield snapshot().run

    @dlt.resource(
        primary_key=["run_id", "species_code"],
        write_disposition="merge",
        columns=_SPECIES_COLUMNS,
    )
    def photo_species_results() -> Iterator[dict[str, Any]]:
        yield from snapshot().species_results

    @dlt.resource(
        primary_key=["run_id", "species_code", "photo_id"],
        write_disposition="merge",
        columns=_PHOTO_COLUMNS,
    )
    def photo_candidates() -> Iterator[dict[str, Any]]:
        yield from snapshot().candidates

    return [photo_discovery_runs, photo_species_results, photo_candidates]
