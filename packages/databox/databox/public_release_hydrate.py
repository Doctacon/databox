"""Hydrate a Pages build from the currently active immutable Rufous release."""

from __future__ import annotations

import argparse
import hashlib
import http.client
import json
import os
import re
import shutil
import ssl
import tempfile
import threading
import time
from collections.abc import Callable, Mapping, Sequence
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path, PurePosixPath
from typing import Any

from databox.public_release import (
    IMMUTABLE_CACHE_CONTROL,
    MAX_APPLICATION_MANIFEST_BYTES,
    MAX_POINTER_BYTES,
    MAX_PUBLIC_OBJECT_BYTES,
    MAX_PUBLIC_RELEASE_BYTES,
    RELEASE_SCHEMA_VERSION,
    PublicReleaseError,
)

APPROVED_PUBLIC_RELEASE_ROOT = "https://rufous-data.loughondata.com/rufous-public"
_APPROVED_HOST = "rufous-data.loughondata.com"
_POINTER_KEY = "rufous-public/manifest.json"
_SHA256 = re.compile(r"^[a-f0-9]{64}$")
_KEY_PART = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,254}$")
_MAX_FILES = 20_000
_MAX_WORKERS = 2
_MAX_FETCH_ATTEMPTS = 5
_MIN_REQUEST_INTERVAL_SECONDS = 0.25
_RETRYABLE_STATUSES = frozenset({408, 425, 429, 500, 502, 503, 504})

FetchObject = Callable[[str, int], bytes]


@dataclass(frozen=True)
class ReleaseFile:
    """One verified immutable JSON asset from a release manifest."""

    path: str
    key: str
    size: int
    sha256: str


@dataclass(frozen=True)
class HydratedRelease:
    """Identity of the production snapshot installed into a Pages build."""

    release_id: str
    data_version: str
    file_count: int
    total_bytes: int


class PublicHttpsFetcher:
    """Bounded read-only client for the one reviewed Rufous public origin."""

    def __init__(self, root: str = APPROVED_PUBLIC_RELEASE_ROOT, *, timeout: float = 20) -> None:
        if root != APPROVED_PUBLIC_RELEASE_ROOT:
            raise PublicReleaseError("Rufous hydration only permits the reviewed public origin")
        if timeout <= 0 or timeout > 120:
            raise PublicReleaseError("Rufous hydration timeout is outside the safe range")
        self._timeout = timeout
        self._context = ssl.create_default_context()
        self._request_lock = threading.Lock()
        self._last_request_at = 0.0

    def __call__(self, key: str, maximum: int) -> bytes:
        _validate_object_key(key)
        if maximum < 0 or maximum > MAX_PUBLIC_OBJECT_BYTES:
            raise PublicReleaseError("Rufous hydration requested an unsafe object size")
        for attempt in range(_MAX_FETCH_ATTEMPTS):
            retry_after = self._fetch_attempt(key, maximum, attempt)
            if isinstance(retry_after, bytes):
                return retry_after
            if attempt + 1 < _MAX_FETCH_ATTEMPTS:
                time.sleep(retry_after)
        raise PublicReleaseError(
            f"Rufous public object {key!r} remained unavailable after bounded retries"
        )

    def _fetch_attempt(self, key: str, maximum: int, attempt: int) -> bytes | float:
        self._wait_for_request_slot()
        connection = http.client.HTTPSConnection(
            _APPROVED_HOST,
            timeout=self._timeout,
            context=self._context,
        )
        try:
            connection.request(
                "GET",
                f"/{key}",
                headers={
                    "Accept": "application/json",
                    "Accept-Encoding": "identity",
                    "User-Agent": "Rufous-Pages-Hydrator/1",
                },
            )
            response = connection.getresponse()
            if response.status in _RETRYABLE_STATUSES:
                return _retry_delay(response.getheader("Retry-After"), attempt)
            if response.status != 200:
                raise PublicReleaseError(
                    f"Rufous public object {key!r} returned HTTP {response.status}"
                )
            if response.getheader("Location") is not None:
                raise PublicReleaseError(
                    f"Rufous public object {key!r} returned an unexpected redirect"
                )
            content_encoding = response.getheader("Content-Encoding")
            if content_encoding not in {None, "identity"}:
                raise PublicReleaseError(f"Rufous public object {key!r} returned encoded content")
            content_type = response.getheader("Content-Type", "").split(";", 1)[0].strip()
            if content_type.casefold() != "application/json":
                raise PublicReleaseError(
                    f"Rufous public object {key!r} returned an invalid content type"
                )
            declared = response.getheader("Content-Length")
            if declared is not None:
                try:
                    declared_size = int(declared)
                except ValueError:
                    raise PublicReleaseError(
                        f"Rufous public object {key!r} returned an invalid length"
                    ) from None
                if declared_size < 0 or declared_size > maximum:
                    raise PublicReleaseError(
                        f"Rufous public object {key!r} exceeds its verified size bound"
                    )
            payload = response.read(maximum + 1)
        except PublicReleaseError:
            raise
        except (OSError, http.client.HTTPException, ssl.SSLError):
            if attempt + 1 < _MAX_FETCH_ATTEMPTS:
                return _retry_delay(None, attempt)
            raise PublicReleaseError(f"Rufous public object {key!r} could not be read") from None
        finally:
            connection.close()
        if len(payload) > maximum:
            raise PublicReleaseError(
                f"Rufous public object {key!r} exceeds its verified size bound"
            )
        return payload

    def _wait_for_request_slot(self) -> None:
        with self._request_lock:
            wait = _MIN_REQUEST_INTERVAL_SECONDS - (time.monotonic() - self._last_request_at)
            if wait > 0:
                time.sleep(wait)
            self._last_request_at = time.monotonic()


