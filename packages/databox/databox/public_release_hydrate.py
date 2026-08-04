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

from databox.public_export import PublicExportError, semantic_data_version
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
APPROVED_PAGES_SNAPSHOT_ROOT = "https://rufous.pages.dev/data"
_APPROVED_HOST = "rufous-data.loughondata.com"
_PAGES_HOST = "rufous.pages.dev"
_POINTER_KEY = "rufous-public/manifest.json"
_PAGES_MANIFEST_KEY = "data/manifest.json"
_SHA256 = re.compile(r"^[a-f0-9]{64}$")
_KEY_PART = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,254}$")
_SPECIES_CODE = re.compile(r"^[a-z0-9][a-z0-9-]{0,31}$")
_CELL_ID = re.compile(r"^n(?:3[1-7])w(?:11[0-5])$")
_PLACE_PREFIX = re.compile(r"^(?:[a-z0-9]{2}|[a-z0-9]_|__)$")
_MAX_FILES = 20_000
_MAX_WORKERS = 2
_MAX_FETCH_ATTEMPTS = 5
_MIN_REQUEST_INTERVAL_SECONDS = 0.25
_RETRYABLE_STATUSES = frozenset({408, 425, 429, 500, 502, 503, 504})
_APPLICATION_MANIFEST_KEYS = frozenset(
    {
        "schema_version",
        "mode",
        "release_mode",
        "generated_at",
        "data_version",
        "region",
        "species",
        "cells",
        "place_prefixes",
        "attribution_path",
        "source_policy",
        "license_policy",
        "counts",
    }
)
_APPLICATION_COUNT_KEYS = frozenset(
    {
        "species",
        "observations",
        "places",
        "attribution_items",
        "media_items",
        "species_with_media",
    }
)
_ARIZONA_REGION = {
    "code": "US-AZ",
    "name": "Arizona",
    "bounds": {"west": -114.82, "south": 31.33, "east": -109.04, "north": 37.01},
}

FetchObject = Callable[[str, int], bytes]


class PublicReleaseUnavailableError(PublicReleaseError):
    """The reviewed public origin could not serve a requested object."""


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


