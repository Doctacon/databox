"""Prepare and publish reviewed Rufous bird audio without recurring hydration.

This module deliberately has no discovery command.  A human-reviewed selection
is the only input it accepts.  ``acquire`` captures (or verifies) the selected
bytes into a content-addressed local preparation, while ``ensure-r2`` checks the
immutable namespace first and contacts an upstream provider only for an object
that is absent from R2.

Ordinary public-data and Pages deployments consume the committed pinned
manifest and never invoke this module's network paths.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import math
import os
import re
import subprocess
import sys
import tempfile
from collections.abc import Callable, Mapping
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urljoin, urlsplit

import httpx

from databox.public_export import (
    PUBLIC_AUDIO_SANITIZATION_NOTICE,
    PublicExportError,
    canonical_license,
    load_public_audio_manifest,
)
from databox.public_release import (
    IMMUTABLE_CACHE_CONTROL,
    LocalReleaseStore,
    PrefixUsageStore,
    PublicReleaseError,
    R2Config,
    R2ReleaseStore,
    SourceObject,
)

AUDIO_SCHEMA_VERSION = 1
SELECTION_MODE = "rufous-audio-selection"
CHECKPOINT_MODE = "rufous-audio-capture-checkpoint"
DEFAULT_AUDIO_PREFIX = "rufous-audio/v1/objects"
PUBLIC_AUDIO_BASE_URL = "https://rufous-data.loughondata.com/rufous-audio/v1/objects"
MAX_AUDIO_OBJECT_BYTES = 25 * 1024 * 1024
MAX_AUDIO_SOURCE_BYTES = 150 * 1024 * 1024
MAX_AUDIO_MANIFEST_BYTES = 25 * 1024 * 1024
MAX_AUDIO_OBJECTS = 10_000
MAX_AUDIO_TOTAL_BYTES = 2 * 1024 * 1024 * 1024
MAX_AUDIO_PREFIX_OBJECTS = 20_000
MAX_AUDIO_PREFIX_BYTES = 10 * 1024 * 1024 * 1024
DURATION_TOLERANCE_SECONDS = 0.25
MAX_AUDIO_REDIRECTS = 5
SANITIZATION_TRANSFORMATION = "sanitize_audio_stream"

_SHA256 = re.compile(r"^[a-f0-9]{64}$")
_SPECIES_CODE = re.compile(r"^[a-z0-9][a-z0-9-]{0,31}$")
_SCIENTIFIC_NAME = re.compile(r"^[A-Z][A-Za-z-]+ [a-z][A-Za-z-]+(?: [A-Za-z-]+)?$")
_XENO_ID = re.compile(r"^XC(?P<id>[1-9][0-9]{0,9})$")
_INAT_ID = re.compile(r"^sound-(?P<id>[1-9][0-9]{0,19})$")
_USFWS_ID = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,238}[a-z0-9])?$")

_MIME_EXTENSIONS = {
    "audio/mpeg": "mp3",
    "audio/ogg": "ogg",
    "audio/wav": "wav",
    "audio/webm": "webm",
    "audio/mp4": "m4a",
}
_PUBLIC_AUDIO_FORMAT_CODECS = {
    "audio/mpeg": ("mp3", frozenset({"mp3"})),
    "audio/wav": (
        "wav",
        frozenset({"pcm_s16le", "pcm_s24le", "pcm_s32le", "pcm_f32le"}),
    ),
    "audio/mp4": ("mov,mp4,m4a,3gp,3g2,mj2", frozenset({"aac"})),
    "audio/ogg": ("ogg", frozenset({"opus"})),
}
_PUBLIC_AUDIO_MIME_TYPES = frozenset(_PUBLIC_AUDIO_FORMAT_CODECS)
_CONTENT_TYPE_ALIASES = {
    "audio/mpeg": frozenset({"audio/mpeg", "audio/mp3"}),
    "audio/ogg": frozenset({"audio/ogg", "application/ogg"}),
    "audio/wav": frozenset({"audio/wav", "audio/wave", "audio/x-wav"}),
    "audio/webm": frozenset({"audio/webm", "video/webm"}),
    "audio/mp4": frozenset({"audio/mp4", "audio/x-m4a", "application/mp4", "video/mp4"}),
}
_PROVIDERS = frozenset({"xeno_canto", "inaturalist", "wikimedia", "usfws"})
_TRANSFORMATIONS = frozenset({SANITIZATION_TRANSFORMATION})
_LEGACY_TRANSFORMATIONS = frozenset({"none", "extract_audio_stream"})
_FETCH_ALLOWED_HOSTS = frozenset(
    {
        "xeno-canto.org",
        "www.xeno-canto.org",
        "static.inaturalist.org",
        "inaturalist-open-data.s3.amazonaws.com",
        "www.inaturalist.org",
        "upload.wikimedia.org",
        "www.fws.gov",
        "fws.gov",
        "digitalmedia.fws.gov",
    }
)

_MANIFEST_ROOT_KEYS = frozenset({"schema_version", "generated_at", "counts", "items"})
_MANIFEST_COUNT_KEYS = frozenset({"items", "objects", "species"})
_MANIFEST_ITEM_KEYS = frozenset(
    {
        "species_code",
        "common_name",
        "scientific_name",
        "provider",
        "provider_id",
        "source_url",
        "creator",
        "license",
        "license_url",
        "original_url",
        "url",
        "sha256",
        "bytes",
        "mime_type",
        "duration_seconds",
        "vocalization_type",
        "modification_notice",
    }
)
_SELECTION_ROOT_KEYS = frozenset({"schema_version", "mode", "reviewed_at", "reviewed_by", "items"})
_SELECTION_ITEM_KEYS = frozenset(
    {
        "species_code",
        "common_name",
        "scientific_name",
        "provider",
        "provider_id",
        "source_url",
        "creator",
        "license",
        "license_url",
        "original_url",
        "expected_sha256",
        "expected_bytes",
        "expected_mime_type",
        "duration_seconds",
        "vocalization_type",
        "modification_notice",
        "transformation",
    }
)
_CHECKPOINT_ROOT_KEYS = frozenset({"schema_version", "mode", "items"})
_CHECKPOINT_ITEM_KEYS = frozenset({"identity", "capture_fingerprint", "public_item"})
_CHECKPOINT_IDENTITY_KEYS = frozenset({"species_code", "provider", "provider_id"})


class PublicAudioError(RuntimeError):
    """A reviewed audio selection cannot safely become a public object."""


@dataclass(frozen=True)
class DownloadedAudio:
    """One bounded HTTP response returned by an injectable fetcher."""

    payload: bytes
    content_type: str
    final_url: str
    redirect_urls: tuple[str, ...] = ()


AudioFetcher = Callable[[str, int], DownloadedAudio]
AudioSanitizer = Callable[[bytes, str, str], bytes]
AudioProbe = Callable[[bytes, str], float]
AudioEquivalenceChecker = Callable[[bytes, str, bytes, str], None]


@dataclass(frozen=True)
class AudioStreamFingerprint:
    codec: str
    sample_rate: int
    channels: int
    duration_seconds: float
    decoded_pcm_sha256: str


@dataclass(frozen=True)
class AudioAcquireResult:
    status: str
    items: int
    downloaded_objects: int
    reused_objects: int
    total_bytes: int
    output: str


@dataclass(frozen=True)
class AudioPublishResult:
    status: str
    dry_run: bool
    items: int
    total_bytes: int
    uploaded_objects: int
    reused_objects: int
    prefix: str


def canonical_audio_manifest_json(payload: object) -> bytes:
    """Serialize the public pin deterministically for review and commits."""
    return (json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode(
        "utf-8"
    )


def canonical_audio_selection_json(payload: object) -> bytes:
    """Serialize the human-reviewed acquisition ledger deterministically."""
    return canonical_audio_manifest_json(payload)


def _text(value: object, *, maximum: int) -> str | None:
    if (
        not isinstance(value, str)
        or not value
        or len(value) > maximum
        or value.strip() != value
        or any(ord(character) < 32 or ord(character) == 127 for character in value)
    ):
        return None
    return value


def _aware_datetime(value: object, *, label: str) -> str:
    raw = _text(value, maximum=100)
    if raw is None:
        raise PublicAudioError(f"{label} must be an ISO 8601 timestamp")
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        raise PublicAudioError(f"{label} must be an ISO 8601 timestamp") from None
    if parsed.tzinfo is None:
        raise PublicAudioError(f"{label} must include a timezone")
    return raw


def _load_json(path: Path, *, label: str) -> tuple[dict[str, Any], bytes]:
    if path.is_symlink() or not path.is_file():
        raise PublicAudioError(f"{label} is missing or unsafe")
    try:
        raw = path.read_bytes()
    except OSError as exc:
        raise PublicAudioError(f"could not read {label}") from exc
    if not raw or len(raw) > MAX_AUDIO_MANIFEST_BYTES:
        raise PublicAudioError(f"{label} is empty or exceeds 25 MiB")
    try:
        payload: object = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise PublicAudioError(f"{label} is not valid UTF-8 JSON") from None
    if not isinstance(payload, dict):
        raise PublicAudioError(f"{label} must be an object")
    return payload, raw


def _https_url(
    value: object,
    *,
    hosts: frozenset[str],
    allow_query: bool = False,
) -> tuple[str, str, str] | None:
    raw = _text(value, maximum=2_000)
    if raw is None:
        return None
    try:
        parsed = urlsplit(raw)
        port = parsed.port
    except ValueError:
        return None
    if (
        parsed.scheme != "https"
        or parsed.hostname not in hosts
        or parsed.username is not None
        or parsed.password is not None
        or port is not None
        or parsed.fragment
        or (parsed.query and not allow_query)
        or (parsed.query and "x-amz-" in parsed.query.casefold())
        or not parsed.path.startswith("/")
    ):
        return None
    return parsed.hostname, parsed.path, parsed.query


def _valid_wikimedia_source(provider_id: str, source_url: str) -> bool:
    if not provider_id.startswith("File:"):
        return False
    parsed = _https_url(source_url, hosts=frozenset({"commons.wikimedia.org"}))
    if parsed is None or not parsed[1].startswith("/wiki/File:"):
        return False
    try:
        filename = unquote(parsed[1].removeprefix("/wiki/File:"), errors="strict")
    except (UnicodeError, ValueError):
        return False
    return bool(
        provider_id == f"File:{filename}"
        and 0 < len(filename) <= 500
        and filename.strip() == filename
        and filename not in {".", ".."}
        and not any(character in filename for character in ("/", "\\"))
        and not any(ord(character) < 32 or ord(character) == 127 for character in filename)
    )


def _valid_source_identity(provider: str, provider_id: str, source_url: str) -> bool:
    if provider == "xeno_canto":
        match = _XENO_ID.fullmatch(provider_id)
        parsed = _https_url(source_url, hosts=frozenset({"xeno-canto.org"}))
        return bool(match and parsed and parsed[1] == f"/{match.group('id')}")
    if provider == "inaturalist":
        parsed = _https_url(source_url, hosts=frozenset({"www.inaturalist.org"}))
        return bool(
            _INAT_ID.fullmatch(provider_id)
            and parsed
            and re.fullmatch(r"/observations/[1-9][0-9]{0,19}", parsed[1])
        )
    if provider == "wikimedia":
        return _valid_wikimedia_source(provider_id, source_url)
    if provider == "usfws":
        parsed = _https_url(source_url, hosts=frozenset({"www.fws.gov"}))
        return bool(
            _USFWS_ID.fullmatch(provider_id) and parsed and parsed[1] == f"/media/{provider_id}"
        )
    return False


def _valid_original_url(provider: str, value: str) -> bool:
    contracts: dict[str, tuple[frozenset[str], re.Pattern[str]]] = {
        "xeno_canto": (
            frozenset({"xeno-canto.org", "www.xeno-canto.org"}),
            re.compile(r"/(?:[1-9][0-9]{0,9}/download|sounds/uploaded/[^/]+/[^/]+)"),
        ),
        "inaturalist": (
            frozenset(
                {
                    "static.inaturalist.org",
                    "inaturalist-open-data.s3.amazonaws.com",
                    "www.inaturalist.org",
                }
            ),
            re.compile(r"/(?:sounds|attachments/sounds)/[^/]+"),
        ),
        "wikimedia": (
            frozenset({"upload.wikimedia.org"}),
            re.compile(r"/wikipedia/commons/(?:[^/]+/){1,4}[^/]+"),
        ),
        "usfws": (
            frozenset({"www.fws.gov", "fws.gov", "digitalmedia.fws.gov"}),
            re.compile(r"/.+"),
        ),
    }
    contract = contracts.get(provider)
    if contract is None:
        return False
    parsed = _https_url(value, hosts=contract[0], allow_query=True)
    return bool(parsed and contract[1].fullmatch(parsed[1]))


def _validate_selection_item(
    raw: object,
    *,
    index: int,
    require_pinned: bool,
    allow_legacy_unsanitized: bool = False,
) -> dict[str, Any]:
    if not isinstance(raw, dict) or set(raw) != _SELECTION_ITEM_KEYS:
        raise PublicAudioError(f"audio selection item {index} has unexpected fields")
    item = dict(raw)
    species_code = _text(item.get("species_code"), maximum=32)
    common_name = _text(item.get("common_name"), maximum=200)
    scientific_name = _text(item.get("scientific_name"), maximum=200)
    provider = _text(item.get("provider"), maximum=32)
    provider_id = _text(item.get("provider_id"), maximum=512)
    source_url = _text(item.get("source_url"), maximum=2_000)
    creator = _text(item.get("creator"), maximum=500)
    original_url = _text(item.get("original_url"), maximum=2_000)
    mime_type = _text(item.get("expected_mime_type"), maximum=64)
    vocalization = _text(item.get("vocalization_type"), maximum=100)
    modifications = _text(item.get("modification_notice"), maximum=1_000)
    transformation = _text(item.get("transformation"), maximum=100)
    duration = item.get("duration_seconds")
    expected_sha = item.get("expected_sha256")
    expected_bytes = item.get("expected_bytes")
    valid_duration = bool(
        duration is not None
        and not isinstance(duration, bool)
        and isinstance(duration, int | float)
        and math.isfinite(float(duration))
        and 0 < float(duration) <= 3_600
    )
    if (
        species_code is None
        or _SPECIES_CODE.fullmatch(species_code) is None
        or common_name is None
        or scientific_name is None
        or _SCIENTIFIC_NAME.fullmatch(scientific_name) is None
        or provider not in _PROVIDERS
        or provider_id is None
        or source_url is None
        or not _valid_source_identity(provider, provider_id, source_url)
        or creator is None
        or original_url is None
        or not _valid_original_url(provider, original_url)
        or (mime_type is not None and mime_type not in _PUBLIC_AUDIO_MIME_TYPES)
        or (require_pinned and mime_type not in _PUBLIC_AUDIO_MIME_TYPES)
        or vocalization is None
        or modifications is None
        or transformation
        not in (_LEGACY_TRANSFORMATIONS if allow_legacy_unsanitized else _TRANSFORMATIONS)
        or (duration is not None and not valid_duration)
        or (require_pinned and not valid_duration)
    ):
        raise PublicAudioError(f"audio selection item {index} fails its reviewed contract")
    license_pair = canonical_license(provider, item.get("license"))
    if (
        license_pair is None
        or item.get("license") != license_pair[0]
        or item.get("license_url") != license_pair[1]
    ):
        raise PublicAudioError(f"audio selection item {index} has a forbidden license")
    if allow_legacy_unsanitized and transformation == "extract_audio_stream":
        if mime_type != "audio/ogg" or "extract" not in modifications.casefold():
            raise PublicAudioError(
                f"audio selection item {index} must disclose its audio-stream extraction"
            )
    elif allow_legacy_unsanitized and "unmodified" not in modifications.casefold():
        raise PublicAudioError(
            f"audio selection item {index} must state that original bytes are unmodified"
        )
    elif not allow_legacy_unsanitized and modifications != PUBLIC_AUDIO_SANITIZATION_NOTICE:
        raise PublicAudioError(
            f"audio selection item {index} must disclose its metadata-stripping remux"
        )
    pinned = expected_sha is not None or expected_bytes is not None
    if pinned and (
        not isinstance(expected_sha, str)
        or _SHA256.fullmatch(expected_sha) is None
        or type(expected_bytes) is not int
        or not 0 < expected_bytes <= MAX_AUDIO_OBJECT_BYTES
    ):
        raise PublicAudioError(f"audio selection item {index} has an invalid expected object")
    if not pinned and (expected_sha is not None or expected_bytes is not None):
        raise PublicAudioError(f"audio selection item {index} has a partial expected object")
    if require_pinned and not pinned:
        raise PublicAudioError(f"audio selection item {index} is not fully pinned")
    return item


def _load_audio_selection(
    path: Path,
    *,
    require_pinned: bool,
    allow_legacy_unsanitized: bool,
) -> dict[str, Any]:
    payload, raw_bytes = _load_json(path, label="audio selection")
    if (
        set(payload) != _SELECTION_ROOT_KEYS
        or payload.get("schema_version") != AUDIO_SCHEMA_VERSION
        or payload.get("mode") != SELECTION_MODE
        or _text(payload.get("reviewed_by"), maximum=200) is None
        or not isinstance(payload.get("items"), list)
        or not payload["items"]
    ):
        raise PublicAudioError("audio selection has an invalid reviewed contract")
    _aware_datetime(payload.get("reviewed_at"), label="audio selection reviewed_at")
    if raw_bytes != canonical_audio_selection_json(payload):
        raise PublicAudioError("audio selection must use canonical sorted JSON")
    items = [
        _validate_selection_item(
            item,
            index=index,
            require_pinned=require_pinned,
            allow_legacy_unsanitized=allow_legacy_unsanitized,
        )
        for index, item in enumerate(payload["items"])
    ]
    ordered = sorted(items, key=lambda item: str(item["species_code"]))
    if items != ordered:
        raise PublicAudioError("audio selection items must be sorted by species_code")
    species_codes = [str(item["species_code"]) for item in items]
    scientific_names = [str(item["scientific_name"]).casefold() for item in items]
    identities = [(str(item["provider"]), str(item["provider_id"])) for item in items]
    if (
        len(set(species_codes)) != len(items)
        or len(set(scientific_names)) != len(items)
        or len(set(identities)) != len(items)
    ):
        raise PublicAudioError("audio selection repeats a species or provider identity")
    return payload


def load_audio_selection(path: Path, *, require_pinned: bool) -> dict[str, Any]:
    """Load a canonical sanitized human-reviewed selection and fail closed."""
    return _load_audio_selection(
        path,
        require_pinned=require_pinned,
        allow_legacy_unsanitized=False,
    )


def _load_legacy_audio_selection(path: Path) -> dict[str, Any]:
    """Load one old unsanitized pin only for the explicit local migration path."""
    return _load_audio_selection(
        path,
        require_pinned=True,
        allow_legacy_unsanitized=True,
    )


def load_pinned_audio_manifest(path: Path) -> dict[str, Any]:
    """Load the exact canonical manifest consumed by the public exporter."""
    payload, raw = _load_json(path, label="pinned audio manifest")
    if (
        set(payload) != _MANIFEST_ROOT_KEYS
        or payload.get("schema_version") != AUDIO_SCHEMA_VERSION
        or not isinstance(payload.get("items"), list)
        or not payload["items"]
        or not isinstance(payload.get("counts"), dict)
        or set(payload["counts"]) != _MANIFEST_COUNT_KEYS
    ):
        raise PublicAudioError("pinned audio manifest has an invalid contract")
    _aware_datetime(payload.get("generated_at"), label="pinned audio generated_at")
    if raw != canonical_audio_manifest_json(payload):
        raise PublicAudioError("pinned audio manifest must use canonical sorted JSON")
    if any(
        not isinstance(item, dict) or set(item) != _MANIFEST_ITEM_KEYS for item in payload["items"]
    ):
        raise PublicAudioError("pinned audio manifest contains malformed items")
    if payload["items"] != sorted(payload["items"], key=lambda item: str(item["species_code"])):
        raise PublicAudioError("pinned audio manifest items must be sorted by species_code")
    try:
        load_public_audio_manifest(path)
    except PublicExportError as exc:
        raise PublicAudioError(
            f"pinned audio manifest fails the exporter contract: {exc}"
        ) from None
    return payload


def _load_legacy_pinned_audio_manifest(path: Path) -> dict[str, Any]:
    """Load an old manifest structurally only for the explicit local migration."""
    payload, raw = _load_json(path, label="legacy pinned audio manifest")
    items = payload.get("items")
    counts = payload.get("counts")
    if (
        set(payload) != _MANIFEST_ROOT_KEYS
        or payload.get("schema_version") != AUDIO_SCHEMA_VERSION
        or not isinstance(items, list)
        or not items
        or not isinstance(counts, dict)
        or set(counts) != _MANIFEST_COUNT_KEYS
        or any(not isinstance(item, dict) or set(item) != _MANIFEST_ITEM_KEYS for item in items)
        or items != sorted(items, key=lambda item: str(item["species_code"]))
    ):
        raise PublicAudioError("legacy pinned audio manifest has an invalid contract")
    _aware_datetime(payload.get("generated_at"), label="legacy pinned audio generated_at")
    if raw != canonical_audio_manifest_json(payload):
        raise PublicAudioError("legacy pinned audio manifest must use canonical sorted JSON")
    expected_counts = {
        "items": len(items),
        "objects": len({str(item.get("sha256")) for item in items}),
        "species": len({str(item.get("species_code")) for item in items}),
    }
    if counts != expected_counts:
        raise PublicAudioError("legacy pinned audio manifest counts are inconsistent")
    return payload


def _detect_mime_type(payload: bytes) -> str | None:
    if len(payload) >= 12 and payload[:4] == b"RIFF" and payload[8:12] == b"WAVE":
        return "audio/wav"
    if payload.startswith(b"OggS"):
        return "audio/ogg"
    if payload.startswith(b"\x1aE\xdf\xa3"):
        return "audio/webm"
    if len(payload) >= 12 and payload[4:8] == b"ftyp":
        return "audio/mp4"
    if payload.startswith(b"ID3") or (
        len(payload) >= 2 and payload[0] == 0xFF and payload[1] & 0xE0 == 0xE0
    ):
        return "audio/mpeg"
    return None


def _header_matches(content_type: str, expected: str) -> bool:
    normalized = content_type.split(";", 1)[0].strip().casefold()
    return normalized in _CONTENT_TYPE_ALIASES[expected]


def _valid_fetch_url(value: str) -> bool:
    return _https_url(value, hosts=_FETCH_ALLOWED_HOSTS, allow_query=True) is not None


def _default_fetch_audio(url: str, maximum: int) -> DownloadedAudio:
    """Fetch one object with every redirect validated before its request.

    The provider-specific path contract is intentionally checked again after
    the download by :func:`_download_item`.  This lower-level allowlist prevents
    the HTTP client from ever following a redirect to another scheme, host, or
    explicit port in the first place.
    """
    headers = {
        "User-Agent": "loughondata.com Rufous audio release / connor@loughondata.com",
        "Accept": "audio/*,video/webm;q=0.8,application/ogg;q=0.8",
    }
    if not _valid_fetch_url(url):
        raise PublicAudioError("upstream audio URL is outside the fetch allowlist")
    current_url = url
    redirects: list[str] = []
    try:
        with httpx.Client(follow_redirects=False, timeout=httpx.Timeout(60.0)) as client:
            for redirect_count in range(MAX_AUDIO_REDIRECTS + 1):
                with client.stream("GET", current_url, headers=headers) as response:
                    if response.status_code in {301, 302, 303, 307, 308}:
                        location = response.headers.get("Location")
                        if location is None or redirect_count >= MAX_AUDIO_REDIRECTS:
                            raise PublicAudioError(
                                "upstream audio exceeded its bounded redirect policy"
                            )
                        next_url = urljoin(str(response.url), location)
                        if not _valid_fetch_url(next_url):
                            raise PublicAudioError(
                                "upstream audio redirect is outside the fetch allowlist"
                            )
                        redirects.append(str(response.url))
                        current_url = next_url
                        continue
                    if 300 <= response.status_code < 400:
                        raise PublicAudioError("upstream audio returned an unsupported redirect")
                    response.raise_for_status()
                    declared = response.headers.get("Content-Length")
                    if declared is not None:
                        try:
                            declared_bytes = int(declared)
                            if declared_bytes < 0 or declared_bytes > maximum:
                                raise PublicAudioError("upstream audio exceeds its download limit")
                        except ValueError:
                            raise PublicAudioError(
                                "upstream audio has an invalid Content-Length"
                            ) from None
                    chunks: list[bytes] = []
                    total = 0
                    for chunk in response.iter_bytes(1024 * 1024):
                        total += len(chunk)
                        if total > maximum:
                            raise PublicAudioError("upstream audio exceeds its download limit")
                        chunks.append(chunk)
                    return DownloadedAudio(
                        payload=b"".join(chunks),
                        content_type=response.headers.get("Content-Type", ""),
                        final_url=str(response.url),
                        redirect_urls=tuple(redirects),
                    )
            raise PublicAudioError("upstream audio exceeded its bounded redirect policy")
    except PublicAudioError:
        raise
    except httpx.HTTPError:
        raise PublicAudioError("upstream audio download failed") from None


def _sanitized_output_mime(source_mime: str) -> str:
    if source_mime == "audio/webm":
        return "audio/ogg"
    if source_mime in _MIME_EXTENSIONS:
        return source_mime
    raise PublicAudioError("upstream audio MIME is not a supported sanitization input")


def _source_discard_padding(payload: bytes, mime_type: str) -> int:
    """Read the first audio stream's final decoder-padding count."""
    extension = _MIME_EXTENSIONS.get(mime_type)
    if extension is None or not payload or len(payload) > MAX_AUDIO_SOURCE_BYTES:
        raise PublicAudioError("audio discard padding cannot be inspected safely")
    with tempfile.TemporaryDirectory(prefix="rufous-audio-padding-") as temporary:
        path = Path(temporary) / f"audio.{extension}"
        path.write_bytes(payload)
        command = [
            "ffprobe",
            "-v",
            "error",
            "-select_streams",
            "a:0",
            "-show_packets",
            "-show_entries",
            "packet=side_data_list",
            "-of",
            "json",
            str(path),
        ]
        try:
            completed = subprocess.run(
                command,
                check=False,
                capture_output=True,
                timeout=60,
            )
        except (OSError, subprocess.TimeoutExpired):
            raise PublicAudioError("audio discard padding could not be inspected") from None
    if completed.returncode != 0 or len(completed.stdout) > 20 * 1024 * 1024:
        raise PublicAudioError("audio discard padding inspection failed")
    try:
        result: object = json.loads(completed.stdout)
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise PublicAudioError("audio discard padding metadata is invalid") from None
    if not isinstance(result, dict) or not isinstance(result.get("packets"), list):
        raise PublicAudioError("audio discard padding metadata is invalid")
    discard_padding = 0
    for packet in result["packets"]:
        if not isinstance(packet, dict):
            raise PublicAudioError("audio discard padding metadata is invalid")
        side_data = packet.get("side_data_list", [])
        if not isinstance(side_data, list):
            raise PublicAudioError("audio discard padding metadata is invalid")
        for entry in side_data:
            if not isinstance(entry, dict) or entry.get("side_data_type") != "Skip Samples":
                continue
            value = entry.get("discard_padding", 0)
            if type(value) is not int or not 0 <= value <= 1_000_000:
                raise PublicAudioError("audio discard padding metadata is invalid")
            discard_padding = value
    return discard_padding


