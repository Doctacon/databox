"""Publish prepared Rufous bird images as immutable content-addressed objects.

The public data release remains JSON-only and atomic.  This publisher owns the
separate shared media namespace referenced by those JSON files.  It never
creates a mutable pointer and never overwrites or deletes an object.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import re
import sys
from collections.abc import Mapping
from dataclasses import asdict, dataclass
from io import BytesIO
from pathlib import Path
from typing import Any

from PIL import Image, UnidentifiedImageError

from databox.public_media_approval import MediaApprovalError, require_visual_approvals
from databox.public_release import (
    IMMUTABLE_CACHE_CONTROL,
    LocalReleaseStore,
    ObjectValue,
    PrefixUsageStore,
    PublicReleaseError,
    R2Config,
    R2ReleaseStore,
    SourceObject,
)

MEDIA_SCHEMA_VERSION = 1
DEFAULT_MEDIA_PREFIX = "rufous-media/v1/objects"
MEDIA_CONTENT_TYPE = "image/webp"
MAX_MEDIA_OBJECT_BYTES = 1 * 1024 * 1024
MAX_MEDIA_WIDTH = 650
MAX_MEDIA_HEIGHT = 650
MAX_MEDIA_PIXELS = MAX_MEDIA_WIDTH * MAX_MEDIA_HEIGHT
MAX_MEDIA_OBJECTS = 10_000
MAX_MEDIA_TOTAL_BYTES = 2 * 1024 * 1024 * 1024
MAX_NEW_MEDIA_OBJECTS = 5_000
MAX_NEW_MEDIA_BYTES = 1 * 1024 * 1024 * 1024
MAX_MEDIA_PREFIX_OBJECTS = 20_000
MAX_MEDIA_PREFIX_BYTES = 5 * 1024 * 1024 * 1024

_SHA256 = re.compile(r"^[a-f0-9]{64}$")
_PREFIX = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._/-]{0,500}$")
_PUBLIC_URL = re.compile(
    r"^https://rufous-data\.loughondata\.com/rufous-media/v1/objects/"
    r"(?P<shard>[a-f0-9]{2})/(?P<sha>[a-f0-9]{64})\.webp$"
)
_MEDIA_PROVIDERS = frozenset({"usfws", "inaturalist", "wikimedia"})


@dataclass(frozen=True)
class MediaPublishResult:
    """Summary suitable for CI logs without exposing credentials or source URLs."""

    status: str
    dry_run: bool
    file_count: int
    total_bytes: int
    uploaded_objects: int
    reused_objects: int
    prefix: str


def _clean_prefix(prefix: str) -> str:
    value = prefix.strip().strip("/")
    if (
        not value
        or not _PREFIX.fullmatch(value)
        or "//" in value
        or any(part in {"", ".", ".."} for part in value.split("/"))
    ):
        raise PublicReleaseError("media prefix is unsafe")
    return value


def _hash_file(path: Path) -> tuple[str, str]:
    sha256 = hashlib.sha256()
    md5 = hashlib.md5(usedforsecurity=False)
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            sha256.update(chunk)
            md5.update(chunk)
    return sha256.hexdigest(), base64.b64encode(md5.digest()).decode()


def _assert_webp_properties(
    image: Image.Image,
    *,
    expected_dimensions: tuple[int, int] | None,
    label: str,
) -> tuple[int, int]:
    width, height = image.size
    if image.format != "WEBP":
        raise PublicReleaseError(f"prepared media object is not WebP: {label}")
    if (
        width < 1
        or height < 1
        or width > MAX_MEDIA_WIDTH
        or height > MAX_MEDIA_HEIGHT
        or width * height > MAX_MEDIA_PIXELS
    ):
        raise PublicReleaseError(f"prepared media object exceeds its pixel limits: {label}")
    if getattr(image, "n_frames", 1) != 1 or bool(getattr(image, "is_animated", False)):
        raise PublicReleaseError(f"prepared media object is animated: {label}")
    if expected_dimensions is not None and (width, height) != expected_dimensions:
        raise PublicReleaseError(
            f"prepared media object dimensions do not match its manifest: {label}"
        )
    return width, height


def _verify_webp_file(
    path: Path,
    *,
    expected_dimensions: tuple[int, int] | None,
    label: str,
) -> tuple[int, int]:
    """Verify and fully decode one bounded local WebP."""
    try:
        with Image.open(path) as image:
            dimensions = _assert_webp_properties(
                image,
                expected_dimensions=expected_dimensions,
                label=label,
            )
            image.verify()
        with Image.open(path) as image:
            _assert_webp_properties(
                image,
                expected_dimensions=dimensions,
                label=label,
            )
            image.load()
    except PublicReleaseError:
        raise
    except (Image.DecompressionBombError, UnidentifiedImageError, OSError, ValueError):
        raise PublicReleaseError(
            f"prepared media object is not a valid fully decodable WebP: {label}"
        ) from None
    return dimensions


def _verify_webp_payload(
    payload: bytes,
    *,
    expected_dimensions: tuple[int, int],
    label: str,
) -> None:
    """Apply the same bounded decoder checks to a read-back object."""
    if not payload or len(payload) > MAX_MEDIA_OBJECT_BYTES:
        raise PublicReleaseError(f"immutable media object exceeds its size limit at {label!r}")
    try:
        with Image.open(BytesIO(payload)) as image:
            _assert_webp_properties(
                image,
                expected_dimensions=expected_dimensions,
                label=label,
            )
            image.verify()
        with Image.open(BytesIO(payload)) as image:
            _assert_webp_properties(
                image,
                expected_dimensions=expected_dimensions,
                label=label,
            )
            image.load()
    except PublicReleaseError:
        raise
    except (Image.DecompressionBombError, UnidentifiedImageError, OSError, ValueError):
        raise PublicReleaseError(
            f"immutable media object is not a valid fully decodable WebP at {label!r}"
        ) from None


def _load_manifest(source_dir: Path) -> dict[str, Any]:
    path = source_dir / "manifest.json"
    if path.is_symlink() or not path.is_file() or path.stat().st_size > 25 * 1024 * 1024:
        raise PublicReleaseError("prepared media manifest is missing or unsafe")
    try:
        payload = json.loads(path.read_bytes())
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        raise PublicReleaseError("prepared media manifest is invalid UTF-8 JSON") from None
    if not isinstance(payload, dict):
        raise PublicReleaseError("prepared media manifest must be an object")
    if payload.get("schema_version") != MEDIA_SCHEMA_VERSION:
        raise PublicReleaseError("prepared media manifest has an unsupported schema version")
    if payload.get("mode") != "rufous-media-preparation":
        raise PublicReleaseError("prepared media manifest has an invalid mode")
    if not isinstance(payload.get("items"), list) or not payload["items"]:
        raise PublicReleaseError("prepared media manifest must contain media items")
    return payload


def scan_prepared_media(
    source_dir: Path,
    *,
    selected_sha256s: frozenset[str] | None = None,
) -> list[SourceObject]:
    """Validate and bind prepared WebPs to their content-addressed names.

    A production selection scans only the selected pixel objects.  Unselected
    candidates remain local preparation output and cannot block or enter the
    immutable public namespace.
    """
    root = source_dir.resolve()
    if source_dir.is_symlink() or not root.is_dir():
        raise PublicReleaseError("prepared media source is not a real directory")
    manifest = _load_manifest(root)
    expected_hashes: set[str] = set()
    expected_dimensions: dict[str, tuple[int, int]] = {}
    for index, item in enumerate(manifest["items"]):
        if not isinstance(item, dict):
            raise PublicReleaseError(f"prepared media item {index} is malformed")
        sha256 = item.get("sha256")
        url = item.get("url")
        mime_type = item.get("mime_type")
        width = item.get("width")
        height = item.get("height")
        match = _PUBLIC_URL.fullmatch(url) if isinstance(url, str) else None
        if (
            not isinstance(sha256, str)
            or not _SHA256.fullmatch(sha256)
            or match is None
            or match.group("sha") != sha256
            or match.group("shard") != sha256[:2]
            or mime_type != MEDIA_CONTENT_TYPE
            or type(width) is not int
            or type(height) is not int
            or not 1 <= width <= MAX_MEDIA_WIDTH
            or not 1 <= height <= MAX_MEDIA_HEIGHT
            or width * height > MAX_MEDIA_PIXELS
        ):
            raise PublicReleaseError(f"prepared media item {index} has an invalid object identity")
        dimensions = (width, height)
        existing_dimensions = expected_dimensions.get(sha256)
        if existing_dimensions is not None and existing_dimensions != dimensions:
            raise PublicReleaseError(
                f"prepared media item {index} conflicts on shared object dimensions"
            )
        expected_dimensions[sha256] = dimensions
        expected_hashes.add(sha256)

    if selected_sha256s is not None:
        if (
            not selected_sha256s
            or any(not _SHA256.fullmatch(value) for value in selected_sha256s)
            or not selected_sha256s.issubset(expected_hashes)
        ):
            raise PublicReleaseError("selected media objects do not match the prepared manifest")
        scanned_hashes = set(selected_sha256s)
    else:
        scanned_hashes = expected_hashes

    object_root = root / "objects"
    if object_root.is_symlink() or not object_root.is_dir():
        raise PublicReleaseError("prepared media objects directory is missing or unsafe")
    paths = sorted(object_root.rglob("*.webp"))
    if not paths or len(paths) > MAX_MEDIA_OBJECTS:
        raise PublicReleaseError("prepared media object count is empty or exceeds the limit")
    objects: list[SourceObject] = []
    actual_hashes: set[str] = set()
    total_bytes = 0
    for path in paths:
        if path.is_symlink() or not path.is_file():
            raise PublicReleaseError("prepared media contains a non-regular object")
        try:
            relative = path.relative_to(object_root)
        except ValueError:
            raise PublicReleaseError("prepared media object escapes its source root") from None
        if len(relative.parts) != 2:
            raise PublicReleaseError(f"prepared media object has an invalid path: {relative}")
        shard, filename = relative.parts
        sha_from_name = filename.removesuffix(".webp")
        if (
            not _SHA256.fullmatch(sha_from_name)
            or shard != sha_from_name[:2]
            or filename != f"{sha_from_name}.webp"
        ):
            raise PublicReleaseError(f"prepared media object has an invalid path: {relative}")
        if selected_sha256s is not None and sha_from_name not in scanned_hashes:
            continue
        size = path.stat().st_size
        if size <= 0 or size > MAX_MEDIA_OBJECT_BYTES:
            raise PublicReleaseError(f"prepared media object exceeds its size limit: {relative}")
        _verify_webp_file(
            path,
            expected_dimensions=expected_dimensions.get(sha_from_name),
            label=str(relative),
        )
        digest, content_md5 = _hash_file(path)
        if digest != sha_from_name:
            raise PublicReleaseError(f"prepared media object hash does not match: {relative}")
        total_bytes += size
        if total_bytes > MAX_MEDIA_TOTAL_BYTES:
            raise PublicReleaseError("prepared media exceeds its total byte limit")
        actual_hashes.add(digest)
        objects.append(
            SourceObject(
                path=path,
                relative_path=f"{shard}/{filename}",
                size=size,
                sha256=digest,
                content_md5=content_md5,
                content_type=MEDIA_CONTENT_TYPE,
            )
        )
    if actual_hashes != scanned_hashes:
        raise PublicReleaseError("prepared media manifest and object set do not match")
    counts = manifest.get("counts")
    if not isinstance(counts, dict) or counts.get("objects") != len(expected_hashes):
        raise PublicReleaseError("prepared media manifest object count does not match")
    return objects


def _assert_source_unchanged(source: SourceObject) -> None:
    if source.path.is_symlink() or not source.path.is_file():
        raise PublicReleaseError(f"media source changed while publishing {source.relative_path!r}")
    digest, content_md5 = _hash_file(source.path)
    if (
        source.path.stat().st_size != source.size
        or digest != source.sha256
        or content_md5 != source.content_md5
    ):
        raise PublicReleaseError(f"media source changed while publishing {source.relative_path!r}")


def _metadata(sha256: str) -> dict[str, str]:
    return {"sha256": sha256, "role": "media", "schema": "rufous-media-v1"}


def _assert_existing(source: SourceObject, key: str, value: ObjectValue) -> None:
    head = value.head
    metadata = head.metadata
    if (
        head.size != source.size
        or len(value.payload) != source.size
        or head.content_type != MEDIA_CONTENT_TYPE
        or head.cache_control != IMMUTABLE_CACHE_CONTROL
        or not isinstance(metadata, Mapping)
    ):
        raise PublicReleaseError(f"immutable media collision at {key!r}")
    expected = _metadata(source.sha256)
    if any(metadata.get(name) != value for name, value in expected.items()):
        raise PublicReleaseError(f"immutable media collision at {key!r}")
    digest = hashlib.sha256(value.payload).hexdigest()
    if digest != source.sha256:
        raise PublicReleaseError(f"immutable media object failed byte verification at {key!r}")
    expected_dimensions = _verify_webp_file(
        source.path,
        expected_dimensions=None,
        label=source.relative_path,
    )
    _verify_webp_payload(
        value.payload,
        expected_dimensions=expected_dimensions,
        label=key,
    )


def _assert_batch_limits(objects: list[SourceObject]) -> int:
    total_bytes = sum(item.size for item in objects)
    if len(objects) > MAX_MEDIA_OBJECTS:
        raise PublicReleaseError("prepared media exceeds its batch object-count limit")
    if total_bytes > MAX_MEDIA_TOTAL_BYTES:
        raise PublicReleaseError("prepared media exceeds its batch byte limit")
    return total_bytes


def _assert_new_upload_limits(objects: list[SourceObject]) -> int:
    total_bytes = sum(item.size for item in objects)
    if len(objects) > MAX_NEW_MEDIA_OBJECTS:
        raise PublicReleaseError("prepared media exceeds its new-upload object-count limit")
    if total_bytes > MAX_NEW_MEDIA_BYTES:
        raise PublicReleaseError("prepared media exceeds its new-upload byte limit")
    return total_bytes


def _assert_projected_prefix_usage(
    store: PrefixUsageStore,
    *,
    prefix: str,
    new_objects: list[SourceObject],
) -> None:
    usage = store.prefix_usage(
        prefix,
        maximum_objects=MAX_MEDIA_PREFIX_OBJECTS,
        maximum_bytes=MAX_MEDIA_PREFIX_BYTES,
    )
    projected_count = usage.object_count + len(new_objects)
    projected_bytes = usage.total_bytes + sum(item.size for item in new_objects)
    if projected_count > MAX_MEDIA_PREFIX_OBJECTS:
        raise PublicReleaseError("media prefix would exceed its cumulative object-count limit")
    if projected_bytes > MAX_MEDIA_PREFIX_BYTES:
        raise PublicReleaseError("media prefix would exceed its cumulative byte limit")


def publish_prepared_media(
    source_dir: Path,
    store: PrefixUsageStore,
    *,
    prefix: str = DEFAULT_MEDIA_PREFIX,
    dry_run: bool = False,
    approval_path: Path | None = None,
    provider: str | None = None,
) -> MediaPublishResult:
    """Create missing media objects, verify existing ones, and mutate nothing else."""
    if provider is not None and provider not in _MEDIA_PROVIDERS:
        raise PublicReleaseError("media provider scope is not reviewed")
    if provider is not None and approval_path is None:
        raise PublicReleaseError(
            "provider-scoped media publication requires a human visual-approval ledger"
        )
    if approval_path is None and not isinstance(store, LocalReleaseStore):
        raise PublicReleaseError("remote media publication requires a human visual-approval ledger")
    selected_sha256s: frozenset[str] | None = None
    if approval_path is not None:
        try:
            media_plan = require_visual_approvals(
                source_dir / "manifest.json",
                approval_path,
                provider=provider,
            )
        except MediaApprovalError as exc:
            raise PublicReleaseError(f"media visual approval failed: {exc}") from None
        selected_sha256s = media_plan.selected_sha256s
    clean_prefix = _clean_prefix(prefix)
    if prefix != DEFAULT_MEDIA_PREFIX or clean_prefix != DEFAULT_MEDIA_PREFIX:
        raise PublicReleaseError(
            f"media prefix must be the canonical {DEFAULT_MEDIA_PREFIX!r} namespace"
        )
    objects = scan_prepared_media(source_dir, selected_sha256s=selected_sha256s)
    total_bytes = _assert_batch_limits(objects)
    pending: list[tuple[SourceObject, str]] = []
    reused = 0

    # Complete the entire source and remote-object preflight before the first write.
    for source in objects:
        _assert_source_unchanged(source)
        key = f"{clean_prefix}/{source.relative_path}"
        existing = store.read_object(key, maximum=MAX_MEDIA_OBJECT_BYTES)
        if existing is not None:
            _assert_existing(source, key, existing)
            reused += 1
            continue
        pending.append((source, key))

    new_objects = [source for source, _ in pending]
    _assert_new_upload_limits(new_objects)
    _assert_projected_prefix_usage(store, prefix=clean_prefix, new_objects=new_objects)

    if not dry_run:
        for source, key in pending:
            _assert_source_unchanged(source)
            store.put_file(
                key,
                source,
                cache_control=IMMUTABLE_CACHE_CONTROL,
                metadata=_metadata(source.sha256),
                if_none_match=True,
            )
            created = store.read_object(key, maximum=MAX_MEDIA_OBJECT_BYTES)
            if created is None:
                raise PublicReleaseError(f"uploaded media object is not readable at {key!r}")
            _assert_existing(source, key, created)
    return MediaPublishResult(
        status="dry-run" if dry_run else "published",
        dry_run=dry_run,
        file_count=len(objects),
        total_bytes=total_bytes,
        uploaded_objects=len(pending),
        reused_objects=reused,
        prefix=clean_prefix,
    )


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", required=True, type=Path)
    destination = parser.add_mutually_exclusive_group(required=True)
    destination.add_argument("--local-root", type=Path)
    destination.add_argument("--r2", action="store_true")
    parser.add_argument("--prefix", default=DEFAULT_MEDIA_PREFIX)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--approvals", type=Path)
    parser.add_argument("--provider", choices=sorted(_MEDIA_PROVIDERS))
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    try:
        store: PrefixUsageStore
        if args.r2:
            if args.approvals is None:
                raise PublicReleaseError(
                    "R2 media publication requires --approvals with the committed human ledger"
                )
            try:
                require_visual_approvals(
                    args.source / "manifest.json",
                    args.approvals,
                    provider=args.provider,
                )
            except MediaApprovalError as exc:
                raise PublicReleaseError(f"media visual approval failed: {exc}") from None
            store = R2ReleaseStore(R2Config.from_env())
        else:
            store = LocalReleaseStore(args.local_root)
        result = publish_prepared_media(
            args.source,
            store,
            prefix=args.prefix,
            dry_run=args.dry_run,
            approval_path=args.approvals,
            provider=args.provider,
        )
    except PublicReleaseError as exc:
        print(f"Rufous media release failed: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(asdict(result), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
