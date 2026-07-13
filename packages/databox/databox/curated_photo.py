"""Bounded metadata-only selection of curated iNaturalist bird photos."""

from __future__ import annotations

import fcntl
import html
import json
import os
import re
import threading
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, Literal, cast
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

from databox.agent_tools.recommendation_media import (
    exact_media_scientific_name,
    parse_creative_commons_license,
)

INATURALIST_V2_TAXA = "https://api.inaturalist.org/v2/taxa"
INATURALIST_V1_TAXON = "https://api.inaturalist.org/v1/taxa/{taxon_id}"
MAX_INATURALIST_PHOTOS = 20
MAX_RESPONSE_BYTES = 1_048_576
HTTP_TIMEOUT_SECONDS = 10.0
MIN_LONG_EDGE = 1_000
MIN_SHORT_EDGE = 750
USER_AGENT = "Rufous/1.0 (local metadata-only representative-photo selector)"

JsonGetter = Callable[[str, Mapping[str, object]], dict[str, Any]]
BeforeRequest = Callable[[], None]
PhotoProvider = Literal["inaturalist", "curated_photo"]
PhotoStatus = Literal["available", "unavailable"]

_FILE_EXTENSIONS = frozenset({"jpg", "jpeg", "png", "webp"})
_INAT_PHOTO_PATH = re.compile(
    r"^/photos/([1-9][0-9]*)/(square|small|medium|large|original)\.([A-Za-z0-9]+)$"
)
_INAT_SOURCE_PATH = re.compile(r"^/photos/([1-9][0-9]*)/?$")


@dataclass(frozen=True)
class CuratedPhotoResult:
    status: PhotoStatus
    source: PhotoProvider
    source_record_id: str | None
    species_name: str | None
    display_url: str | None
    source_url: str | None
    creator: str | None
    license_code: str | None
    license_url: str | None
    original_width: int | None
    original_height: int | None
    selection_reason: str | None
    lookup_at: str
    identity: dict[str, str | int | None]
    caveats: tuple[str, ...] = ()
    attempted_sources: tuple[str, ...] = ()
    request_count: int = 0
    failure_class: str | None = None
    retryable: bool = False


class _NoRedirectHandler(HTTPRedirectHandler):
    def redirect_request(
        self,
        _request: Request,
        _fp: Any,
        _code: int,
        _message: str,
        _headers: Any,
        _new_url: str,
    ) -> None:
        return None


_NO_REDIRECT_OPENER = build_opener(_NoRedirectHandler())


class _PlainTextParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []

    def handle_data(self, data: str) -> None:
        self.parts.append(data)


class RetryablePhotoError(RuntimeError):
    """A provider/budget failure that an explicit operator rerun may retry."""

    def __init__(self, message: str, *, failure_class: str = "schema") -> None:
        super().__init__(message)
        self.failure_class = failure_class


class TerminalPhotoIdentityError(ValueError):
    """A valid provider response cannot establish one governed exact identity."""