def _ogg_crc(payload: bytes) -> int:
    checksum = 0
    for value in payload:
        checksum ^= value << 24
        for _ in range(8):
            checksum = (
                ((checksum << 1) ^ 0x04C11DB7) & 0xFFFFFFFF
                if checksum & 0x80000000
                else (checksum << 1) & 0xFFFFFFFF
            )
    return checksum


def _apply_ogg_discard_padding(payload: bytes, discard_padding: int) -> bytes:
    """Translate Matroska end padding into the Ogg EOS granule position."""
    if discard_padding == 0:
        return payload
    result = bytearray(payload)
    offset = 0
    final_page: tuple[int, int] | None = None
    while offset < len(result):
        if len(result) - offset < 27 or result[offset : offset + 4] != b"OggS":
            raise PublicAudioError("sanitized Ogg page structure is invalid")
        segment_count = result[offset + 26]
        header_size = 27 + segment_count
        if len(result) - offset < header_size:
            raise PublicAudioError("sanitized Ogg page structure is invalid")
        body_size = sum(result[offset + 27 : offset + header_size])
        page_size = header_size + body_size
        if len(result) - offset < page_size:
            raise PublicAudioError("sanitized Ogg page structure is invalid")
        if result[offset + 5] & 0x04:
            if final_page is not None:
                raise PublicAudioError("sanitized Ogg contains multiple terminal streams")
            final_page = (offset, page_size)
        offset += page_size
    if offset != len(result) or final_page is None or final_page[0] + final_page[1] != len(result):
        raise PublicAudioError("sanitized Ogg terminal page is invalid")
    page_offset, page_size = final_page
    granule = int.from_bytes(result[page_offset + 6 : page_offset + 14], "little")
    if granule == 0xFFFFFFFFFFFFFFFF or not 0 < discard_padding < granule:
        raise PublicAudioError("sanitized Ogg cannot represent its source end padding")
    result[page_offset + 6 : page_offset + 14] = (granule - discard_padding).to_bytes(8, "little")
    result[page_offset + 22 : page_offset + 26] = b"\0\0\0\0"
    checksum = _ogg_crc(bytes(result[page_offset : page_offset + page_size]))
    result[page_offset + 22 : page_offset + 26] = checksum.to_bytes(4, "little")
    return bytes(result)


