"""Immutable shared-media publication tests."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from io import BytesIO
from pathlib import Path

import databox.public_media_release as public_media_release_module
import pytest
from databox.public_media_approval import (
    SELECTION_REASON,
    canonical_approval_json,
    empty_approval_ledger,
)
from databox.public_media_release import (
    DEFAULT_MEDIA_PREFIX,
    MEDIA_CONTENT_TYPE,
    publish_prepared_media,
    scan_prepared_media,
)
from databox.public_release import (
    IMMUTABLE_CACHE_CONTROL,
    LocalReleaseStore,
    PublicReleaseError,
    R2ReleaseStore,
    SourceObject,
)
from PIL import Image


def _webp(
    *,
    size: tuple[int, int] = (4, 3),
    color: tuple[int, int, int] = (180, 72, 42),
) -> bytes:
    output = BytesIO()
    Image.new("RGB", size, color).save(output, format="WEBP", lossless=True)
    return output.getvalue()


def _animated_webp() -> bytes:
    output = BytesIO()
    frames = [Image.new("RGB", (4, 3), color) for color in ((0, 0, 0), (255, 255, 255))]
    frames[0].save(
        output,
        format="WEBP",
        save_all=True,
        append_images=frames[1:],
        duration=100,
        loop=0,
        lossless=True,
    )
    return output.getvalue()


def _source(
    tmp_path: Path,
    payload: bytes | None = None,
    *,
    manifest_dimensions: tuple[int, int] = (4, 3),
) -> tuple[Path, str]:
    payload = payload if payload is not None else _webp(size=manifest_dimensions)
    digest = hashlib.sha256(payload).hexdigest()
    source = tmp_path / "prepared"
    path = source / "objects" / digest[:2] / f"{digest}.webp"
    path.parent.mkdir(parents=True)
    path.write_bytes(payload)
    manifest = {
        "schema_version": 1,
        "mode": "rufous-media-preparation",
        "generated_at": "2026-08-03T00:00:00Z",
        "items": [
            {
                "sha256": digest,
                "url": (
                    "https://rufous-data.loughondata.com/rufous-media/v1/objects/"
                    f"{digest[:2]}/{digest}.webp"
                ),
                "mime_type": "image/webp",
                "width": manifest_dimensions[0],
                "height": manifest_dimensions[1],
                "scientific_name": "Selasphorus rufus",
                "source_page_url": "https://www.fws.gov/media/rufous-hummingbird-test",
            }
        ],
        "counts": {"items": 1, "objects": 1, "species": 1},
    }
    (source / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    return source, digest


def _add_source_object(
    source: Path,
    payload: bytes,
    *,
    manifest_dimensions: tuple[int, int] = (4, 3),
) -> str:
    digest = hashlib.sha256(payload).hexdigest()
    path = source / "objects" / digest[:2] / f"{digest}.webp"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(payload)
    manifest_path = source / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["items"].append(
        {
            "sha256": digest,
            "url": (
                "https://rufous-data.loughondata.com/rufous-media/v1/objects/"
                f"{digest[:2]}/{digest}.webp"
            ),
            "mime_type": "image/webp",
            "width": manifest_dimensions[0],
            "height": manifest_dimensions[1],
            "scientific_name": "Selasphorus rufus",
            "source_page_url": f"https://www.fws.gov/media/rufous-{digest[:12]}",
        }
    )
    manifest["counts"]["items"] += 1
    manifest["counts"]["objects"] += 1
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    return digest


def _approvals(tmp_path: Path, source: Path, digest: str, *, approved: bool = True) -> Path:
    manifest = json.loads((source / "manifest.json").read_text(encoding="utf-8"))
    matching = [item for item in manifest["items"] if item["sha256"] == digest]
    payload = empty_approval_ledger()
    if approved:
        payload["selections"] = [
            {
                "sha256": digest,
                "decision": "selected",
                "reason": SELECTION_REASON,
                "reviewed_at": "2026-08-03",
                "reviewed_by": "Test Human",
                "scientific_name": matching[0]["scientific_name"],
                "source_page_urls": sorted({item["source_page_url"] for item in matching}),
            }
        ]
    path = tmp_path / "approvals.json"
    path.write_bytes(canonical_approval_json(payload))
    return path


def _set_inaturalist_provider(source: Path, *, photo_id: int = 2498155) -> None:
    manifest_path = source / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["items"][0]["provider"] = "inaturalist"
    manifest["items"][0]["source_page_url"] = f"https://www.inaturalist.org/photos/{photo_id}"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")


def _set_wikimedia_provider(source: Path) -> None:
    manifest_path = source / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["items"][0]["provider"] = "wikimedia"
    manifest["items"][0]["source_page_url"] = (
        "https://commons.wikimedia.org/wiki/File:Rufous_Hummingbird.jpg"
    )
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")


def _add_unrelated_usfws_selection(approvals: Path) -> None:
    payload = json.loads(approvals.read_text(encoding="utf-8"))
    payload["selections"].append(
        {
            "sha256": "a" * 64,
            "decision": "selected",
            "reason": SELECTION_REASON,
            "reviewed_at": "2026-08-03",
            "reviewed_by": "Test Human",
            "scientific_name": "Calypte anna",
            "source_page_urls": ["https://www.fws.gov/media/anna-test"],
        }
    )
    payload["selections"].sort(
        key=lambda item: (item["scientific_name"].casefold(), item["sha256"])
    )
    approvals.write_bytes(canonical_approval_json(payload))


def test_scan_binds_webp_bytes_to_exact_content_address(tmp_path: Path) -> None:
    source, digest = _source(tmp_path)

    objects = scan_prepared_media(source)

    assert len(objects) == 1
    assert objects[0].sha256 == digest
    assert objects[0].relative_path == f"{digest[:2]}/{digest}.webp"
    assert objects[0].content_type == MEDIA_CONTENT_TYPE


def test_publish_creates_once_then_verifies_and_reuses(tmp_path: Path) -> None:
    source, digest = _source(tmp_path)
    store = LocalReleaseStore(tmp_path / "store")

    first = publish_prepared_media(source, store)
    second = publish_prepared_media(source, store)

    key = f"{DEFAULT_MEDIA_PREFIX}/{digest[:2]}/{digest}.webp"
    head = store.head_object(key)
    assert first.uploaded_objects == 1
    assert first.reused_objects == 0
    assert second.uploaded_objects == 0
    assert second.reused_objects == 1
    assert head is not None
    assert head.content_type == MEDIA_CONTENT_TYPE
    assert head.cache_control == IMMUTABLE_CACHE_CONTROL
    assert head.metadata == {
        "sha256": digest,
        "role": "media",
        "schema": "rufous-media-v1",
    }


def test_dry_run_writes_nothing(tmp_path: Path) -> None:
    source, digest = _source(tmp_path)
    store = LocalReleaseStore(tmp_path / "store")

    result = publish_prepared_media(source, store, dry_run=True)

    assert result.status == "dry-run"
    assert result.uploaded_objects == 1
    key = f"{DEFAULT_MEDIA_PREFIX}/{digest[:2]}/{digest}.webp"
    assert store.head_object(key) is None


def test_explicit_visual_approval_is_checked_before_local_store_access(tmp_path: Path) -> None:
    source, digest = _source(tmp_path)
    store = LocalReleaseStore(tmp_path / "store")
    approvals = _approvals(tmp_path, source, digest, approved=False)

    with pytest.raises(PublicReleaseError, match="lack a committed human image selection"):
        publish_prepared_media(source, store, approval_path=approvals)

    target = store.root / DEFAULT_MEDIA_PREFIX / digest[:2] / f"{digest}.webp"
    assert not target.exists()


def test_approved_media_can_exercise_local_publisher(tmp_path: Path) -> None:
    source, digest = _source(tmp_path)
    approvals = _approvals(tmp_path, source, digest)
    store = LocalReleaseStore(tmp_path / "store")

    result = publish_prepared_media(source, store, approval_path=approvals)

    assert result.uploaded_objects == 1
    assert store.head_object(f"{DEFAULT_MEDIA_PREFIX}/{digest[:2]}/{digest}.webp") is not None


def test_inaturalist_scoped_publish_uses_only_scoped_ledger_and_object(
    tmp_path: Path,
) -> None:
    source, digest = _source(tmp_path)
    _set_inaturalist_provider(source)
    approvals = _approvals(tmp_path, source, digest)
    _add_unrelated_usfws_selection(approvals)
    store = LocalReleaseStore(tmp_path / "store")

    result = publish_prepared_media(
        source,
        store,
        approval_path=approvals,
        provider="inaturalist",
    )

    assert result.file_count == 1
    assert result.uploaded_objects == 1
    assert store.head_object(f"{DEFAULT_MEDIA_PREFIX}/{digest[:2]}/{digest}.webp") is not None


def test_provider_scoped_publish_requires_approvals_even_for_local_store(
    tmp_path: Path,
) -> None:
    source, _ = _source(tmp_path)
    _set_inaturalist_provider(source)

    with pytest.raises(PublicReleaseError, match="provider-scoped.*requires"):
        publish_prepared_media(
            source,
            LocalReleaseStore(tmp_path / "store"),
            provider="inaturalist",
        )


def test_inaturalist_scoped_publish_rejects_mixed_manifest_before_store_access(
    tmp_path: Path,
) -> None:
    source, digest = _source(tmp_path)
    _set_inaturalist_provider(source)
    _add_source_object(source, _webp(color=(30, 120, 180)))
    approvals = _approvals(tmp_path, source, digest)
    store = LocalReleaseStore(tmp_path / "store")

    with pytest.raises(PublicReleaseError, match="outside the requested inaturalist"):
        publish_prepared_media(
            source,
            store,
            approval_path=approvals,
            provider="inaturalist",
        )

    assert not [path for path in store.root.rglob("*") if path.is_file()]


def test_local_cli_accepts_inaturalist_provider_scope(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    source, digest = _source(tmp_path)
    _set_inaturalist_provider(source)
    approvals = _approvals(tmp_path, source, digest)

    result = public_media_release_module.main(
        [
            "--source",
            str(source),
            "--local-root",
            str(tmp_path / "store"),
            "--approvals",
            str(approvals),
            "--provider",
            "inaturalist",
        ]
    )

    assert result == 0
    output = json.loads(capsys.readouterr().out)
    assert output["file_count"] == 1


def test_local_cli_accepts_wikimedia_provider_scope(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    source, digest = _source(tmp_path)
    _set_wikimedia_provider(source)
    approvals = _approvals(tmp_path, source, digest)

    result = public_media_release_module.main(
        [
            "--source",
            str(source),
            "--local-root",
            str(tmp_path / "store"),
            "--approvals",
            str(approvals),
            "--provider",
            "wikimedia",
        ]
    )

    assert result == 0
    output = json.loads(capsys.readouterr().out)
    assert output["file_count"] == 1
    assert output["uploaded_objects"] == 1


def test_publisher_ignores_and_never_uploads_unselected_candidate(tmp_path: Path) -> None:
    source, selected = _source(tmp_path)
    unselected = _add_source_object(
        source,
        _webp(color=(30, 120, 180)),
    )
    # Even damaged unselected bytes cannot block a selected production image.
    unselected_path = source / "objects" / unselected[:2] / f"{unselected}.webp"
    unselected_path.write_bytes(b"not an image")
    approvals = _approvals(tmp_path, source, selected)
    store = LocalReleaseStore(tmp_path / "store")

    result = publish_prepared_media(source, store, approval_path=approvals)

    assert result.file_count == 1
    assert result.uploaded_objects == 1
    assert store.head_object(f"{DEFAULT_MEDIA_PREFIX}/{selected[:2]}/{selected}.webp") is not None
    assert store.head_object(f"{DEFAULT_MEDIA_PREFIX}/{unselected[:2]}/{unselected}.webp") is None


def test_r2_media_publisher_requires_approval_even_for_direct_library_call(
    tmp_path: Path,
) -> None:
    source, _ = _source(tmp_path)
    store = object.__new__(R2ReleaseStore)

    with pytest.raises(PublicReleaseError, match="requires a human visual-approval ledger"):
        publish_prepared_media(source, store)


def test_r2_cli_requires_approval_before_loading_cloud_configuration(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    source, _ = _source(tmp_path)

    assert public_media_release_module.main(["--source", str(source), "--r2"]) == 2
    assert "requires --approvals" in capsys.readouterr().err


def test_scan_rejects_hash_path_manifest_and_format_mismatches(tmp_path: Path) -> None:
    source, digest = _source(tmp_path)
    path = next((source / "objects").rglob("*.webp"))
    valid_payload = path.read_bytes()
    path.write_bytes(b"not webp")
    with pytest.raises(PublicReleaseError, match="fully decodable WebP|hash does not match"):
        scan_prepared_media(source)

    path.write_bytes(valid_payload)
    manifest_path = source / "manifest.json"
    manifest = json.loads(manifest_path.read_text())
    manifest["items"][0]["url"] = manifest["items"][0]["url"].replace(digest, "f" * 64)
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(PublicReleaseError, match="invalid object identity"):
        scan_prepared_media(source)


def test_scan_rejects_header_spoof_and_truncated_webp(tmp_path: Path) -> None:
    spoof = b"RIFF\x04\x00\x00\x00WEBP"
    source, _ = _source(tmp_path, spoof)
    with pytest.raises(PublicReleaseError, match="fully decodable WebP"):
        scan_prepared_media(source)

    valid = _webp()
    source, _ = _source(tmp_path, valid[:-5])
    with pytest.raises(PublicReleaseError, match="fully decodable WebP"):
        scan_prepared_media(source)


def test_scan_requires_exact_manifest_dimensions(tmp_path: Path) -> None:
    source, _ = _source(
        tmp_path,
        _webp(size=(5, 3)),
        manifest_dimensions=(4, 3),
    )

    with pytest.raises(PublicReleaseError, match="dimensions do not match"):
        scan_prepared_media(source)


def test_scan_rejects_animated_webp(tmp_path: Path) -> None:
    source, _ = _source(tmp_path, _animated_webp())

    with pytest.raises(PublicReleaseError, match="animated"):
        scan_prepared_media(source)


def test_scan_rejects_manifest_and_decoded_dimension_limits(tmp_path: Path) -> None:
    source, _ = _source(tmp_path, manifest_dimensions=(651, 1))
    with pytest.raises(PublicReleaseError, match="invalid object identity"):
        scan_prepared_media(source)

    source, _ = _source(
        tmp_path / "decoded",
        _webp(size=(651, 1)),
        manifest_dimensions=(650, 1),
    )
    with pytest.raises(PublicReleaseError, match="pixel limits"):
        scan_prepared_media(source)


def test_scan_rejects_conflicting_dimensions_for_shared_object(tmp_path: Path) -> None:
    source, _ = _source(tmp_path)
    manifest_path = source / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    duplicate = dict(manifest["items"][0])
    duplicate["width"] = 3
    manifest["items"].append(duplicate)
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(PublicReleaseError, match="conflicts on shared object dimensions"):
        scan_prepared_media(source)


@pytest.mark.parametrize(
    "prefix",
    ["", "/", "../rufous-media", "rufous-media//objects", "rufous media"],
)
def test_publish_rejects_unsafe_prefixes(tmp_path: Path, prefix: str) -> None:
    source, _ = _source(tmp_path)
    with pytest.raises(PublicReleaseError, match="prefix is unsafe"):
        publish_prepared_media(source, LocalReleaseStore(tmp_path / "store"), prefix=prefix)


@pytest.mark.parametrize(
    "prefix",
    [
        "rufous-media/v2/objects",
        "rufous-media/v1",
        "another-safe-prefix",
        "/rufous-media/v1/objects/",
    ],
)
def test_publish_rejects_safe_but_noncanonical_prefixes(tmp_path: Path, prefix: str) -> None:
    source, _ = _source(tmp_path)
    store = LocalReleaseStore(tmp_path / "store")

    with pytest.raises(PublicReleaseError, match="canonical"):
        publish_prepared_media(source, store, prefix=prefix)

    assert not [path for path in store.root.rglob("*") if path.is_file()]


def test_existing_object_with_wrong_immutable_metadata_fails_closed(tmp_path: Path) -> None:
    source, digest = _source(tmp_path)
    store = LocalReleaseStore(tmp_path / "store")
    object_source = scan_prepared_media(source)[0]
    key = f"{DEFAULT_MEDIA_PREFIX}/{digest[:2]}/{digest}.webp"
    store.put_file(
        key,
        object_source,
        cache_control="public,max-age=60",
        metadata={"sha256": digest, "role": "media", "schema": "rufous-media-v1"},
        if_none_match=True,
    )

    with pytest.raises(PublicReleaseError, match="immutable media collision"):
        publish_prepared_media(source, store)


def test_reused_same_size_wrong_bytes_fail_closed(tmp_path: Path) -> None:
    source, digest = _source(tmp_path)
    store = LocalReleaseStore(tmp_path / "store")
    publish_prepared_media(source, store)
    key = f"{DEFAULT_MEDIA_PREFIX}/{digest[:2]}/{digest}.webp"
    target = store.root.joinpath(*key.split("/"))
    original = target.read_bytes()
    target.write_bytes(original[:-1] + bytes([original[-1] ^ 1]))

    with pytest.raises(PublicReleaseError, match="failed byte verification"):
        publish_prepared_media(source, store)


def test_fresh_upload_is_read_back_and_same_size_corruption_fails(tmp_path: Path) -> None:
    class CorruptingStore(LocalReleaseStore):
        def put_file(
            self,
            key: str,
            source: SourceObject,
            *,
            cache_control: str,
            metadata: Mapping[str, str],
            if_none_match: bool,
        ) -> None:
            super().put_file(
                key,
                source,
                cache_control=cache_control,
                metadata=metadata,
                if_none_match=if_none_match,
            )
            target = self.root.joinpath(*key.split("/"))
            original = target.read_bytes()
            target.write_bytes(original[:-1] + bytes([original[-1] ^ 1]))

    source, _ = _source(tmp_path)

    with pytest.raises(PublicReleaseError, match="failed byte verification"):
        publish_prepared_media(source, CorruptingStore(tmp_path / "store"))


def test_all_remote_objects_are_preflighted_before_any_write(tmp_path: Path) -> None:
    source, _ = _source(tmp_path)
    _add_source_object(source, _webp(color=(42, 90, 180)))
    objects = scan_prepared_media(source)
    missing, collision = objects
    store = LocalReleaseStore(tmp_path / "store")
    collision_key = f"{DEFAULT_MEDIA_PREFIX}/{collision.relative_path}"
    store.put_file(
        collision_key,
        collision,
        cache_control=IMMUTABLE_CACHE_CONTROL,
        metadata={
            "sha256": collision.sha256,
            "role": "media",
            "schema": "rufous-media-v1",
        },
        if_none_match=True,
    )
    collision_target = store.root.joinpath(*collision_key.split("/"))
    collision_payload = collision_target.read_bytes()
    collision_target.write_bytes(collision_payload[:-1] + bytes([collision_payload[-1] ^ 1]))

    with pytest.raises(PublicReleaseError, match="failed byte verification"):
        publish_prepared_media(source, store)

    missing_key = f"{DEFAULT_MEDIA_PREFIX}/{missing.relative_path}"
    assert store.head_object(missing_key) is None


def test_new_upload_and_projected_prefix_limits_fail_before_writes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source, digest = _source(tmp_path)
    source_size = next((source / "objects").rglob("*.webp")).stat().st_size
    store = LocalReleaseStore(tmp_path / "store")
    legacy_payload = b"legacy-object"
    store.put_bytes(
        f"{DEFAULT_MEDIA_PREFIX}/legacy/object.bin",
        legacy_payload,
        content_type="application/octet-stream",
        cache_control=IMMUTABLE_CACHE_CONTROL,
        metadata={"role": "legacy"},
        if_none_match=True,
    )
    target_key = f"{DEFAULT_MEDIA_PREFIX}/{digest[:2]}/{digest}.webp"

    monkeypatch.setattr(public_media_release_module, "MAX_NEW_MEDIA_BYTES", source_size - 1)
    with pytest.raises(PublicReleaseError, match="new-upload byte limit"):
        publish_prepared_media(source, store)
    assert store.head_object(target_key) is None

    monkeypatch.setattr(public_media_release_module, "MAX_NEW_MEDIA_BYTES", source_size)
    monkeypatch.setattr(
        public_media_release_module,
        "MAX_MEDIA_PREFIX_BYTES",
        len(legacy_payload) + source_size - 1,
    )
    with pytest.raises(PublicReleaseError, match="cumulative byte limit"):
        publish_prepared_media(source, store)
    assert store.head_object(target_key) is None


def test_manifest_cannot_omit_or_smuggle_an_object(tmp_path: Path) -> None:
    source, _ = _source(tmp_path)
    extra = _webp(color=(42, 90, 180))
    digest = hashlib.sha256(extra).hexdigest()
    path = source / "objects" / digest[:2] / f"{digest}.webp"
    path.parent.mkdir(parents=True)
    path.write_bytes(extra)

    with pytest.raises(PublicReleaseError, match="manifest and object set do not match"):
        scan_prepared_media(source)