def hydrate_active_public_release(
    site_root: Path,
    *,
    fetch: FetchObject | None = None,
    workers: int = _MAX_WORKERS,
) -> HydratedRelease:
    """Replace ``site_root/data`` with a fully verified active production snapshot."""

    site = site_root.resolve()
    if site_root.is_symlink() or not site.is_dir() or not (site / "index.html").is_file():
        raise PublicReleaseError("Rufous hydration requires an existing built static site")
    destination = site / "data"
    if destination.is_symlink():
        raise PublicReleaseError("Rufous hydration refuses a symlinked data destination")
    if workers < 1 or workers > _MAX_WORKERS:
        raise PublicReleaseError("Rufous hydration worker count is outside the safe range")

    reader = fetch or PublicHttpsFetcher()
    pointer_payload = reader(_POINTER_KEY, MAX_POINTER_BYTES)
    pointer = _validated_pointer(_json_object(pointer_payload, "release pointer"))
    release_payload = reader(pointer["release_manifest_key"], MAX_APPLICATION_MANIFEST_BYTES)
    if _sha256(release_payload) != pointer["release_manifest_sha256"]:
        raise PublicReleaseError("active Rufous release manifest failed SHA-256 verification")
    release, files = _validated_release_manifest(
        _json_object(release_payload, "release manifest"), pointer
    )

    staging_root = Path(tempfile.mkdtemp(prefix=".rufous-pages-data-", dir=site.parent))
    try:
        staging_data = staging_root / "data"
        staging_data.mkdir()
        with ThreadPoolExecutor(max_workers=min(workers, len(files))) as executor:
            futures = {
                executor.submit(_download_file, item, staging_root, reader): item for item in files
            }
            try:
                for future in as_completed(futures):
                    future.result()
            except Exception:
                for future in futures:
                    future.cancel()
                raise

        application_manifest = _json_object(
            (staging_root / "data" / "manifest.json").read_bytes(),
            "application manifest",
        )
        if (
            application_manifest.get("schema_version") != RELEASE_SCHEMA_VERSION
            or application_manifest.get("mode") != "public"
            or application_manifest.get("release_mode") != "production"
            or application_manifest.get("data_version") != pointer["data_version"]
        ):
            raise PublicReleaseError(
                "active Rufous application manifest is not a matching production snapshot"
            )

        final_pointer = _validated_pointer(
            _json_object(reader(_POINTER_KEY, MAX_POINTER_BYTES), "release pointer")
        )
        stable_fields = (
            "release_id",
            "data_version",
            "manifest_sha256",
            "release_manifest_sha256",
            "release_manifest_key",
            "asset_base_key",
            "file_count",
            "total_bytes",
        )
        if any(final_pointer[field] != pointer[field] for field in stable_fields):
            raise PublicReleaseError("active Rufous release changed during Pages hydration")

        _install_data_directory(staging_data, destination, site.parent)
    finally:
        shutil.rmtree(staging_root, ignore_errors=True)

    return HydratedRelease(
        release_id=release["release_id"],
        data_version=release["data_version"],
        file_count=release["file_count"],
        total_bytes=release["total_bytes"],
    )