def _syncsafe_id3_size(raw: bytes) -> int:
    if len(raw) != 4 or any(value & 0x80 for value in raw):
        raise PublicAudioError("MP3 ID3v2 metadata has an invalid syncsafe size")
    return (raw[0] << 21) | (raw[1] << 14) | (raw[2] << 7) | raw[3]


def _strip_leading_id3v2(payload: bytes) -> tuple[bytes, bool]:
    if not payload.startswith(b"ID3"):
        return payload, False
    if len(payload) < 10:
        raise PublicAudioError("MP3 ID3v2 metadata is truncated")
    major = payload[3]
    revision = payload[4]
    flags = payload[5]
    allowed_flags = {2: 0xC0, 3: 0xE0, 4: 0xF0}.get(major)
    if (
        allowed_flags is None
        or revision == 0xFF
        or flags & ~allowed_flags
        or (major != 4 and flags & 0x10)
    ):
        raise PublicAudioError("MP3 ID3v2 metadata has an invalid header")
    declared_size = _syncsafe_id3_size(payload[6:10])
    tag_end = 10 + declared_size
    if tag_end > len(payload):
        raise PublicAudioError("MP3 ID3v2 metadata exceeds the source bytes")
    if flags & 0x10:
        footer_start: int
        if tag_end >= 20 and payload[tag_end - 10 : tag_end - 7] == b"3DI":
            footer_start = tag_end - 10
        elif tag_end + 10 <= len(payload) and payload[tag_end : tag_end + 3] == b"3DI":
            footer_start = tag_end
            tag_end += 10
        else:
            raise PublicAudioError("MP3 ID3v2 footer is missing or malformed")
        footer = payload[footer_start : footer_start + 10]
        if (
            footer[3] != major
            or footer[4] != revision
            or footer[5] != flags
            or _syncsafe_id3_size(footer[6:10]) != declared_size
        ):
            raise PublicAudioError("MP3 ID3v2 footer differs from its header")
    return payload[tag_end:], True


def _strip_trailing_apev2(payload: bytes) -> tuple[bytes, bool]:
    if len(payload) < 32 or payload[-32:-24] != b"APETAGEX":
        return payload, False
    footer = payload[-32:]
    version = int.from_bytes(footer[8:12], "little")
    tag_size = int.from_bytes(footer[12:16], "little")
    item_count = int.from_bytes(footer[16:20], "little")
    flags = int.from_bytes(footer[20:24], "little")
    if (
        version != 2_000
        or not 32 <= tag_size <= min(len(payload), 16 * 1024 * 1024)
        or item_count > 1_024
        or flags & ~0xC0000007
        or flags & 0x20000000
        or footer[24:32] != b"\0" * 8
    ):
        raise PublicAudioError("MP3 APEv2 metadata has an invalid footer")
    items_start = len(payload) - tag_size
    footer_start = len(payload) - 32
    offset = items_start
    for _ in range(item_count):
        if offset + 8 > footer_start:
            raise PublicAudioError("MP3 APEv2 metadata item is truncated")
        value_size = int.from_bytes(payload[offset : offset + 4], "little")
        item_flags = int.from_bytes(payload[offset + 4 : offset + 8], "little")
        key_start = offset + 8
        key_end = payload.find(b"\0", key_start, min(footer_start, key_start + 256))
        if key_end < 0:
            raise PublicAudioError("MP3 APEv2 metadata key is invalid")
        key = payload[key_start:key_end]
        if (
            not 2 <= len(key) <= 255
            or any(value < 0x20 or value > 0x7E or value == 0x3D for value in key)
            or item_flags & ~0x7
            or value_size > footer_start - key_end - 1
        ):
            raise PublicAudioError("MP3 APEv2 metadata item is invalid")
        offset = key_end + 1 + value_size
    if offset != footer_start:
        raise PublicAudioError("MP3 APEv2 metadata size is inconsistent")
    remove_start = items_start
    if flags & 0x80000000:
        header_start = items_start - 32
        if header_start < 0:
            raise PublicAudioError("MP3 APEv2 metadata header is missing")
        header = payload[header_start:items_start]
        if (
            header[:8] != b"APETAGEX"
            or header[8:20] != footer[8:20]
            or int.from_bytes(header[20:24], "little") != flags | 0x20000000
            or header[24:32] != b"\0" * 8
        ):
            raise PublicAudioError("MP3 APEv2 metadata header differs from its footer")
        remove_start = header_start
    return payload[:remove_start], True


def _mp3_frame_size(payload: bytes, offset: int) -> int:
    mpeg1_bitrates = (0, 32, 40, 48, 56, 64, 80, 96, 112, 128, 160, 192, 224, 256, 320)
    mpeg2_bitrates = (0, 8, 16, 24, 32, 40, 48, 56, 64, 80, 96, 112, 128, 144, 160)
    base_sample_rates = (44_100, 48_000, 32_000)
    if len(payload) - offset < 4:
        raise PublicAudioError("MP3 frame sequence has trailing non-audio bytes")
    header = int.from_bytes(payload[offset : offset + 4], "big")
    version_bits = (header >> 19) & 0x3
    layer_bits = (header >> 17) & 0x3
    bitrate_index = (header >> 12) & 0xF
    sample_rate_index = (header >> 10) & 0x3
    if (
        header >> 21 != 0x7FF
        or version_bits == 0x1
        or layer_bits != 0x1
        or bitrate_index in {0, 0xF}
        or sample_rate_index == 0x3
    ):
        raise PublicAudioError("MP3 frame sequence is malformed or non-contiguous")
    if version_bits == 0x3:
        bitrate = mpeg1_bitrates[bitrate_index]
        sample_rate = base_sample_rates[sample_rate_index]
        coefficient = 144_000
    else:
        bitrate = mpeg2_bitrates[bitrate_index]
        divisor = 2 if version_bits == 0x2 else 4
        sample_rate = base_sample_rates[sample_rate_index] // divisor
        coefficient = 72_000
    padding = (header >> 9) & 0x1
    frame_size = coefficient * bitrate // sample_rate + padding
    if frame_size < 4:
        raise PublicAudioError("MP3 frame sequence has an invalid frame size")
    return frame_size


def _normalize_contiguous_mp3_frames(payload: bytes) -> bytes:
    """Validate all frames and zero-complete at most one truncated final frame."""
    offset = 0
    frames = 0
    while offset < len(payload):
        frame_size = _mp3_frame_size(payload, offset)
        if offset + frame_size > len(payload):
            # Some legacy MP3s place APEv2 inside the nominal final frame.
            # After the validated tag is removed, zero completion preserves the
            # decoder flush while making the public file structurally exact.
            return payload + b"\0" * (offset + frame_size - len(payload))
        offset += frame_size
        frames += 1
    if frames == 0:
        raise PublicAudioError("MP3 metadata stripping produced no audio frames")
    return payload


def _validate_contiguous_mp3_frames(payload: bytes) -> None:
    normalized = _normalize_contiguous_mp3_frames(payload)
    if normalized != payload:
        raise PublicAudioError("public MP3 ends inside a truncated MPEG frame")


def _strip_mp3_metadata(payload: bytes) -> bytes:
    """Remove only validated ID3/APE wrappers while preserving all MPEG frames."""
    stripped, leading_removed = _strip_leading_id3v2(payload)
    trailing_removed = False
    for _ in range(4):
        if len(stripped) >= 128 and stripped[-128:-125] == b"TAG":
            stripped = stripped[:-128]
            trailing_removed = True
            continue
        stripped, ape_removed = _strip_trailing_apev2(stripped)
        if ape_removed:
            trailing_removed = True
            continue
        break
    if not leading_removed and not trailing_removed:
        raise PublicAudioError("MP3 metadata-strip fallback found no validated metadata")
    normalized = _normalize_contiguous_mp3_frames(stripped)
    _validate_contiguous_mp3_frames(normalized)
    return normalized


def _finalize_public_mp3(payload: bytes) -> bytes:
    """Strip every validated MP3 wrapper and require exact MPEG-frame EOF."""
    try:
        return _strip_mp3_metadata(payload)
    except PublicAudioError as exc:
        if "found no validated metadata" not in str(exc):
            raise
    normalized = _normalize_contiguous_mp3_frames(payload)
    _validate_contiguous_mp3_frames(normalized)
    return normalized