class InaturalistRateLimiter:
    """Atomic local limiter shared by processes and preserved across restarts."""

    def __init__(
        self,
        *,
        state_path: str | Path | None = None,
        interval_seconds: float = 1.0,
        daily_limit: int = 9_999,
        now: Callable[[], float] = time.time,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        resolved_state_path: str | Path = (
            state_path
            if state_path is not None
            else os.environ.get(
                "DATABOX_INATURALIST_RATE_STATE",
                "data/.inaturalist-photo-rate.json",
            )
        )
        self.state_path = Path(resolved_state_path)
        self.interval_seconds = interval_seconds
        self.daily_limit = daily_limit
        self._now = now
        self._sleep = sleep
        self._thread_lock = threading.Lock()

    def wait(self) -> None:
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        lock_path = self.state_path.with_suffix(f"{self.state_path.suffix}.lock")
        with self._thread_lock, lock_path.open("a+b") as lock:
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
            state = self._load_state()
            current = self._now()
            day = datetime.fromtimestamp(current, UTC).date().isoformat()
            if state["day"] != day:
                state = {"day": day, "count": 0, "last_request": 0.0}
            delay = self.interval_seconds - (current - float(state["last_request"]))
            if delay > 0:
                self._sleep(delay)
                current = self._now()
            if int(state["count"]) >= self.daily_limit:
                raise RetryablePhotoError(
                    "iNaturalist daily metadata request budget is exhausted",
                    failure_class="budget",
                )
            state["count"] = int(state["count"]) + 1
            state["last_request"] = current
            self._store_state(state)

    def _load_state(self) -> dict[str, str | int | float]:
        if not self.state_path.exists():
            return {"day": "", "count": 0, "last_request": 0.0}
        try:
            value = json.loads(self.state_path.read_text())
            if (
                not isinstance(value, dict)
                or set(value) != {"day", "count", "last_request"}
                or not isinstance(value["day"], str)
                or isinstance(value["count"], bool)
                or not isinstance(value["count"], int)
                or value["count"] < 0
                or isinstance(value["last_request"], bool)
                or not isinstance(value["last_request"], int | float)
                or value["last_request"] < 0
            ):
                raise ValueError
            return cast(dict[str, str | int | float], value)
        except (OSError, UnicodeDecodeError, json.JSONDecodeError, ValueError):
            raise RetryablePhotoError(
                "iNaturalist request budget state is malformed", failure_class="budget"
            ) from None

    def _store_state(self, state: Mapping[str, object]) -> None:
        temporary = self.state_path.with_name(
            f".{self.state_path.name}.{os.getpid()}.{threading.get_ident()}.tmp"
        )
        encoded = json.dumps(state, sort_keys=True, separators=(",", ":"))
        try:
            temporary.write_text(encoded)
            os.replace(temporary, self.state_path)
        finally:
            temporary.unlink(missing_ok=True)


_INATURALIST_LIMITER = InaturalistRateLimiter()


def select_curated_photo(
    scientific_name: object,
    *,
    getter: JsonGetter | None = None,
    before_inaturalist_request: BeforeRequest | None = None,
    now: Callable[[], datetime] | None = None,
) -> CuratedPhotoResult:
    """Select the first eligible exact-species curated iNaturalist photo."""

    lookup_at = (now or (lambda: datetime.now(UTC)))().isoformat()
    species = exact_media_scientific_name(scientific_name)
    if species is None:
        return _unavailable(
            lookup_at,
            "An exact current binomial scientific name is required; fallback is prohibited",
            (),
            species=None,
        )
    return _lookup_inaturalist(
        species,
        getter or _get_json,
        before_inaturalist_request or _INATURALIST_LIMITER.wait,
        lookup_at=lookup_at,
    )


def curated_photo_result_is_safe(result: CuratedPhotoResult, scientific_name: object) -> bool:
    """Validate a complete persisted curated-photo result without network access."""

    species = exact_media_scientific_name(scientific_name)
    try:
        looked_up = datetime.fromisoformat(result.lookup_at)
    except ValueError:
        return False
    if (
        looked_up.tzinfo is None
        or len(result.caveats) > 10
        or any(not 0 < len(item) <= 500 for item in result.caveats)
        or isinstance(result.request_count, bool)
        or result.request_count not in {0, 1, 2}
        or (
            result.failure_class is not None
            and not re.fullmatch(r"[a-z_]{1,64}", result.failure_class)
        )
        or (result.retryable and result.status != "unavailable")
    ):
        return False
    if result.status == "unavailable":
        return bool(
            result.source == "curated_photo"
            and result.species_name == species
            and result.source_record_id is None
            and result.display_url is None
            and result.source_url is None
            and result.creator is None
            and result.license_code is None
            and result.license_url is None
            and result.original_width is None
            and result.original_height is None
            and result.selection_reason is None
            and result.identity == {}
            and result.attempted_sources in {(), ("inaturalist",)}
            and result.caveats
        )
    if (
        result.status != "available"
        or species is None
        or result.species_name != species
        or result.source != "inaturalist"
        or not result.source_record_id
        or not result.creator
        or _plain_text(result.creator, maximum=500) != result.creator
        or not _dimensions_eligible(result.original_width, result.original_height)
        or not result.selection_reason
        or _plain_text(result.selection_reason, maximum=500) != result.selection_reason
    ):
        return False
    license_info = parse_creative_commons_license(result.license_url, allow_audio_nd=False)
    if license_info is None or result.license_code != license_info[0]:
        return False
    photo_id = _positive_id(result.identity.get("photo_id"))
    taxon_id = _positive_id(result.identity.get("taxon_id"))
    position = _positive_id(result.identity.get("curated_position"))
    return bool(
        set(result.identity) == {"taxon_id", "photo_id", "curated_position"}
        and photo_id
        and taxon_id
        and position
        and position <= MAX_INATURALIST_PHOTOS
        and result.attempted_sources == ("inaturalist",)
        and result.source_record_id == str(photo_id)
        and safe_inaturalist_display_url(result.display_url, photo_id=photo_id)
        and safe_inaturalist_source_url(result.source_url, photo_id=photo_id)
    )


def curated_photo_result_is_retryable(result: CuratedPhotoResult) -> bool:
    """Return whether an unavailable persisted result needs operator retry."""

    return bool(
        result.status == "unavailable"
        and (
            result.retryable
            or result.failure_class in {"budget", "transport", "schema"}
            or (len(result.caveats) == 1 and result.caveats[0].startswith("Retryable iNaturalist "))
        )
    )


def curated_photo_outcome_keys(result: CuratedPhotoResult) -> tuple[str, ...]:
    """Return bounded run-counter keys without provider payloads or URLs."""

    if not result.attempted_sources:
        return ("identity.unavailable",)
    if result.source == "inaturalist" and result.status == "available":
        return ("inaturalist.available",)
    if curated_photo_result_is_retryable(result):
        return (f"inaturalist.failed.{result.failure_class or 'metadata'}",)
    if result.failure_class == "identity":
        return ("identity.unavailable",)
    return ("inaturalist.no_eligible",)


def safe_inaturalist_display_url(value: object, *, photo_id: int) -> str | None:
    raw = _bounded_text(value, maximum=2_000)
    parsed = _strict_https(raw, {"inaturalist-open-data.s3.amazonaws.com"})
    if parsed is None:
        return None
    match = _INAT_PHOTO_PATH.fullmatch(parsed.path)
    if match is None:
        return None
    path_id, variant, extension = match.groups()
    if int(path_id) != photo_id or variant != "large" or extension.lower() not in _FILE_EXTENSIONS:
        return None
    return raw


def safe_inaturalist_source_url(value: object, *, photo_id: int) -> str | None:
    raw = _bounded_text(value, maximum=2_000)
    parsed = _strict_https(raw, {"www.inaturalist.org"})
    if parsed is None:
        return None
    match = _INAT_SOURCE_PATH.fullmatch(parsed.path)
    return raw if match is not None and int(match.group(1)) == photo_id else None


def _lookup_inaturalist(
    species: str,
    getter: JsonGetter,
    before_request: BeforeRequest,
    *,
    lookup_at: str,
) -> CuratedPhotoResult:
    attempted = ("inaturalist",)
    request_count = 0
    try:
        before_request()
        request_count += 1
        v2 = getter(
            INATURALIST_V2_TAXA,
            {
                "q": species,
                "rank": "species",
                "fields": "id,name,rank,is_active",
                "per_page": MAX_INATURALIST_PHOTOS,
            },
        )
        taxon_id = _v2_exact_taxon(v2, species)
        before_request()
        request_count += 1
        v1 = getter(INATURALIST_V1_TAXON.format(taxon_id=taxon_id), {})
        photos = _v1_taxon_photos(v1, species=species, taxon_id=taxon_id)
    except TerminalPhotoIdentityError:
        return _unavailable(
            lookup_at,
            "Exact active iNaturalist species identity was unavailable or ambiguous",
            attempted,
            species=species,
            request_count=request_count,
            failure_class="identity",
        )
    except RetryablePhotoError as exc:
        failure_class = exc.failure_class
        return _unavailable(
            lookup_at,
            f"Retryable iNaturalist {failure_class} failure",
            attempted,
            species=species,
            request_count=request_count,
            failure_class=failure_class,
            retryable=True,
        )
    except Exception:  # noqa: BLE001 - transport failures persist safe retryable evidence.
        return _unavailable(
            lookup_at,
            "Retryable iNaturalist transport failure",
            attempted,
            species=species,
            request_count=request_count,
            failure_class="transport",
            retryable=True,
        )
    for position, row in enumerate(photos[:MAX_INATURALIST_PHOTOS], start=1):
        candidate = _inaturalist_candidate(
            row,
            species=species,
            taxon_id=taxon_id,
            position=position,
            lookup_at=lookup_at,
            request_count=request_count,
        )
        if candidate is not None:
            return candidate
    return _unavailable(
        lookup_at,
        "No eligible exact-species curated iNaturalist taxon photo was found",
        attempted,
        species=species,
        request_count=request_count,
        failure_class="no_eligible",
    )


def _v2_exact_taxon(payload: Mapping[str, Any], species: str) -> int:
    rows = payload.get("results")
    if not isinstance(rows, list) or len(rows) > MAX_INATURALIST_PHOTOS:
        raise RetryablePhotoError("iNaturalist v2 taxa schema is malformed")
    exact: list[int] = []
    for row in rows:
        if not isinstance(row, dict):
            raise RetryablePhotoError("iNaturalist v2 taxon schema is malformed")
        taxon_id = _positive_id(row.get("id"))
        if (
            row.get("name") == species
            and row.get("rank") == "species"
            and row.get("is_active") is True
            and taxon_id is not None
        ):
            exact.append(taxon_id)
    if len(exact) != 1:
        raise TerminalPhotoIdentityError("iNaturalist v2 exact taxon is missing or ambiguous")
    return exact[0]


def _v1_taxon_photos(
    payload: Mapping[str, Any], *, species: str, taxon_id: int
) -> list[Mapping[str, Any]]:
    rows = payload.get("results")
    if not isinstance(rows, list) or len(rows) != 1 or not isinstance(rows[0], dict):
        raise RetryablePhotoError("iNaturalist v1 taxon schema is malformed")
    row = rows[0]
    if (
        _positive_id(row.get("id")) != taxon_id
        or row.get("name") != species
        or row.get("rank") != "species"
        or row.get("is_active") is not True
    ):
        raise TerminalPhotoIdentityError("iNaturalist v1/v2 taxon identity mismatch")
    taxon_photos = row.get("taxon_photos")
    if not isinstance(taxon_photos, list) or len(taxon_photos) > MAX_INATURALIST_PHOTOS:
        raise RetryablePhotoError("iNaturalist curated shortlist schema is malformed")
    output: list[Mapping[str, Any]] = []
    for item in taxon_photos:
        if not isinstance(item, dict) or not isinstance(item.get("photo"), dict):
            raise RetryablePhotoError("iNaturalist curated photo row schema is malformed")
        output.append(cast(Mapping[str, Any], item["photo"]))
    return output


def _inaturalist_candidate(
    photo: Mapping[str, Any],
    *,
    species: str,
    taxon_id: int,
    position: int,
    lookup_at: str,
    request_count: int,
) -> CuratedPhotoResult | None:
    photo_id = _positive_id(photo.get("id"))
    dimensions = photo.get("original_dimensions")
    width = _positive_id(dimensions.get("width")) if isinstance(dimensions, dict) else None
    height = _positive_id(dimensions.get("height")) if isinstance(dimensions, dict) else None
    creator = _plain_text(photo.get("attribution"), maximum=500)
    license_info = _inaturalist_license(photo.get("license_code"))
    if (
        photo_id is None
        or width is None
        or height is None
        or not _dimensions_eligible(width, height)
        or creator is None
        or license_info is None
    ):
        return None
    display_url = _inaturalist_large_url(photo.get("url"), photo_id=photo_id)
    source_url = f"https://www.inaturalist.org/photos/{photo_id}"
    if (
        safe_inaturalist_display_url(display_url, photo_id=photo_id) is None
        or safe_inaturalist_source_url(source_url, photo_id=photo_id) is None
    ):
        return None
    license_code, license_url = license_info
    result = CuratedPhotoResult(
        status="available",
        source="inaturalist",
        source_record_id=str(photo_id),
        species_name=species,
        display_url=display_url,
        source_url=source_url,
        creator=creator,
        license_code=license_code,
        license_url=license_url,
        original_width=width,
        original_height=height,
        selection_reason=(
            f"First eligible photo in curated iNaturalist shortlist position {position}"
        ),
        lookup_at=lookup_at,
        identity={"taxon_id": taxon_id, "photo_id": photo_id, "curated_position": position},
        caveats=(),
        attempted_sources=("inaturalist",),
        request_count=request_count,
    )
    return result if curated_photo_result_is_safe(result, species) else None


def _inaturalist_large_url(value: object, *, photo_id: int) -> str | None:
    raw = _bounded_text(value, maximum=2_000)
    parsed = _strict_https(raw, {"inaturalist-open-data.s3.amazonaws.com"})
    if parsed is None:
        return None
    match = _INAT_PHOTO_PATH.fullmatch(parsed.path)
    if match is None or int(match.group(1)) != photo_id:
        return None
    _, _, extension = match.groups()
    if extension.lower() not in _FILE_EXTENSIONS:
        return None
    return f"https://inaturalist-open-data.s3.amazonaws.com/photos/{photo_id}/large.{extension}"


def _inaturalist_license(value: object) -> tuple[str, str] | None:
    raw = _bounded_text(value, maximum=40)
    if raw is None:
        return None
    slug = raw.casefold().removeprefix("cc-")
    if slug == "cc0" or raw.casefold() == "cc0":
        return "CC0 1.0", "https://creativecommons.org/publicdomain/zero/1.0/"
    if slug not in {"by", "by-sa", "by-nc", "by-nc-sa"}:
        return None
    return f"CC {slug.upper()} 4.0", f"https://creativecommons.org/licenses/{slug}/4.0/"


def _unavailable(
    lookup_at: str,
    caveat: str,
    attempted: tuple[str, ...],
    *,
    species: str | None,
    request_count: int = 0,
    failure_class: str | None = None,
    retryable: bool = False,
) -> CuratedPhotoResult:
    return CuratedPhotoResult(
        status="unavailable",
        source="curated_photo",
        source_record_id=None,
        species_name=species,
        display_url=None,
        source_url=None,
        creator=None,
        license_code=None,
        license_url=None,
        original_width=None,
        original_height=None,
        selection_reason=None,
        lookup_at=lookup_at,
        identity={},
        caveats=(caveat,),
        attempted_sources=attempted,
        request_count=request_count,
        failure_class=failure_class,
        retryable=retryable,
    )


def _get_json(endpoint: str, params: Mapping[str, object]) -> dict[str, Any]:
    if endpoint != INATURALIST_V2_TAXA and not re.fullmatch(
        r"https://api\.inaturalist\.org/v1/taxa/[1-9][0-9]*", endpoint
    ):
        raise ValueError("unsupported curated-photo endpoint")
    return _request_json(endpoint, params)


def _open_metadata_request(request: Request) -> Any:
    return _NO_REDIRECT_OPENER.open(request, timeout=HTTP_TIMEOUT_SECONDS)


def _response_matches_endpoint(value: object, endpoint: str) -> bool:
    raw = _bounded_text(value, maximum=4_000)
    if raw is None:
        return False
    try:
        actual = urlsplit(raw)
        expected = urlsplit(endpoint)
        if actual.port is not None:
            return False
    except ValueError:
        return False
    return bool(
        actual.scheme == expected.scheme == "https"
        and actual.hostname == expected.hostname
        and actual.path == expected.path
        and actual.username is None
        and actual.password is None
        and not actual.fragment
    )


def _request_json(endpoint: str, params: Mapping[str, object]) -> dict[str, Any]:
    url = f"{endpoint}?{urlencode(params)}" if params else endpoint
    request = Request(url, headers={"Accept": "application/json", "User-Agent": USER_AGENT})
    try:
        with _open_metadata_request(request) as response:
            if not _response_matches_endpoint(response.geturl(), endpoint):
                raise ValueError("curated-photo response origin changed")
            declared = response.headers.get("Content-Length")
            if declared is not None and int(declared) > MAX_RESPONSE_BYTES:
                raise ValueError("curated-photo response is too large")
            body = response.read(MAX_RESPONSE_BYTES + 1)
    except (HTTPError, TimeoutError, URLError, OSError, ValueError):
        raise RetryablePhotoError(
            "curated-photo metadata discovery failed", failure_class="transport"
        ) from None
    if len(body) > MAX_RESPONSE_BYTES:
        raise RetryablePhotoError(
            "curated-photo metadata response is oversized", failure_class="schema"
        )
    try:
        payload = json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise RetryablePhotoError(
            "curated-photo metadata response is malformed", failure_class="schema"
        ) from None
    if not isinstance(payload, dict):
        raise RetryablePhotoError(
            "curated-photo metadata response is malformed", failure_class="schema"
        )
    return cast(dict[str, Any], payload)


def _strict_https(raw: str | None, hosts: set[str]) -> Any | None:
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
        or parsed.hostname not in hosts
        or parsed.username is not None
        or parsed.password is not None
        or parsed.query
        or parsed.fragment
    ):
        return None
    return parsed


def _plain_text(value: object, *, maximum: int) -> str | None:
    raw = value.strip() if isinstance(value, str) and value.strip() else None
    if raw is None or len(raw) > maximum * 4:
        return None
    parser = _PlainTextParser()
    try:
        parser.feed(raw)
        parser.close()
    except ValueError:
        return None
    text = " ".join(html.unescape(" ".join(parser.parts)).split())
    return text if 0 < len(text) <= maximum and "<" not in text and ">" not in text else None


def _dimensions_eligible(width: object, height: object) -> bool:
    if (
        isinstance(width, bool)
        or isinstance(height, bool)
        or not isinstance(width, int)
        or not isinstance(height, int)
    ):
        return False
    return (
        width > 0
        and height > 0
        and max(width, height) >= MIN_LONG_EDGE
        and min(width, height) >= MIN_SHORT_EDGE
    )


def _positive_id(value: object) -> int | None:
    return value if isinstance(value, int) and not isinstance(value, bool) and value > 0 else None


def _bounded_text(value: object, *, maximum: int = 500) -> str | None:
    return value.strip() if isinstance(value, str) and 0 < len(value.strip()) <= maximum else None