@dataclass(frozen=True)
class SnapshotReference:
    """One path and cardinality pinned by a Pages application manifest."""

    path: str
    kind: str
    identity: str | None
    count: int | None


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

    @property
    def _host(self) -> str:
        return _APPROVED_HOST

    def _validate_fetch_key(self, key: str) -> None:
        _validate_object_key(key)

    def __call__(self, key: str, maximum: int) -> bytes:
        self._validate_fetch_key(key)
        if maximum < 0 or maximum > MAX_PUBLIC_OBJECT_BYTES:
            raise PublicReleaseError("Rufous hydration requested an unsafe object size")
        for attempt in range(_MAX_FETCH_ATTEMPTS):
            retry_after = self._fetch_attempt(key, maximum, attempt)
            if isinstance(retry_after, bytes):
                return retry_after
            if attempt + 1 < _MAX_FETCH_ATTEMPTS:
                time.sleep(retry_after)
        raise PublicReleaseUnavailableError(
            f"Rufous public object {key!r} remained unavailable after bounded retries"
        )

    def _fetch_attempt(self, key: str, maximum: int, attempt: int) -> bytes | float:
        self._wait_for_request_slot()
        connection = http.client.HTTPSConnection(
            self._host,
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
            if response.status in {401, 403}:
                raise PublicReleaseUnavailableError(
                    f"Rufous public object {key!r} is unavailable (HTTP {response.status})"
                )
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
            raise PublicReleaseUnavailableError(
                f"Rufous public object {key!r} could not be read"
            ) from None
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


class PagesSnapshotHttpsFetcher(PublicHttpsFetcher):
    """Bounded read-only client for the fixed Rufous Pages snapshot origin."""

    def __init__(self, root: str = APPROVED_PAGES_SNAPSHOT_ROOT, *, timeout: float = 20) -> None:
        if root != APPROVED_PAGES_SNAPSHOT_ROOT:
            raise PublicReleaseError("Rufous snapshot hydration only permits the reviewed origin")
        if timeout <= 0 or timeout > 120:
            raise PublicReleaseError("Rufous hydration timeout is outside the safe range")
        self._timeout = timeout
        self._context = ssl.create_default_context()
        self._request_lock = threading.Lock()
        self._last_request_at = 0.0

    @property
    def _host(self) -> str:
        return _PAGES_HOST

    def _validate_fetch_key(self, key: str) -> None:
        _validate_data_path(key)


def hydrate_active_public_release(
    site_root: Path,
    *,
    fetch: FetchObject | None = None,
    snapshot_fetch: FetchObject | None = None,
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
    try:
        pointer_payload = reader(_POINTER_KEY, MAX_POINTER_BYTES)
    except PublicReleaseUnavailableError:
        snapshot_reader = snapshot_fetch or PagesSnapshotHttpsFetcher()
        return _hydrate_pages_snapshot(site, destination, snapshot_reader, workers)
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


def _hydrate_pages_snapshot(
    site: Path,
    destination: Path,
    fetch: FetchObject,
    workers: int,
) -> HydratedRelease:
    """Hydrate the last deployed Pages snapshot when the R2 pointer is unreachable."""

    manifest_payload = fetch(_PAGES_MANIFEST_KEY, MAX_APPLICATION_MANIFEST_BYTES)
    if not manifest_payload:
        raise PublicReleaseError("deployed Rufous Pages manifest is empty")
    manifest = _json_object(manifest_payload, "deployed Pages application manifest")
    references = _validated_pages_snapshot_manifest(manifest)

    staging_root = Path(tempfile.mkdtemp(prefix=".rufous-pages-data-", dir=site.parent))
    try:
        staging_data = staging_root / "data"
        staging_data.mkdir()
        manifest_target = staging_root / _PAGES_MANIFEST_KEY
        manifest_target.write_bytes(manifest_payload)
        files = [
            ReleaseFile(
                path=_PAGES_MANIFEST_KEY,
                key=_PAGES_MANIFEST_KEY,
                size=len(manifest_payload),
                sha256=_sha256(manifest_payload),
            )
        ]
        assets: dict[str, object] = {_PAGES_MANIFEST_KEY: manifest}
        total_bytes = len(manifest_payload)
        with ThreadPoolExecutor(max_workers=min(workers, len(references))) as executor:
            futures = {
                executor.submit(_download_snapshot_file, reference, staging_root, fetch): reference
                for reference in references
            }
            try:
                for future in as_completed(futures):
                    item, payload = future.result()
                    files.append(item)
                    assets[item.path] = payload
                    total_bytes += item.size
                    if total_bytes > MAX_PUBLIC_RELEASE_BYTES:
                        raise PublicReleaseError(
                            "deployed Rufous Pages snapshot exceeds the total byte limit"
                        )
            except Exception:
                for future in futures:
                    future.cancel()
                raise

        try:
            computed_data_version = semantic_data_version(assets)
        except PublicExportError as exc:
            raise PublicReleaseError(
                f"deployed Rufous Pages snapshot has an invalid data identity: {exc}"
            ) from None
        if computed_data_version != manifest["data_version"]:
            raise PublicReleaseError(
                "deployed Rufous Pages snapshot does not match its data version"
            )

        final_manifest_payload = fetch(_PAGES_MANIFEST_KEY, MAX_APPLICATION_MANIFEST_BYTES)
        if final_manifest_payload != manifest_payload:
            raise PublicReleaseError("deployed Rufous Pages snapshot changed during hydration")

        _install_data_directory(staging_data, destination, site.parent)
    finally:
        shutil.rmtree(staging_root, ignore_errors=True)

    return HydratedRelease(
        release_id=_release_id(files),
        data_version=manifest["data_version"],
        file_count=len(files),
        total_bytes=total_bytes,
    )


def _download_snapshot_file(
    reference: SnapshotReference,
    staging_root: Path,
    fetch: FetchObject,
) -> tuple[ReleaseFile, dict[str, Any]]:
    payload = fetch(reference.path, MAX_PUBLIC_OBJECT_BYTES)
    if not payload or len(payload) > MAX_PUBLIC_OBJECT_BYTES:
        raise PublicReleaseError(
            f"deployed Rufous Pages object {reference.path!r} has an unsafe size"
        )
    value = _json_object(payload, f"deployed Pages object {reference.path!r}")
    _validate_snapshot_object(value, reference)
    target = staging_root.joinpath(*PurePosixPath(reference.path).parts)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(payload)
    return (
        ReleaseFile(
            path=reference.path,
            key=reference.path,
            size=len(payload),
            sha256=_sha256(payload),
        ),
        value,
    )


def _validated_pages_snapshot_manifest(
    value: Mapping[str, Any],
) -> tuple[SnapshotReference, ...]:
    if (
        set(value) != _APPLICATION_MANIFEST_KEYS
        or type(value.get("schema_version")) is not int
        or value.get("schema_version") != RELEASE_SCHEMA_VERSION
        or value.get("mode") != "public"
        or value.get("release_mode") != "production"
        or value.get("region") != _ARIZONA_REGION
    ):
        raise PublicReleaseError("deployed Rufous Pages manifest is not a production snapshot")
    data_version = value.get("data_version")
    if not isinstance(data_version, str) or not _SHA256.fullmatch(data_version):
        raise PublicReleaseError("deployed Rufous Pages manifest has an invalid data version")
    generated_at = value.get("generated_at")
    if not isinstance(generated_at, str):
        raise PublicReleaseError("deployed Rufous Pages manifest has an invalid timestamp")
    try:
        timestamp = datetime.fromisoformat(generated_at.replace("Z", "+00:00"))
    except ValueError:
        raise PublicReleaseError(
            "deployed Rufous Pages manifest has an invalid timestamp"
        ) from None
    if timestamp.tzinfo is None:
        raise PublicReleaseError("deployed Rufous Pages manifest timestamp lacks a timezone")
    source_policy = value.get("source_policy")
    if (
        not isinstance(source_policy, dict)
        or source_policy.get("direct_ebird") != "excluded"
        or source_policy.get("occurrence_source") != "gbif"
    ):
        raise PublicReleaseError("deployed Rufous Pages manifest violates the source boundary")
    license_policy = value.get("license_policy")
    if (
        not isinstance(license_policy, dict)
        or type(license_policy.get("version")) is not int
        or license_policy.get("version") != 1
    ):
        raise PublicReleaseError("deployed Rufous Pages manifest lacks the license policy")
    counts = value.get("counts")
    if (
        not isinstance(counts, dict)
        or set(counts) != _APPLICATION_COUNT_KEYS
        or any(type(counts[field]) is not int or counts[field] < 0 for field in counts)
    ):
        raise PublicReleaseError("deployed Rufous Pages manifest has invalid counts")
    if value.get("attribution_path") != "/data/attribution.json":
        raise PublicReleaseError("deployed Rufous Pages manifest has an invalid attribution path")

    references = [
        SnapshotReference(
            path="data/attribution.json",
            kind="attribution",
            identity=None,
            count=counts["attribution_items"],
        )
    ]
    seen = {_PAGES_MANIFEST_KEY, "data/attribution.json"}

    raw_species = value.get("species")
    if not isinstance(raw_species, list) or len(raw_species) != counts["species"]:
        raise PublicReleaseError("deployed Rufous Pages manifest has an invalid species index")
    species_codes: list[str] = []
    media_items = 0
    species_with_media = 0
    for row in raw_species:
        if not isinstance(row, dict):
            raise PublicReleaseError("deployed Rufous Pages manifest has a malformed species item")
        code = row.get("species_code")
        photo_count = row.get("photo_count")
        if (
            not isinstance(code, str)
            or not _SPECIES_CODE.fullmatch(code)
            or type(photo_count) is not int
            or photo_count < 0
        ):
            raise PublicReleaseError("deployed Rufous Pages manifest has a malformed species item")
        path = f"data/species/{code}.json"
        if row.get("profile_path") != f"/{path}" or path in seen:
            raise PublicReleaseError("deployed Rufous Pages manifest has an unsafe species path")
        seen.add(path)
        species_codes.append(code)
        media_items += photo_count
        species_with_media += int(photo_count > 0)
        references.append(SnapshotReference(path=path, kind="species", identity=code, count=None))
    if species_codes != sorted(species_codes) or (
        media_items != counts["media_items"] or species_with_media != counts["species_with_media"]
    ):
        raise PublicReleaseError("deployed Rufous Pages manifest has inconsistent species counts")

    raw_cells = value.get("cells")
    if not isinstance(raw_cells, list):
        raise PublicReleaseError("deployed Rufous Pages manifest has an invalid cell index")
    cell_ids: list[str] = []
    observation_count = 0
    for row in raw_cells:
        if not isinstance(row, dict):
            raise PublicReleaseError("deployed Rufous Pages manifest has a malformed cell item")
        cell_id = row.get("cell_id")
        count = row.get("observation_count")
        if (
            not isinstance(cell_id, str)
            or not _CELL_ID.fullmatch(cell_id)
            or type(count) is not int
            or count < 1
        ):
            raise PublicReleaseError("deployed Rufous Pages manifest has a malformed cell item")
        path = f"data/cells/{cell_id}.json"
        if row.get("path") != f"/{path}" or path in seen:
            raise PublicReleaseError("deployed Rufous Pages manifest has an unsafe cell path")
        seen.add(path)
        cell_ids.append(cell_id)
        observation_count += count
        references.append(SnapshotReference(path=path, kind="cell", identity=cell_id, count=count))
    if cell_ids != sorted(cell_ids) or observation_count != counts["observations"]:
        raise PublicReleaseError("deployed Rufous Pages manifest has inconsistent cell counts")

    raw_prefixes = value.get("place_prefixes")
    if not isinstance(raw_prefixes, list):
        raise PublicReleaseError("deployed Rufous Pages manifest has an invalid place index")
    prefixes: list[str] = []
    place_count = 0
    for row in raw_prefixes:
        if not isinstance(row, dict):
            raise PublicReleaseError("deployed Rufous Pages manifest has a malformed place item")
        prefix = row.get("prefix")
        count = row.get("count")
        if (
            not isinstance(prefix, str)
            or not _PLACE_PREFIX.fullmatch(prefix)
            or type(count) is not int
            or count < 1
        ):
            raise PublicReleaseError("deployed Rufous Pages manifest has a malformed place item")
        path = f"data/places/{prefix}.json"
        if row.get("path") != f"/{path}" or path in seen:
            raise PublicReleaseError("deployed Rufous Pages manifest has an unsafe place path")
        seen.add(path)
        prefixes.append(prefix)
        place_count += count
        references.append(SnapshotReference(path=path, kind="place", identity=prefix, count=count))
    if prefixes != sorted(prefixes) or place_count != counts["places"]:
        raise PublicReleaseError("deployed Rufous Pages manifest has inconsistent place counts")
    if len(seen) > _MAX_FILES:
        raise PublicReleaseError("deployed Rufous Pages snapshot exceeds the file-count limit")
    return tuple(references)


def _validate_snapshot_object(value: Mapping[str, Any], reference: SnapshotReference) -> None:
    if (
        type(value.get("schema_version")) is not int
        or value.get("schema_version") != RELEASE_SCHEMA_VERSION
    ):
        raise PublicReleaseError(f"deployed Pages object {reference.path!r} has an invalid schema")
    contracts = {
        "attribution": (None, None, "items"),
        "species": ("species_code", reference.identity, None),
        "cell": ("cell_id", reference.identity, "observations"),
        "place": ("prefix", reference.identity, "places"),
    }
    identity_field, expected_identity, collection_field = contracts[reference.kind]
    if identity_field is not None and value.get(identity_field) != expected_identity:
        raise PublicReleaseError(
            f"deployed Pages object {reference.path!r} disagrees with its manifest"
        )
    if collection_field is not None:
        collection = value.get(collection_field)
        if not isinstance(collection, list) or len(collection) != reference.count:
            raise PublicReleaseError(
                f"deployed Pages object {reference.path!r} disagrees with its manifest count"
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