def _validate_public_wav(payload: bytes) -> None:
    if (
        len(payload) < 20
        or payload[:4] != b"RIFF"
        or payload[8:12] != b"WAVE"
        or int.from_bytes(payload[4:8], "little") + 8 != len(payload)
    ):
        raise PublicAudioError("public WAV has an invalid RIFF boundary")
    offset = 12
    seen: dict[bytes, int] = {}
    allowed = {b"fmt ", b"fact", b"data"}
    while offset < len(payload):
        if len(payload) - offset < 8:
            raise PublicAudioError("public WAV has trailing opaque bytes")
        chunk_type = payload[offset : offset + 4]
        chunk_size = int.from_bytes(payload[offset + 4 : offset + 8], "little")
        data_end = offset + 8 + chunk_size
        padded_end = data_end + (chunk_size & 1)
        if chunk_type not in allowed or data_end > len(payload) or padded_end > len(payload):
            raise PublicAudioError("public WAV contains a forbidden or malformed chunk")
        if padded_end > data_end and payload[data_end:padded_end] != b"\0":
            raise PublicAudioError("public WAV has nonzero chunk padding")
        seen[chunk_type] = seen.get(chunk_type, 0) + 1
        if seen[chunk_type] > 1:
            raise PublicAudioError("public WAV repeats a structural chunk")
        offset = padded_end
    if offset != len(payload) or seen.get(b"fmt ") != 1 or seen.get(b"data") != 1:
        raise PublicAudioError("public WAV is missing its format or audio-data chunk")


_MP4_CONTAINERS = frozenset({b"moov", b"trak", b"mdia", b"minf", b"stbl", b"edts", b"dinf"})
_MP4_FORBIDDEN_ATOMS = frozenset(
    {b"udta", b"meta", b"ilst", b"keys", b"uuid", b"loci", b"\xa9xyz", b"XMP_"}
)


def _neutralize_m4a_metadata_atoms(payload: bytes) -> bytes:
    """Replace parsed metadata atoms with same-size zeroed free-space atoms."""
    result = bytearray(payload)

    def walk(start: int, end: int, depth: int) -> None:
        if depth > 12:
            raise PublicAudioError("sanitized M4A atom nesting exceeds its limit")
        offset = start
        while offset < end:
            if end - offset < 8:
                raise PublicAudioError("sanitized M4A has trailing opaque bytes")
            size = int.from_bytes(result[offset : offset + 4], "big")
            atom_type = bytes(result[offset + 4 : offset + 8])
            header_size = 8
            if size == 1:
                if end - offset < 16:
                    raise PublicAudioError("sanitized M4A has a truncated extended atom")
                size = int.from_bytes(result[offset + 8 : offset + 16], "big")
                header_size = 16
            if size == 0 or size < header_size or offset + size > end:
                raise PublicAudioError("sanitized M4A has an invalid atom boundary")
            if atom_type in _MP4_FORBIDDEN_ATOMS:
                result[offset + 4 : offset + 8] = b"free"
                result[offset + header_size : offset + size] = b"\0" * (size - header_size)
            elif atom_type in _MP4_CONTAINERS:
                walk(offset + header_size, offset + size, depth + 1)
            offset += size
        if offset != end:
            raise PublicAudioError("sanitized M4A atoms do not end at EOF")

    walk(0, len(result), 0)
    return bytes(result)


def _validate_mp4_atoms(payload: bytes, start: int, end: int, *, depth: int) -> list[bytes]:
    if depth > 12:
        raise PublicAudioError("public M4A atom nesting exceeds its limit")
    offset = start
    atoms: list[bytes] = []
    while offset < end:
        if end - offset < 8:
            raise PublicAudioError("public M4A has trailing opaque bytes")
        size = int.from_bytes(payload[offset : offset + 4], "big")
        atom_type = payload[offset + 4 : offset + 8]
        header_size = 8
        if size == 1:
            if end - offset < 16:
                raise PublicAudioError("public M4A has a truncated extended atom")
            size = int.from_bytes(payload[offset + 8 : offset + 16], "big")
            header_size = 16
        if size == 0 or size < header_size or offset + size > end:
            raise PublicAudioError("public M4A has an invalid atom boundary")
        if atom_type in _MP4_FORBIDDEN_ATOMS:
            raise PublicAudioError("public M4A contains a forbidden metadata atom")
        atoms.append(atom_type)
        if atom_type in _MP4_CONTAINERS:
            _validate_mp4_atoms(
                payload,
                offset + header_size,
                offset + size,
                depth=depth + 1,
            )
        offset += size
    if offset != end:
        raise PublicAudioError("public M4A atoms do not end at EOF")
    return atoms


def _validate_public_m4a(payload: bytes) -> None:
    atoms = _validate_mp4_atoms(payload, 0, len(payload), depth=0)
    if (
        not atoms
        or atoms[0] != b"ftyp"
        or atoms.count(b"moov") != 1
        or atoms.count(b"mdat") != 1
        or any(atom not in {b"ftyp", b"moov", b"free", b"skip", b"wide", b"mdat"} for atom in atoms)
    ):
        raise PublicAudioError("public M4A has a forbidden top-level atom layout")


def _validate_public_ogg(payload: bytes) -> None:
    offset = 0
    serial: int | None = None
    expected_sequence = 0
    unfinished_packet = bytearray()
    packets: list[bytes] = []
    pages = 0
    while offset < len(payload):
        if len(payload) - offset < 27 or payload[offset : offset + 4] != b"OggS":
            raise PublicAudioError("public Ogg has an invalid page boundary")
        if payload[offset + 4] != 0:
            raise PublicAudioError("public Ogg uses an unsupported page version")
        flags = payload[offset + 5]
        page_serial = int.from_bytes(payload[offset + 14 : offset + 18], "little")
        sequence = int.from_bytes(payload[offset + 18 : offset + 22], "little")
        segment_count = payload[offset + 26]
        header_size = 27 + segment_count
        if len(payload) - offset < header_size:
            raise PublicAudioError("public Ogg has a truncated segment table")
        segments = payload[offset + 27 : offset + header_size]
        body_size = sum(segments)
        page_size = header_size + body_size
        if len(payload) - offset < page_size:
            raise PublicAudioError("public Ogg has a truncated page body")
        if serial is None:
            serial = page_serial
        if page_serial != serial or sequence != expected_sequence:
            raise PublicAudioError("public Ogg contains multiple or unordered logical streams")
        if pages == 0 and not flags & 0x02:
            raise PublicAudioError("public Ogg first page is not a beginning-of-stream page")
        if bool(flags & 0x01) != bool(unfinished_packet):
            raise PublicAudioError("public Ogg packet continuation flags are inconsistent")
        page = bytearray(payload[offset : offset + page_size])
        stored_checksum = int.from_bytes(page[22:26], "little")
        page[22:26] = b"\0\0\0\0"
        if _ogg_crc(bytes(page)) != stored_checksum:
            raise PublicAudioError("public Ogg page CRC is invalid")
        body = payload[offset + header_size : offset + page_size]
        body_offset = 0
        for segment_size in segments:
            unfinished_packet.extend(body[body_offset : body_offset + segment_size])
            body_offset += segment_size
            if segment_size < 255:
                packets.append(bytes(unfinished_packet))
                unfinished_packet.clear()
        pages += 1
        expected_sequence += 1
        offset += page_size
        if offset == len(payload) and not flags & 0x04:
            raise PublicAudioError("public Ogg final page is not an end-of-stream page")
    if offset != len(payload) or unfinished_packet or len(packets) < 3:
        raise PublicAudioError("public Ogg packet structure is incomplete")
    if not packets[0].startswith(b"OpusHead") or len(packets[1]) < 16:
        raise PublicAudioError("public Ogg is not a single Opus logical stream")
    tags = packets[1]
    if not tags.startswith(b"OpusTags"):
        raise PublicAudioError("public Ogg lacks its sanitized OpusTags packet")
    vendor_size = int.from_bytes(tags[8:12], "little")
    vendor_end = 12 + vendor_size
    if (
        vendor_end + 4 != len(tags)
        or tags[12:vendor_end] != b"ffmpeg"
        or int.from_bytes(tags[vendor_end : vendor_end + 4], "little") != 0
    ):
        raise PublicAudioError("public Ogg contains user comments or an unknown vendor")


def _validate_public_audio_structure(payload: bytes, mime_type: str) -> None:
    if mime_type == "audio/mpeg":
        _validate_contiguous_mp3_frames(payload)
    elif mime_type == "audio/wav":
        _validate_public_wav(payload)
    elif mime_type == "audio/mp4":
        _validate_public_m4a(payload)
    elif mime_type == "audio/ogg":
        _validate_public_ogg(payload)
    else:
        raise PublicAudioError("public audio MIME has no structural validator")


def _sanitize_audio_stream(payload: bytes, source_mime: str, output_mime: str) -> bytes:
    """Stream-copy one audio stream into a deterministic metadata-free container."""
    if not payload or len(payload) > MAX_AUDIO_SOURCE_BYTES:
        raise PublicAudioError("reviewed audio sanitization input exceeds its limit")
    if output_mime != _sanitized_output_mime(source_mime):
        raise PublicAudioError("reviewed audio sanitization has an invalid output container")
    source_extension = _MIME_EXTENSIONS[source_mime]
    output_extension = _MIME_EXTENSIONS[output_mime]
    output_format = {
        "audio/mpeg": "mp3",
        "audio/ogg": "ogg",
        "audio/wav": "wav",
        "audio/webm": "webm",
        "audio/mp4": "mp4",
    }[output_mime]
    format_options: list[str] = []
    format_option_candidates: list[list[str]]
    if output_mime == "audio/mpeg":
        # Source MP3s vary: some require a newly generated technical Xing frame
        # to preserve gapless decoding, while adding one to others changes the
        # decoded boundary samples. Try both deterministic metadata-free muxes
        # and accept only the first exact decoded-PCM match.
        format_option_candidates = [
            ["-id3v2_version", "0"],
            ["-id3v2_version", "0", "-write_xing", "0"],
        ]
    elif output_mime == "audio/ogg":
        # A fixed non-default serial proves that even an already-clean Ogg
        # source passed through this remux instead of being copied byte-for-byte.
        format_options = ["-serial_offset", "1"]
    elif output_mime == "audio/mp4":
        # Pin structural brands and atom placement; personal source tags remain removed.
        format_options = ["-movflags", "+faststart", "-brand", "isom"]
    if output_mime != "audio/mpeg":
        format_option_candidates = [format_options]
    with tempfile.TemporaryDirectory(prefix="rufous-audio-sanitize-") as temporary:
        root = Path(temporary)
        source = root / f"source.{source_extension}"
        output = root / f"audio.{output_extension}"
        source.write_bytes(payload)
        result: bytes | None = None
        for candidate_options in format_option_candidates:
            command = [
                "ffmpeg",
                "-nostdin",
                "-hide_banner",
                "-loglevel",
                "error",
                "-fflags",
                "+bitexact",
                "-i",
                str(source),
                "-map",
                "0:a:0",
                "-vn",
                "-sn",
                "-dn",
                "-map_metadata",
                "-1",
                "-map_metadata:s:a",
                "-1",
                "-map_chapters",
                "-1",
                "-c:a",
                "copy",
                "-fflags",
                "+bitexact",
                "-flags:a",
                "+bitexact",
                *candidate_options,
                "-f",
                output_format,
                "-y",
                str(output),
            ]
            try:
                completed = subprocess.run(
                    command,
                    check=False,
                    capture_output=True,
                    timeout=120,
                )
            except (OSError, subprocess.TimeoutExpired):
                raise PublicAudioError("reviewed audio sanitization could not run") from None
            if completed.returncode != 0 or not output.is_file():
                raise PublicAudioError("reviewed audio sanitization failed")
            candidate = output.read_bytes()
            if output_mime == "audio/mpeg":
                candidate = _finalize_public_mp3(candidate)
            elif output_mime == "audio/mp4":
                candidate = _neutralize_m4a_metadata_atoms(candidate)
            if output_mime != "audio/mpeg":
                result = candidate
                break
            try:
                _verify_audio_equivalence(payload, source_mime, candidate, output_mime)
            except PublicAudioError:
                continue
            result = candidate
            break
        if result is None:
            # Last resort for files whose existing technical Xing/LAME frame is
            # itself required for gapless PCM: remove only validated outer tag
            # structures and preserve the contiguous MPEG frames byte-for-byte.
            stripped = _strip_mp3_metadata(payload)
            _verify_audio_equivalence(payload, source_mime, stripped, output_mime)
            _probe_audio(stripped, output_mime)
            result = stripped
    if source_mime == "audio/webm" and output_mime == "audio/ogg":
        result = _apply_ogg_discard_padding(
            result,
            _source_discard_padding(payload, source_mime),
        )
    if not result or len(result) > MAX_AUDIO_OBJECT_BYTES:
        raise PublicAudioError("sanitized audio exceeds its public object limit")
    _validate_public_audio_structure(result, output_mime)
    return result