def _download_file(item: ReleaseFile, staging_root: Path, fetch: FetchObject) -> None:
    payload = fetch(item.key, item.size)
    if len(payload) != item.size or _sha256(payload) != item.sha256:
        raise PublicReleaseError(f"Rufous release object {item.path!r} failed byte verification")
    _json_object(payload, f"release object {item.path!r}")
    target = staging_root.joinpath(*PurePosixPath(item.path).parts)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(payload)


def _install_data_directory(staging_data: Path, destination: Path, parent: Path) -> None:
    backup_root = Path(tempfile.mkdtemp(prefix=".rufous-pages-backup-", dir=parent))
    previous = backup_root / "previous-data"
    preserve_backup = False
    try:
        if destination.exists():
            if not destination.is_dir():
                raise PublicReleaseError("Rufous data destination is not a directory")
            try:
                os.replace(destination, previous)
            except OSError:
                raise PublicReleaseError(
                    "Rufous data destination could not be preserved before replacement"
                ) from None
        try:
            os.replace(staging_data, destination)
        except OSError:
            if previous.exists():
                try:
                    os.replace(previous, destination)
                except OSError:
                    preserve_backup = True
                    raise PublicReleaseError(
                        "Rufous data replacement and recovery failed; "
                        f"the previous data is preserved at {previous}"
                    ) from None
            raise PublicReleaseError("Rufous data destination could not be replaced") from None
    finally:
        if not preserve_backup:
            shutil.rmtree(backup_root, ignore_errors=True)


def _validated_pointer(value: Mapping[str, Any]) -> dict[str, Any]:
    required = {
        "schema_version": int,
        "mode": str,
        "release_id": str,
        "data_version": str,
        "published_at": str,
        "manifest_path": str,
        "manifest_sha256": str,
        "release_manifest_sha256": str,
        "release_manifest_key": str,
        "asset_base_key": str,
        "file_count": int,
        "total_bytes": int,
        "previous_releases": list,
    }
    for field, expected in required.items():
        if type(value.get(field)) is not expected:
            raise PublicReleaseError(f"active Rufous release pointer has an invalid {field!r}")
    if (
        value["schema_version"] != RELEASE_SCHEMA_VERSION
        or value["mode"] != "public-release-pointer"
    ):
        raise PublicReleaseError("active Rufous release pointer uses an unsupported contract")
    for field in ("release_id", "data_version", "manifest_sha256", "release_manifest_sha256"):
        if not _SHA256.fullmatch(value[field]):
            raise PublicReleaseError(f"active Rufous release pointer has an invalid {field!r}")
    try:
        timestamp = datetime.fromisoformat(value["published_at"].replace("Z", "+00:00"))
    except ValueError:
        raise PublicReleaseError("active Rufous release pointer has an invalid timestamp") from None
    if timestamp.tzinfo is None:
        raise PublicReleaseError("active Rufous release pointer timestamp lacks a timezone")
    if len(value["previous_releases"]) > 100:
        raise PublicReleaseError("active Rufous release pointer contains too much history")
    if (
        value["file_count"] < 1
        or value["file_count"] > _MAX_FILES
        or value["total_bytes"] < 1
        or value["total_bytes"] > MAX_PUBLIC_RELEASE_BYTES
    ):
        raise PublicReleaseError("active Rufous release pointer exceeds Pages limits")
    release_id = value["release_id"]
    asset_base = f"rufous-public/releases/{release_id}/objects"
    if (
        value["asset_base_key"] != asset_base
        or value["manifest_path"] != f"{asset_base}/data/manifest.json"
        or value["release_manifest_key"] != f"rufous-public/releases/{release_id}/release.json"
    ):
        raise PublicReleaseError("active Rufous release pointer contains an unsafe object path")
    for field in ("manifest_path", "release_manifest_key", "asset_base_key"):
        _validate_object_key(value[field])
    return dict(value)


