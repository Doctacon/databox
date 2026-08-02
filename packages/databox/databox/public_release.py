"""Publish an audited Rufous data directory as an atomic, immutable release.

This module does not sanitize or select source data.  It requires the reviewed
public-export contract, reruns its privacy/licensing/source audit, independently
checks its semantic version, then gives it a content-addressed layout.  A small
mutable pointer advances only after every immutable object verifies.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import importlib
import json
import mimetypes
import os
import re
import shutil
import sys
import tempfile
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath
from typing import Any, BinaryIO, Literal, Protocol, cast

from databox.public_export import PublicExportError, semantic_data_version
from databox.public_export_audit import audit_public_site

RELEASE_SCHEMA_VERSION = 1
IMMUTABLE_CACHE_CONTROL = "public,max-age=31536000,immutable,no-transform"
POINTER_CACHE_CONTROL = "no-cache,max-age=0,must-revalidate"
DEFAULT_PREFIX = "rufous-public"
DEFAULT_HISTORY_LIMIT = 20
MAX_POINTER_BYTES = 1 * 1024 * 1024
MAX_APPLICATION_MANIFEST_BYTES = 5 * 1024 * 1024
MAX_PUBLIC_OBJECT_BYTES = 25 * 1024 * 1024
MAX_PUBLIC_RELEASE_BYTES = 256 * 1024 * 1024

_SHA256 = re.compile(r"^[a-f0-9]{64}$")
_ACCOUNT_ID = re.compile(r"^[a-f0-9]{32}$")
_BUCKET = re.compile(r"^[a-z0-9][a-z0-9.-]{1,61}[a-z0-9]$")
_KEY_PART = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,254}$")
_SOURCE_REVISION = re.compile(r"^[a-f0-9]{40}(?:[a-f0-9]{24})?$")
_MAX_PUBLICATION_NUMBER = 2**63 - 1


class PublicReleaseError(RuntimeError):
    """The public release could not be published safely."""


@dataclass(frozen=True)
class SourceObject:
    """A source file and the stable public metadata derived from its bytes."""

    path: Path
    relative_path: str
    size: int
    sha256: str
    content_md5: str
    content_type: str


@dataclass(frozen=True)
class ObjectHead:
    """Metadata needed to verify an existing immutable object."""

    size: int
    content_type: str
    cache_control: str
    metadata: Mapping[str, str]
    etag: str | None = None


@dataclass(frozen=True)
class ObjectValue:
    """A bounded object read paired with the generation used for CAS."""

    payload: bytes
    head: ObjectHead


@dataclass(frozen=True)
class PublicationMetadata:
    """Monotonic identity of one serialized publication attempt."""

    sequence: int
    attempt: int
    source_revision: str

    def as_pointer_fields(self) -> dict[str, object]:
        return {
            "publication_sequence": self.sequence,
            "publication_attempt": self.attempt,
            "source_revision": self.source_revision,
        }


class ReleaseStore(Protocol):
    """The minimal object-store surface required by the publisher."""

    def head_object(self, key: str) -> ObjectHead | None: ...

    def read_object(self, key: str, *, maximum: int) -> ObjectValue | None: ...

    def put_file(
        self,
        key: str,
        source: SourceObject,
        *,
        cache_control: str,
        metadata: Mapping[str, str],
        if_none_match: bool,
    ) -> None: ...

    def put_bytes(
        self,
        key: str,
        payload: bytes,
        *,
        content_type: str,
        cache_control: str,
        metadata: Mapping[str, str],
        if_none_match: bool,
        if_match: str | None = None,
    ) -> None: ...


@dataclass(frozen=True, repr=False)
class R2Config:
    """R2 S3 credentials loaded only from the process environment."""

    account_id: str
    bucket: str
    access_key_id: str
    secret_access_key: str

    @classmethod
    def from_env(cls, environ: Mapping[str, str] | None = None) -> R2Config:
        values = os.environ if environ is None else environ
        names = (
            "RUFOUS_R2_ACCOUNT_ID",
            "RUFOUS_R2_BUCKET",
            "RUFOUS_R2_ACCESS_KEY_ID",
            "RUFOUS_R2_SECRET_ACCESS_KEY",
        )
        missing = [name for name in names if not values.get(name, "").strip()]
        if missing:
            raise PublicReleaseError(
                "missing required R2 environment variables: " + ", ".join(missing)
            )
        config = cls(
            account_id=values[names[0]].strip(),
            bucket=values[names[1]].strip(),
            access_key_id=values[names[2]].strip(),
            secret_access_key=values[names[3]].strip(),
        )
        config.validate()
        return config

    @property
    def endpoint_url(self) -> str:
        return f"https://{self.account_id}.r2.cloudflarestorage.com"

    def validate(self) -> None:
        if not _ACCOUNT_ID.fullmatch(self.account_id):
            raise PublicReleaseError("RUFOUS_R2_ACCOUNT_ID must be 32 lowercase hex characters")
        if (
            not _BUCKET.fullmatch(self.bucket)
            or ".." in self.bucket
            or _looks_like_ipv4(self.bucket)
        ):
            raise PublicReleaseError("RUFOUS_R2_BUCKET is not a safe S3 bucket name")
        credentials = (self.access_key_id, self.secret_access_key)
        if any(
            not value or len(value) > 256 or any(character in value for character in "\r\n\x00")
            for value in credentials
        ):
            raise PublicReleaseError("R2 credential values are empty, unsafe, or too long")

    def __repr__(self) -> str:
        return (
            "R2Config("
            f"account_id={self.account_id!r}, bucket={self.bucket!r}, "
            "access_key_id='redacted', secret_access_key='redacted')"
        )


class R2ReleaseStore:
    """Cloudflare R2 implementation of :class:`ReleaseStore`."""

    def __init__(self, config: R2Config, client: Any | None = None) -> None:
        config.validate()
        self._config = config
        self._client = client if client is not None else self._build_client(config)

    @staticmethod
    def _build_client(config: R2Config) -> Any:
        try:
            boto3 = importlib.import_module("boto3")
            botocore_config = importlib.import_module("botocore.config")
            return boto3.client(
                service_name="s3",
                endpoint_url=config.endpoint_url,
                aws_access_key_id=config.access_key_id,
                aws_secret_access_key=config.secret_access_key,
                region_name="auto",
                config=botocore_config.Config(
                    signature_version="s3v4",
                    retries={"max_attempts": 4, "mode": "standard"},
                    s3={"addressing_style": "path"},
                ),
            )
        except ModuleNotFoundError:
            raise PublicReleaseError(
                "R2 publishing requires the optional databox[r2] dependency"
            ) from None
        except Exception:
            raise PublicReleaseError("could not initialize the R2 client") from None

    def head_object(self, key: str) -> ObjectHead | None:
        _validate_key(key)
        try:
            response = self._client.head_object(Bucket=self._config.bucket, Key=key)
        except Exception as exc:
            if _r2_error_code(exc) in {"404", "NoSuchKey", "NotFound"}:
                return None
            raise PublicReleaseError(f"R2 head failed for {key!r}") from None
        size = response.get("ContentLength")
        metadata = response.get("Metadata", {})
        if not isinstance(size, int) or not isinstance(metadata, Mapping):
            raise PublicReleaseError(f"R2 returned invalid metadata for {key!r}")
        return ObjectHead(
            size=size,
            content_type=_response_header(response.get("ContentType"), "Content-Type", key),
            cache_control=_response_header(response.get("CacheControl"), "Cache-Control", key),
            metadata=_validated_metadata(metadata),
            etag=_optional_etag(response.get("ETag"), key),
        )

    def read_object(self, key: str, *, maximum: int) -> ObjectValue | None:
        _validate_key(key)
        body: Any = None
        try:
            response = self._client.get_object(Bucket=self._config.bucket, Key=key)
            size = response.get("ContentLength")
            metadata = response.get("Metadata", {})
            if not isinstance(size, int) or not isinstance(metadata, Mapping):
                raise PublicReleaseError(f"R2 returned invalid metadata for {key!r}")
            if size > maximum:
                raise PublicReleaseError(f"R2 object {key!r} exceeds the safe read limit")
            body = response["Body"]
            payload = cast(bytes, body.read(maximum + 1))
        except PublicReleaseError:
            raise
        except Exception as exc:
            if _r2_error_code(exc) in {"404", "NoSuchKey", "NotFound"}:
                return None
            raise PublicReleaseError(f"R2 read failed for {key!r}") from None
        finally:
            if body is not None:
                close = getattr(body, "close", None)
                if callable(close):
                    close()
        if len(payload) > maximum:
            raise PublicReleaseError(f"R2 object {key!r} exceeds the safe read limit")
        if len(payload) != size:
            raise PublicReleaseError(f"R2 object {key!r} returned an unexpected byte count")
        return ObjectValue(
            payload=payload,
            head=ObjectHead(
                size=size,
                content_type=_response_header(response.get("ContentType"), "Content-Type", key),
                cache_control=_response_header(response.get("CacheControl"), "Cache-Control", key),
                metadata=_validated_metadata(metadata),
                etag=_optional_etag(response.get("ETag"), key),
            ),
        )

    def put_file(
        self,
        key: str,
        source: SourceObject,
        *,
        cache_control: str,
        metadata: Mapping[str, str],
        if_none_match: bool,
    ) -> None:
        _validate_key(key)
        if source.size > MAX_PUBLIC_OBJECT_BYTES:
            raise PublicReleaseError(f"{source.relative_path!r} exceeds 25 MiB")
        arguments: dict[str, Any] = {
            "Bucket": self._config.bucket,
            "Key": key,
            "ContentLength": source.size,
            "ContentType": source.content_type,
            "CacheControl": cache_control,
            "ContentMD5": source.content_md5,
            "Metadata": dict(metadata),
        }
        if if_none_match:
            arguments["IfNoneMatch"] = "*"
        try:
            with source.path.open("rb") as stream:
                arguments["Body"] = stream
                self._client.put_object(**arguments)
        except Exception:
            raise PublicReleaseError(f"R2 upload failed for {key!r}") from None

    def put_bytes(
        self,
        key: str,
        payload: bytes,
        *,
        content_type: str,
        cache_control: str,
        metadata: Mapping[str, str],
        if_none_match: bool,
        if_match: str | None = None,
    ) -> None:
        _validate_key(key)
        arguments: dict[str, Any] = {
            "Bucket": self._config.bucket,
            "Key": key,
            "Body": payload,
            "ContentLength": len(payload),
            "ContentType": content_type,
            "CacheControl": cache_control,
            "ContentMD5": base64.b64encode(
                hashlib.md5(payload, usedforsecurity=False).digest()
            ).decode(),
            "Metadata": dict(metadata),
        }
        if if_none_match and if_match is not None:
            raise PublicReleaseError("an object write cannot use both If-Match and If-None-Match")
        if if_none_match:
            arguments["IfNoneMatch"] = "*"
        if if_match is not None:
            arguments["IfMatch"] = _validate_etag(if_match)
        try:
            self._client.put_object(**arguments)
        except Exception:
            raise PublicReleaseError(f"R2 upload failed for {key!r}") from None


class LocalReleaseStore:
    """Filesystem object store for local previews and deterministic tests."""

    def __init__(self, root: Path) -> None:
        self.root = root.resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self._metadata_root = self.root / ".rufous-object-metadata"
        if self._metadata_root.exists() and (
            self._metadata_root.is_symlink() or not self._metadata_root.is_dir()
        ):
            raise PublicReleaseError("local object metadata root is not a real directory")
        self._metadata_root.mkdir(parents=True, exist_ok=True)

    def _path(self, key: str) -> Path:
        _validate_key(key)
        candidate = self.root.joinpath(*PurePosixPath(key).parts)
        try:
            candidate.resolve(strict=False).relative_to(self.root)
        except ValueError:
            raise PublicReleaseError(
                f"object key escapes the local release root: {key!r}"
            ) from None
        return candidate

    def _metadata_path(self, key: str) -> Path:
        object_path = self._path(key)
        relative = object_path.relative_to(self.root)
        candidate = self._metadata_root.joinpath(*relative.parts).with_suffix(
            object_path.suffix + ".metadata.json"
        )
        try:
            candidate.resolve(strict=False).relative_to(self._metadata_root)
        except ValueError:
            raise PublicReleaseError(f"object metadata path escapes its root: {key!r}") from None
        return candidate

    def _head_for_path(self, key: str, path: Path) -> ObjectHead:
        metadata_path = self._metadata_path(key)
        if not metadata_path.exists() or metadata_path.is_symlink() or not metadata_path.is_file():
            raise PublicReleaseError(f"local object metadata is missing or unsafe: {key!r}")
        try:
            envelope = json.loads(metadata_path.read_bytes())
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            raise PublicReleaseError(f"local object metadata is invalid: {key!r}") from None
        if not isinstance(envelope, dict) or not isinstance(envelope.get("metadata"), dict):
            raise PublicReleaseError(f"local object metadata is invalid: {key!r}")
        metadata = _validated_metadata(envelope["metadata"])
        content_type = _response_header(envelope.get("content_type"), "Content-Type", key)
        cache_control = _response_header(envelope.get("cache_control"), "Cache-Control", key)
        digest, _ = _hash_file(path)
        return ObjectHead(
            size=path.stat().st_size,
            content_type=content_type,
            cache_control=cache_control,
            metadata=metadata,
            etag=digest,
        )

    def _write_metadata(
        self,
        key: str,
        *,
        content_type: str,
        cache_control: str,
        metadata: Mapping[str, str],
    ) -> None:
        metadata_path = self._metadata_path(key)
        metadata_path.parent.mkdir(parents=True, exist_ok=True)
        payload = _json_bytes(
            {
                "content_type": _validate_header_value(content_type, "Content-Type"),
                "cache_control": _validate_header_value(cache_control, "Cache-Control"),
                "metadata": _validated_metadata(metadata),
            }
        )
        self._atomic_bytes(payload, metadata_path)

    def head_object(self, key: str) -> ObjectHead | None:
        path = self._path(key)
        if not path.exists():
            return None
        if path.is_symlink() or not path.is_file():
            raise PublicReleaseError(f"local release object is not a regular file: {key!r}")
        return self._head_for_path(key, path)

    def read_object(self, key: str, *, maximum: int) -> ObjectValue | None:
        path = self._path(key)
        if not path.exists():
            return None
        if path.is_symlink() or not path.is_file():
            raise PublicReleaseError(f"local release object is not a regular file: {key!r}")
        if path.stat().st_size > maximum:
            raise PublicReleaseError(f"local object {key!r} exceeds the safe read limit")
        payload = path.read_bytes()
        if len(payload) > maximum:
            raise PublicReleaseError(f"local object {key!r} exceeds the safe read limit")
        return ObjectValue(
            payload=payload,
            head=self._head_for_path(key, path),
        )

    def put_file(
        self,
        key: str,
        source: SourceObject,
        *,
        cache_control: str,
        metadata: Mapping[str, str],
        if_none_match: bool,
    ) -> None:
        target = self._path(key)
        if if_none_match and target.exists():
            raise PublicReleaseError(f"immutable local object already exists: {key!r}")
        target.parent.mkdir(parents=True, exist_ok=True)
        with source.path.open("rb") as stream:
            self._atomic_copy(stream, target)
        digest, content_md5 = _hash_file(target)
        if digest != source.sha256 or content_md5 != source.content_md5:
            target.unlink(missing_ok=True)
            raise PublicReleaseError(f"source changed while publishing {source.relative_path!r}")
        self._write_metadata(
            key,
            content_type=source.content_type,
            cache_control=cache_control,
            metadata=metadata,
        )

    def put_bytes(
        self,
        key: str,
        payload: bytes,
        *,
        content_type: str,
        cache_control: str,
        metadata: Mapping[str, str],
        if_none_match: bool,
        if_match: str | None = None,
    ) -> None:
        target = self._path(key)
        if if_none_match and if_match is not None:
            raise PublicReleaseError("an object write cannot use both If-Match and If-None-Match")
        if if_none_match and target.exists():
            raise PublicReleaseError(f"conditional local write failed for {key!r}")
        if if_match is not None:
            current = self.head_object(key)
            if current is None or current.etag != _validate_etag(if_match):
                raise PublicReleaseError(f"conditional local write failed for {key!r}")
        self._atomic_bytes(payload, target)
        self._write_metadata(
            key,
            content_type=content_type,
            cache_control=cache_control,
            metadata=metadata,
        )

    @staticmethod
    def _atomic_bytes(payload: bytes, target: Path) -> None:
        target.parent.mkdir(parents=True, exist_ok=True)
        temporary_path: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(dir=target.parent, delete=False) as temporary:
                temporary_path = Path(temporary.name)
                temporary.write(payload)
                temporary.flush()
                os.fsync(temporary.fileno())
            os.replace(temporary_path, target)
        finally:
            if temporary_path is not None:
                temporary_path.unlink(missing_ok=True)

    @staticmethod
    def _atomic_copy(stream: BinaryIO, target: Path) -> None:
        temporary_path: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(dir=target.parent, delete=False) as temporary:
                temporary_path = Path(temporary.name)
                shutil.copyfileobj(stream, temporary, length=1024 * 1024)
                temporary.flush()
                os.fsync(temporary.fileno())
            os.replace(temporary_path, target)
        finally:
            if temporary_path is not None:
                temporary_path.unlink(missing_ok=True)


@dataclass(frozen=True)
class PublishResult:
    """A credential-free summary suitable for CI output."""

    status: Literal["published", "rolled-back", "unchanged", "dry-run"]
    changed: bool
    dry_run: bool
    release_id: str
    data_version: str
    file_count: int
    total_bytes: int
    uploaded_assets: int
    reused_assets: int
    release_manifest_key: str
    pointer_key: str

    def as_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class PointerState:
    """A validated mutable pointer and the generation read with it."""

    value: dict[str, Any]
    etag: str


def _publication_metadata(
    sequence: int | None, attempt: int | None, source_revision: str | None
) -> PublicationMetadata | None:
    values = (sequence, attempt, source_revision)
    if all(value is None for value in values):
        return None
    if any(value is None for value in values):
        raise PublicReleaseError(
            "publication_sequence, publication_attempt, and source_revision "
            "must be provided together"
        )
    if type(sequence) is not int or sequence < 1 or sequence > _MAX_PUBLICATION_NUMBER:
        raise PublicReleaseError("publication_sequence must be a positive signed 64-bit integer")
    if type(attempt) is not int or attempt < 1 or attempt > _MAX_PUBLICATION_NUMBER:
        raise PublicReleaseError("publication_attempt must be a positive signed 64-bit integer")
    if not isinstance(source_revision, str) or not _SOURCE_REVISION.fullmatch(source_revision):
        raise PublicReleaseError(
            "source_revision must be a lowercase 40- or 64-character hexadecimal revision"
        )
    return PublicationMetadata(sequence, attempt, source_revision)


def _publication_from_pointer(value: Mapping[str, Any]) -> PublicationMetadata | None:
    return _publication_metadata(
        cast(int | None, value.get("publication_sequence")),
        cast(int | None, value.get("publication_attempt")),
        cast(str | None, value.get("source_revision")),
    )


def _reject_stale_publication(
    current: PointerState | None, publication: PublicationMetadata | None
) -> None:
    if current is None:
        return
    active = _publication_from_pointer(current.value)
    if active is None:
        return
    if publication is None:
        raise PublicReleaseError(
            "publication metadata is required because the active pointer is monotonic"
        )
    candidate_order = (publication.sequence, publication.attempt)
    active_order = (active.sequence, active.attempt)
    if candidate_order < active_order:
        raise PublicReleaseError("stale publication attempt is older than the active pointer")
    if candidate_order == active_order and publication.source_revision != active.source_revision:
        raise PublicReleaseError(
            "publication sequence and attempt were reused for a different source revision"
        )


def _advance_publication_fence(
    store: ReleaseStore,
    current: PointerState,
    publication: PublicationMetadata | None,
    *,
    pointer_key: str,
    prefix: str,
    dry_run: bool,
) -> None:
    """Record an accepted newer run even when its public data is unchanged."""
    if publication is None or _publication_from_pointer(current.value) == publication:
        return
    pointer = dict(current.value)
    pointer.update(publication.as_pointer_fields())
    payload = _json_bytes(pointer)
    if dry_run:
        return
    _put_pointer(
        store,
        pointer_key,
        pointer,
        payload,
        if_none_match=False,
        if_match=current.etag,
    )
    activated = _read_pointer(store, pointer_key, prefix=prefix)
    if activated is None or _publication_from_pointer(activated.value) != publication:
        raise PublicReleaseError("publication fence could not be verified after activation")


def _put_pointer(
    store: ReleaseStore,
    pointer_key: str,
    pointer: Mapping[str, Any],
    payload: bytes,
    *,
    if_none_match: bool,
    if_match: str | None,
) -> None:
    release_id = pointer.get("release_id")
    if not isinstance(release_id, str) or not _SHA256.fullmatch(release_id):
        raise PublicReleaseError("cannot write a pointer with an invalid release_id")
    pointer_sha256 = hashlib.sha256(payload).hexdigest()
    store.put_bytes(
        pointer_key,
        payload,
        content_type="application/json; charset=utf-8",
        cache_control=POINTER_CACHE_CONTROL,
        metadata=_object_metadata(pointer_sha256, release_id, "pointer"),
        if_none_match=if_none_match,
        if_match=if_match,
    )


def publish_public_release(
    source_dir: Path,
    store: ReleaseStore,
    *,
    prefix: str = DEFAULT_PREFIX,
    dry_run: bool = False,
    history_limit: int = DEFAULT_HISTORY_LIMIT,
    published_at: datetime | None = None,
    publication_sequence: int | None = None,
    publication_attempt: int | None = None,
    source_revision: str | None = None,
) -> PublishResult:
    """Publish ``source_dir`` and advance its pointer only after full success."""
    clean_prefix = _validate_prefix(prefix)
    publication = _publication_metadata(publication_sequence, publication_attempt, source_revision)
    if not 0 <= history_limit <= 100:
        raise PublicReleaseError("history_limit must be between 0 and 100")
    objects = scan_public_release(source_dir)
    _require_audited_source(source_dir)
    # Bind the audit to the exact byte set scanned above. A concurrent source
    # change must fail before the first object-store read.
    for item in objects:
        _assert_source_unchanged(item)
    data_version, application_manifest_sha256 = _application_manifest_identity(objects)
    release_id = _release_id(objects)
    asset_base_key = f"{clean_prefix}/releases/{release_id}/objects"
    manifest_path = f"{asset_base_key}/data/manifest.json"
    release_manifest_key = f"{clean_prefix}/releases/{release_id}/release.json"
    pointer_key = f"{clean_prefix}/manifest.json"
    current = _read_pointer(store, pointer_key, prefix=clean_prefix)
    _reject_stale_publication(current, publication)
    total_bytes = sum(item.size for item in objects)
    if current is not None and current.value["data_version"] == data_version:
        active = current.value
        _verify_complete_release(store, active, prefix=clean_prefix)
        _advance_publication_fence(
            store,
            current,
            publication,
            pointer_key=pointer_key,
            prefix=clean_prefix,
            dry_run=dry_run,
        )
        return PublishResult(
            status="unchanged",
            changed=False,
            dry_run=dry_run,
            release_id=active["release_id"],
            data_version=data_version,
            file_count=active["file_count"],
            total_bytes=active["total_bytes"],
            uploaded_assets=0,
            reused_assets=active["file_count"],
            release_manifest_key=active["release_manifest_key"],
            pointer_key=pointer_key,
        )
    if current is not None and current.value["release_id"] == release_id:
        raise PublicReleaseError("current pointer data_version conflicts with its release_id")
    if (
        current is not None
        and publication is not None
        and _publication_from_pointer(current.value) == publication
    ):
        raise PublicReleaseError(
            "publication identity was already used for a different semantic release"
        )

    file_entries = [
        {
            "path": item.relative_path,
            "key": f"{asset_base_key}/{item.relative_path}",
            "bytes": item.size,
            "sha256": item.sha256,
            "content_type": item.content_type,
            "cache_control": IMMUTABLE_CACHE_CONTROL,
        }
        for item in objects
    ]
    release_manifest = {
        "schema_version": RELEASE_SCHEMA_VERSION,
        "release_id": release_id,
        "data_version": data_version,
        "manifest_path": manifest_path,
        "manifest_sha256": application_manifest_sha256,
        "asset_base_key": asset_base_key,
        "file_count": len(objects),
        "total_bytes": total_bytes,
        "files": file_entries,
    }
    release_payload = _json_bytes(release_manifest)
    release_sha256 = hashlib.sha256(release_payload).hexdigest()
    timestamp = _publication_timestamp(published_at)
    previous_releases = _history_for_pointer(current.value if current else None, history_limit)
    pointer = {
        "schema_version": RELEASE_SCHEMA_VERSION,
        "mode": "public-release-pointer",
        "release_id": release_id,
        "data_version": data_version,
        "published_at": timestamp,
        "manifest_path": manifest_path,
        "manifest_sha256": application_manifest_sha256,
        "release_manifest_sha256": release_sha256,
        "release_manifest_key": release_manifest_key,
        "asset_base_key": asset_base_key,
        "file_count": len(objects),
        "total_bytes": total_bytes,
        "previous_releases": previous_releases,
    }
    if publication is not None:
        pointer.update(publication.as_pointer_fields())
    pointer_payload = _json_bytes(pointer)

    uploaded_assets = 0
    reused_assets = 0
    for item in objects:
        key = f"{asset_base_key}/{item.relative_path}"
        asset_metadata = _object_metadata(item.sha256, release_id, "asset")
        existing = store.head_object(key)
        if existing is not None:
            _assert_existing_object(
                existing,
                key=key,
                sha256=item.sha256,
                size=item.size,
                content_type=item.content_type,
                cache_control=IMMUTABLE_CACHE_CONTROL,
                metadata=asset_metadata,
            )
            reused_assets += 1
            continue
        uploaded_assets += 1
        if not dry_run:
            _assert_source_unchanged(item)
            store.put_file(
                key,
                item,
                cache_control=IMMUTABLE_CACHE_CONTROL,
                metadata=asset_metadata,
                if_none_match=True,
            )
            uploaded = store.head_object(key)
            if uploaded is None:
                raise PublicReleaseError(f"uploaded object is not readable at {key!r}")
            _assert_existing_object(
                uploaded,
                key=key,
                sha256=item.sha256,
                size=item.size,
                content_type=item.content_type,
                cache_control=IMMUTABLE_CACHE_CONTROL,
                metadata=asset_metadata,
            )

    release_metadata = _object_metadata(release_sha256, release_id, "manifest")
    existing_manifest = store.head_object(release_manifest_key)
    if existing_manifest is not None:
        _assert_existing_object(
            existing_manifest,
            key=release_manifest_key,
            sha256=release_sha256,
            size=len(release_payload),
            content_type="application/json; charset=utf-8",
            cache_control=IMMUTABLE_CACHE_CONTROL,
            metadata=release_metadata,
        )
    elif not dry_run:
        store.put_bytes(
            release_manifest_key,
            release_payload,
            content_type="application/json; charset=utf-8",
            cache_control=IMMUTABLE_CACHE_CONTROL,
            metadata=release_metadata,
            if_none_match=True,
        )
        uploaded_manifest = store.head_object(release_manifest_key)
        if uploaded_manifest is None:
            raise PublicReleaseError("uploaded release manifest is not readable")
        _assert_existing_object(
            uploaded_manifest,
            key=release_manifest_key,
            sha256=release_sha256,
            size=len(release_payload),
            content_type="application/json; charset=utf-8",
            cache_control=IMMUTABLE_CACHE_CONTROL,
            metadata=release_metadata,
        )

    if not dry_run:
        _verify_complete_release(store, pointer, prefix=clean_prefix)
        _put_pointer(
            store,
            pointer_key,
            pointer,
            pointer_payload,
            if_none_match=current is None,
            if_match=current.etag if current is not None else None,
        )
        activated = _read_pointer(store, pointer_key, prefix=clean_prefix)
        if activated is None or activated.value["release_id"] != release_id:
            raise PublicReleaseError("release pointer could not be verified after activation")
    return PublishResult(
        status="dry-run" if dry_run else "published",
        changed=True,
        dry_run=dry_run,
        release_id=release_id,
        data_version=data_version,
        file_count=len(objects),
        total_bytes=total_bytes,
        uploaded_assets=uploaded_assets,
        reused_assets=reused_assets,
        release_manifest_key=release_manifest_key,
        pointer_key=pointer_key,
    )


def rollback_public_release(
    store: ReleaseStore,
    release_id: str,
    *,
    prefix: str = DEFAULT_PREFIX,
    dry_run: bool = False,
    history_limit: int = DEFAULT_HISTORY_LIMIT,
    publication_sequence: int | None = None,
    publication_attempt: int | None = None,
    source_revision: str | None = None,
) -> PublishResult:
    """CAS-repoint to a complete immutable release already present in history."""
    clean_prefix = _validate_prefix(prefix)
    publication = _publication_metadata(publication_sequence, publication_attempt, source_revision)
    if not _SHA256.fullmatch(release_id):
        raise PublicReleaseError("rollback release_id must be a lowercase SHA-256")
    if not 0 <= history_limit <= 100:
        raise PublicReleaseError("history_limit must be between 0 and 100")
    pointer_key = f"{clean_prefix}/manifest.json"
    current = _read_pointer(store, pointer_key, prefix=clean_prefix)
    if current is None:
        raise PublicReleaseError("cannot rollback before an initial release exists")
    _reject_stale_publication(current, publication)
    if current.value["release_id"] == release_id:
        _verify_complete_release(store, current.value, prefix=clean_prefix)
        _advance_publication_fence(
            store,
            current,
            publication,
            pointer_key=pointer_key,
            prefix=clean_prefix,
            dry_run=dry_run,
        )
        return PublishResult(
            status="unchanged",
            changed=False,
            dry_run=dry_run,
            release_id=release_id,
            data_version=current.value["data_version"],
            file_count=current.value["file_count"],
            total_bytes=current.value["total_bytes"],
            uploaded_assets=0,
            reused_assets=current.value["file_count"],
            release_manifest_key=current.value["release_manifest_key"],
            pointer_key=pointer_key,
        )
    candidates = [cast(dict[str, Any], item) for item in current.value["previous_releases"]]
    target = next((item for item in candidates if item["release_id"] == release_id), None)
    if target is None:
        raise PublicReleaseError("rollback target is not present in verified release history")
    if publication is not None and _publication_from_pointer(current.value) == publication:
        raise PublicReleaseError(
            "publication identity was already used for a different pointer activation"
        )
    _verify_complete_release(store, target, prefix=clean_prefix)
    pointer = {
        "schema_version": RELEASE_SCHEMA_VERSION,
        "mode": "public-release-pointer",
        **_pointer_summary(target),
        "previous_releases": _rollback_history(current.value, release_id, history_limit),
    }
    if publication is not None:
        pointer.update(publication.as_pointer_fields())
    payload = _json_bytes(pointer)
    if not dry_run:
        _put_pointer(
            store,
            pointer_key,
            pointer,
            payload,
            if_none_match=False,
            if_match=current.etag,
        )
        activated = _read_pointer(store, pointer_key, prefix=clean_prefix)
        if activated is None or activated.value["release_id"] != release_id:
            raise PublicReleaseError("rollback pointer could not be verified after activation")
    return PublishResult(
        status="dry-run" if dry_run else "rolled-back",
        changed=True,
        dry_run=dry_run,
        release_id=release_id,
        data_version=target["data_version"],
        file_count=target["file_count"],
        total_bytes=target["total_bytes"],
        uploaded_assets=0,
        reused_assets=target["file_count"],
        release_manifest_key=target["release_manifest_key"],
        pointer_key=pointer_key,
    )


def _require_audited_source(source_dir: Path) -> None:
    findings = audit_public_site(source_dir)
    if not findings:
        return
    shown = [finding.replace("\n", " ")[:240] for finding in findings[:5]]
    remainder = len(findings) - len(shown)
    suffix = f"; plus {remainder} more finding(s)" if remainder else ""
    raise PublicReleaseError("public export audit failed: " + "; ".join(shown) + suffix)


def scan_public_release(source_dir: Path) -> list[SourceObject]:
    """Hash a directory without following symlinks or accepting unsafe URL paths."""
    try:
        source = source_dir.resolve(strict=True)
    except OSError:
        raise PublicReleaseError(f"public export directory does not exist: {source_dir}") from None
    if source_dir.is_symlink() or not source.is_dir():
        raise PublicReleaseError("public export source must be a real directory, not a symlink")
    discovered: list[SourceObject] = []
    for root, directory_names, file_names in os.walk(source, followlinks=False):
        root_path = Path(root)
        for name in directory_names:
            directory = root_path / name
            relative = directory.relative_to(source)
            _validate_relative_path(relative)
            if directory.is_symlink():
                raise PublicReleaseError(
                    f"public export contains a symlink: {relative.as_posix()!r}"
                )
        for name in file_names:
            path = root_path / name
            relative = path.relative_to(source)
            relative_path = _validate_relative_path(relative)
            if path.is_symlink():
                raise PublicReleaseError(f"public export contains a symlink: {relative_path!r}")
            if not path.is_file():
                raise PublicReleaseError(
                    f"public export contains a non-regular file: {relative_path!r}"
                )
            _validate_reviewed_path(relative_path)
            size = path.stat().st_size
            if size > MAX_PUBLIC_OBJECT_BYTES:
                raise PublicReleaseError(f"public export object exceeds 25 MiB: {relative_path!r}")
            if _has_raw_signature(path):
                raise PublicReleaseError(
                    f"public export contains a database/raw file signature: {relative_path!r}"
                )
            sha256, content_md5 = _hash_file(path)
            discovered.append(
                SourceObject(
                    path=path,
                    relative_path=relative_path,
                    size=size,
                    sha256=sha256,
                    content_md5=content_md5,
                    content_type=_content_type(path),
                )
            )
    if not discovered:
        raise PublicReleaseError("public export directory contains no files")
    total_bytes = sum(item.size for item in discovered)
    if total_bytes > MAX_PUBLIC_RELEASE_BYTES:
        raise PublicReleaseError("public export exceeds the conservative 256 MiB release limit")
    return sorted(discovered, key=lambda item: item.relative_path)


def _application_manifest_identity(objects: Sequence[SourceObject]) -> tuple[str, str]:
    candidates = [item for item in objects if item.relative_path == "data/manifest.json"]
    if len(candidates) != 1:
        raise PublicReleaseError("public export must contain exactly one data/manifest.json")
    source = candidates[0]
    if source.size > MAX_APPLICATION_MANIFEST_BYTES:
        raise PublicReleaseError("data/manifest.json exceeds the safe validation limit")
    _assert_source_unchanged(source)
    try:
        value = json.loads(source.path.read_bytes())
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise PublicReleaseError("data/manifest.json is not valid UTF-8 JSON") from None
    if not isinstance(value, dict):
        raise PublicReleaseError("data/manifest.json must be a JSON object")
    if type(value.get("schema_version")) is not int or value["schema_version"] != 1:
        raise PublicReleaseError("data/manifest.json has an unsupported schema_version")
    if value.get("mode") != "public":
        raise PublicReleaseError("data/manifest.json mode must be 'public'")
    if value.get("release_mode") not in {"synthetic", "production"}:
        raise PublicReleaseError("data/manifest.json has an invalid release_mode")
    source_policy = value.get("source_policy")
    if not isinstance(source_policy, dict) or source_policy.get("direct_ebird") != "excluded":
        raise PublicReleaseError("data/manifest.json does not enforce the public source boundary")
    license_policy = value.get("license_policy")
    if (
        not isinstance(license_policy, dict)
        or type(license_policy.get("version")) is not int
        or license_policy["version"] != 1
    ):
        raise PublicReleaseError("data/manifest.json does not contain the audited license policy")
    generated_at = value.get("generated_at")
    if not isinstance(generated_at, str):
        raise PublicReleaseError("data/manifest.json has an invalid generated_at")
    _parse_timestamp(generated_at)
    data_version = value.get("data_version")
    if not isinstance(data_version, str) or not _SHA256.fullmatch(data_version):
        raise PublicReleaseError("data/manifest.json data_version must be a lowercase SHA-256")
    referenced = {"data/manifest.json"}
    attribution_path = value.get("attribution_path")
    referenced.add(_manifest_asset_path(attribution_path, "data/attribution.json"))
    referenced.update(_manifest_shard_paths(value, "species", "profile_path", "species"))
    referenced.update(_manifest_shard_paths(value, "cells", "path", "cells"))
    referenced.update(_manifest_shard_paths(value, "place_prefixes", "path", "places"))
    actual = {item.relative_path for item in objects}
    if actual != referenced:
        unreferenced = sorted(actual - referenced)
        missing = sorted(referenced - actual)
        details = []
        if unreferenced:
            details.append("unreferenced=" + ",".join(unreferenced[:5]))
        if missing:
            details.append("missing=" + ",".join(missing[:5]))
        raise PublicReleaseError(
            "public export files do not match data/manifest.json (" + "; ".join(details) + ")"
        )
    computed_data_version = _semantic_data_version(objects)
    if computed_data_version != data_version:
        raise PublicReleaseError(
            "data/manifest.json data_version does not match the referenced public JSON"
        )
    return data_version, source.sha256


def _manifest_asset_path(value: object, expected_path: str) -> str:
    if not isinstance(value, str) or not value.startswith("/"):
        raise PublicReleaseError("data/manifest.json contains an invalid public asset path")
    relative = value.removeprefix("/")
    _validate_key(relative)
    _validate_reviewed_path(relative)
    if relative != expected_path:
        raise PublicReleaseError("data/manifest.json contains an unexpected public asset path")
    return relative


def _manifest_shard_paths(
    manifest: Mapping[str, Any], field: str, path_field: str, directory: str
) -> set[str]:
    rows = manifest.get(field)
    if not isinstance(rows, list):
        raise PublicReleaseError(f"data/manifest.json has an invalid {field!r} index")
    paths: set[str] = set()
    for row in rows:
        if not isinstance(row, dict):
            raise PublicReleaseError(f"data/manifest.json has a non-object {field!r} entry")
        path = row.get(path_field)
        if not isinstance(path, str) or not path.startswith("/"):
            raise PublicReleaseError(f"data/manifest.json has an invalid {field!r} path")
        relative = path.removeprefix("/")
        _validate_key(relative)
        _validate_reviewed_path(relative)
        if not relative.startswith(f"data/{directory}/"):
            raise PublicReleaseError(f"data/manifest.json has an unexpected {field!r} path")
        if relative in paths:
            raise PublicReleaseError(f"data/manifest.json repeats a {field!r} path")
        paths.add(relative)
    return paths


def _semantic_data_version(objects: Sequence[SourceObject]) -> str:
    assets: dict[str, object] = {}
    for source in objects:
        _assert_source_unchanged(source)
        try:
            payload = json.loads(source.path.read_bytes())
        except (UnicodeDecodeError, json.JSONDecodeError):
            raise PublicReleaseError(f"public JSON is invalid: {source.relative_path!r}") from None
        assets[source.relative_path] = payload
    try:
        return semantic_data_version(assets)
    except PublicExportError as exc:
        raise PublicReleaseError(str(exc)) from None


def _hash_file(path: Path) -> tuple[str, str]:
    sha256 = hashlib.sha256()
    md5 = hashlib.md5(usedforsecurity=False)
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            sha256.update(chunk)
            md5.update(chunk)
    return sha256.hexdigest(), base64.b64encode(md5.digest()).decode()


def _release_id(objects: Sequence[SourceObject]) -> str:
    digest = hashlib.sha256(b"rufous-public-release-v1\0")
    for item in objects:
        digest.update(item.relative_path.encode("ascii"))
        digest.update(b"\0")
        digest.update(str(item.size).encode("ascii"))
        digest.update(b"\0")
        digest.update(bytes.fromhex(item.sha256))
    return digest.hexdigest()


def _assert_source_unchanged(source: SourceObject) -> None:
    if source.path.is_symlink() or not source.path.is_file():
        raise PublicReleaseError(f"source changed while publishing {source.relative_path!r}")
    digest, content_md5 = _hash_file(source.path)
    if (
        source.path.stat().st_size != source.size
        or digest != source.sha256
        or content_md5 != source.content_md5
    ):
        raise PublicReleaseError(f"source changed while publishing {source.relative_path!r}")


def _object_metadata(sha256: str, release_id: str, role: str) -> dict[str, str]:
    if not _SHA256.fullmatch(sha256) or not _SHA256.fullmatch(release_id):
        raise PublicReleaseError("cannot construct object metadata with an invalid SHA-256")
    if role not in {"asset", "manifest", "pointer"}:
        raise PublicReleaseError("cannot construct object metadata with an invalid role")
    return {"sha256": sha256, "release-id": release_id, "role": role}


def _assert_existing_object(
    existing: ObjectHead,
    *,
    key: str,
    sha256: str,
    size: int,
    content_type: str,
    cache_control: str,
    metadata: Mapping[str, str],
) -> None:
    expected_metadata = _validated_metadata(metadata)
    actual_metadata = _validated_metadata(existing.metadata)
    if (
        existing.size != size
        or existing.content_type != content_type
        or existing.cache_control != cache_control
        or any(actual_metadata.get(name) != value for name, value in expected_metadata.items())
        or actual_metadata.get("sha256") != sha256
    ):
        raise PublicReleaseError(f"immutable object collision at {key!r}")


def _verify_complete_release(
    store: ReleaseStore, pointer: Mapping[str, Any], *, prefix: str
) -> None:
    """Read and hash every immutable object described by a release manifest."""
    _validate_release_paths(pointer, prefix=prefix)
    release_manifest_key = cast(str, pointer["release_manifest_key"])
    stored = store.read_object(release_manifest_key, maximum=MAX_APPLICATION_MANIFEST_BYTES)
    if stored is None:
        raise PublicReleaseError("release manifest is missing before activation")
    release_sha256 = hashlib.sha256(stored.payload).hexdigest()
    if release_sha256 != pointer.get("release_manifest_sha256"):
        raise PublicReleaseError("release manifest failed immutable verification")
    try:
        _assert_existing_object(
            stored.head,
            key=release_manifest_key,
            sha256=release_sha256,
            size=len(stored.payload),
            content_type="application/json; charset=utf-8",
            cache_control=IMMUTABLE_CACHE_CONTROL,
            metadata=_object_metadata(release_sha256, cast(str, pointer["release_id"]), "manifest"),
        )
    except PublicReleaseError:
        raise PublicReleaseError("release manifest failed immutable verification") from None
    try:
        manifest = json.loads(stored.payload)
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise PublicReleaseError("release manifest is not valid UTF-8 JSON") from None
    if not isinstance(manifest, dict):
        raise PublicReleaseError("release manifest must be a JSON object")
    for field in (
        "release_id",
        "data_version",
        "manifest_path",
        "manifest_sha256",
        "asset_base_key",
        "file_count",
        "total_bytes",
    ):
        if manifest.get(field) != pointer.get(field):
            raise PublicReleaseError(f"release manifest disagrees with pointer field {field!r}")
    if manifest.get("schema_version") != RELEASE_SCHEMA_VERSION:
        raise PublicReleaseError("release manifest uses an unsupported schema version")
    files = manifest.get("files")
    if not isinstance(files, list) or len(files) != pointer["file_count"]:
        raise PublicReleaseError("release manifest has an invalid file index")
    seen: set[str] = set()
    total_bytes = 0
    application_manifest_seen = False
    asset_base_key = cast(str, pointer["asset_base_key"])
    for item in files:
        if not isinstance(item, dict):
            raise PublicReleaseError("release manifest file index contains a non-object entry")
        path = item.get("path")
        key = item.get("key")
        size = item.get("bytes")
        sha256 = item.get("sha256")
        content_type = item.get("content_type")
        if (
            not isinstance(path, str)
            or not isinstance(key, str)
            or type(size) is not int
            or not isinstance(sha256, str)
            or not isinstance(content_type, str)
            or size < 0
            or size > MAX_PUBLIC_OBJECT_BYTES
            or not _SHA256.fullmatch(sha256)
        ):
            raise PublicReleaseError("release manifest contains invalid file metadata")
        _validate_key(path)
        _validate_reviewed_path(path)
        if key != f"{asset_base_key}/{path}":
            raise PublicReleaseError("release manifest contains a key outside its asset base")
        if item.get("cache_control") != IMMUTABLE_CACHE_CONTROL:
            raise PublicReleaseError("release manifest contains unsafe cache metadata")
        if content_type != _content_type(Path(path)):
            raise PublicReleaseError("release manifest contains invalid content-type metadata")
        if path in seen:
            raise PublicReleaseError("release manifest contains a duplicate file path")
        seen.add(path)
        total_bytes += size
        stored_asset = store.read_object(key, maximum=size)
        if stored_asset is None:
            raise PublicReleaseError(f"release object is missing at {key!r}")
        if hashlib.sha256(stored_asset.payload).hexdigest() != sha256:
            raise PublicReleaseError(f"release object failed byte verification at {key!r}")
        _assert_existing_object(
            stored_asset.head,
            key=key,
            sha256=sha256,
            size=size,
            content_type=content_type,
            cache_control=IMMUTABLE_CACHE_CONTROL,
            metadata=_object_metadata(sha256, cast(str, pointer["release_id"]), "asset"),
        )
        if path == "data/manifest.json":
            application_manifest_seen = True
            if sha256 != pointer["manifest_sha256"]:
                raise PublicReleaseError("application manifest hash disagrees with release pointer")
    if not application_manifest_seen:
        raise PublicReleaseError("release manifest does not include data/manifest.json")
    if total_bytes != pointer["total_bytes"] or total_bytes > MAX_PUBLIC_RELEASE_BYTES:
        raise PublicReleaseError("release manifest total bytes failed verification")


def _read_pointer(store: ReleaseStore, pointer_key: str, *, prefix: str) -> PointerState | None:
    stored = store.read_object(pointer_key, maximum=MAX_POINTER_BYTES)
    if stored is None:
        return None
    try:
        value = json.loads(stored.payload)
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise PublicReleaseError("current release pointer is not valid UTF-8 JSON") from None
    if not isinstance(value, dict):
        raise PublicReleaseError("current release pointer must be a JSON object")
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
    for field, expected_type in required.items():
        if not isinstance(value.get(field), expected_type):
            raise PublicReleaseError(f"current release pointer has an invalid {field!r}")
    if value["schema_version"] != RELEASE_SCHEMA_VERSION:
        raise PublicReleaseError("current release pointer uses an unsupported schema version")
    if value["mode"] != "public-release-pointer":
        raise PublicReleaseError("current release pointer has an invalid mode")
    if not _SHA256.fullmatch(value["release_id"]):
        raise PublicReleaseError("current release pointer has an invalid release_id")
    if not _SHA256.fullmatch(value["data_version"]):
        raise PublicReleaseError("current release pointer has an invalid data_version")
    if not _SHA256.fullmatch(value["manifest_sha256"]):
        raise PublicReleaseError("current release pointer has an invalid manifest_sha256")
    if not _SHA256.fullmatch(value["release_manifest_sha256"]):
        raise PublicReleaseError("current release pointer has an invalid release_manifest_sha256")
    _validate_release_paths(value, prefix=prefix)
    if (
        type(value["file_count"]) is not int
        or type(value["total_bytes"]) is not int
        or value["file_count"] < 0
        or value["total_bytes"] < 0
    ):
        raise PublicReleaseError("current release pointer has invalid counts")
    _parse_timestamp(value["published_at"])
    history = value["previous_releases"]
    if len(history) > 100:
        raise PublicReleaseError("current release pointer contains too much history")
    for item in history:
        _validate_history_item(item, prefix=prefix)
    _publication_from_pointer(value)
    pointer_sha256 = hashlib.sha256(stored.payload).hexdigest()
    try:
        _assert_existing_object(
            stored.head,
            key=pointer_key,
            sha256=pointer_sha256,
            size=len(stored.payload),
            content_type="application/json; charset=utf-8",
            cache_control=POINTER_CACHE_CONTROL,
            metadata=_object_metadata(pointer_sha256, value["release_id"], "pointer"),
        )
    except PublicReleaseError:
        raise PublicReleaseError(
            "current release pointer failed object metadata verification"
        ) from None
    if stored.head.etag is None:
        raise PublicReleaseError("current release pointer is missing an ETag for safe replacement")
    return PointerState(value=value, etag=_validate_etag(stored.head.etag))


def _history_for_pointer(current: dict[str, Any] | None, limit: int) -> list[dict[str, Any]]:
    if current is None or limit == 0:
        return []
    history = [_pointer_summary(current)]
    seen = {current["release_id"]}
    for raw in current["previous_releases"]:
        item = cast(dict[str, Any], raw)
        release_id = cast(str, item["release_id"])
        if release_id in seen:
            continue
        history.append(dict(item))
        seen.add(release_id)
        if len(history) == limit:
            break
    return history[:limit]


def _rollback_history(
    current: dict[str, Any], target_release_id: str, limit: int
) -> list[dict[str, Any]]:
    if limit == 0:
        return []
    history = [_pointer_summary(current)]
    seen = {target_release_id, current["release_id"]}
    for raw in current["previous_releases"]:
        item = cast(dict[str, Any], raw)
        release_id = cast(str, item["release_id"])
        if release_id in seen:
            continue
        history.append(dict(item))
        seen.add(release_id)
        if len(history) == limit:
            break
    return history[:limit]


def _pointer_summary(pointer: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "release_id": pointer["release_id"],
        "data_version": pointer["data_version"],
        "published_at": pointer["published_at"],
        "manifest_path": pointer["manifest_path"],
        "manifest_sha256": pointer["manifest_sha256"],
        "release_manifest_sha256": pointer["release_manifest_sha256"],
        "release_manifest_key": pointer["release_manifest_key"],
        "asset_base_key": pointer["asset_base_key"],
        "file_count": pointer["file_count"],
        "total_bytes": pointer["total_bytes"],
    }


def _validate_history_item(value: object, *, prefix: str) -> None:
    if not isinstance(value, dict):
        raise PublicReleaseError("release pointer history contains a non-object entry")
    required = {
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
    }
    for field, expected_type in required.items():
        if not isinstance(value.get(field), expected_type):
            raise PublicReleaseError(f"release pointer history has an invalid {field!r}")
    if not _SHA256.fullmatch(value["release_id"]):
        raise PublicReleaseError("release pointer history has an invalid release_id")
    if not _SHA256.fullmatch(value["data_version"]):
        raise PublicReleaseError("release pointer history has an invalid data_version")
    if not _SHA256.fullmatch(value["manifest_sha256"]):
        raise PublicReleaseError("release pointer history has an invalid manifest_sha256")
    if not _SHA256.fullmatch(value["release_manifest_sha256"]):
        raise PublicReleaseError("release pointer history has an invalid release_manifest_sha256")
    _parse_timestamp(value["published_at"])
    _validate_release_paths(value, prefix=prefix)
    if (
        type(value["file_count"]) is not int
        or type(value["total_bytes"]) is not int
        or value["file_count"] < 0
        or value["total_bytes"] < 0
    ):
        raise PublicReleaseError("release pointer history has invalid counts")


def _validate_release_paths(value: Mapping[str, Any], *, prefix: str) -> None:
    release_id = cast(str, value["release_id"])
    manifest_path = cast(str, value["manifest_path"])
    release_manifest_key = cast(str, value["release_manifest_key"])
    asset_base_key = cast(str, value["asset_base_key"])
    _validate_key(manifest_path)
    _validate_key(release_manifest_key)
    _validate_key(asset_base_key)
    if asset_base_key != f"{prefix}/releases/{release_id}/objects":
        raise PublicReleaseError("release pointer asset_base_key does not match release_id")
    if manifest_path != f"{asset_base_key}/data/manifest.json":
        raise PublicReleaseError("release pointer manifest_path does not match asset_base_key")
    expected_release_manifest = f"{asset_base_key.removesuffix('/objects')}/release.json"
    if release_manifest_key != expected_release_manifest:
        raise PublicReleaseError("release pointer release_manifest_key does not match release_id")


def _publication_timestamp(value: datetime | None) -> str:
    timestamp = datetime.now(UTC) if value is None else value
    if timestamp.tzinfo is None:
        raise PublicReleaseError("published_at must include a timezone")
    return timestamp.astimezone(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _parse_timestamp(value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        raise PublicReleaseError("release pointer timestamp is not ISO 8601") from None
    if parsed.tzinfo is None:
        raise PublicReleaseError("release pointer timestamp must include a timezone")
    return parsed


def _content_type(path: Path) -> str:
    overrides = {
        ".arrow": "application/vnd.apache.arrow.file",
        ".css": "text/css; charset=utf-8",
        ".csv": "text/csv; charset=utf-8",
        ".html": "text/html; charset=utf-8",
        ".js": "text/javascript; charset=utf-8",
        ".json": "application/json; charset=utf-8",
        ".mjs": "text/javascript; charset=utf-8",
        ".parquet": "application/vnd.apache.parquet",
        ".svg": "image/svg+xml",
        ".txt": "text/plain; charset=utf-8",
        ".wasm": "application/wasm",
    }
    suffix = path.suffix.casefold()
    if suffix in overrides:
        return overrides[suffix]
    guessed, _ = mimetypes.guess_type(path.name, strict=False)
    if guessed is None:
        return "application/octet-stream"
    return f"{guessed}; charset=utf-8" if guessed.startswith("text/") else guessed


def _validate_prefix(prefix: str) -> str:
    if not isinstance(prefix, str) or not prefix or prefix != prefix.strip("/"):
        raise PublicReleaseError("release prefix must not be empty or start/end with a slash")
    _validate_key(prefix)
    return prefix


def _validate_relative_path(relative: Path) -> str:
    if relative.is_absolute():
        raise PublicReleaseError("public export contains an absolute path")
    value = relative.as_posix()
    _validate_key(value)
    return value


def _validate_reviewed_path(relative_path: str) -> None:
    parts = relative_path.split("/")
    root_file = (
        len(parts) == 2
        and parts[0] == "data"
        and parts[1]
        in {
            "attribution.json",
            "manifest.json",
        }
    )
    shard = (
        len(parts) == 3
        and parts[0] == "data"
        and parts[1] in {"cells", "places", "species"}
        and parts[2].endswith(".json")
    )
    if not root_file and not shard:
        raise PublicReleaseError(
            f"public export path is outside the reviewed JSON contract: {relative_path!r}"
        )


def _has_raw_signature(path: Path) -> bool:
    with path.open("rb") as stream:
        header = stream.read(16)
    return bool(
        header.startswith((b"SQLite format 3\x00", b"PAR1", b"ARROW1", b"Obj\x01"))
        or header[8:12] == b"DUCK"
    )


def _validate_key(key: str) -> None:
    if not isinstance(key, str) or not key or len(key.encode("utf-8")) > 1024:
        raise PublicReleaseError("object key is empty or exceeds 1024 bytes")
    if "\\" in key or key.startswith("/") or key.endswith("/") or "//" in key:
        raise PublicReleaseError(f"unsafe object key: {key!r}")
    parts = key.split("/")
    if any(part in {"", ".", ".."} or not _KEY_PART.fullmatch(part) for part in parts):
        raise PublicReleaseError(f"unsafe object key: {key!r}")


def _looks_like_ipv4(value: str) -> bool:
    parts = value.split(".")
    return len(parts) == 4 and all(part.isdigit() and 0 <= int(part) <= 255 for part in parts)


def _string_mapping(value: Mapping[Any, Any]) -> dict[str, str]:
    result: dict[str, str] = {}
    for key, item in value.items():
        if isinstance(key, str) and isinstance(item, str):
            result[key.casefold()] = item
    return result


def _validated_metadata(value: Mapping[Any, Any]) -> dict[str, str]:
    result = _string_mapping(value)
    if len(result) != len(value):
        raise PublicReleaseError("object store returned invalid custom metadata")
    for key, item in result.items():
        if (
            not key
            or len(key) > 128
            or not item
            or len(item) > 1024
            or any(character in key + item for character in "\r\n\x00")
        ):
            raise PublicReleaseError("object store returned unsafe custom metadata")
    return result


def _validate_header_value(value: str, label: str) -> str:
    if not value or len(value) > 1024 or any(character in value for character in "\r\n\x00"):
        raise PublicReleaseError(f"{label} is empty, unsafe, or too long")
    return value


def _response_header(value: object, label: str, key: str) -> str:
    if not isinstance(value, str):
        raise PublicReleaseError(f"object store returned an invalid {label} for {key!r}")
    try:
        return _validate_header_value(value, label)
    except PublicReleaseError:
        raise PublicReleaseError(f"object store returned an invalid {label} for {key!r}") from None


def _optional_etag(value: object, key: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise PublicReleaseError(f"object store returned an invalid ETag for {key!r}")
    return _validate_etag(value)


def _validate_etag(value: str) -> str:
    if not value or len(value) > 256 or any(character in value for character in "\r\n\x00"):
        raise PublicReleaseError("object store returned an unsafe ETag")
    return value


def _r2_error_code(exc: Exception) -> str | None:
    response = getattr(exc, "response", None)
    if not isinstance(response, Mapping):
        return None
    error = response.get("Error")
    if not isinstance(error, Mapping):
        return None
    code = error.get("Code")
    return code if isinstance(code, str) else None


def _json_bytes(value: Mapping[str, Any]) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode("utf-8")


def _parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    operation = parser.add_mutually_exclusive_group(required=True)
    operation.add_argument("--source", type=Path, help="audited public export directory")
    operation.add_argument("--rollback", help="verified historical release SHA-256 to repoint")
    destination = parser.add_mutually_exclusive_group(required=True)
    destination.add_argument(
        "--r2", action="store_true", help="publish to R2 using environment credentials"
    )
    destination.add_argument(
        "--local-root", type=Path, help="publish to a local object-store directory"
    )
    parser.add_argument("--prefix", default=DEFAULT_PREFIX)
    parser.add_argument("--history-limit", type=int, default=DEFAULT_HISTORY_LIMIT)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--publication-sequence", type=int)
    parser.add_argument("--publication-attempt", type=int)
    parser.add_argument("--source-revision")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv)
    try:
        publication = _publication_metadata(
            args.publication_sequence,
            args.publication_attempt,
            args.source_revision,
        )
        if args.r2 and publication is None:
            raise PublicReleaseError(
                "--r2 requires --publication-sequence, --publication-attempt, and --source-revision"
            )
        store: ReleaseStore
        if args.r2:
            store = R2ReleaseStore(R2Config.from_env())
        else:
            store = LocalReleaseStore(args.local_root)
        if args.rollback:
            result = rollback_public_release(
                store,
                args.rollback,
                prefix=args.prefix,
                dry_run=args.dry_run,
                history_limit=args.history_limit,
                publication_sequence=args.publication_sequence,
                publication_attempt=args.publication_attempt,
                source_revision=args.source_revision,
            )
        else:
            result = publish_public_release(
                args.source,
                store,
                prefix=args.prefix,
                dry_run=args.dry_run,
                history_limit=args.history_limit,
                publication_sequence=args.publication_sequence,
                publication_attempt=args.publication_attempt,
                source_revision=args.source_revision,
            )
    except PublicReleaseError as exc:
        print(f"Rufous public release failed: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(result.as_dict(), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