def _audio_stream_fingerprint(payload: bytes, mime_type: str) -> AudioStreamFingerprint:
    """Decode the first audio stream into canonical PCM and fingerprint its semantics."""
    extension = _MIME_EXTENSIONS.get(mime_type)
    if extension is None or not payload or len(payload) > MAX_AUDIO_SOURCE_BYTES:
        raise PublicAudioError("audio stream cannot be fingerprinted safely")
    with tempfile.TemporaryDirectory(prefix="rufous-audio-fingerprint-") as temporary:
        path = Path(temporary) / f"audio.{extension}"
        path.write_bytes(payload)
        probe_command = [
            "ffprobe",
            "-v",
            "error",
            "-select_streams",
            "a:0",
            "-show_entries",
            "stream=codec_name,sample_rate,channels,duration:format=duration",
            "-of",
            "json",
            str(path),
        ]
        hash_command = [
            "ffmpeg",
            "-nostdin",
            "-hide_banner",
            "-loglevel",
            "error",
            "-fflags",
            "+bitexact",
            "-i",
            str(path),
            "-map",
            "0:a:0",
            "-vn",
            "-sn",
            "-dn",
            "-map_metadata",
            "-1",
            "-c:a",
            "pcm_s32le",
            "-flags:a",
            "+bitexact",
            "-f",
            "hash",
            "-hash",
            "sha256",
            "-",
        ]
        try:
            probed = subprocess.run(
                probe_command,
                check=False,
                capture_output=True,
                timeout=30,
            )
            hashed = subprocess.run(
                hash_command,
                check=False,
                capture_output=True,
                timeout=120,
            )
        except (OSError, subprocess.TimeoutExpired):
            raise PublicAudioError("audio semantic fingerprinting could not run") from None
    if (
        probed.returncode != 0
        or hashed.returncode != 0
        or len(probed.stdout) > 1024 * 1024
        or len(hashed.stdout) > 1_024
    ):
        raise PublicAudioError("audio semantic fingerprinting failed")
    try:
        result: object = json.loads(probed.stdout)
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise PublicAudioError("audio semantic fingerprint metadata is invalid") from None
    if not isinstance(result, dict):
        raise PublicAudioError("audio semantic fingerprint metadata is invalid")
    streams = result.get("streams")
    metadata = result.get("format")
    if (
        not isinstance(streams, list)
        or len(streams) != 1
        or not isinstance(streams[0], dict)
        or not isinstance(metadata, dict)
    ):
        raise PublicAudioError("audio semantic fingerprint has no single selected stream")
    stream = streams[0]
    codec = stream.get("codec_name")
    sample_rate = stream.get("sample_rate")
    channels = stream.get("channels")
    duration_value = stream.get("duration", metadata.get("duration"))
    try:
        parsed_sample_rate = int(str(sample_rate))
        parsed_channels = int(str(channels))
        duration = float(str(duration_value))
    except (TypeError, ValueError):
        raise PublicAudioError("audio semantic fingerprint fields are invalid") from None
    digest_match = re.fullmatch(rb"SHA256=([a-f0-9]{64})\r?\n?", hashed.stdout)
    if (
        not isinstance(codec, str)
        or not codec
        or not 0 < parsed_sample_rate <= 768_000
        or not 0 < parsed_channels <= 64
        or not math.isfinite(duration)
        or not 0 < duration <= 3_600
        or digest_match is None
    ):
        raise PublicAudioError("audio semantic fingerprint fields are invalid")
    return AudioStreamFingerprint(
        codec=codec,
        sample_rate=parsed_sample_rate,
        channels=parsed_channels,
        duration_seconds=round(duration, 6),
        decoded_pcm_sha256=digest_match.group(1).decode("ascii"),
    )


def _verify_audio_equivalence(
    source_payload: bytes,
    source_mime: str,
    sanitized_payload: bytes,
    sanitized_mime: str,
) -> None:
    """Prove that sanitization changed only the container and metadata."""
    source = _audio_stream_fingerprint(source_payload, source_mime)
    sanitized = _audio_stream_fingerprint(sanitized_payload, sanitized_mime)
    if (
        source.codec != sanitized.codec
        or source.sample_rate != sanitized.sample_rate
        or source.channels != sanitized.channels
        or source.decoded_pcm_sha256 != sanitized.decoded_pcm_sha256
        or abs(source.duration_seconds - sanitized.duration_seconds) > DURATION_TOLERANCE_SECONDS
    ):
        raise PublicAudioError(
            "sanitized audio differs from the source codec, shape, duration, or decoded PCM"
        )


def _probe_audio(payload: bytes, mime_type: str) -> float:
    """Fail-closed inspect one sanitized audio payload with ffprobe.

    The returned duration is rounded to milliseconds for a stable committed
    value.  Subsequent acquisitions accept at most
    :data:`DURATION_TOLERANCE_SECONDS` of decoder/container variance.
    """
    extension = _MIME_EXTENSIONS.get(mime_type)
    format_codec_contract = _PUBLIC_AUDIO_FORMAT_CODECS.get(mime_type)
    if (
        extension is None
        or format_codec_contract is None
        or not payload
        or len(payload) > MAX_AUDIO_OBJECT_BYTES
    ):
        raise PublicAudioError("prepared audio cannot be probed safely")
    _validate_public_audio_structure(payload, mime_type)
    with tempfile.TemporaryDirectory(prefix="rufous-audio-probe-") as temporary:
        path = Path(temporary) / f"audio.{extension}"
        path.write_bytes(payload)
        command = [
            "ffprobe",
            "-v",
            "error",
            "-show_streams",
            "-show_format",
            "-show_chapters",
            "-show_programs",
            "-of",
            "json",
            str(path),
        ]
        try:
            completed = subprocess.run(
                command,
                check=False,
                capture_output=True,
                timeout=30,
            )
        except (OSError, subprocess.TimeoutExpired):
            raise PublicAudioError("prepared audio could not be decoded by ffprobe") from None
    if completed.returncode != 0 or len(completed.stdout) > 1024 * 1024:
        raise PublicAudioError("prepared audio could not be decoded by ffprobe")
    try:
        result: object = json.loads(completed.stdout)
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise PublicAudioError("ffprobe returned invalid audio metadata") from None
    if not isinstance(result, dict):
        raise PublicAudioError("ffprobe returned invalid audio metadata")
    streams = result.get("streams")
    metadata = result.get("format")
    chapters = result.get("chapters")
    programs = result.get("programs")
    stream_groups = result.get("stream_groups", [])
    if (
        not isinstance(streams, list)
        or len(streams) != 1
        or not isinstance(streams[0], dict)
        or streams[0].get("codec_type") != "audio"
        or not isinstance(metadata, dict)
        or metadata.get("nb_streams") != 1
        or metadata.get("nb_programs") not in {None, 0}
        or not isinstance(chapters, list)
        or chapters
        or (programs is not None and (not isinstance(programs, list) or programs))
        or not isinstance(stream_groups, list)
        or stream_groups
    ):
        raise PublicAudioError(
            "prepared object must contain exactly one audio stream and no chapters or programs"
        )
    disposition = streams[0].get("disposition")
    if isinstance(disposition, dict) and disposition.get("attached_pic") not in {None, 0}:
        raise PublicAudioError("prepared object contains a disallowed attached picture")
    side_data = streams[0].get("side_data_list", [])
    allowed_mp3_side_data = [{"side_data_type": "Replay Gain"}]
    if not isinstance(side_data, list) or (
        side_data and not (mime_type == "audio/mpeg" and side_data == allowed_mp3_side_data)
    ):
        raise PublicAudioError("prepared object contains disallowed stream side data")
    expected_format, allowed_codecs = format_codec_contract
    codec_name = streams[0].get("codec_name")
    sample_rate = streams[0].get("sample_rate")
    channels = streams[0].get("channels")
    try:
        parsed_sample_rate = int(str(sample_rate))
        parsed_channels = int(str(channels))
    except ValueError:
        raise PublicAudioError("prepared audio has invalid stream parameters") from None
    if (
        metadata.get("format_name") != expected_format
        or codec_name not in allowed_codecs
        or not 4_000 <= parsed_sample_rate <= 384_000
        or not 1 <= parsed_channels <= 8
    ):
        raise PublicAudioError("prepared audio format or codec is outside the public allowlist")
    format_tags = metadata.get("tags", {})
    stream_tags = streams[0].get("tags", {})
    allowed_format_tag_options: list[dict[str, str]] = [{}]
    allowed_stream_tag_options: list[dict[str, str]] = [{}]
    if mime_type == "audio/mp4":
        # These are fixed MP4 muxer structure, not copied source metadata.
        allowed_format_tag_options = [
            {
                "major_brand": "isom",
                "minor_version": "512",
                "compatible_brands": "isomiso2mp41",
            }
        ]
        allowed_stream_tag_options = [
            {
                "language": "und",
                "handler_name": "SoundHandler",
                "vendor_id": "[0][0][0][0]",
            }
        ]
    elif mime_type == "audio/mpeg":
        # Some MP3 streams cause the muxer's technical Xing frame to surface
        # as this fixed tag. It is generated by the sanitizer and contains no
        # copied source value; omitting the Xing frame changes decoded PCM.
        allowed_stream_tag_options.append({"encoder": "Lavf"})
        # This exact LAME marker lives in a technical Xing/LAME frame whose
        # removal changes decoded boundary samples for one reviewed source.
        allowed_stream_tag_options.append({"encoder": "LAME3.100"})
    elif mime_type == "audio/webm":
        # Kept for defensive compatibility even though WebM inputs publish as Ogg.
        allowed_format_tag_options = [{"encoder": "Lavf"}]
        duration_tag = stream_tags.get("DURATION") if isinstance(stream_tags, dict) else None
        if isinstance(duration_tag, str) and re.fullmatch(r"[0-9:.]+", duration_tag):
            allowed_stream_tag_options = [{"DURATION": duration_tag}]
    if (
        format_tags not in allowed_format_tag_options
        or stream_tags not in allowed_stream_tag_options
    ):
        raise PublicAudioError("prepared audio contains disallowed source metadata")
    duration_value = metadata.get("duration")
    if not isinstance(duration_value, str | int | float) or isinstance(duration_value, bool):
        raise PublicAudioError("prepared audio has no measurable duration")
    try:
        duration = float(duration_value)
    except (TypeError, ValueError):
        raise PublicAudioError("prepared audio has no measurable duration") from None
    if not math.isfinite(duration) or not 0 < duration <= 3_600:
        raise PublicAudioError("prepared audio duration exceeds its public safety limit")
    return round(duration, 3)


def _download_item(
    item: Mapping[str, Any],
    *,
    fetcher: AudioFetcher,
    sanitizer: AudioSanitizer,
    equivalence_checker: AudioEquivalenceChecker,
    probe: AudioProbe,
    require_expected: bool,
) -> tuple[bytes, str, int, float, str]:
    if item.get("transformation") != SANITIZATION_TRANSFORMATION:
        raise PublicAudioError("reviewed audio does not require the mandatory sanitization")
    maximum = MAX_AUDIO_SOURCE_BYTES
    downloaded = fetcher(str(item["original_url"]), maximum)
    provider = str(item["provider"])
    visited = (*downloaded.redirect_urls, downloaded.final_url)
    if any(not _valid_original_url(provider, url) for url in visited):
        raise PublicAudioError("upstream audio redirected outside its reviewed provider hosts")
    if not downloaded.payload or len(downloaded.payload) > maximum:
        raise PublicAudioError("upstream audio is empty or exceeds its download limit")
    detected_source = _detect_mime_type(downloaded.payload)
    if detected_source not in _MIME_EXTENSIONS or not _header_matches(
        downloaded.content_type, detected_source
    ):
        raise PublicAudioError("upstream audio MIME does not match its reviewed selection")
    expected_mime = _sanitized_output_mime(detected_source)
    reviewed_mime = item.get("expected_mime_type")
    if reviewed_mime is not None and reviewed_mime != expected_mime:
        raise PublicAudioError("sanitized audio MIME differs from its reviewed selection")
    payload = sanitizer(downloaded.payload, detected_source, expected_mime)
    if (
        not payload
        or len(payload) > MAX_AUDIO_OBJECT_BYTES
        or _detect_mime_type(payload) != expected_mime
    ):
        raise PublicAudioError("prepared audio does not match its reviewed output MIME")
    equivalence_checker(downloaded.payload, detected_source, payload, expected_mime)
    digest = hashlib.sha256(payload).hexdigest()
    size = len(payload)
    measured_duration = probe(payload, expected_mime)
    if not math.isfinite(measured_duration) or not 0 < measured_duration <= 3_600:
        raise PublicAudioError("prepared audio probe returned an unsafe duration")
    expected_sha = item.get("expected_sha256")
    expected_bytes = item.get("expected_bytes")
    if require_expected and (digest != expected_sha or size != expected_bytes):
        raise PublicAudioError("upstream audio bytes differ from the committed pin")
    if expected_sha is not None and (digest != expected_sha or size != expected_bytes):
        raise PublicAudioError("upstream audio bytes differ from the reviewed expectation")
    expected_duration = item.get("duration_seconds")
    if (require_expected or expected_sha is not None) and (
        not isinstance(expected_duration, int | float)
        or isinstance(expected_duration, bool)
        or abs(float(expected_duration) - measured_duration) > DURATION_TOLERANCE_SECONDS
    ):
        raise PublicAudioError("prepared audio duration differs from the committed pin")
    return payload, digest, size, measured_duration, expected_mime