def _validated_release_manifest(
    value: Mapping[str, Any], pointer: Mapping[str, Any]
) -> tuple[dict[str, Any], tuple[ReleaseFile, ...]]:
    identity_fields = (
        "release_id",
        "data_version",
        "manifest_path",
        "manifest_sha256",
        "asset_base_key",
        "file_count",
        "total_bytes",
    )
    if value.get("schema_version") != RELEASE_SCHEMA_VERSION or any(
        value.get(field) != pointer[field] for field in identity_fields
    ):
        raise PublicReleaseError("active Rufous release manifest disagrees with its pointer")
    raw_files = value.get("files")
    if not isinstance(raw_files, list) or len(raw_files) != pointer["file_count"]:
        raise PublicReleaseError("active Rufous release manifest has an invalid file index")

    files: list[ReleaseFile] = []
    seen: set[str] = set()
    total_bytes = 0
    manifest_seen = False
    for raw in raw_files:
        if not isinstance(raw, dict) or set(raw) != {
            "path",
            "key",
            "bytes",
            "sha256",
            "content_type",
            "cache_control",
        }:
            raise PublicReleaseError("active Rufous release manifest has invalid file metadata")
        path = raw["path"]
        key = raw["key"]
        size = raw["bytes"]
        sha256 = raw["sha256"]
        if (
            not isinstance(path, str)
            or not isinstance(key, str)
            or type(size) is not int
            or not isinstance(sha256, str)
            or size < 1
            or size > MAX_PUBLIC_OBJECT_BYTES
            or not _SHA256.fullmatch(sha256)
            or raw["content_type"] != "application/json; charset=utf-8"
            or raw["cache_control"] != IMMUTABLE_CACHE_CONTROL
        ):
            raise PublicReleaseError("active Rufous release manifest has invalid file metadata")
        _validate_data_path(path)
        expected_key = f"{pointer['asset_base_key']}/{path}"
        if key != expected_key:
            raise PublicReleaseError("active Rufous release file escaped its immutable prefix")
        _validate_object_key(key)
        if path in seen:
            raise PublicReleaseError("active Rufous release manifest contains a duplicate path")
        seen.add(path)
        total_bytes += size
        if total_bytes > MAX_PUBLIC_RELEASE_BYTES:
            raise PublicReleaseError("active Rufous release exceeds the total byte limit")
        if path == "data/manifest.json":
            manifest_seen = True
            if sha256 != pointer["manifest_sha256"]:
                raise PublicReleaseError("application manifest hash disagrees with release pointer")
        files.append(ReleaseFile(path=path, key=key, size=size, sha256=sha256))
    if not manifest_seen or total_bytes != pointer["total_bytes"]:
        raise PublicReleaseError("active Rufous release manifest failed completeness checks")
    if _release_id(files) != pointer["release_id"]:
        raise PublicReleaseError("active Rufous release identity failed verification")
    return dict(value), tuple(files)


def _validate_data_path(path: str) -> None:
    pure = PurePosixPath(path)
    if (
        path.startswith("/")
        or len(path) > 512
        or pure.as_posix() != path
        or len(pure.parts) < 2
        or pure.parts[0] != "data"
        or pure.suffix.casefold() != ".json"
        or any(part in {"", ".", ".."} or not _KEY_PART.fullmatch(part) for part in pure.parts)
    ):
        raise PublicReleaseError(f"active Rufous release contains unsafe data path {path!r}")


def _validate_object_key(key: str) -> None:
    pure = PurePosixPath(key)
    if (
        key.startswith("/")
        or len(key) > 1024
        or pure.as_posix() != key
        or any(part in {"", ".", ".."} or not _KEY_PART.fullmatch(part) for part in pure.parts)
    ):
        raise PublicReleaseError("Rufous public object key is unsafe")


def _json_object(payload: bytes, label: str) -> dict[str, Any]:
    try:
        value = json.loads(payload.decode("utf-8", errors="strict"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise PublicReleaseError(f"{label} is not valid UTF-8 JSON") from None
    if not isinstance(value, dict):
        raise PublicReleaseError(f"{label} must be a JSON object")
    return value


def _release_id(files: Sequence[ReleaseFile]) -> str:
    digest = hashlib.sha256(b"rufous-public-release-v1\0")
    for item in sorted(files, key=lambda candidate: candidate.path):
        digest.update(item.path.encode("ascii"))
        digest.update(b"\0")
        digest.update(str(item.size).encode("ascii"))
        digest.update(b"\0")
        digest.update(bytes.fromhex(item.sha256))
    return digest.hexdigest()


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _retry_delay(value: str | None, attempt: int) -> float:
    if value is not None:
        try:
            seconds = int(value)
        except ValueError:
            pass
        else:
            if 1 <= seconds <= 60:
                return float(seconds)
    return min(0.5 * (2**attempt), 8.0)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Hydrate a built Pages site from the active immutable Rufous release."
    )
    parser.add_argument("site", type=Path, help="Built static site root containing index.html")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        result = hydrate_active_public_release(args.site)
    except PublicReleaseError as exc:
        print(f"Rufous Pages hydration failed: {exc}")
        return 1
    print(
        "hydrated active Rufous release "
        f"{result.release_id} ({result.file_count} files, {result.total_bytes} bytes)"
    )
    return 0
