"""Prepare licensed bird images for Rufous's immutable public-media release.

The database model is the licensing and identity gate.  This module reads that
model without modifying it, independently revalidates every row, downloads and
decodes every eligible image with strict limits, and only then replaces the
prepared output tree.  A failed image therefore cannot advance or damage the
last successful preparation.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
import shutil
import stat
import tempfile
import time
import uuid
import warnings
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime
from io import BytesIO
from pathlib import Path
from urllib.parse import SplitResult, unquote, urljoin, urlsplit

import duckdb
import httpx
import PIL
from PIL import Image, ImageOps, UnidentifiedImageError

import databox.public_restricted_marks as restricted_marks
from databox.public_media_approval import (
    MediaApprovalError,
    load_visual_approvals,
    require_visual_approvals,
)

SCHEMA_VERSION = 1
MODE = "rufous-media-preparation"
SOURCE_TABLES = (
    ("usfws", "rufous_public", "usfws_commercial_image", True),
    ("inaturalist", "rufous_public", "inaturalist_commercial_image", False),
    ("wikimedia", "rufous_public", "wikimedia_commercial_image", False),
)
PUBLIC_BASE_URL = "https://rufous-data.loughondata.com/rufous-media/v1"
USER_AGENT = (
    "RufousMediaBuilder/1.0 "
    "(+https://loughondata.com/projects/rufous/; mailto:connor@loughondata.com)"
)

MAX_REDIRECTS = 3
MAX_ATTEMPTS = 6
MAX_DOWNLOAD_BYTES = 8 * 1024 * 1024
MAX_OUTPUT_BYTES = 1 * 1024 * 1024
MAX_MANIFEST_BYTES = 16 * 1024 * 1024
MAX_SOURCE_PIXELS = 50_000_000
MAX_OUTPUT_DIMENSION = 650
MAX_ELIGIBLE_ROWS = 10_000
MAX_PREPARED_OBJECTS = 10_000
MAX_UNAVAILABLE_SOURCE_OBJECTS = 10
MAX_TOTAL_PREPARED_BYTES = 1 * 1024 * 1024 * 1024
DOWNLOAD_TIMEOUT = httpx.Timeout(connect=5.0, read=30.0, write=5.0, pool=5.0)

SOURCE_COLUMNS = (
    "species_code",
    "common_name",
    "scientific_name",
    "source_page_url",
    "source_image_url",
    "creator",
    "license",
    "title",
    "caption",
    "alt_text",
    "source_published_at",
    "source_width",
    "source_height",
    "mime_type",
    "discovery_method",
    "loaded_at",
)

_SAFE_SPECIES_CODE = re.compile(r"^[a-z0-9][a-z0-9._-]{0,63}$")
_SAFE_MEDIA_SLUG = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,238}[a-z0-9])?$")
_SCIENTIFIC_BINOMIAL = re.compile(r"^[A-Z][A-Za-z-]{1,79} [a-z][A-Za-z-]{1,79}$")
_SHA256 = re.compile(r"^[a-f0-9]{64}$")
_FWS_HOSTS = frozenset({"fws.gov", "www.fws.gov"})
_INATURALIST_PHOTO_PAGE = re.compile(r"^/photos/(?P<photo_id>[1-9][0-9]*)$")
_INATURALIST_IMAGE_PATH = re.compile(
    r"^/photos/(?P<photo_id>[1-9][0-9]*)/original\.(?:jpg|jpeg|png|webp)$",
    re.IGNORECASE,
)
_WIKIMEDIA_FILE_PATH = re.compile(r"^/wiki/File:(?P<filename>[^/]+)$")
_WIKIMEDIA_ORIGINAL_IMAGE_PATH = re.compile(
    r"^/wikipedia/commons/[a-f0-9]/[a-f0-9]{2}/(?P<filename>[^/]+)$",
    re.IGNORECASE,
)
_WIKIMEDIA_THUMB_IMAGE_PATH = re.compile(
    r"^/wikipedia/commons/thumb/[a-f0-9]/[a-f0-9]{2}/(?P<filename>[^/]+)/"
    r"[1-9][0-9]{1,4}px-(?P<thumbnail>[^/]+)$",
    re.IGNORECASE,
)
_MALFORMED_PERCENT_ESCAPE = re.compile(r"%(?![0-9A-Fa-f]{2})")
_MEDIA_PROVIDERS = frozenset({"usfws", "inaturalist", "wikimedia"})
_REDIRECT_STATUSES = frozenset({301, 302, 303, 307, 308})
_RETRY_STATUSES = frozenset({408, 425, 429, 500, 502, 503, 504})
_UNAVAILABLE_REASONS = frozenset(
    {
        "timeout",
        "transport_error",
        "missing_http_content_type",
        "unsupported_http_content_type",
        "truncated_response_body",
        *(f"retryable_http_{status}" for status in _RETRY_STATUSES),
    }
)
_SOURCE_MIME_TYPES = {
    "image/jpeg": ("image/jpeg", "JPEG"),
    "image/jpg": ("image/jpeg", "JPEG"),
    "image/png": ("image/png", "PNG"),
    "image/webp": ("image/webp", "WEBP"),
}
_DECODED_SOURCE_MIME_TYPES = {
    "JPEG": "image/jpeg",
    "PNG": "image/png",
    "WEBP": "image/webp",
}
_CC_VERSIONS = frozenset({"1.0", "2.0", "2.5", "3.0", "4.0"})
_CC_HOSTS = frozenset({"creativecommons.org", "www.creativecommons.org"})
_DRUPAL_IMAGE_QUERY = re.compile(r"^itok=[A-Za-z0-9_-]{1,128}$")


class PublicMediaError(RuntimeError):
    """The public-media preparation failed without replacing the last output."""


class UnavailableSourceError(PublicMediaError):
    """A source stayed unavailable through every bounded retry."""

    def __init__(self, reason: str) -> None:
        self.reason = _validate_unavailable_reason(reason)
        super().__init__(f"source image failed after bounded retries: {self.reason}")


@dataclass(frozen=True)
class SourceImageRow:
    provider: str
    species_code: str
    common_name: str
    scientific_name: str
    source_page_url: str
    source_image_url: str
    creator: str
    license: str
    license_url: str
    title: str
    caption: str | None
    alt_text: str
    source_published_at: str | None
    source_width: int
    source_height: int
    source_mime_type: str
    discovery_method: str
    loaded_at: str

    @classmethod
    def from_values(cls, values: Mapping[str, object]) -> SourceImageRow:
        provider = _required_text(values.get("provider", "usfws"), "provider", 32)
        if provider not in _MEDIA_PROVIDERS:
            raise PublicMediaError("media provider is not reviewed")
        license_name, license_url = normalize_license(values.get("license"), provider=provider)
        width = _positive_int(values.get("source_width"), "source_width")
        height = _positive_int(values.get("source_height"), "source_height")
        if width * height > MAX_SOURCE_PIXELS:
            raise PublicMediaError("declared source dimensions exceed the safe pixel limit")

        source_mime_type, _ = _normalize_source_mime(values.get("mime_type"))
        row = cls(
            provider=provider,
            species_code=_required_text(values.get("species_code"), "species_code", 64),
            common_name=_required_text(values.get("common_name"), "common_name", 200),
            scientific_name=_required_text(values.get("scientific_name"), "scientific_name", 200),
            source_page_url=validate_source_page_url(
                values.get("source_page_url"), provider=provider
            ),
            source_image_url=validate_source_image_url(
                values.get("source_image_url"), provider=provider
            ),
            creator=_required_text(values.get("creator"), "creator", 300),
            license=license_name,
            license_url=license_url,
            title=_required_text(values.get("title"), "title", 500),
            caption=_optional_text(values.get("caption"), "caption", 2_000),
            alt_text=_required_text(values.get("alt_text"), "alt_text", 1_000),
            source_published_at=_optional_timestamp(
                values.get("source_published_at"), "source_published_at"
            ),
            source_width=width,
            source_height=height,
            source_mime_type=source_mime_type,
            discovery_method=_required_text(
                values.get("discovery_method"), "discovery_method", 200
            ),
            loaded_at=_required_timestamp(values.get("loaded_at"), "loaded_at"),
        )
        if not _SAFE_SPECIES_CODE.fullmatch(row.species_code):
            raise PublicMediaError("species_code is not a safe public identifier")
        if not _SCIENTIFIC_BINOMIAL.fullmatch(row.scientific_name):
            raise PublicMediaError("scientific_name must be an exact binomial")
        for field_name, field_value in (
            ("creator", row.creator),
            ("title", row.title),
            ("caption", row.caption),
            ("alt_text", row.alt_text),
        ):
            if field_value is not None and any(
                ord(character) < 32 or ord(character) == 127 for character in field_value
            ):
                raise PublicMediaError(f"{field_name} contains control characters")
        weak_creator_values = {
            "unknown",
            "n/a",
            "na",
            "none",
            "null",
            "anonymous",
            "public domain",
            "copyrighted",
            row.common_name.casefold(),
            row.scientific_name.casefold(),
            row.title.casefold(),
        }
        if row.caption is not None:
            weak_creator_values.add(row.caption.casefold())
        if (
            len(row.creator) > 200
            or not any(character.isalpha() for character in row.creator)
            or any(character in "<>" for character in row.creator)
            or row.creator.casefold() in weak_creator_values
        ):
            raise PublicMediaError("creator is not a credible attribution")
        if row.provider == "inaturalist":
            page_match = _INATURALIST_PHOTO_PAGE.fullmatch(urlsplit(row.source_page_url).path)
            image_match = _INATURALIST_IMAGE_PATH.fullmatch(urlsplit(row.source_image_url).path)
            if (
                page_match is None
                or image_match is None
                or page_match.group("photo_id") != image_match.group("photo_id")
            ):
                raise PublicMediaError("iNaturalist source URLs identify different photos")
        if row.provider == "wikimedia":
            page_name = _wikimedia_page_filename(row.source_page_url)
            image_name = _wikimedia_image_filename(row.source_image_url)
            if page_name != image_name:
                raise PublicMediaError("Wikimedia source URLs identify different files")
        if row.provider == "usfws":
            restricted_mark = restricted_marks.restricted_usfws_mark_reason(
                (
                    row.title,
                    row.caption,
                    row.alt_text,
                    row.source_page_url,
                    row.source_image_url,
                )
            )
            if restricted_mark is not None:
                raise PublicMediaError(
                    f"USFWS media metadata identifies restricted mark: {restricted_mark}"
                )
        return row

    def semantic_key(self) -> tuple[object, ...]:
        """Identity of a distinct metadata row, excluding the refresh timestamp."""
        return (
            self.species_code,
            self.common_name,
            self.scientific_name,
            self.source_page_url,
            self.source_image_url,
            self.creator,
            self.license,
            self.license_url,
            self.title,
            self.caption,
            self.alt_text,
            self.source_published_at,
            self.source_width,
            self.source_height,
            self.source_mime_type,
            self.discovery_method,
        )

    def source_object_key(self) -> tuple[object, ...]:
        return (
            self.source_image_url,
            self.source_published_at,
            self.source_width,
            self.source_height,
            self.source_mime_type,
        )

    def cache_key(self, preparer_fingerprint: str) -> str:
        payload = _canonical_json_bytes(
            {
                "preparer_fingerprint": preparer_fingerprint,
                "semantic_row": self.semantic_key(),
            }
        )
        return hashlib.sha256(payload).hexdigest()


@dataclass(frozen=True)
class PreparedObject:
    sha256: str
    width: int
    height: int
    byte_size: int

    @property
    def relative_path(self) -> str:
        return f"objects/{self.sha256[:2]}/{self.sha256}.webp"

    @property
    def public_url(self) -> str:
        return f"{PUBLIC_BASE_URL}/{self.relative_path}"


@dataclass(frozen=True)
class CacheEntry:
    cache_key: str
    sha256: str
    width: int
    height: int
    byte_size: int
    decoded_source_mime_type: str
    path: Path


@dataclass(frozen=True)
class PreparationResult:
    output_dir: Path
    manifest_path: Path
    items: int
    objects: int
    species: int


@dataclass(frozen=True)
class _ValidatedOutput:
    kind: str
    preparer_fingerprint: str | None = None
    cache_identity: str | None = None
    cache: Mapping[str, CacheEntry] | None = None

    @property
    def state(self) -> tuple[str, str | None, str | None]:
        return self.kind, self.preparer_fingerprint, self.cache_identity


def normalize_license(value: object, *, provider: str = "usfws") -> tuple[str, str]:
    """Normalize the deliberately narrow commercial-reuse license allowlist."""
    if provider not in _MEDIA_PROVIDERS:
        raise PublicMediaError("media provider is not reviewed")
    raw = _required_text(value, "license", 100)
    if any(ord(character) < 32 or ord(character) == 127 for character in raw):
        raise PublicMediaError("media license contains control characters")
    if raw.casefold() == "public domain":
        if provider == "usfws":
            return "Public Domain", "https://www.fws.gov/notices"
        if provider == "wikimedia":
            return (
                "Public Domain",
                "https://commons.wikimedia.org/wiki/Commons:Copyright_tags/General_public_domain",
            )

    family: str
    version: str
    if "://" in raw:
        try:
            parsed = urlsplit(raw)
            port = parsed.port
        except ValueError as exc:
            raise PublicMediaError("media license URL is malformed") from exc
        if (
            parsed.scheme.casefold() not in {"http", "https"}
            or parsed.hostname not in _CC_HOSTS
            or parsed.username is not None
            or parsed.password is not None
            or port is not None
            or parsed.query
            or parsed.fragment
        ):
            raise PublicMediaError("media license URL is not an allowed Creative Commons URL")
        match = re.fullmatch(
            r"/(?:licenses/(?P<family>by|by-sa)|publicdomain/(?P<zero>zero))/"
            r"(?P<version>[0-9]+(?:\.[0-9]+)?)(?:/legalcode)?/?",
            parsed.path.casefold(),
        )
        if match is None:
            raise PublicMediaError("media license URL is not commercially reusable")
        family = "cc0" if match.group("zero") else match.group("family")
        version = match.group("version")
    else:
        normalized = re.sub(r"[^a-z0-9]+", " ", raw.casefold()).strip()
        if normalized == "cc0":
            family, version = "cc0", "1.0"
        else:
            text_match = re.fullmatch(
                r"(?P<family>cc0|cc by|cc by sa|creative commons zero|"
                r"creative commons cc0|creative commons attribution|"
                r"creative commons attribution sharealike) "
                r"(?P<major>[0-9]+) (?P<minor>[0-9]+)(?: universal)?",
                normalized,
            )
            if text_match is None:
                raise PublicMediaError(
                    "media license is absent, malformed, or not commercially reusable"
                )
            raw_family = text_match.group("family")
            if raw_family in {"cc0", "creative commons zero", "creative commons cc0"}:
                family = "cc0"
            elif raw_family in {"cc by sa", "creative commons attribution sharealike"}:
                family = "by-sa"
            else:
                family = "by"
            version = f"{text_match.group('major')}.{text_match.group('minor')}"

    if family == "cc0":
        if version != "1.0":
            raise PublicMediaError("only the defined CC0 1.0 license is eligible")
        return "CC0 1.0", "https://creativecommons.org/publicdomain/zero/1.0/"
    if provider == "inaturalist" and version != "4.0":
        raise PublicMediaError("iNaturalist media must use the reviewed 4.0 license family")
    if version not in _CC_VERSIONS:
        raise PublicMediaError("Creative Commons license version is not allowed")
    code = "CC BY-SA" if family == "by-sa" else "CC BY"
    return f"{code} {version}", f"https://creativecommons.org/licenses/{family}/{version}/"


def validate_source_page_url(value: object, *, provider: str = "usfws") -> str:
    if provider == "inaturalist":
        raw, parsed = _validated_https_url(
            value,
            "source_page_url",
            hosts=frozenset({"www.inaturalist.org"}),
        )
        if (
            parsed.query
            or parsed.fragment
            or _INATURALIST_PHOTO_PAGE.fullmatch(parsed.path) is None
        ):
            raise PublicMediaError("iNaturalist source_page_url must identify one exact photo")
        return raw
    if provider == "wikimedia":
        raw, parsed = _validated_https_url(
            value,
            "source_page_url",
            hosts=frozenset({"commons.wikimedia.org"}),
        )
        if parsed.query or parsed.fragment or _WIKIMEDIA_FILE_PATH.fullmatch(parsed.path) is None:
            raise PublicMediaError(
                "Wikimedia source_page_url must identify one exact Commons File page"
            )
        _wikimedia_page_filename(raw)
        return raw
    if provider != "usfws":
        raise PublicMediaError("media provider is not reviewed")
    raw, parsed = _validated_fws_url(value, "source_page_url")
    if parsed.query or parsed.fragment:
        raise PublicMediaError("source_page_url must not contain a query or fragment")
    match = re.fullmatch(r"/media/(?P<slug>[^/]+)", parsed.path)
    if match is None or _SAFE_MEDIA_SLUG.fullmatch(match.group("slug")) is None:
        raise PublicMediaError("source_page_url must be an exact safe /media/<slug> URL")
    return raw


def validate_source_image_url(value: object, *, provider: str = "usfws") -> str:
    if provider == "inaturalist":
        raw, parsed = _validated_https_url(
            value,
            "source_image_url",
            hosts=frozenset({"inaturalist-open-data.s3.amazonaws.com"}),
        )
        if (
            parsed.query
            or parsed.fragment
            or _INATURALIST_IMAGE_PATH.fullmatch(parsed.path) is None
        ):
            raise PublicMediaError(
                "iNaturalist source_image_url must be one exact original photo object"
            )
        return raw
    if provider == "wikimedia":
        raw, parsed = _validated_https_url(
            value,
            "source_image_url",
            hosts=frozenset({"upload.wikimedia.org"}),
        )
        if (
            parsed.query
            or parsed.fragment
            or (
                _WIKIMEDIA_ORIGINAL_IMAGE_PATH.fullmatch(parsed.path) is None
                and _WIKIMEDIA_THUMB_IMAGE_PATH.fullmatch(parsed.path) is None
            )
        ):
            raise PublicMediaError(
                "Wikimedia source_image_url must be one exact Commons image object"
            )
        filename = _wikimedia_image_filename(raw)
        if Path(filename).suffix.casefold() not in {".jpg", ".jpeg", ".png", ".webp"}:
            raise PublicMediaError("Wikimedia source_image_url has an unsupported image suffix")
        return raw
    if provider != "usfws":
        raise PublicMediaError("media provider is not reviewed")
    raw, parsed = _validated_fws_url(value, "source_image_url")
    if parsed.fragment or (parsed.query and _DRUPAL_IMAGE_QUERY.fullmatch(parsed.query) is None):
        raise PublicMediaError("source_image_url has an unsafe query or fragment")
    try:
        decoded_path = unquote(parsed.path, errors="strict")
    except UnicodeError as exc:
        raise PublicMediaError("source_image_url contains malformed escaping") from exc
    if (
        not decoded_path.startswith("/sites/default/files/")
        or "\\" in decoded_path
        or "//" in decoded_path
        or any(part in {"", ".", ".."} for part in decoded_path.split("/")[4:])
        or any(ord(character) < 32 for character in decoded_path)
    ):
        raise PublicMediaError("source_image_url is not a safe USFWS public-file path")
    suffix = Path(decoded_path).suffix.casefold()
    if suffix not in {".jpg", ".jpeg", ".png", ".webp"}:
        raise PublicMediaError("source_image_url has an unsupported image suffix")
    return raw


def _wikimedia_page_filename(source_url: str) -> str:
    match = _WIKIMEDIA_FILE_PATH.fullmatch(urlsplit(source_url).path)
    if match is None:  # pragma: no cover - validated by the public entry point.
        raise PublicMediaError("Wikimedia source page lost its exact file identity")
    return _safe_wikimedia_filename(match.group("filename"))


def _wikimedia_image_filename(source_url: str) -> str:
    path = urlsplit(source_url).path
    original_match = _WIKIMEDIA_ORIGINAL_IMAGE_PATH.fullmatch(path)
    if original_match is not None:
        return _safe_wikimedia_filename(original_match.group("filename"))
    thumb_match = _WIKIMEDIA_THUMB_IMAGE_PATH.fullmatch(path)
    if thumb_match is None:  # pragma: no cover - validated by the public entry point.
        raise PublicMediaError("Wikimedia source image lost its exact file identity")
    filename = _safe_wikimedia_filename(thumb_match.group("filename"))
    thumbnail = _safe_wikimedia_filename(thumb_match.group("thumbnail"))
    if thumbnail != filename:
        raise PublicMediaError("Wikimedia thumbnail URL identifies a different file")
    return filename


def _safe_wikimedia_filename(value: str) -> str:
    if _MALFORMED_PERCENT_ESCAPE.search(value) is not None:
        raise PublicMediaError("Wikimedia file URL contains malformed escaping")
    try:
        decoded = unquote(value, errors="strict")
    except UnicodeError as exc:
        raise PublicMediaError("Wikimedia file URL contains malformed escaping") from exc
    if (
        not decoded
        or len(decoded) > 500
        or decoded.strip() != decoded
        or "/" in decoded
        or "\\" in decoded
        or decoded in {".", ".."}
        or any(ord(character) < 32 or ord(character) == 127 for character in decoded)
    ):
        raise PublicMediaError("Wikimedia file URL contains an unsafe file name")
    return decoded.replace(" ", "_")


def prepare_public_media(
    database_path: str | Path,
    output_dir: str | Path,
    *,
    client: httpx.Client | None = None,
    reuse_cache: bool = True,
    sleeper: Callable[[float], None] = time.sleep,
    provider: str | None = None,
    approval_path: str | Path | None = None,
) -> PreparationResult:
    """Prepare eligible rows and atomically replace ``output_dir`` on success.

    ``provider=None`` retains the complete release behavior.  An explicit
    provider reads only that reviewed model, which supports small immutable
    provider-delta releases without touching another provider's source table.
    """
    database = Path(database_path).expanduser().resolve()
    requested_output = Path(output_dir).expanduser()
    if requested_output.is_symlink():
        raise PublicMediaError("media output must not be a symbolic link")
    output = requested_output.resolve()
    if not database.is_file():
        raise PublicMediaError("media preparation database does not exist")
    existing_output = _validate_output_target(output)
    if output == database or output in database.parents:
        raise PublicMediaError("media output must not contain its source database")
    if approval_path is not None and provider is None:
        raise PublicMediaError("media approval filtering requires an explicit provider scope")

    rows = _read_source_rows(database, provider=provider)
    approvals: Path | None = None
    if approval_path is not None:
        assert provider is not None  # guarded above
        approvals = Path(approval_path).expanduser().resolve()
        selected_pages = _selected_source_pages(approvals, provider=provider)
        rows = [row for row in rows if row.source_page_url in selected_pages]
        if not rows:
            raise PublicMediaError(
                f"the reviewed {provider} model contains none of the selected source pages"
            )
    source_object_count = len({row.source_object_key() for row in rows})
    if source_object_count > MAX_PREPARED_OBJECTS:
        raise PublicMediaError("eligible media exceeds the prepared-object candidate limit")
    preparer_fingerprint = _preparer_fingerprint()
    cache: Mapping[str, CacheEntry] = {}
    if (
        reuse_cache
        and existing_output.preparer_fingerprint == preparer_fingerprint
        and existing_output.cache is not None
    ):
        cache = existing_output.cache
    output.parent.mkdir(parents=True, exist_ok=True)
    stage = Path(tempfile.mkdtemp(prefix=f".{output.name}.stage-", dir=output.parent))
    owns_client = client is None
    active_client = client or httpx.Client(follow_redirects=False, timeout=DOWNLOAD_TIMEOUT)

    try:
        objects_by_source: dict[tuple[object, ...], tuple[PreparedObject, str]] = {}
        objects_by_hash: dict[str, PreparedObject] = {}
        unavailable_by_source: dict[tuple[object, ...], str] = {}
        total_prepared_bytes = 0
        items: list[dict[str, object]] = []
        successful_rows: list[tuple[SourceImageRow, str]] = []
        unavailable_rows: list[tuple[SourceImageRow, str]] = []
        for row in rows:
            source_key = row.source_object_key()
            unavailable_reason = unavailable_by_source.get(source_key)
            if unavailable_reason is not None:
                unavailable_rows.append((row, unavailable_reason))
                continue
            prepared_source = objects_by_source.get(source_key)
            if prepared_source is None:
                prepared: PreparedObject | None = None
                decoded_source_mime_type: str | None = None
                cached = cache.get(row.cache_key(preparer_fingerprint))
                if cached is not None:
                    candidate = PreparedObject(
                        sha256=cached.sha256,
                        width=cached.width,
                        height=cached.height,
                        byte_size=cached.byte_size,
                    )
                    existing = objects_by_hash.get(candidate.sha256)
                    if existing is not None:
                        prepared = _matching_prepared_object(existing, candidate)
                    else:
                        _check_prepared_object_limits(
                            candidate,
                            object_count=len(objects_by_hash),
                            total_bytes=total_prepared_bytes,
                        )
                        try:
                            _materialize_cached_object(cached, stage)
                        except PublicMediaError:
                            cached = None
                        else:
                            objects_by_hash[candidate.sha256] = candidate
                            total_prepared_bytes += candidate.byte_size
                            prepared = candidate
                    if cached is not None:
                        decoded_source_mime_type = cached.decoded_source_mime_type
                if cached is None:
                    try:
                        source, response_mime_type = _download_image(
                            active_client,
                            row.source_image_url,
                            provider=row.provider,
                            expected_mime_type=row.source_mime_type,
                            sleeper=sleeper,
                        )
                    except UnavailableSourceError as exc:
                        if len(unavailable_by_source) >= MAX_UNAVAILABLE_SOURCE_OBJECTS:
                            raise PublicMediaError(
                                "unavailable source-object limit exceeded"
                            ) from exc
                        unavailable_by_source[source_key] = exc.reason
                        unavailable_rows.append((row, exc.reason))
                        continue
                    candidate, payload, decoded_source_mime_type = _prepare_image(
                        source,
                        row,
                        response_mime_type=response_mime_type,
                    )
                    existing = objects_by_hash.get(candidate.sha256)
                    if existing is not None:
                        prepared = _matching_prepared_object(existing, candidate)
                    else:
                        _check_prepared_object_limits(
                            candidate,
                            object_count=len(objects_by_hash),
                            total_bytes=total_prepared_bytes,
                        )
                        _write_object(stage, candidate, payload)
                        objects_by_hash[candidate.sha256] = candidate
                        total_prepared_bytes += candidate.byte_size
                        prepared = candidate
                if (
                    prepared is None or decoded_source_mime_type is None
                ):  # pragma: no cover - defensive local invariant
                    raise PublicMediaError("media preparation produced no object")
                prepared_source = (prepared, decoded_source_mime_type)
            if prepared_source is None:  # pragma: no cover - defensive local invariant
                raise PublicMediaError("media preparation produced no object")
            prepared, decoded_source_mime_type = prepared_source
            objects_by_source[source_key] = prepared_source
            items.append(
                _manifest_item(
                    row,
                    prepared,
                    decoded_source_mime_type=decoded_source_mime_type,
                )
            )
            successful_rows.append((row, decoded_source_mime_type))

        items.sort(key=_manifest_item_sort_key)
        unavailable_rows.sort(key=lambda value: _source_row_sort_key(value[0]))
        unavailable_items = [
            _manifest_unavailable_item(row, reason) for row, reason in unavailable_rows
        ]
        cache_identity = _cache_identity(
            successful_rows,
            preparer_fingerprint,
            unavailable_rows=unavailable_rows,
        )
        manifest = {
            "schema_version": SCHEMA_VERSION,
            "mode": MODE,
            "generated_at": max(row.loaded_at for row in rows),
            "preparer_fingerprint": preparer_fingerprint,
            "cache_identity": cache_identity,
            "public_base_url": PUBLIC_BASE_URL,
            "counts": {
                "items": len(items),
                "objects": len(objects_by_hash),
                "species": len({row.species_code for row, _mime in successful_rows}),
                "unavailable_items": len(unavailable_items),
                "unavailable_source_objects": len(unavailable_by_source),
            },
            "items": items,
            "unavailable_items": unavailable_items,
        }
        _write_json(stage / "manifest.json", manifest)
        if approvals is not None:
            assert provider is not None  # guarded above
            try:
                require_visual_approvals(
                    stage / "manifest.json",
                    approvals,
                    provider=provider,
                )
            except MediaApprovalError as exc:
                raise PublicMediaError(f"prepared media visual approval failed: {exc}") from None
        _publish_staged_tree(stage, output, expected=existing_output)
    except PublicMediaError:
        shutil.rmtree(stage, ignore_errors=True)
        raise
    except Exception as exc:
        shutil.rmtree(stage, ignore_errors=True)
        raise PublicMediaError("media preparation failed before atomic publication") from exc
    finally:
        if owns_client:
            active_client.close()

    counts = manifest["counts"]
    if not isinstance(counts, dict):  # pragma: no cover - locally constructed invariant
        raise PublicMediaError("internal manifest count invariant failed")
    return PreparationResult(
        output_dir=output,
        manifest_path=output / "manifest.json",
        items=int(counts["items"]),
        objects=int(counts["objects"]),
        species=int(counts["species"]),
    )


def _read_source_rows(
    database: Path,
    *,
    provider: str | None = None,
) -> list[SourceImageRow]:
    expected = list(SOURCE_COLUMNS)
    raw_rows: list[tuple[str, tuple[object, ...]]] = []
    total_eligible_rows = 0
    source_tables: Sequence[tuple[str, str, str, bool]]
    if provider is None:
        source_tables = SOURCE_TABLES
    else:
        if provider not in _MEDIA_PROVIDERS:
            raise PublicMediaError("media provider is not reviewed")
        selected = [table for table in SOURCE_TABLES if table[0] == provider]
        if len(selected) != 1:  # pragma: no cover - constant contract invariant
            raise PublicMediaError("media provider has no reviewed source model")
        provider_name, schema_name, table_name, _required = selected[0]
        source_tables = ((provider_name, schema_name, table_name, True),)
    try:
        with duckdb.connect(str(database), read_only=True) as connection:
            for provider_name, schema_name, table_name, required in source_tables:
                exists = connection.execute(
                    """SELECT 1
                    FROM information_schema.tables
                    WHERE table_schema = ? AND table_name = ?""",
                    [schema_name, table_name],
                ).fetchone()
                if exists is None:
                    if required:
                        raise PublicMediaError(
                            f"{schema_name}.{table_name} is missing from the reviewed media models"
                        )
                    continue
                actual = [
                    row[0]
                    for row in connection.execute(
                        """
                    SELECT column_name
                    FROM information_schema.columns
                    WHERE table_schema = ? AND table_name = ?
                    ORDER BY ordinal_position
                    """,
                        [schema_name, table_name],
                    ).fetchall()
                ]
                if actual != expected:
                    raise PublicMediaError(
                        f"{schema_name}.{table_name} does not have the exact reviewed schema"
                    )
                qualified = f'"{schema_name}"."{table_name}"'
                raw_count = connection.execute(f"SELECT COUNT(*) FROM {qualified}").fetchone()
                if raw_count is None or isinstance(raw_count[0], bool):
                    raise PublicMediaError(
                        f"could not count the reviewed {provider_name} media model"
                    )
                total_eligible_rows += int(raw_count[0])
                if total_eligible_rows > MAX_ELIGIBLE_ROWS:
                    raise PublicMediaError("eligible media exceeds the reviewed row limit")
                quoted = ", ".join(f'"{column}"' for column in SOURCE_COLUMNS)
                cursor = connection.execute(f"SELECT {quoted} FROM {qualified}")
                raw_rows.extend((provider_name, tuple(row)) for row in cursor.fetchall())
    except PublicMediaError:
        raise
    except duckdb.Error as exc:
        raise PublicMediaError("could not read the reviewed media models") from exc

    if not raw_rows:
        raise PublicMediaError("the reviewed media models are empty")

    distinct: dict[tuple[object, ...], SourceImageRow] = {}
    for provider, raw_row in raw_rows:
        values = dict(zip(SOURCE_COLUMNS, raw_row, strict=True))
        values["provider"] = provider
        row = SourceImageRow.from_values(values)
        previous = distinct.get(row.semantic_key())
        if previous is None or row.loaded_at > previous.loaded_at:
            distinct[row.semantic_key()] = row
    return sorted(distinct.values(), key=_source_row_sort_key)


def _selected_source_pages(approval_path: Path, *, provider: str) -> frozenset[str]:
    """Load exact selected provenance pages for a provider-only preparation."""
    try:
        selections = load_visual_approvals(approval_path).values()
    except MediaApprovalError as exc:
        raise PublicMediaError(f"media visual approval failed: {exc}") from None
    pages: set[str] = set()
    for selection in selections:
        for source_page_url in selection.source_page_urls:
            try:
                validate_source_page_url(source_page_url, provider=provider)
            except PublicMediaError:
                continue
            pages.add(source_page_url)
    if not pages:
        raise PublicMediaError(f"visual-approval ledger has no selected {provider} source pages")
    return frozenset(pages)


def _download_image(
    client: httpx.Client,
    source_url: str,
    *,
    provider: str = "usfws",
    expected_mime_type: str,
    sleeper: Callable[[float], None],
) -> tuple[bytes, str]:
    source_url = validate_source_image_url(source_url, provider=provider)
    reviewed_wikimedia_filename = (
        _wikimedia_image_filename(source_url) if provider == "wikimedia" else None
    )
    last_error: Exception | None = None
    for attempt in range(MAX_ATTEMPTS):
        current_url = source_url
        try:
            for redirect_count in range(MAX_REDIRECTS + 1):
                validate_source_image_url(current_url, provider=provider)
                with client.stream(
                    "GET",
                    current_url,
                    headers={
                        "User-Agent": USER_AGENT,
                        "Accept": expected_mime_type,
                    },
                    timeout=DOWNLOAD_TIMEOUT,
                ) as response:
                    if response.status_code in _REDIRECT_STATUSES:
                        if redirect_count >= MAX_REDIRECTS:
                            raise PublicMediaError("source image exceeded the redirect limit")
                        location = response.headers.get("location")
                        if not location:
                            raise PublicMediaError("source image redirect omitted Location")
                        redirect_url = validate_source_image_url(
                            urljoin(str(response.url), location), provider=provider
                        )
                        if (
                            reviewed_wikimedia_filename is not None
                            and _wikimedia_image_filename(redirect_url)
                            != reviewed_wikimedia_filename
                        ):
                            raise PublicMediaError(
                                "Wikimedia redirect changed the reviewed file identity"
                            )
                        current_url = redirect_url
                        continue
                    if response.status_code in _RETRY_STATUSES:
                        raise _RetryableDownloadError(f"retryable_http_{response.status_code}")
                    if response.status_code != 200:
                        raise PublicMediaError(f"source image returned HTTP {response.status_code}")

                    raw_response_mime = (
                        response.headers.get("content-type", "").split(";", 1)[0].strip()
                    )
                    try:
                        response_mime, _ = _normalize_source_mime(raw_response_mime)
                    except PublicMediaError as exc:
                        raise _RetryableDownloadError(
                            "unsupported_http_content_type"
                            if raw_response_mime
                            else "missing_http_content_type"
                        ) from exc
                    length = response.headers.get("content-length")
                    if length is not None:
                        try:
                            declared_length = int(length)
                        except ValueError as exc:
                            raise PublicMediaError(
                                "source image returned malformed Content-Length"
                            ) from exc
                        if declared_length < 0 or declared_length > MAX_DOWNLOAD_BYTES:
                            raise PublicMediaError("source image exceeds the download-size limit")

                    payload = bytearray()
                    for chunk in response.iter_bytes():
                        payload.extend(chunk)
                        if len(payload) > MAX_DOWNLOAD_BYTES:
                            raise PublicMediaError("source image exceeds the download-size limit")
                    if not payload:
                        raise _RetryableDownloadError("truncated_response_body")
                    if length is not None and len(payload) != declared_length:
                        raise _RetryableDownloadError("truncated_response_body")
                    return bytes(payload), response_mime
            raise PublicMediaError("source image redirect handling failed")
        except (httpx.TimeoutException, httpx.TransportError, _RetryableDownloadError) as exc:
            last_error = exc
            if attempt + 1 < MAX_ATTEMPTS:
                sleeper(float(2**attempt))
                continue
        break
    raise UnavailableSourceError(_unavailable_reason(last_error)) from last_error


class _RetryableDownloadError(RuntimeError):
    def __init__(self, reason: str) -> None:
        self.reason = _validate_unavailable_reason(reason)
        super().__init__(self.reason)


def _unavailable_reason(error: Exception | None) -> str:
    if isinstance(error, _RetryableDownloadError):
        return error.reason
    if isinstance(error, httpx.TimeoutException):
        return "timeout"
    if isinstance(error, httpx.TransportError):
        return "transport_error"
    raise PublicMediaError("media retry state ended without an unavailable-source reason")


def _prepare_image(
    payload: bytes,
    row: SourceImageRow,
    *,
    response_mime_type: str,
) -> tuple[PreparedObject, bytes, str]:
    # The reviewed model and HTTP Content-Type must both stay within the narrow
    # allowlist, but neither is trusted as a statement about the downloaded
    # bytes. Pillow's decoded format is the authority after the byte, frame,
    # dimension, pixel, and decoder-integrity checks below all pass.
    _normalize_source_mime(response_mime_type)
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(BytesIO(payload)) as probe:
                decoded_source_mime_type = _decoded_source_mime_type(probe.format)
                if getattr(probe, "n_frames", 1) != 1:
                    raise PublicMediaError("animated source images are not eligible")
                _validate_source_dimensions(probe.size, row)
                probe.verify()

            with Image.open(BytesIO(payload)) as source:
                if _decoded_source_mime_type(source.format) != decoded_source_mime_type:
                    raise PublicMediaError("source image format changed while decoding")
                if getattr(source, "n_frames", 1) != 1:
                    raise PublicMediaError("animated source images are not eligible")
                _validate_source_dimensions(source.size, row)
                source.load()
                oriented = ImageOps.exif_transpose(source)
                mode = "RGBA" if "A" in oriented.getbands() else "RGB"
                prepared_image = oriented.convert(mode)
                prepared_image.thumbnail(
                    (MAX_OUTPUT_DIMENSION, MAX_OUTPUT_DIMENSION),
                    Image.Resampling.LANCZOS,
                )
                encoded = _encode_webp(prepared_image)
    except PublicMediaError:
        raise
    except (Image.DecompressionBombError, Image.DecompressionBombWarning) as exc:
        raise PublicMediaError("source image exceeds Pillow's decompression safety limits") from exc
    except (UnidentifiedImageError, OSError, SyntaxError, ValueError) as exc:
        raise PublicMediaError("source image could not be safely decoded") from exc

    digest = hashlib.sha256(encoded).hexdigest()
    prepared = PreparedObject(
        sha256=digest,
        width=prepared_image.width,
        height=prepared_image.height,
        byte_size=len(encoded),
    )
    return prepared, encoded, decoded_source_mime_type


def _decoded_source_mime_type(value: object) -> str:
    if not isinstance(value, str):
        raise PublicMediaError("decoded source image has no supported format")
    mime_type = _DECODED_SOURCE_MIME_TYPES.get(value)
    if mime_type is None:
        raise PublicMediaError("decoded source image has an unsupported format")
    return mime_type


def _validate_source_dimensions(size: tuple[int, int], row: SourceImageRow) -> None:
    width, height = size
    if width <= 0 or height <= 0 or width * height > MAX_SOURCE_PIXELS:
        raise PublicMediaError("decoded source image exceeds the safe pixel limit")
    if (width, height) not in {
        (row.source_width, row.source_height),
        (row.source_height, row.source_width),
    }:
        raise PublicMediaError("decoded source dimensions do not match reviewed metadata")


def _encode_webp(image: Image.Image) -> bytes:
    for quality in (84, 76, 68, 60, 52, 44, 36):
        output = BytesIO()
        image.save(
            output,
            format="WEBP",
            quality=quality,
            method=6,
            lossless=False,
            exact=True,
        )
        payload = output.getvalue()
        if len(payload) <= MAX_OUTPUT_BYTES:
            return payload
    raise PublicMediaError("normalized WebP could not meet the one-megabyte limit")


def _manifest_item(
    row: SourceImageRow,
    prepared: PreparedObject,
    *,
    decoded_source_mime_type: str,
) -> dict[str, object]:
    normalized_decoded_mime, _ = _normalize_source_mime(decoded_source_mime_type)
    media_id = _media_id(row)
    attribution_payload = "\x1f".join(
        (row.creator, row.license, row.license_url, row.source_page_url)
    ).encode("utf-8")
    attribution_id = (
        f"inaturalist-attribution-{_inaturalist_photo_id(row)}"
        if row.provider == "inaturalist"
        else f"{row.provider}-attribution-" + hashlib.sha256(attribution_payload).hexdigest()[:24]
    )
    item: dict[str, object] = {
        "provider": row.provider,
        "species_code": row.species_code,
        "common_name": row.common_name,
        "scientific_name": row.scientific_name,
        "media_id": media_id,
        "source_page_url": row.source_page_url,
        "source_image_url": row.source_image_url,
        "creator": row.creator,
        "license": row.license,
        "license_url": row.license_url,
        "title": row.title,
        "caption": row.caption,
        "alt_text": row.alt_text,
        "width": prepared.width,
        "height": prepared.height,
        "byte_size": prepared.byte_size,
        "mime_type": "image/webp",
        "sha256": prepared.sha256,
        "object_path": prepared.relative_path,
        "url": prepared.public_url,
        "attribution_id": attribution_id,
        "hero_score": _hero_score(row),
        "source_width": row.source_width,
        "source_height": row.source_height,
        "source_mime_type": row.source_mime_type,
        "decoded_source_mime_type": normalized_decoded_mime,
        "discovery_method": row.discovery_method,
        "loaded_at": row.loaded_at,
    }
    if row.source_published_at is not None:
        item["source_published_at"] = row.source_published_at
    return item


def _manifest_unavailable_item(row: SourceImageRow, reason: str) -> dict[str, object]:
    item: dict[str, object] = {
        "provider": row.provider,
        "species_code": row.species_code,
        "common_name": row.common_name,
        "scientific_name": row.scientific_name,
        "media_id": _media_id(row),
        "source_page_url": row.source_page_url,
        "source_image_url": row.source_image_url,
        "creator": row.creator,
        "license": row.license,
        "license_url": row.license_url,
        "title": row.title,
        "caption": row.caption,
        "alt_text": row.alt_text,
        "source_width": row.source_width,
        "source_height": row.source_height,
        "source_mime_type": row.source_mime_type,
        "discovery_method": row.discovery_method,
        "loaded_at": row.loaded_at,
        "attempts": MAX_ATTEMPTS,
        "reason": _validate_unavailable_reason(reason),
    }
    if row.source_published_at is not None:
        item["source_published_at"] = row.source_published_at
    return item


def _media_id(row: SourceImageRow) -> str:
    if row.provider == "inaturalist":
        return f"inaturalist-{_inaturalist_photo_id(row)}"
    semantic_payload = json.dumps(
        row.semantic_key(), ensure_ascii=False, separators=(",", ":")
    ).encode("utf-8")
    return f"{row.provider}-" + hashlib.sha256(semantic_payload).hexdigest()[:24]


def _inaturalist_photo_id(row: SourceImageRow) -> str:
    if row.provider != "inaturalist":
        raise PublicMediaError("iNaturalist photo identity requested for another provider")
    match = _INATURALIST_PHOTO_PAGE.fullmatch(urlsplit(row.source_page_url).path)
    if match is None:  # pragma: no cover - SourceImageRow already validates this.
        raise PublicMediaError("iNaturalist source page lost its exact photo identity")
    return match.group("photo_id")


def _manifest_item_sort_key(item: dict[str, object]) -> tuple[str, int, str]:
    hero_score = item["hero_score"]
    if not isinstance(hero_score, int):
        raise PublicMediaError("manifest hero score must be an integer")
    return str(item["species_code"]), -hero_score, str(item["media_id"])


def _hero_score(row: SourceImageRow) -> int:
    min_dimension = min(row.source_width, row.source_height)
    resolution = min(40, math.floor((min_dimension / 1_300) * 40))
    ratio = row.source_width / row.source_height
    if 0.667 <= ratio <= 1.8:
        composition = 20
    elif 0.5 <= ratio <= 2.2:
        composition = 10
    else:
        composition = 0
    generic = {row.common_name.casefold(), row.scientific_name.casefold(), row.title.casefold()}
    creator = 15 if row.creator.casefold() not in generic else 5
    alt = 10 if len(row.alt_text) >= 12 and row.alt_text.casefold() not in generic else 0
    caption = (
        10
        if row.caption is not None
        and len(row.caption) >= 12
        and row.caption.casefold() not in generic
        else 0
    )
    discovery = 5 if "species" in row.discovery_method.casefold() else 0
    return resolution + composition + creator + alt + caption + discovery


def _write_object(stage: Path, prepared: PreparedObject, payload: bytes) -> None:
    if len(payload) != prepared.byte_size:
        raise PublicMediaError("prepared object size changed before staging")
    if hashlib.sha256(payload).hexdigest() != prepared.sha256:
        raise PublicMediaError("prepared object hash changed before staging")
    target = stage / prepared.relative_path
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("xb") as handle:
        handle.write(payload)
        handle.flush()
        os.fsync(handle.fileno())


def _write_json(path: Path, value: Mapping[str, object]) -> None:
    payload = (
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"
    ).encode("utf-8")
    if len(payload) > MAX_MANIFEST_BYTES:
        raise PublicMediaError("internal media manifest exceeds the safe size limit")
    with path.open("xb") as handle:
        handle.write(payload)
        handle.flush()
        os.fsync(handle.fileno())


def _preparer_fingerprint() -> str:
    """Fingerprint the running preparer source and its image-encoding runtime."""
    try:
        source = Path(__file__).read_bytes()
        restricted_mark_policy = Path(restricted_marks.__file__).read_bytes()
    except OSError as exc:
        raise PublicMediaError("could not fingerprint the media preparer source") from exc
    runtime = _canonical_json_bytes(
        {
            "pillow_version": PIL.__version__,
            "webp_version": str(getattr(Image.core, "webp_version", "unavailable")),
        }
    )
    digest = hashlib.sha256()
    digest.update(source)
    digest.update(b"\x00rufous-restricted-mark-policy\x00")
    digest.update(restricted_mark_policy)
    digest.update(b"\x00rufous-preparer-runtime\x00")
    digest.update(runtime)
    return digest.hexdigest()


def _cache_identity(
    rows: Sequence[tuple[SourceImageRow, str]],
    preparer_fingerprint: str,
    *,
    unavailable_rows: Sequence[tuple[SourceImageRow, str]] = (),
) -> str:
    """Return a stable cache identity without refresh or generation timestamps."""
    semantic_outcomes = []
    for row, decoded_source_mime_type in rows:
        normalized_decoded_mime, _ = _normalize_source_mime(decoded_source_mime_type)
        semantic_outcomes.append(
            {
                "outcome": "prepared",
                "decoded_source_mime_type": normalized_decoded_mime,
                "semantic_row": row.semantic_key(),
            }
        )
    semantic_outcomes.extend(
        {
            "outcome": "unavailable",
            "reason": _validate_unavailable_reason(reason),
            "semantic_row": row.semantic_key(),
        }
        for row, reason in unavailable_rows
    )
    semantic_outcomes.sort(key=_canonical_json_bytes)
    payload = _canonical_json_bytes(
        {
            "schema_version": SCHEMA_VERSION,
            "mode": MODE,
            "public_base_url": PUBLIC_BASE_URL,
            "preparer_fingerprint": preparer_fingerprint,
            "semantic_outcomes": semantic_outcomes,
        }
    )
    return hashlib.sha256(payload).hexdigest()


def _canonical_json_bytes(value: object) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _check_prepared_object_limits(
    prepared: PreparedObject,
    *,
    object_count: int,
    total_bytes: int,
) -> None:
    if (
        not _SHA256.fullmatch(prepared.sha256)
        or prepared.width <= 0
        or prepared.height <= 0
        or prepared.width > MAX_OUTPUT_DIMENSION
        or prepared.height > MAX_OUTPUT_DIMENSION
        or prepared.byte_size <= 0
        or prepared.byte_size > MAX_OUTPUT_BYTES
    ):
        raise PublicMediaError("prepared object has unsafe metadata")
    if object_count >= MAX_PREPARED_OBJECTS:
        raise PublicMediaError("prepared media exceeds the object-count limit")
    if total_bytes + prepared.byte_size > MAX_TOTAL_PREPARED_BYTES:
        raise PublicMediaError("prepared media exceeds the total-byte limit")


def _matching_prepared_object(
    existing: PreparedObject, candidate: PreparedObject
) -> PreparedObject:
    if existing != candidate:
        raise PublicMediaError("one prepared hash has conflicting object metadata")
    return existing


def _load_cache(
    output: Path,
    *,
    preparer_fingerprint: str,
) -> dict[str, CacheEntry]:
    manifest_path = output / "manifest.json"
    try:
        manifest_stat = manifest_path.lstat()
    except OSError as exc:
        raise PublicMediaError("existing media cache has no safe manifest") from exc
    if not stat.S_ISREG(manifest_stat.st_mode) or manifest_path.is_symlink():
        raise PublicMediaError("existing media cache has no safe manifest")
    if manifest_stat.st_size > MAX_MANIFEST_BYTES:
        raise PublicMediaError("existing media cache manifest exceeds the safe size limit")
    try:
        raw: object = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise PublicMediaError("existing media cache manifest is malformed") from exc
    if not isinstance(raw, dict):
        raise PublicMediaError("existing media cache manifest must be an object")
    if set(raw) != {
        "schema_version",
        "mode",
        "generated_at",
        "preparer_fingerprint",
        "cache_identity",
        "public_base_url",
        "counts",
        "items",
        "unavailable_items",
    }:
        raise PublicMediaError("existing media cache manifest has an unexpected contract")
    if raw.get("schema_version") != SCHEMA_VERSION or raw.get("mode") != MODE:
        raise PublicMediaError("existing media cache manifest has an unsupported contract")
    if raw.get("public_base_url") != PUBLIC_BASE_URL:
        raise PublicMediaError("existing media cache has an unexpected public base URL")
    raw_fingerprint = raw.get("preparer_fingerprint")
    raw_identity = raw.get("cache_identity")
    if (
        not isinstance(raw_fingerprint, str)
        or not _SHA256.fullmatch(raw_fingerprint)
        or raw_fingerprint != preparer_fingerprint
        or not isinstance(raw_identity, str)
        or not _SHA256.fullmatch(raw_identity)
    ):
        raise PublicMediaError("existing media cache identity does not match this preparation")
    raw_items = raw.get("items")
    raw_unavailable = raw.get("unavailable_items")
    if not isinstance(raw_items, list) or not isinstance(raw_unavailable, list):
        raise PublicMediaError("existing media cache manifest has malformed item lists")
    if len(raw_items) + len(raw_unavailable) > MAX_ELIGIBLE_ROWS:
        raise PublicMediaError("existing media cache exceeds the reviewed row limit")

    cache: dict[str, CacheEntry] = {}
    cached_rows: list[tuple[SourceImageRow, str]] = []
    cached_semantic_keys: set[tuple[object, ...]] = set()
    successful_source_keys: set[tuple[object, ...]] = set()
    objects: dict[str, PreparedObject] = {}
    total_cached_bytes = 0
    for raw_item in raw_items:
        if not isinstance(raw_item, dict):
            raise PublicMediaError("existing media cache contains a malformed item")
        source_values = {
            column: raw_item.get("source_mime_type" if column == "mime_type" else column)
            for column in SOURCE_COLUMNS
        }
        source_values["provider"] = raw_item.get("provider")
        row = SourceImageRow.from_values(source_values)
        if row.semantic_key() in cached_semantic_keys:
            raise PublicMediaError("existing media cache repeats one semantic row")
        cached_semantic_keys.add(row.semantic_key())
        successful_source_keys.add(row.source_object_key())
        sha256 = _required_text(raw_item.get("sha256"), "sha256", 64)
        if not _SHA256.fullmatch(sha256):
            raise PublicMediaError("existing media cache has an invalid object hash")
        width = _positive_int(raw_item.get("width"), "width")
        height = _positive_int(raw_item.get("height"), "height")
        if width > MAX_OUTPUT_DIMENSION or height > MAX_OUTPUT_DIMENSION:
            raise PublicMediaError("existing media cache has invalid output dimensions")
        byte_size = _positive_int(raw_item.get("byte_size"), "byte_size")
        if byte_size > MAX_OUTPUT_BYTES:
            raise PublicMediaError("existing media cache object has an unsafe size")
        prepared = PreparedObject(
            sha256=sha256,
            width=width,
            height=height,
            byte_size=byte_size,
        )
        decoded_source_mime_type, _ = _normalize_source_mime(
            raw_item.get("decoded_source_mime_type")
        )
        expected_item = _manifest_item(
            row,
            prepared,
            decoded_source_mime_type=decoded_source_mime_type,
        )
        if raw_item != expected_item:
            raise PublicMediaError("existing media cache item does not match reviewed metadata")
        prior_object = objects.get(sha256)
        if prior_object is not None:
            _matching_prepared_object(prior_object, prepared)
        else:
            _check_prepared_object_limits(
                prepared,
                object_count=len(objects),
                total_bytes=total_cached_bytes,
            )
            objects[sha256] = prepared
            total_cached_bytes += prepared.byte_size
        relative = Path("objects") / sha256[:2] / f"{sha256}.webp"
        entry = CacheEntry(
            cache_key=row.cache_key(preparer_fingerprint),
            sha256=sha256,
            width=width,
            height=height,
            byte_size=byte_size,
            decoded_source_mime_type=decoded_source_mime_type,
            path=output / relative,
        )
        previous = cache.get(entry.cache_key)
        if previous is not None and previous.sha256 != entry.sha256:
            raise PublicMediaError("existing media cache maps one source to multiple objects")
        if previous is not None:
            raise PublicMediaError("existing media cache repeats one semantic row")
        cache[entry.cache_key] = entry
        cached_rows.append((row, decoded_source_mime_type))

    unavailable_rows: list[tuple[SourceImageRow, str]] = []
    unavailable_source_reasons: dict[tuple[object, ...], str] = {}
    for raw_item in raw_unavailable:
        if not isinstance(raw_item, dict):
            raise PublicMediaError("existing media cache contains a malformed unavailable item")
        source_values = {
            column: raw_item.get("source_mime_type" if column == "mime_type" else column)
            for column in SOURCE_COLUMNS
        }
        source_values["provider"] = raw_item.get("provider")
        row = SourceImageRow.from_values(source_values)
        reason = _validate_unavailable_reason(raw_item.get("reason"))
        expected_item = _manifest_unavailable_item(row, reason)
        if raw_item != expected_item:
            raise PublicMediaError(
                "existing media cache unavailable item does not match reviewed metadata"
            )
        semantic_key = row.semantic_key()
        if semantic_key in cached_semantic_keys:
            raise PublicMediaError("existing media cache repeats one semantic row")
        cached_semantic_keys.add(semantic_key)
        source_key = row.source_object_key()
        if source_key in successful_source_keys:
            raise PublicMediaError(
                "existing media cache marks one source both prepared and unavailable"
            )
        previous_reason = unavailable_source_reasons.get(source_key)
        if previous_reason is not None and previous_reason != reason:
            raise PublicMediaError(
                "existing media cache gives one unavailable source conflicting reasons"
            )
        unavailable_source_reasons[source_key] = reason
        unavailable_rows.append((row, reason))

    if len(unavailable_source_reasons) > MAX_UNAVAILABLE_SOURCE_OBJECTS:
        raise PublicMediaError("existing media cache exceeds the unavailable-source limit")
    if unavailable_rows != sorted(
        unavailable_rows, key=lambda value: _source_row_sort_key(value[0])
    ):
        raise PublicMediaError("existing media cache unavailable items are not deterministic")
    if (
        _cache_identity(
            cached_rows,
            preparer_fingerprint,
            unavailable_rows=unavailable_rows,
        )
        != raw_identity
    ):
        raise PublicMediaError("existing media cache items do not match its cache identity")
    complete_rows = [
        *(row for row, _mime in cached_rows),
        *(row for row, _reason in unavailable_rows),
    ]
    if not complete_rows or raw.get("generated_at") != max(row.loaded_at for row in complete_rows):
        raise PublicMediaError("existing media cache generation time does not match its items")
    expected_counts = {
        "items": len(raw_items),
        "objects": len(objects),
        "species": len({row.species_code for row, _mime in cached_rows}),
        "unavailable_items": len(raw_unavailable),
        "unavailable_source_objects": len(unavailable_source_reasons),
    }
    if raw.get("counts") != expected_counts:
        raise PublicMediaError("existing media cache counts do not match its items")
    return cache


def _materialize_cached_object(entry: CacheEntry, stage: Path) -> None:
    try:
        file_stat = entry.path.lstat()
    except OSError as exc:
        raise PublicMediaError("existing media cache object is missing") from exc
    if not stat.S_ISREG(file_stat.st_mode) or entry.path.is_symlink():
        raise PublicMediaError("existing media cache object is not a regular file")
    if file_stat.st_size != entry.byte_size:
        raise PublicMediaError("existing media cache object has an unsafe size")
    target = stage / "objects" / entry.sha256[:2] / f"{entry.sha256}.webp"
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_name(f".{target.name}.copy-{uuid.uuid4().hex}")
    try:
        source_fd = os.open(
            entry.path,
            os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0),
        )
    except OSError as exc:
        raise PublicMediaError("existing media cache object could not be read") from exc
    try:
        digest = hashlib.sha256()
        copied = 0
        with os.fdopen(source_fd, "rb") as source, temporary.open("xb") as destination:
            opened_stat = os.fstat(source.fileno())
            if not stat.S_ISREG(opened_stat.st_mode) or opened_stat.st_size != entry.byte_size:
                raise PublicMediaError("existing media cache object changed while reading")
            while True:
                chunk = source.read(64 * 1024)
                if not chunk:
                    break
                copied += len(chunk)
                if copied > entry.byte_size:
                    raise PublicMediaError("existing media cache object changed while reading")
                digest.update(chunk)
                destination.write(chunk)
            destination.flush()
            os.fsync(destination.fileno())
        if copied != entry.byte_size or digest.hexdigest() != entry.sha256:
            raise PublicMediaError("existing media cache object hash does not match its manifest")
        with Image.open(temporary) as image:
            if (
                image.format != "WEBP"
                or image.size != (entry.width, entry.height)
                or getattr(image, "n_frames", 1) != 1
            ):
                raise PublicMediaError("existing media cache object metadata is invalid")
            image.verify()
        os.replace(temporary, target)
    except PublicMediaError:
        temporary.unlink(missing_ok=True)
        raise
    except (UnidentifiedImageError, OSError, SyntaxError, ValueError) as exc:
        temporary.unlink(missing_ok=True)
        raise PublicMediaError("existing media cache object is not a safe WebP") from exc


def _publish_staged_tree(stage: Path, output: Path, *, expected: _ValidatedOutput) -> None:
    current = _validate_output_target(output)
    if current.state != expected.state:
        raise PublicMediaError("media output changed while the new preparation was being built")
    _fsync_tree_directories(stage)

    backup: Path | None = None
    if output.exists():
        backup = output.with_name(f".{output.name}.backup-{uuid.uuid4().hex}")
        try:
            os.replace(output, backup)
            _fsync_directory(output.parent)
        except OSError as exc:
            raise PublicMediaError("could not preserve the previous media preparation") from exc
    try:
        os.replace(stage, output)
        _fsync_directory(output.parent)
    except OSError as exc:
        if backup is not None and backup.exists():
            try:
                os.replace(backup, output)
                _fsync_directory(output.parent)
            except OSError as restore_exc:
                raise PublicMediaError(
                    "could not publish the media preparation or restore its preserved backup"
                ) from restore_exc
        raise PublicMediaError("could not atomically publish the media preparation") from exc
    if backup is not None:
        try:
            shutil.rmtree(backup)
        except OSError:
            # Publication succeeded and the prior tree remains a recoverable,
            # uniquely named backup.  Cleanup must not invalidate the new tree.
            pass


def _validate_output_target(output: Path) -> _ValidatedOutput:
    if output == Path(output.anchor) or output == output.parent:
        raise PublicMediaError("media output path is too broad")
    if not output.exists():
        return _ValidatedOutput(kind="absent")
    try:
        output_stat = output.lstat()
    except OSError as exc:
        raise PublicMediaError("existing media output could not be inspected") from exc
    if not stat.S_ISDIR(output_stat.st_mode) or output.is_symlink():
        raise PublicMediaError("existing media output must be a real directory")
    try:
        if next(output.iterdir(), None) is None:
            return _ValidatedOutput(kind="empty")
    except OSError as exc:
        raise PublicMediaError("existing media output could not be inspected") from exc

    preparer_fingerprint, cache_identity = _existing_output_identity(output)
    cache = _load_cache(output, preparer_fingerprint=preparer_fingerprint)
    _validate_existing_media_inventory(output, cache)
    for entry in {item.sha256: item for item in cache.values()}.values():
        _verify_existing_media_object(entry)
    return _ValidatedOutput(
        kind="rufous-media",
        preparer_fingerprint=preparer_fingerprint,
        cache_identity=cache_identity,
        cache=cache,
    )


def _existing_output_identity(output: Path) -> tuple[str, str]:
    manifest_path = output / "manifest.json"
    try:
        manifest_stat = manifest_path.lstat()
    except OSError as exc:
        raise PublicMediaError(
            "refusing to replace a non-empty directory without a valid Rufous media manifest"
        ) from exc
    if (
        not stat.S_ISREG(manifest_stat.st_mode)
        or manifest_path.is_symlink()
        or manifest_stat.st_size > MAX_MANIFEST_BYTES
    ):
        raise PublicMediaError(
            "refusing to replace a non-empty directory without a valid Rufous media manifest"
        )
    try:
        raw: object = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise PublicMediaError(
            "refusing to replace a non-empty directory without a valid Rufous media manifest"
        ) from exc
    if not isinstance(raw, dict):
        raise PublicMediaError(
            "refusing to replace a non-empty directory without a valid Rufous media manifest"
        )
    preparer_fingerprint = raw.get("preparer_fingerprint")
    cache_identity = raw.get("cache_identity")
    if (
        not isinstance(preparer_fingerprint, str)
        or _SHA256.fullmatch(preparer_fingerprint) is None
        or not isinstance(cache_identity, str)
        or _SHA256.fullmatch(cache_identity) is None
    ):
        raise PublicMediaError(
            "refusing to replace a non-empty directory without a valid Rufous media manifest"
        )
    return preparer_fingerprint, cache_identity


def _validate_existing_media_inventory(
    output: Path,
    cache: Mapping[str, CacheEntry],
) -> None:
    expected_files = {Path("manifest.json")}
    expected_files.update(
        Path("objects") / entry.sha256[:2] / f"{entry.sha256}.webp" for entry in cache.values()
    )
    expected_directories: set[Path] = set()
    for relative in expected_files:
        parent = relative.parent
        while parent != Path("."):
            expected_directories.add(parent)
            parent = parent.parent

    actual_files: set[Path] = set()
    actual_directories: set[Path] = set()

    def walk_error(exc: OSError) -> None:
        raise PublicMediaError("existing media output could not be inspected") from exc

    for root, directories, files in os.walk(output, topdown=True, onerror=walk_error):
        root_path = Path(root)
        for name in directories:
            child = root_path / name
            try:
                child_stat = child.lstat()
            except OSError as exc:
                raise PublicMediaError("existing media output could not be inspected") from exc
            if child.is_symlink() or not stat.S_ISDIR(child_stat.st_mode):
                raise PublicMediaError("existing media output contains an unsafe directory")
            actual_directories.add(child.relative_to(output))
        for name in files:
            child = root_path / name
            try:
                child_stat = child.lstat()
            except OSError as exc:
                raise PublicMediaError("existing media output could not be inspected") from exc
            if child.is_symlink() or not stat.S_ISREG(child_stat.st_mode):
                raise PublicMediaError("existing media output contains an unsafe file")
            actual_files.add(child.relative_to(output))
    if actual_files != expected_files or actual_directories != expected_directories:
        raise PublicMediaError("existing media output does not match its exact Rufous manifest")


def _verify_existing_media_object(entry: CacheEntry) -> None:
    try:
        file_stat = entry.path.lstat()
        if entry.path.is_symlink() or not stat.S_ISREG(file_stat.st_mode):
            raise PublicMediaError("existing media cache object is not a regular file")
        source_fd = os.open(entry.path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
    except PublicMediaError:
        raise
    except OSError as exc:
        raise PublicMediaError("existing media cache object could not be read") from exc
    try:
        digest = hashlib.sha256()
        copied = 0
        with os.fdopen(source_fd, "rb") as source:
            opened_stat = os.fstat(source.fileno())
            if not stat.S_ISREG(opened_stat.st_mode) or opened_stat.st_size != entry.byte_size:
                raise PublicMediaError("existing media cache object changed while reading")
            while True:
                chunk = source.read(64 * 1024)
                if not chunk:
                    break
                copied += len(chunk)
                if copied > entry.byte_size:
                    raise PublicMediaError("existing media cache object changed while reading")
                digest.update(chunk)
            if copied != entry.byte_size or digest.hexdigest() != entry.sha256:
                raise PublicMediaError(
                    "existing media cache object hash does not match its manifest"
                )
            source.seek(0)
            with Image.open(source) as image:
                if (
                    image.format != "WEBP"
                    or image.size != (entry.width, entry.height)
                    or getattr(image, "n_frames", 1) != 1
                ):
                    raise PublicMediaError("existing media cache object metadata is invalid")
                image.verify()
    except PublicMediaError:
        raise
    except (UnidentifiedImageError, OSError, SyntaxError, ValueError) as exc:
        raise PublicMediaError("existing media cache object is not a safe WebP") from exc


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


def _source_row_sort_key(row: SourceImageRow) -> tuple[str, ...]:
    return tuple("" if value is None else str(value) for value in row.semantic_key())


def _validated_fws_url(value: object, field: str) -> tuple[str, SplitResult]:
    return _validated_https_url(
        value,
        field,
        hosts=_FWS_HOSTS,
        origin_description="an exact HTTPS fws.gov origin",
    )


def _validated_https_url(
    value: object,
    field: str,
    *,
    hosts: frozenset[str],
    origin_description: str = "an exact reviewed HTTPS origin",
) -> tuple[str, SplitResult]:
    raw = _required_text(value, field, 2_000)
    if any(ord(character) < 32 or ord(character) == 127 for character in raw):
        raise PublicMediaError(f"{field} contains control characters")
    try:
        parsed = urlsplit(raw)
        port = parsed.port
    except ValueError as exc:
        raise PublicMediaError(f"{field} is malformed") from exc
    if (
        parsed.scheme != "https"
        or parsed.hostname not in hosts
        or parsed.username is not None
        or parsed.password is not None
        or port is not None
        or not parsed.path.startswith("/")
    ):
        raise PublicMediaError(f"{field} must use {origin_description}")
    return raw, parsed


def _required_text(value: object, field: str, maximum: int) -> str:
    if not isinstance(value, str):
        raise PublicMediaError(f"{field} must be text")
    normalized = value.strip()
    if (
        not normalized
        or len(normalized) > maximum
        or any(ord(character) < 32 and character not in "\t\n" for character in normalized)
    ):
        raise PublicMediaError(f"{field} is empty, unsafe, or too long")
    return normalized


def _optional_text(value: object, field: str, maximum: int) -> str | None:
    if value is None:
        return None
    return _required_text(value, field, maximum)


def _positive_int(value: object, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise PublicMediaError(f"{field} must be a positive integer")
    return value


def _normalize_source_mime(value: object) -> tuple[str, str]:
    raw = _required_text(value, "mime_type", 100).casefold()
    normalized = _SOURCE_MIME_TYPES.get(raw)
    if normalized is None:
        raise PublicMediaError("source image has an unsupported MIME type")
    return normalized


def _validate_unavailable_reason(value: object) -> str:
    reason = _required_text(value, "unavailable_reason", 100)
    if reason not in _UNAVAILABLE_REASONS:
        raise PublicMediaError("unavailable source has an unsupported reason")
    return reason


def _required_timestamp(value: object, field: str) -> str:
    normalized = _optional_timestamp(value, field)
    if normalized is None:
        raise PublicMediaError(f"{field} is required")
    return normalized


def _optional_timestamp(value: object, field: str) -> str | None:
    if value is None:
        return None
    parsed: datetime
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, date):
        parsed = datetime(value.year, value.month, value.day, tzinfo=UTC)
    elif isinstance(value, str):
        raw = _required_text(value, field, 100)
        try:
            parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        except ValueError as exc:
            raise PublicMediaError(f"{field} is not a valid timestamp") from exc
    else:
        raise PublicMediaError(f"{field} is not a valid timestamp")
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    parsed = parsed.astimezone(UTC)
    return parsed.isoformat(timespec="seconds").replace("+00:00", "Z")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database-path", default="data/databox.duckdb")
    parser.add_argument("--output-dir", default="build/rufous-media")
    parser.add_argument(
        "--no-cache-reuse",
        action="store_true",
        help="redownload every source instead of reusing verified prepared objects",
    )
    parser.add_argument(
        "--provider",
        choices=sorted(_MEDIA_PROVIDERS),
        help="prepare only one reviewed provider model (default: complete release)",
    )
    parser.add_argument(
        "--approvals",
        type=Path,
        help="download only selected pages and verify final hashes (requires --provider)",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        result = prepare_public_media(
            args.database_path,
            args.output_dir,
            reuse_cache=not args.no_cache_reuse,
            provider=args.provider,
            approval_path=args.approvals,
        )
    except PublicMediaError as exc:
        print(f"Rufous media preparation failed: {exc}")
        return 1
    print(
        "Prepared Rufous media: "
        f"{result.items} items, {result.objects} objects, {result.species} species"
    )
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