def _public_item(item: Mapping[str, Any], *, sha256: str, size: int) -> dict[str, Any]:
    mime_type = str(item["expected_mime_type"])
    extension = _MIME_EXTENSIONS[mime_type]
    return {
        "species_code": item["species_code"],
        "common_name": item["common_name"],
        "scientific_name": item["scientific_name"],
        "provider": item["provider"],
        "provider_id": item["provider_id"],
        "source_url": item["source_url"],
        "creator": item["creator"],
        "license": item["license"],
        "license_url": item["license_url"],
        "original_url": item["original_url"],
        "url": f"{PUBLIC_AUDIO_BASE_URL}/{sha256[:2]}/{sha256}.{extension}",
        "sha256": sha256,
        "bytes": size,
        "mime_type": mime_type,
        "duration_seconds": item["duration_seconds"],
        "vocalization_type": item["vocalization_type"],
        "modification_notice": item["modification_notice"],
    }


def _pinned_selection_item(
    item: Mapping[str, Any], public_item: Mapping[str, Any]
) -> dict[str, Any]:
    return {
        **dict(item),
        "expected_sha256": public_item["sha256"],
        "expected_bytes": public_item["bytes"],
        "expected_mime_type": public_item["mime_type"],
        "duration_seconds": public_item["duration_seconds"],
    }


def _object_relative(item: Mapping[str, Any]) -> str:
    digest = str(item["sha256"])
    extension = _MIME_EXTENSIONS[str(item["mime_type"])]
    return f"{digest[:2]}/{digest}.{extension}"


def _atomic_write(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as temporary:
            temporary_path = Path(temporary.name)
            temporary.write(payload)
            temporary.flush()
            os.fsync(temporary.fileno())
        os.replace(temporary_path, path)
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)


def _capture_fingerprint(item: Mapping[str, Any]) -> str:
    payload = json.dumps(
        dict(item),
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _capture_identity(item: Mapping[str, Any]) -> dict[str, str]:
    return {
        "species_code": str(item["species_code"]),
        "provider": str(item["provider"]),
        "provider_id": str(item["provider_id"]),
    }


def _checkpoint_entry(
    selection_item: Mapping[str, Any], public_item: Mapping[str, Any]
) -> dict[str, Any]:
    return {
        "identity": _capture_identity(selection_item),
        "capture_fingerprint": _capture_fingerprint(selection_item),
        "public_item": dict(public_item),
    }


def _checkpoint_expected_public_item(
    selection_item: Mapping[str, Any], candidate: Mapping[str, Any]
) -> dict[str, Any]:
    digest = candidate.get("sha256")
    size = candidate.get("bytes")
    mime_type = candidate.get("mime_type")
    duration = candidate.get("duration_seconds")
    if (
        not isinstance(digest, str)
        or _SHA256.fullmatch(digest) is None
        or type(size) is not int
        or not 0 < size <= MAX_AUDIO_OBJECT_BYTES
        or mime_type not in _PUBLIC_AUDIO_MIME_TYPES
        or isinstance(duration, bool)
        or not isinstance(duration, int | float)
        or not math.isfinite(float(duration))
        or not 0 < float(duration) <= 3_600
    ):
        raise PublicAudioError("audio capture checkpoint contains an invalid object identity")
    comparison = dict(selection_item)
    is_pinned = comparison.get("expected_sha256") is not None
    if is_pinned and (
        comparison.get("expected_sha256") != digest
        or comparison.get("expected_bytes") != size
        or comparison.get("expected_mime_type") != mime_type
        or not isinstance(comparison.get("duration_seconds"), int | float)
        or isinstance(comparison.get("duration_seconds"), bool)
        or abs(float(comparison["duration_seconds"]) - float(duration)) > DURATION_TOLERANCE_SECONDS
    ):
        raise PublicAudioError("audio capture checkpoint differs from its committed pin")
    if comparison.get("expected_mime_type") is None:
        comparison["expected_mime_type"] = mime_type
    if not is_pinned:
        comparison["duration_seconds"] = duration
    return _public_item(comparison, sha256=digest, size=size)


def _load_capture_checkpoint(
    path: Path,
    selection_items: Mapping[str, Mapping[str, Any]],
) -> dict[str, dict[str, Any]]:
    if not path.exists():
        return {}
    payload, raw = _load_json(path, label="audio capture checkpoint")
    if (
        set(payload) != _CHECKPOINT_ROOT_KEYS
        or payload.get("schema_version") != AUDIO_SCHEMA_VERSION
        or payload.get("mode") != CHECKPOINT_MODE
        or not isinstance(payload.get("items"), list)
    ):
        raise PublicAudioError("audio capture checkpoint has an invalid contract")
    if raw != canonical_audio_manifest_json(payload):
        raise PublicAudioError("audio capture checkpoint must use canonical sorted JSON")
    completed: dict[str, dict[str, Any]] = {}
    previous_identity: tuple[str, str, str] | None = None
    for index, raw_entry in enumerate(payload["items"]):
        if not isinstance(raw_entry, dict) or set(raw_entry) != _CHECKPOINT_ITEM_KEYS:
            raise PublicAudioError(f"audio capture checkpoint item {index} is malformed")
        identity = raw_entry.get("identity")
        fingerprint = raw_entry.get("capture_fingerprint")
        candidate = raw_entry.get("public_item")
        if (
            not isinstance(identity, dict)
            or set(identity) != _CHECKPOINT_IDENTITY_KEYS
            or not isinstance(fingerprint, str)
            or _SHA256.fullmatch(fingerprint) is None
            or not isinstance(candidate, dict)
            or set(candidate) != _MANIFEST_ITEM_KEYS
        ):
            raise PublicAudioError(f"audio capture checkpoint item {index} is malformed")
        identity_tuple = (
            str(identity.get("species_code", "")),
            str(identity.get("provider", "")),
            str(identity.get("provider_id", "")),
        )
        if previous_identity is not None and identity_tuple <= previous_identity:
            raise PublicAudioError("audio capture checkpoint identities are not canonical")
        previous_identity = identity_tuple
        species_code = identity_tuple[0]
        selection_item = selection_items.get(species_code)
        if (
            selection_item is None
            or identity != _capture_identity(selection_item)
            or fingerprint != _capture_fingerprint(selection_item)
        ):
            raise PublicAudioError(
                f"audio capture checkpoint is stale or tampered for {species_code!r}"
            )
        expected = _checkpoint_expected_public_item(selection_item, candidate)
        if candidate != expected:
            raise PublicAudioError(
                f"audio capture checkpoint object is stale or tampered for {species_code!r}"
            )
        completed[species_code] = candidate
    return completed


def _write_capture_checkpoint(
    path: Path,
    selection_items: Mapping[str, Mapping[str, Any]],
    completed: Mapping[str, Mapping[str, Any]],
) -> None:
    entries = [
        _checkpoint_entry(selection_items[species_code], public_item)
        for species_code, public_item in completed.items()
    ]
    entries.sort(
        key=lambda entry: (
            str(entry["identity"]["species_code"]),
            str(entry["identity"]["provider"]),
            str(entry["identity"]["provider_id"]),
        )
    )
    payload = {
        "schema_version": AUDIO_SCHEMA_VERSION,
        "mode": CHECKPOINT_MODE,
        "items": entries,
    }
    _atomic_write(path, canonical_audio_manifest_json(payload))


def _verify_payload(payload: bytes, item: Mapping[str, Any], *, label: str) -> None:
    if (
        len(payload) != item["bytes"]
        or hashlib.sha256(payload).hexdigest() != item["sha256"]
        or _detect_mime_type(payload) != item["mime_type"]
    ):
        raise PublicAudioError(f"audio object bytes do not match the pin: {label}")


def _verify_payload_duration(
    payload: bytes,
    item: Mapping[str, Any],
    *,
    label: str,
    probe: AudioProbe,
) -> None:
    measured = probe(payload, str(item["mime_type"]))
    expected = float(item["duration_seconds"])
    if abs(measured - expected) > DURATION_TOLERANCE_SECONDS:
        raise PublicAudioError(f"audio object duration does not match the pin: {label}")


def _existing_cached_item(
    item: Mapping[str, Any],
    previous: Mapping[str, Any] | None,
) -> dict[str, Any] | None:
    if previous is None:
        return None
    previous_items = previous.get("items")
    if not isinstance(previous_items, list):
        return None
    for candidate in previous_items:
        if not isinstance(candidate, dict) or candidate.get("species_code") != item["species_code"]:
            continue
        comparison_item = dict(item)
        if comparison_item.get("duration_seconds") is None:
            comparison_item["duration_seconds"] = candidate.get("duration_seconds")
        if comparison_item.get("expected_mime_type") is None:
            comparison_item["expected_mime_type"] = candidate.get("mime_type")
        expected = _public_item(
            comparison_item,
            sha256=str(candidate.get("sha256", "")),
            size=int(candidate.get("bytes", 0)),
        )
        if candidate == expected:
            return candidate
    return None


def acquire_reviewed_audio(
    selection_path: Path,
    output_dir: Path,
    *,
    capture_unpinned: bool = False,
    pinned_selection_output: Path | None = None,
    generated_at: str | None = None,
    fetcher: AudioFetcher = _default_fetch_audio,
    sanitizer: AudioSanitizer = _sanitize_audio_stream,
    equivalence_checker: AudioEquivalenceChecker = _verify_audio_equivalence,
    probe: AudioProbe = _probe_audio,
) -> AudioAcquireResult:
    """Acquire exactly the reviewed rows and emit a canonical immutable pin."""
    selection = load_audio_selection(selection_path, require_pinned=not capture_unpinned)
    root = output_dir.resolve()
    if output_dir.is_symlink() or (root.exists() and not root.is_dir()):
        raise PublicAudioError("audio preparation output is unsafe")
    root.mkdir(parents=True, exist_ok=True)
    object_root = root / "objects"
    if object_root.is_symlink():
        raise PublicAudioError("audio preparation objects directory is unsafe")
    object_root.mkdir(parents=True, exist_ok=True)

    previous: dict[str, Any] | None = None
    manifest_path = root / "manifest.json"
    if manifest_path.exists():
        previous = load_pinned_audio_manifest(manifest_path)

    selection_items = {str(item["species_code"]): item for item in selection["items"]}
    checkpoint_path = root / "capture-checkpoint.json"
    checkpoint_items = _load_capture_checkpoint(checkpoint_path, selection_items)

    public_items: list[dict[str, Any]] = []
    pinned_items: list[dict[str, Any]] = []
    downloaded_count = 0
    reused_count = 0
    for raw_item in selection["items"]:
        item = dict(raw_item)
        cached: dict[str, Any] | None = None
        checkpoint_candidate = checkpoint_items.get(str(item["species_code"]))
        if checkpoint_candidate is not None:
            candidate_path = object_root / _object_relative(checkpoint_candidate)
            if candidate_path.is_symlink() or not candidate_path.is_file():
                raise PublicAudioError("audio capture checkpoint object is missing or unsafe")
            candidate_payload = candidate_path.read_bytes()
            _verify_payload(
                candidate_payload,
                checkpoint_candidate,
                label=str(candidate_path),
            )
            _verify_payload_duration(
                candidate_payload,
                checkpoint_candidate,
                label=str(candidate_path),
                probe=probe,
            )
            cached = checkpoint_candidate
        expected_sha = item.get("expected_sha256")
        if cached is None and isinstance(expected_sha, str):
            expected_public = _public_item(
                item,
                sha256=expected_sha,
                size=int(item["expected_bytes"]),
            )
            candidate_path = object_root / _object_relative(expected_public)
            if candidate_path.is_file() and not candidate_path.is_symlink():
                _verify_payload(
                    candidate_path.read_bytes(),
                    expected_public,
                    label=str(candidate_path),
                )
                _verify_payload_duration(
                    candidate_path.read_bytes(),
                    expected_public,
                    label=str(candidate_path),
                    probe=probe,
                )
                cached = expected_public
        elif cached is None and capture_unpinned:
            previous_candidate = _existing_cached_item(item, previous)
            if previous_candidate is not None:
                candidate_path = object_root / _object_relative(previous_candidate)
                if candidate_path.is_file() and not candidate_path.is_symlink():
                    _verify_payload(
                        candidate_path.read_bytes(), previous_candidate, label=str(candidate_path)
                    )
                    _verify_payload_duration(
                        candidate_path.read_bytes(),
                        previous_candidate,
                        label=str(candidate_path),
                        probe=probe,
                    )
                    cached = previous_candidate
        if cached is None:
            payload, digest, size, measured_duration, detected_mime = _download_item(
                item,
                fetcher=fetcher,
                sanitizer=sanitizer,
                equivalence_checker=equivalence_checker,
                probe=probe,
                require_expected=not capture_unpinned,
            )
            output_duration = (
                item["duration_seconds"]
                if item.get("expected_sha256") is not None
                else measured_duration
            )
            measured_item = {
                **item,
                "duration_seconds": output_duration,
                "expected_mime_type": detected_mime,
            }
            public_item = _public_item(measured_item, sha256=digest, size=size)
            target = object_root / _object_relative(public_item)
            if target.exists():
                if target.is_symlink() or not target.is_file():
                    raise PublicAudioError("content-addressed audio target is unsafe")
                _verify_payload(target.read_bytes(), public_item, label=str(target))
                _verify_payload_duration(
                    target.read_bytes(), public_item, label=str(target), probe=probe
                )
                reused_count += 1
            else:
                _atomic_write(target, payload)
                _verify_payload(target.read_bytes(), public_item, label=str(target))
                _verify_payload_duration(
                    target.read_bytes(), public_item, label=str(target), probe=probe
                )
                downloaded_count += 1
        else:
            public_item = cached
            reused_count += 1
        public_items.append(public_item)
        pinned_items.append(_pinned_selection_item(item, public_item))
        checkpoint_items[str(item["species_code"])] = public_item
        _write_capture_checkpoint(
            checkpoint_path,
            selection_items,
            checkpoint_items,
        )

    public_items.sort(key=lambda item: str(item["species_code"]))
    pinned_items.sort(key=lambda item: str(item["species_code"]))
    previous_items = previous.get("items") if previous is not None else None
    if generated_at is None and previous is not None and previous_items == public_items:
        generated = str(previous["generated_at"])
    else:
        generated = generated_at or datetime.now(UTC).isoformat().replace("+00:00", "Z")
    _aware_datetime(generated, label="audio manifest generated_at")
    manifest = {
        "schema_version": AUDIO_SCHEMA_VERSION,
        "generated_at": generated,
        "counts": {
            "items": len(public_items),
            "objects": len({str(item["sha256"]) for item in public_items}),
            "species": len({str(item["species_code"]) for item in public_items}),
        },
        "items": public_items,
    }
    _atomic_write(manifest_path, canonical_audio_manifest_json(manifest))
    load_pinned_audio_manifest(manifest_path)
    if pinned_selection_output is not None:
        pinned_selection = {
            "schema_version": AUDIO_SCHEMA_VERSION,
            "mode": SELECTION_MODE,
            "reviewed_at": selection["reviewed_at"],
            "reviewed_by": selection["reviewed_by"],
            "items": pinned_items,
        }
        _atomic_write(
            pinned_selection_output,
            canonical_audio_selection_json(pinned_selection),
        )
        load_audio_selection(pinned_selection_output, require_pinned=True)
        verify_selection_matches_manifest(pinned_selection_output, manifest_path)
    checkpoint_path.unlink(missing_ok=True)
    return AudioAcquireResult(
        status="prepared",
        items=len(public_items),
        downloaded_objects=downloaded_count,
        reused_objects=reused_count,
        total_bytes=sum(int(item["bytes"]) for item in public_items),
        output=str(root),
    )


def verify_selection_matches_manifest(selection_path: Path, manifest_path: Path) -> int:
    """Prove that a committed review ledger and public pin are identical."""
    selection = load_audio_selection(selection_path, require_pinned=True)
    manifest = load_pinned_audio_manifest(manifest_path)
    projected = [
        _public_item(
            item,
            sha256=str(item["expected_sha256"]),
            size=int(item["expected_bytes"]),
        )
        for item in selection["items"]
    ]
    if projected != manifest["items"]:
        raise PublicAudioError("pinned audio manifest differs from its reviewed selection")
    return len(projected)


def _verify_legacy_selection_matches_manifest(
    selection: Mapping[str, Any], manifest: Mapping[str, Any]
) -> None:
    projected = [
        _public_item(
            item,
            sha256=str(item["expected_sha256"]),
            size=int(item["expected_bytes"]),
        )
        for item in selection["items"]
    ]
    if projected != manifest["items"]:
        raise PublicAudioError("legacy audio preparation differs from its reviewed selection")


def sanitize_prepared_audio(
    selection_path: Path,
    source_dir: Path,
    output_dir: Path,
    pinned_selection_output: Path,
    *,
    generated_at: str | None = None,
    sanitizer: AudioSanitizer = _sanitize_audio_stream,
    equivalence_checker: AudioEquivalenceChecker = _verify_audio_equivalence,
    probe: AudioProbe = _probe_audio,
) -> AudioAcquireResult:
    """One-time local migration from exact old pins to sanitized immutable pins.

    This path never contacts a provider.  It first binds every old local object
    to the old committed selection and manifest, then remuxes every object and
    emits a new selection/manifest pair.  Ordinary deployment commands accept
    only the new sanitized contract.
    """
    legacy_selection = _load_legacy_audio_selection(selection_path)
    source_root = source_dir.resolve()
    output_root = output_dir.resolve()
    if (
        source_dir.is_symlink()
        or not source_root.is_dir()
        or output_dir.is_symlink()
        or source_root == output_root
        or (output_root.exists() and not output_root.is_dir())
    ):
        raise PublicAudioError("audio sanitization preparation path is unsafe")
    legacy_manifest = _load_legacy_pinned_audio_manifest(source_root / "manifest.json")
    _verify_legacy_selection_matches_manifest(legacy_selection, legacy_manifest)
    output_root.mkdir(parents=True, exist_ok=True)
    object_root = output_root / "objects"
    if object_root.is_symlink():
        raise PublicAudioError("sanitized audio objects directory is unsafe")
    object_root.mkdir(parents=True, exist_ok=True)

    selections = {str(item["species_code"]): dict(item) for item in legacy_selection["items"]}
    public_items: list[dict[str, Any]] = []
    pinned_items: list[dict[str, Any]] = []
    total_bytes = 0
    for old_item in legacy_manifest["items"]:
        source_relative = _object_relative(old_item)
        source_path = source_root / "objects" / source_relative
        if source_path.is_symlink() or not source_path.is_file():
            raise PublicAudioError(f"legacy audio object is missing or unsafe: {source_relative}")
        source_payload = source_path.read_bytes()
        _verify_payload(source_payload, old_item, label=source_relative)
        source_mime = str(old_item["mime_type"])
        output_mime = _sanitized_output_mime(source_mime)
        try:
            payload = sanitizer(source_payload, source_mime, output_mime)
            if (
                not payload
                or len(payload) > MAX_AUDIO_OBJECT_BYTES
                or _detect_mime_type(payload) != output_mime
            ):
                raise PublicAudioError("sanitized local audio has an invalid output container")
            equivalence_checker(source_payload, source_mime, payload, output_mime)
            measured_duration = probe(payload, output_mime)
        except PublicAudioError as exc:
            raise PublicAudioError(
                f"sanitization failed for {old_item['species_code']}: {exc}"
            ) from exc
        digest = hashlib.sha256(payload).hexdigest()
        size = len(payload)
        total_bytes += size
        if total_bytes > MAX_AUDIO_TOTAL_BYTES:
            raise PublicAudioError("sanitized audio exceeds its total byte limit")
        migrated_selection = {
            **selections[str(old_item["species_code"])],
            "expected_sha256": digest,
            "expected_bytes": size,
            "expected_mime_type": output_mime,
            "duration_seconds": measured_duration,
            "modification_notice": PUBLIC_AUDIO_SANITIZATION_NOTICE,
            "transformation": SANITIZATION_TRANSFORMATION,
        }
        public_item = _public_item(migrated_selection, sha256=digest, size=size)
        target = object_root / _object_relative(public_item)
        if target.exists():
            if target.is_symlink() or not target.is_file():
                raise PublicAudioError("content-addressed sanitized audio target is unsafe")
            _verify_payload(target.read_bytes(), public_item, label=str(target))
            _verify_payload_duration(
                target.read_bytes(), public_item, label=str(target), probe=probe
            )
        else:
            _atomic_write(target, payload)
        public_items.append(public_item)
        pinned_items.append(migrated_selection)

    public_items.sort(key=lambda item: str(item["species_code"]))
    pinned_items.sort(key=lambda item: str(item["species_code"]))
    generated = generated_at or datetime.now(UTC).isoformat().replace("+00:00", "Z")
    _aware_datetime(generated, label="audio manifest generated_at")
    manifest = {
        "schema_version": AUDIO_SCHEMA_VERSION,
        "generated_at": generated,
        "counts": {
            "items": len(public_items),
            "objects": len({str(item["sha256"]) for item in public_items}),
            "species": len({str(item["species_code"]) for item in public_items}),
        },
        "items": public_items,
    }
    pinned_selection = {
        "schema_version": AUDIO_SCHEMA_VERSION,
        "mode": SELECTION_MODE,
        "reviewed_at": legacy_selection["reviewed_at"],
        "reviewed_by": legacy_selection["reviewed_by"],
        "items": pinned_items,
    }
    manifest_path = output_root / "manifest.json"
    _atomic_write(manifest_path, canonical_audio_manifest_json(manifest))
    _atomic_write(
        pinned_selection_output,
        canonical_audio_selection_json(pinned_selection),
    )
    load_pinned_audio_manifest(manifest_path)
    load_audio_selection(pinned_selection_output, require_pinned=True)
    verify_selection_matches_manifest(pinned_selection_output, manifest_path)
    return AudioAcquireResult(
        status="sanitized",
        items=len(public_items),
        downloaded_objects=0,
        reused_objects=0,
        total_bytes=total_bytes,
        output=str(output_root),
    )


def scan_prepared_audio(
    source_dir: Path, *, probe: AudioProbe = _probe_audio
) -> list[SourceObject]:
    """Verify local prepared bytes and bind them to content-addressed paths."""
    root = source_dir.resolve()
    if source_dir.is_symlink() or not root.is_dir():
        raise PublicAudioError("prepared audio source is missing or unsafe")
    manifest = load_pinned_audio_manifest(root / "manifest.json")
    objects: list[SourceObject] = []
    total_bytes = 0
    for item in manifest["items"]:
        relative = _object_relative(item)
        path = root / "objects" / relative
        if path.is_symlink() or not path.is_file():
            raise PublicAudioError(f"prepared audio object is missing or unsafe: {relative}")
        payload = path.read_bytes()
        _verify_payload(payload, item, label=relative)
        _validate_public_audio_structure(payload, str(item["mime_type"]))
        _verify_payload_duration(payload, item, label=relative, probe=probe)
        total_bytes += len(payload)
        if total_bytes > MAX_AUDIO_TOTAL_BYTES:
            raise PublicAudioError("prepared audio exceeds its total byte limit")
        objects.append(
            SourceObject(
                path=path,
                relative_path=relative,
                size=len(payload),
                sha256=str(item["sha256"]),
                content_md5=base64.b64encode(
                    hashlib.md5(payload, usedforsecurity=False).digest()
                ).decode(),
                content_type=str(item["mime_type"]),
            )
        )
    if not objects or len(objects) > MAX_AUDIO_OBJECTS:
        raise PublicAudioError("prepared audio object count is empty or exceeds its limit")
    return objects


def scan_preverified_audio_bytes(source_dir: Path) -> list[SourceObject]:
    """Bind a previously verified artifact to its committed byte-level pins.

    This deliberately performs no media parsing or provider contact. It is
    reserved for the credentialed upload half of the two-job release workflow;
    the preceding unprivileged job runs :func:`scan_prepared_audio` in full.
    """
    root = source_dir.resolve()
    if source_dir.is_symlink() or not root.is_dir():
        raise PublicAudioError("prepared audio source is missing or unsafe")
    manifest = load_pinned_audio_manifest(root / "manifest.json")
    objects: list[SourceObject] = []
    total_bytes = 0
    for item in manifest["items"]:
        relative = _object_relative(item)
        path = root / "objects" / relative
        if path.is_symlink() or not path.is_file():
            raise PublicAudioError(f"prepared audio object is missing or unsafe: {relative}")
        payload = path.read_bytes()
        _verify_payload(payload, item, label=relative)
        total_bytes += len(payload)
        if total_bytes > MAX_AUDIO_TOTAL_BYTES:
            raise PublicAudioError("prepared audio exceeds its total byte limit")
        objects.append(
            SourceObject(
                path=path,
                relative_path=relative,
                size=len(payload),
                sha256=str(item["sha256"]),
                content_md5=base64.b64encode(
                    hashlib.md5(payload, usedforsecurity=False).digest()
                ).decode(),
                content_type=str(item["mime_type"]),
            )
        )
    if not objects or len(objects) > MAX_AUDIO_OBJECTS:
        raise PublicAudioError("prepared audio object count is empty or exceeds its limit")
    return objects


def verify_preverified_audio_package(source_dir: Path, selection_path: Path) -> dict[str, object]:
    """Recheck an already parsed package using only its exact committed byte pins."""
    verify_selection_matches_manifest(selection_path, source_dir / "manifest.json")
    objects = scan_preverified_audio_bytes(source_dir)
    return {
        "status": "verified",
        "objects": len(objects),
        "total_bytes": sum(item.size for item in objects),
    }


def _duration_metadata(value: object) -> str:
    if type(value) is int:
        return str(value)
    if not isinstance(value, float):
        raise PublicAudioError("pinned audio duration is not numeric")
    return format(float(value), ".15g")


def _object_metadata(item: Mapping[str, Any]) -> dict[str, str]:
    return {
        "sha256": str(item["sha256"]),
        "role": "audio",
        "schema": "rufous-audio-v1",
        "duration-seconds": _duration_metadata(item["duration_seconds"]),
    }


def _assert_existing_head(item: Mapping[str, Any], key: str, head: object) -> None:
    size = getattr(head, "size", None)
    content_type = getattr(head, "content_type", None)
    cache_control = getattr(head, "cache_control", None)
    metadata = getattr(head, "metadata", None)
    if (
        size != item["bytes"]
        or content_type != item["mime_type"]
        or cache_control != IMMUTABLE_CACHE_CONTROL
        or not isinstance(metadata, Mapping)
        or any(metadata.get(name) != value for name, value in _object_metadata(item).items())
    ):
        raise PublicAudioError(f"immutable audio collision at {key!r}")


def ensure_pinned_audio(
    selection_path: Path,
    manifest_path: Path,
    store: PrefixUsageStore,
    *,
    dry_run: bool = False,
    fetcher: AudioFetcher = _default_fetch_audio,
    sanitizer: AudioSanitizer = _sanitize_audio_stream,
    equivalence_checker: AudioEquivalenceChecker = _verify_audio_equivalence,
    probe: AudioProbe = _probe_audio,
) -> AudioPublishResult:
    """Ensure a reviewed pin exists remotely, fetching only absent objects."""
    verify_selection_matches_manifest(selection_path, manifest_path)
    manifest = load_pinned_audio_manifest(manifest_path)
    selection = load_audio_selection(selection_path, require_pinned=True)
    selections = {str(item["species_code"]): item for item in selection["items"]}
    pending: list[dict[str, Any]] = []
    reused = 0
    for item in manifest["items"]:
        key = f"{DEFAULT_AUDIO_PREFIX}/{_object_relative(item)}"
        head = store.head_object(key)
        if head is None:
            pending.append(item)
        else:
            _assert_existing_head(item, key, head)
            reused += 1
    usage = store.prefix_usage(
        DEFAULT_AUDIO_PREFIX,
        maximum_objects=MAX_AUDIO_PREFIX_OBJECTS,
        maximum_bytes=MAX_AUDIO_PREFIX_BYTES,
    )
    projected_count = usage.object_count + len(pending)
    projected_bytes = usage.total_bytes + sum(int(item["bytes"]) for item in pending)
    if projected_count > MAX_AUDIO_PREFIX_OBJECTS or projected_bytes > MAX_AUDIO_PREFIX_BYTES:
        raise PublicAudioError("audio namespace would exceed its cumulative safety limit")
    if not dry_run:
        for item in pending:
            selection_item = selections[str(item["species_code"])]
            payload, digest, size, measured_duration, detected_mime = _download_item(
                selection_item,
                fetcher=fetcher,
                sanitizer=sanitizer,
                equivalence_checker=equivalence_checker,
                probe=probe,
                require_expected=True,
            )
            if (
                digest != item["sha256"]
                or size != item["bytes"]
                or detected_mime != item["mime_type"]
                or abs(measured_duration - float(item["duration_seconds"]))
                > DURATION_TOLERANCE_SECONDS
            ):
                raise PublicAudioError("downloaded audio differs from the verified manifest")
            key = f"{DEFAULT_AUDIO_PREFIX}/{_object_relative(item)}"
            try:
                store.put_bytes(
                    key,
                    payload,
                    content_type=str(item["mime_type"]),
                    cache_control=IMMUTABLE_CACHE_CONTROL,
                    metadata=_object_metadata(item),
                    if_none_match=True,
                )
            except PublicReleaseError:
                raced = store.head_object(key)
                if raced is None:
                    raise
                _assert_existing_head(item, key, raced)
                continue
            created = store.head_object(key)
            if created is None:
                raise PublicAudioError(f"uploaded audio is not readable at {key!r}")
            _assert_existing_head(item, key, created)
    return AudioPublishResult(
        status="dry-run" if dry_run else "published",
        dry_run=dry_run,
        items=len(manifest["items"]),
        total_bytes=sum(int(item["bytes"]) for item in manifest["items"]),
        uploaded_objects=len(pending) if not dry_run else 0,
        reused_objects=reused,
        prefix=DEFAULT_AUDIO_PREFIX,
    )


def verify_pinned_audio_store(
    selection_path: Path,
    manifest_path: Path,
    store: PrefixUsageStore,
) -> AudioPublishResult:
    """HEAD-verify every pinned object without provider contact or writes."""
    verify_selection_matches_manifest(selection_path, manifest_path)
    manifest = load_pinned_audio_manifest(manifest_path)
    for item in manifest["items"]:
        key = f"{DEFAULT_AUDIO_PREFIX}/{_object_relative(item)}"
        head = store.head_object(key)
        if head is None:
            raise PublicAudioError(f"pinned audio object is missing from R2 at {key!r}")
        _assert_existing_head(item, key, head)
    return AudioPublishResult(
        status="verified",
        dry_run=False,
        items=len(manifest["items"]),
        total_bytes=sum(int(item["bytes"]) for item in manifest["items"]),
        uploaded_objects=0,
        reused_objects=len(manifest["items"]),
        prefix=DEFAULT_AUDIO_PREFIX,
    )


def publish_prepared_audio(
    source_dir: Path,
    selection_path: Path,
    store: PrefixUsageStore,
    *,
    dry_run: bool = False,
    probe: AudioProbe = _probe_audio,
    preverified: bool = False,
) -> AudioPublishResult:
    """Publish an already-local reviewed preparation without any source contact."""
    manifest_path = source_dir / "manifest.json"
    verify_selection_matches_manifest(selection_path, manifest_path)
    manifest = load_pinned_audio_manifest(manifest_path)
    scanned = (
        scan_preverified_audio_bytes(source_dir)
        if preverified
        else scan_prepared_audio(source_dir, probe=probe)
    )
    objects = {item.relative_path: item for item in scanned}
    pending: list[tuple[dict[str, Any], SourceObject, str]] = []
    reused = 0
    for item in manifest["items"]:
        relative = _object_relative(item)
        source = objects[relative]
        key = f"{DEFAULT_AUDIO_PREFIX}/{relative}"
        head = store.head_object(key)
        if head is None:
            pending.append((item, source, key))
        else:
            _assert_existing_head(item, key, head)
            reused += 1
    usage = store.prefix_usage(
        DEFAULT_AUDIO_PREFIX,
        maximum_objects=MAX_AUDIO_PREFIX_OBJECTS,
        maximum_bytes=MAX_AUDIO_PREFIX_BYTES,
    )
    if (
        usage.object_count + len(pending) > MAX_AUDIO_PREFIX_OBJECTS
        or usage.total_bytes + sum(source.size for _, source, _ in pending) > MAX_AUDIO_PREFIX_BYTES
    ):
        raise PublicAudioError("audio namespace would exceed its cumulative safety limit")
    if not dry_run:
        for item, source, key in pending:
            store.put_file(
                key,
                source,
                cache_control=IMMUTABLE_CACHE_CONTROL,
                metadata=_object_metadata(item),
                if_none_match=True,
            )
            created = store.head_object(key)
            if created is None:
                raise PublicAudioError(f"uploaded audio is not readable at {key!r}")
            _assert_existing_head(item, key, created)
    return AudioPublishResult(
        status="dry-run" if dry_run else "published",
        dry_run=dry_run,
        items=len(manifest["items"]),
        total_bytes=sum(int(item["bytes"]) for item in manifest["items"]),
        uploaded_objects=len(pending) if not dry_run else 0,
        reused_objects=reused,
        prefix=DEFAULT_AUDIO_PREFIX,
    )


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    acquire = subparsers.add_parser("acquire", help="capture reviewed upstream audio locally")
    acquire.add_argument("--selection", required=True, type=Path)
    acquire.add_argument("--output", required=True, type=Path)
    acquire.add_argument("--pinned-selection-output", type=Path)
    acquire.add_argument("--capture-unpinned", action="store_true")
    acquire.add_argument("--generated-at")

    sanitize_prepared = subparsers.add_parser(
        "sanitize-prepared",
        help="locally remux an exact legacy preparation and emit new sanitized pins",
    )
    sanitize_prepared.add_argument("--selection", required=True, type=Path)
    sanitize_prepared.add_argument("--source", required=True, type=Path)
    sanitize_prepared.add_argument("--output", required=True, type=Path)
    sanitize_prepared.add_argument("--pinned-selection-output", required=True, type=Path)
    sanitize_prepared.add_argument("--generated-at")

    verify = subparsers.add_parser("verify", help="verify a prepared pin and its local bytes")
    verify.add_argument("--source", required=True, type=Path)
    verify.add_argument("--selection", type=Path)

    verify_preverified = subparsers.add_parser(
        "verify-preverified",
        help="recheck cached prepared bytes without media parsing or provider contact",
    )
    verify_preverified.add_argument("--source", required=True, type=Path)
    verify_preverified.add_argument("--selection", required=True, type=Path)

    verify_pin = subparsers.add_parser(
        "verify-pin", help="verify the committed review and manifest without audio or network"
    )
    verify_pin.add_argument("--selection", required=True, type=Path)
    verify_pin.add_argument("--verify-manifest", required=True, type=Path)

    publish_local = subparsers.add_parser(
        "publish-local", help="copy a reviewed preparation into a local object-store root"
    )
    publish_local.add_argument("--source", required=True, type=Path)
    publish_local.add_argument("--selection", required=True, type=Path)
    publish_local.add_argument("--root", required=True, type=Path)
    publish_local.add_argument("--dry-run", action="store_true")

    publish_r2 = subparsers.add_parser(
        "publish-r2",
        help="upload already-sanitized local bytes without contacting any provider",
    )
    publish_r2.add_argument("--source", required=True, type=Path)
    publish_r2.add_argument("--selection", required=True, type=Path)
    publish_r2.add_argument("--dry-run", action="store_true")

    publish_preverified_r2 = subparsers.add_parser(
        "publish-preverified-r2",
        help="upload a verified workflow artifact without media parsing or provider contact",
    )
    publish_preverified_r2.add_argument("--source", required=True, type=Path)
    publish_preverified_r2.add_argument("--selection", required=True, type=Path)
    publish_preverified_r2.add_argument("--dry-run", action="store_true")

    ensure_r2 = subparsers.add_parser(
        "ensure-r2", help="create only missing objects from a committed reviewed pin"
    )
    ensure_r2.add_argument("--selection", required=True, type=Path)
    ensure_r2.add_argument("--verify-manifest", required=True, type=Path)
    ensure_r2.add_argument("--dry-run", action="store_true")

    verify_r2 = subparsers.add_parser(
        "verify-r2", help="HEAD-verify every committed object without provider contact"
    )
    verify_r2.add_argument("--selection", required=True, type=Path)
    verify_r2.add_argument("--verify-manifest", required=True, type=Path)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    result: AudioAcquireResult | AudioPublishResult | dict[str, object]
    try:
        if args.command == "acquire":
            result = acquire_reviewed_audio(
                args.selection,
                args.output,
                capture_unpinned=args.capture_unpinned,
                pinned_selection_output=args.pinned_selection_output,
                generated_at=args.generated_at,
            )
        elif args.command == "sanitize-prepared":
            result = sanitize_prepared_audio(
                args.selection,
                args.source,
                args.output,
                args.pinned_selection_output,
                generated_at=args.generated_at,
            )
        elif args.command == "verify":
            objects = scan_prepared_audio(args.source)
            if args.selection is not None:
                verify_selection_matches_manifest(args.selection, args.source / "manifest.json")
            result = {
                "status": "verified",
                "objects": len(objects),
                "total_bytes": sum(item.size for item in objects),
            }
        elif args.command == "verify-preverified":
            result = verify_preverified_audio_package(args.source, args.selection)
        elif args.command == "verify-pin":
            result = {
                "status": "verified",
                "items": verify_selection_matches_manifest(args.selection, args.verify_manifest),
            }
        elif args.command == "publish-local":
            result = publish_prepared_audio(
                args.source,
                args.selection,
                LocalReleaseStore(args.root),
                dry_run=args.dry_run,
            )
        elif args.command == "publish-r2":
            result = publish_prepared_audio(
                args.source,
                args.selection,
                R2ReleaseStore(R2Config.from_env()),
                dry_run=args.dry_run,
            )
        elif args.command == "publish-preverified-r2":
            result = publish_prepared_audio(
                args.source,
                args.selection,
                R2ReleaseStore(R2Config.from_env()),
                dry_run=args.dry_run,
                preverified=True,
            )
        elif args.command == "ensure-r2":
            result = ensure_pinned_audio(
                args.selection,
                args.verify_manifest,
                R2ReleaseStore(R2Config.from_env()),
                dry_run=args.dry_run,
            )
        else:
            result = verify_pinned_audio_store(
                args.selection,
                args.verify_manifest,
                R2ReleaseStore(R2Config.from_env()),
            )
    except (OSError, PublicAudioError, PublicReleaseError) as exc:
        print(f"Rufous audio release failed: {exc}", file=sys.stderr)
        return 1
    serializable = (
        asdict(result) if isinstance(result, AudioAcquireResult | AudioPublishResult) else result
    )
    print(json.dumps(serializable, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
