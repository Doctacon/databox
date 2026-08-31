"""Atomic publication tests for sanitized Rufous release artifacts."""

from __future__ import annotations

import base64
import hashlib
import io
import json
from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import databox.public_release as public_release_module
import pytest
from databox.public_export import export_public_data, semantic_data_version
from databox.public_release import (
    IMMUTABLE_CACHE_CONTROL,
    POINTER_CACHE_CONTROL,
    LocalReleaseStore,
    ObjectHead,
    ObjectValue,
    PublicReleaseError,
    R2Config,
    R2ReleaseStore,
    SourceObject,
    publish_public_release,
    rollback_public_release,
    scan_public_release,
)

PUBLISHED_AT = datetime(2026, 8, 2, 12, 30, tzinfo=UTC)
REVISION_A = "a" * 40
REVISION_B = "b" * 40
REVISION_C = "c" * 40


class MemoryStore:
    def __init__(self) -> None:
        self.objects: dict[str, bytes] = {}
        self.metadata: dict[str, dict[str, str]] = {}
        self.headers: dict[str, tuple[str, str]] = {}
        self.puts: list[dict[str, Any]] = []
        self.reads: list[str] = []
        self.fail_after: int | None = None
        self.mutate_before_cas = False

    @staticmethod
    def _etag(payload: bytes) -> str:
        return hashlib.sha256(payload).hexdigest()

    def head_object(self, key: str) -> ObjectHead | None:
        self.reads.append(f"HEAD {key}")
        payload = self.objects.get(key)
        if payload is None:
            return None
        return ObjectHead(
            size=len(payload),
            content_type=self.headers.get(key, ("", ""))[0],
            cache_control=self.headers.get(key, ("", ""))[1],
            metadata=self.metadata.get(key, {}),
            etag=self._etag(payload),
        )

    def read_object(self, key: str, *, maximum: int) -> ObjectValue | None:
        self.reads.append(f"GET {key}")
        payload = self.objects.get(key)
        if payload is None:
            return None
        if len(payload) > maximum:
            raise PublicReleaseError("test object too large")
        return ObjectValue(
            payload=payload,
            head=ObjectHead(
                size=len(payload),
                content_type=self.headers.get(key, ("", ""))[0],
                cache_control=self.headers.get(key, ("", ""))[1],
                metadata=self.metadata.get(key, {}),
                etag=self._etag(payload),
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
        self._maybe_fail()
        self._put(
            key,
            source.path.read_bytes(),
            content_type=source.content_type,
            cache_control=cache_control,
            metadata=metadata,
            if_none_match=if_none_match,
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
        self._maybe_fail()
        if if_match is not None and self.mutate_before_cas:
            self.objects[key] += b" "
            self.mutate_before_cas = False
        self._put(
            key,
            payload,
            content_type=content_type,
            cache_control=cache_control,
            metadata=metadata,
            if_none_match=if_none_match,
            if_match=if_match,
        )

    def _put(
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
        current = self.objects.get(key)
        if if_none_match and current is not None:
            raise PublicReleaseError("test If-None-Match failed")
        if if_match is not None and (current is None or self._etag(current) != if_match):
            raise PublicReleaseError("test If-Match failed")
        self.objects[key] = payload
        self.metadata[key] = dict(metadata)
        self.headers[key] = (content_type, cache_control)
        self.puts.append(
            {
                "key": key,
                "content_type": content_type,
                "cache_control": cache_control,
                "if_none_match": if_none_match,
                "if_match": if_match,
            }
        )

    def _maybe_fail(self) -> None:
        if self.fail_after is not None and len(self.puts) >= self.fail_after:
            raise PublicReleaseError("synthetic upload failure")


def _source(tmp_path: Path) -> Path:
    source = tmp_path / "public"
    export_public_data(
        mode="synthetic",
        output_dir=source,
        generated_at="2026-08-01T12:00:00Z",
    )
    return source


def _refresh_data_version(source: Path) -> str:
    assets = {
        path.relative_to(source).as_posix(): json.loads(path.read_text(encoding="utf-8"))
        for path in source.rglob("*.json")
    }
    data_version = semantic_data_version(assets)
    manifest_path = source / "data/manifest.json"
    manifest = assets["data/manifest.json"]
    manifest["data_version"] = data_version
    manifest_path.write_text(json.dumps(manifest) + "\n", encoding="utf-8")
    return data_version


def _make_semantic_change(source: Path) -> str:
    profile_path = sorted((source / "data/species").glob("*.json"))[0]
    profile = json.loads(profile_path.read_text(encoding="utf-8"))
    profile["traits"]["habitat"] = "Riparian woodland"
    profile_path.write_text(json.dumps(profile) + "\n", encoding="utf-8")
    manifest_path = source / "data/manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    summary = next(
        item for item in manifest["species"] if item["species_code"] == profile["species_code"]
    )
    summary["trait_summary"]["habitat"] = "Riparian woodland"
    manifest_path.write_text(json.dumps(manifest) + "\n", encoding="utf-8")
    return _refresh_data_version(source)


def test_publish_orders_assets_manifest_and_pointer_with_public_metadata(tmp_path: Path) -> None:
    source = _source(tmp_path)
    store = MemoryStore()
    object_count = len(scan_public_release(source))

    result = publish_public_release(source, store, prefix="rufous/data", published_at=PUBLISHED_AT)

    assert result.status == "published"
    assert result.uploaded_assets == object_count
    put_keys = [item["key"] for item in store.puts]
    asset_keys = put_keys[:object_count]
    assert asset_keys == sorted(asset_keys)
    assert all(f"/releases/{result.release_id}/objects/data/" in key for key in asset_keys)
    assert put_keys[-2:] == [result.release_manifest_key, result.pointer_key]
    assert all(item["content_type"] == "application/json; charset=utf-8" for item in store.puts)
    assert all(item["cache_control"] == IMMUTABLE_CACHE_CONTROL for item in store.puts[:-1])
    assert store.puts[-1]["cache_control"] == POINTER_CACHE_CONTROL
    assert store.puts[-1]["if_none_match"] is True

    pointer = json.loads(store.objects[result.pointer_key])
    manifest = json.loads(store.objects[result.release_manifest_key])
    assert pointer["mode"] == "public-release-pointer"
    assert pointer["published_at"] == "2026-08-02T12:30:00Z"
    assert pointer["data_version"] == result.data_version
    assert pointer["manifest_path"].endswith("/objects/data/manifest.json")
    assert pointer["previous_releases"] == []
    assert manifest["release_id"] == result.release_id
    assert manifest["data_version"] == result.data_version
    assert manifest["manifest_sha256"] == pointer["manifest_sha256"]
    for item in manifest["files"]:
        assert store.headers[item["key"]] == (
            item["content_type"],
            IMMUTABLE_CACHE_CONTROL,
        )
        assert store.metadata[item["key"]] == {
            "sha256": item["sha256"],
            "release-id": result.release_id,
            "role": "asset",
        }
    assert store.metadata[result.release_manifest_key]["role"] == "manifest"
    assert store.headers[result.release_manifest_key] == (
        "application/json; charset=utf-8",
        IMMUTABLE_CACHE_CONTROL,
    )
    assert store.metadata[result.pointer_key]["role"] == "pointer"
    assert store.headers[result.pointer_key] == (
        "application/json; charset=utf-8",
        POINTER_CACHE_CONTROL,
    )


def test_semantic_noop_ignores_volatile_manifest_bytes_after_verifying_release(
    tmp_path: Path,
) -> None:
    source = _source(tmp_path)
    store = MemoryStore()
    first = publish_public_release(source, store, published_at=PUBLISHED_AT)
    puts = list(store.puts)
    manifest_path = source / "data/manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["generated_at"] = "2026-08-03T00:00:00Z"
    manifest_path.write_text(json.dumps(manifest) + "\n", encoding="utf-8")
    reads_before = len(store.reads)

    second = publish_public_release(
        source,
        store,
        published_at=datetime(2026, 8, 3, tzinfo=UTC),
    )

    assert second.status == "unchanged"
    assert second.release_id == first.release_id
    assert second.data_version == first.data_version
    assert store.puts == puts
    assert len(store.reads) > reads_before


def test_nonvolatile_manifest_change_creates_a_new_semantic_release(tmp_path: Path) -> None:
    source = _source(tmp_path)
    store = MemoryStore()
    first = publish_public_release(source, store, published_at=PUBLISHED_AT)
    manifest_path = source / "data/manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["region"]["name"] = "Arizona public birding region"
    manifest_path.write_text(json.dumps(manifest) + "\n", encoding="utf-8")
    second_data_version = _refresh_data_version(source)

    second = publish_public_release(
        source,
        store,
        published_at=datetime(2026, 8, 3, tzinfo=UTC),
    )

    assert second.status == "published"
    assert second.data_version == second_data_version
    assert second.data_version != first.data_version
    assert second.release_id != first.release_id


def test_monotonic_publication_rejects_a_to_b_then_stale_a_before_writes(
    tmp_path: Path,
) -> None:
    source_a = _source(tmp_path / "a")
    source_b = _source(tmp_path / "b")
    _make_semantic_change(source_b)
    store = MemoryStore()

    first = publish_public_release(
        source_a,
        store,
        published_at=PUBLISHED_AT,
        publication_sequence=100,
        publication_attempt=1,
        source_revision=REVISION_A,
    )
    second = publish_public_release(
        source_b,
        store,
        published_at=datetime(2026, 8, 3, tzinfo=UTC),
        publication_sequence=101,
        publication_attempt=1,
        source_revision=REVISION_B,
    )
    puts_before = list(store.puts)

    with pytest.raises(PublicReleaseError, match="stale publication"):
        publish_public_release(
            source_a,
            store,
            published_at=datetime(2026, 8, 4, tzinfo=UTC),
            publication_sequence=100,
            publication_attempt=1,
            source_revision=REVISION_A,
        )

    assert first.release_id != second.release_id
    assert store.puts == puts_before
    pointer = json.loads(store.objects[second.pointer_key])
    assert pointer["publication_sequence"] == 101
    assert pointer["publication_attempt"] == 1
    assert pointer["source_revision"] == REVISION_B


def test_newer_semantic_noop_advances_the_publication_fence(tmp_path: Path) -> None:
    source = _source(tmp_path)
    store = MemoryStore()
    first = publish_public_release(
        source,
        store,
        published_at=PUBLISHED_AT,
        publication_sequence=200,
        publication_attempt=1,
        source_revision=REVISION_A,
    )
    manifest_path = source / "data/manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["generated_at"] = "2026-08-03T00:00:00Z"
    manifest_path.write_text(json.dumps(manifest) + "\n", encoding="utf-8")

    second = publish_public_release(
        source,
        store,
        published_at=datetime(2026, 8, 3, tzinfo=UTC),
        publication_sequence=202,
        publication_attempt=1,
        source_revision=REVISION_B,
    )

    assert second.status == "unchanged"
    assert second.release_id == first.release_id
    pointer = json.loads(store.objects[first.pointer_key])
    assert pointer["publication_sequence"] == 202
    puts_before = list(store.puts)
    _make_semantic_change(source)
    with pytest.raises(PublicReleaseError, match="stale publication"):
        publish_public_release(
            source,
            store,
            publication_sequence=201,
            publication_attempt=1,
            source_revision=REVISION_C,
        )
    assert store.puts == puts_before


def test_publication_attempt_orders_retries_and_rejects_identity_reuse(
    tmp_path: Path,
) -> None:
    source_a = _source(tmp_path / "a")
    source_b = _source(tmp_path / "b")
    _make_semantic_change(source_b)
    store = MemoryStore()
    publish_public_release(
        source_a,
        store,
        publication_sequence=400,
        publication_attempt=1,
        source_revision=REVISION_A,
    )
    second = publish_public_release(
        source_b,
        store,
        publication_sequence=400,
        publication_attempt=2,
        source_revision=REVISION_B,
    )
    pointer = json.loads(store.objects[second.pointer_key])
    assert pointer["publication_sequence"] == 400
    assert pointer["publication_attempt"] == 2

    with pytest.raises(PublicReleaseError, match="stale publication"):
        publish_public_release(
            source_a,
            store,
            publication_sequence=400,
            publication_attempt=1,
            source_revision=REVISION_A,
        )
    with pytest.raises(PublicReleaseError, match="different source revision"):
        publish_public_release(
            source_b,
            store,
            publication_sequence=400,
            publication_attempt=2,
            source_revision=REVISION_C,
        )
    with pytest.raises(PublicReleaseError, match="metadata is required"):
        publish_public_release(source_b, store)


def test_noop_fails_if_active_release_is_incomplete(tmp_path: Path) -> None:
    source = _source(tmp_path)
    store = MemoryStore()
    first = publish_public_release(source, store, published_at=PUBLISHED_AT)
    release = json.loads(store.objects[first.release_manifest_key])
    del store.objects[release["files"][0]["key"]]

    with pytest.raises(PublicReleaseError, match="release object is missing"):
        publish_public_release(source, store, published_at=PUBLISHED_AT)


def test_new_release_keeps_prior_release_metadata_and_objects(tmp_path: Path) -> None:
    source = _source(tmp_path)
    store = MemoryStore()
    first = publish_public_release(source, store, published_at=PUBLISHED_AT)
    old_manifest = store.objects[first.release_manifest_key]
    second_data_version = _make_semantic_change(source)

    second = publish_public_release(
        source,
        store,
        published_at=datetime(2026, 8, 4, 9, 15, tzinfo=UTC),
    )

    pointer = json.loads(store.objects[second.pointer_key])
    assert pointer["release_id"] == second.release_id
    assert pointer["data_version"] == second_data_version
    assert pointer["previous_releases"][0]["release_id"] == first.release_id
    assert pointer["previous_releases"][0]["data_version"] == first.data_version
    assert pointer["previous_releases"][0]["release_manifest_key"] == first.release_manifest_key
    assert store.objects[first.release_manifest_key] == old_manifest
    assert store.puts[-1]["if_match"] is not None
    assert store.puts[-1]["if_none_match"] is False


def test_pointer_compare_and_swap_rejects_a_concurrent_writer(tmp_path: Path) -> None:
    source = _source(tmp_path)
    store = MemoryStore()
    first = publish_public_release(source, store, published_at=PUBLISHED_AT)
    _make_semantic_change(source)
    store.mutate_before_cas = True

    with pytest.raises(PublicReleaseError, match="If-Match failed"):
        publish_public_release(
            source,
            store,
            published_at=datetime(2026, 8, 4, tzinfo=UTC),
        )

    assert json.loads(store.objects[first.pointer_key])["release_id"] == first.release_id
    assert store.objects[first.pointer_key].endswith(b" ")


def test_rollback_only_repoints_to_a_complete_verified_historical_release(
    tmp_path: Path,
) -> None:
    source = _source(tmp_path)
    store = MemoryStore()
    first = publish_public_release(source, store, published_at=PUBLISHED_AT)
    _make_semantic_change(source)
    second = publish_public_release(source, store, published_at=datetime(2026, 8, 4, tzinfo=UTC))
    immutable_keys = set(store.objects) - {second.pointer_key}

    rolled_back = rollback_public_release(store, first.release_id)

    assert rolled_back.status == "rolled-back"
    assert rolled_back.release_id == first.release_id
    assert json.loads(store.objects[first.pointer_key])["release_id"] == first.release_id
    assert set(store.objects) - {first.pointer_key} == immutable_keys
    assert store.puts[-1]["if_match"] is not None
    assert store.puts[-1]["key"] == first.pointer_key


def test_rollback_preserves_and_advances_the_monotonic_publication_guard(
    tmp_path: Path,
) -> None:
    source_a = _source(tmp_path / "a")
    source_b = _source(tmp_path / "b")
    _make_semantic_change(source_b)
    store = MemoryStore()
    first = publish_public_release(
        source_a,
        store,
        published_at=PUBLISHED_AT,
        publication_sequence=300,
        publication_attempt=1,
        source_revision=REVISION_A,
    )
    second = publish_public_release(
        source_b,
        store,
        published_at=datetime(2026, 8, 3, tzinfo=UTC),
        publication_sequence=301,
        publication_attempt=1,
        source_revision=REVISION_B,
    )

    rolled_back = rollback_public_release(
        store,
        first.release_id,
        publication_sequence=302,
        publication_attempt=1,
        source_revision=REVISION_C,
    )

    assert rolled_back.status == "rolled-back"
    pointer = json.loads(store.objects[rolled_back.pointer_key])
    assert pointer["release_id"] == first.release_id
    assert pointer["publication_sequence"] == 302
    assert pointer["source_revision"] == REVISION_C
    puts_before = list(store.puts)
    with pytest.raises(PublicReleaseError, match="stale publication"):
        publish_public_release(
            source_b,
            store,
            publication_sequence=301,
            publication_attempt=1,
            source_revision=REVISION_B,
        )
    assert second.release_id != first.release_id
    assert store.puts == puts_before


def test_rollback_rejects_unknown_or_incomplete_history_target(tmp_path: Path) -> None:
    source = _source(tmp_path)
    store = MemoryStore()
    first = publish_public_release(source, store, published_at=PUBLISHED_AT)
    _make_semantic_change(source)
    publish_public_release(source, store, published_at=datetime(2026, 8, 4, tzinfo=UTC))

    with pytest.raises(PublicReleaseError, match="not present"):
        rollback_public_release(store, "f" * 64)

    release = json.loads(store.objects[first.release_manifest_key])
    del store.objects[release["files"][0]["key"]]
    pointer_before = store.objects[first.pointer_key]
    with pytest.raises(PublicReleaseError, match="release object is missing"):
        rollback_public_release(store, first.release_id)
    assert store.objects[first.pointer_key] == pointer_before


def test_dry_run_reads_state_but_writes_nothing(tmp_path: Path) -> None:
    store = MemoryStore()
    result = publish_public_release(
        _source(tmp_path), store, dry_run=True, published_at=PUBLISHED_AT
    )

    assert result.status == "dry-run"
    assert result.changed is True
    assert result.uploaded_assets > 0
    assert store.puts == []


def test_failed_upload_never_advances_pointer_and_retry_reuses_partial_data(
    tmp_path: Path,
) -> None:
    source = _source(tmp_path)
    store = MemoryStore()
    store.fail_after = 1

    with pytest.raises(PublicReleaseError, match="synthetic upload failure"):
        publish_public_release(source, store, published_at=PUBLISHED_AT)

    assert "rufous-public/manifest.json" not in store.objects
    store.fail_after = None
    result = publish_public_release(source, store, published_at=PUBLISHED_AT)
    assert result.reused_assets == 1
    assert result.uploaded_assets == result.file_count - 1
    assert result.pointer_key in store.objects


def test_immutable_collision_fails_closed(tmp_path: Path) -> None:
    source = _source(tmp_path)
    store = MemoryStore()
    planned = publish_public_release(source, store, dry_run=True, published_at=PUBLISHED_AT)
    key = f"rufous-public/releases/{planned.release_id}/objects/data/manifest.json"
    store.objects[key] = b"tampered"
    store.metadata[key] = {"sha256": hashlib.sha256(b"tampered").hexdigest()}

    with pytest.raises(PublicReleaseError, match="immutable object collision"):
        publish_public_release(source, store, published_at=PUBLISHED_AT)

    assert planned.pointer_key not in store.objects


def test_expected_headers_metadata_and_size_cannot_hide_tampered_asset_before_activation(
    tmp_path: Path,
) -> None:
    source = _source(tmp_path)
    store = MemoryStore()
    planned = publish_public_release(source, store, dry_run=True, published_at=PUBLISHED_AT)
    asset = scan_public_release(source)[0]
    asset_key = f"rufous-public/releases/{planned.release_id}/objects/{asset.relative_path}"
    original = asset.path.read_bytes()
    store.objects[asset_key] = bytes([original[0] ^ 1]) + original[1:]
    store.headers[asset_key] = (asset.content_type, IMMUTABLE_CACHE_CONTROL)
    store.metadata[asset_key] = {
        "sha256": asset.sha256,
        "release-id": planned.release_id,
        "role": "asset",
    }

    with pytest.raises(PublicReleaseError, match="failed byte verification"):
        publish_public_release(source, store, published_at=PUBLISHED_AT)

    assert len(store.objects[asset_key]) == asset.size
    assert planned.pointer_key not in store.objects


def test_post_upload_header_mismatch_never_advances_pointer(tmp_path: Path) -> None:
    class CorruptingStore(MemoryStore):
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
            self.headers[key] = ("application/octet-stream", cache_control)

    store = CorruptingStore()
    with pytest.raises(PublicReleaseError, match="immutable object collision"):
        publish_public_release(_source(tmp_path), store, published_at=PUBLISHED_AT)
    assert "rufous-public/manifest.json" not in store.objects


def test_unchanged_release_reverifies_asset_headers_and_custom_metadata(
    tmp_path: Path,
) -> None:
    source = _source(tmp_path)
    store = MemoryStore()
    first = publish_public_release(source, store, published_at=PUBLISHED_AT)
    release = json.loads(store.objects[first.release_manifest_key])
    asset_key = release["files"][0]["key"]
    store.headers[asset_key] = ("text/plain; charset=utf-8", IMMUTABLE_CACHE_CONTROL)

    with pytest.raises(PublicReleaseError, match="immutable object collision"):
        publish_public_release(source, store, published_at=PUBLISHED_AT)

    store.headers[asset_key] = (
        release["files"][0]["content_type"],
        IMMUTABLE_CACHE_CONTROL,
    )
    store.metadata[asset_key]["role"] = "manifest"
    with pytest.raises(PublicReleaseError, match="immutable object collision"):
        publish_public_release(source, store, published_at=PUBLISHED_AT)


def test_unchanged_release_hashes_asset_bytes_instead_of_trusting_metadata(
    tmp_path: Path,
) -> None:
    source = _source(tmp_path)
    store = MemoryStore()
    first = publish_public_release(source, store, published_at=PUBLISHED_AT)
    release = json.loads(store.objects[first.release_manifest_key])
    asset = release["files"][0]
    asset_key = asset["key"]
    original = store.objects[asset_key]
    store.objects[asset_key] = bytes([original[0] ^ 1]) + original[1:]

    assert len(store.objects[asset_key]) == asset["bytes"]
    assert store.headers[asset_key] == (
        asset["content_type"],
        IMMUTABLE_CACHE_CONTROL,
    )
    assert store.metadata[asset_key] == {
        "sha256": asset["sha256"],
        "release-id": first.release_id,
        "role": "asset",
    }
    with pytest.raises(PublicReleaseError, match="failed byte verification"):
        publish_public_release(source, store, published_at=PUBLISHED_AT)


def test_unchanged_release_reverifies_manifest_and_pointer_headers(
    tmp_path: Path,
) -> None:
    source = _source(tmp_path)
    store = MemoryStore()
    first = publish_public_release(source, store, published_at=PUBLISHED_AT)
    store.headers[first.release_manifest_key] = (
        "application/json; charset=utf-8",
        POINTER_CACHE_CONTROL,
    )
    with pytest.raises(PublicReleaseError, match="release manifest failed"):
        publish_public_release(source, store, published_at=PUBLISHED_AT)

    store.headers[first.release_manifest_key] = (
        "application/json; charset=utf-8",
        IMMUTABLE_CACHE_CONTROL,
    )
    store.metadata[first.pointer_key]["role"] = "asset"
    with pytest.raises(PublicReleaseError, match="pointer failed object metadata"):
        publish_public_release(source, store, published_at=PUBLISHED_AT)


def test_publisher_runs_privacy_audit_before_accessing_store(tmp_path: Path) -> None:
    source = _source(tmp_path)
    profile_path = sorted((source / "data/species").glob("*.json"))[0]
    profile = json.loads(profile_path.read_text(encoding="utf-8"))
    profile["email"] = "private@example.com"
    profile_path.write_text(json.dumps(profile) + "\n", encoding="utf-8")
    _refresh_data_version(source)
    store = MemoryStore()

    with pytest.raises(PublicReleaseError, match="public export audit failed"):
        publish_public_release(source, store, published_at=PUBLISHED_AT)

    assert store.reads == []
    assert store.puts == []


def test_publisher_binds_audit_to_the_scanned_source_bytes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = _source(tmp_path)
    profile_path = sorted((source / "data/species").glob("*.json"))[0]
    store = MemoryStore()

    def mutate_during_audit(_source_dir: Path) -> list[str]:
        profile = json.loads(profile_path.read_text(encoding="utf-8"))
        profile["email"] = "private@example.com"
        profile_path.write_text(json.dumps(profile) + "\n", encoding="utf-8")
        return []

    monkeypatch.setattr(public_release_module, "audit_public_site", mutate_during_audit)

    with pytest.raises(PublicReleaseError, match="source changed while publishing"):
        publish_public_release(source, store, published_at=PUBLISHED_AT)

    assert store.reads == []
    assert store.puts == []


def test_publisher_recomputes_data_version_instead_of_trusting_stale_manifest(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = _source(tmp_path)
    profile_path = sorted((source / "data/species").glob("*.json"))[0]
    profile = json.loads(profile_path.read_text(encoding="utf-8"))
    profile["traits"] = {"changed_without_version_update": 1}
    profile_path.write_text(json.dumps(profile) + "\n", encoding="utf-8")
    monkeypatch.setattr("databox.public_release.audit_public_site", lambda _: [])
    store = MemoryStore()

    with pytest.raises(PublicReleaseError, match="data_version does not match"):
        publish_public_release(source, store, published_at=PUBLISHED_AT)

    assert store.reads == []
    assert store.puts == []


def test_scanner_rejects_symlinks_unsafe_names_and_parquet(tmp_path: Path) -> None:
    source = _source(tmp_path)
    (source / "data/link.json").symlink_to(source / "data/manifest.json")
    with pytest.raises(PublicReleaseError, match="symlink"):
        scan_public_release(source)

    (source / "data/link.json").unlink()
    (source / "bad name.json").write_text("{}", encoding="utf-8")
    with pytest.raises(PublicReleaseError, match="unsafe object key"):
        scan_public_release(source)

    (source / "bad name.json").unlink()
    (source / "data/cells/not-yet-audited.parquet").write_bytes(b"PAR1fakePAR1")
    with pytest.raises(PublicReleaseError, match="reviewed JSON contract"):
        scan_public_release(source)


def test_local_store_round_trip_and_change_detection(tmp_path: Path) -> None:
    source = _source(tmp_path)
    destination = tmp_path / "objects"
    first = publish_public_release(
        source,
        LocalReleaseStore(destination),
        prefix="preview",
        published_at=PUBLISHED_AT,
    )
    second = publish_public_release(
        source,
        LocalReleaseStore(destination),
        prefix="preview",
        published_at=PUBLISHED_AT,
    )

    assert first.status == "published"
    assert second.status == "unchanged"
    assert (destination / first.pointer_key).is_file()
    assert (destination / first.release_manifest_key).is_file()


def test_publication_metadata_is_optional_locally_but_validated_as_one_unit(
    tmp_path: Path,
) -> None:
    source = _source(tmp_path)
    with pytest.raises(PublicReleaseError, match="must be provided together"):
        publish_public_release(source, MemoryStore(), publication_sequence=1)
    with pytest.raises(PublicReleaseError, match="positive signed 64-bit"):
        publish_public_release(
            source,
            MemoryStore(),
            publication_sequence=0,
            publication_attempt=1,
            source_revision=REVISION_A,
        )
    with pytest.raises(PublicReleaseError, match="lowercase 40- or 64-character"):
        publish_public_release(
            source,
            MemoryStore(),
            publication_sequence=1,
            publication_attempt=1,
            source_revision="not-a-revision",
        )


def test_r2_cli_requires_monotonic_publication_metadata_before_credentials(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    result = public_release_module.main(["--source", str(_source(tmp_path)), "--r2"])

    assert result == 2
    assert "--publication-sequence" in capsys.readouterr().err


def test_r2_config_is_environment_only_validated_and_redacted() -> None:
    values = {
        "RUFOUS_R2_ACCOUNT_ID": "a" * 32,
        "RUFOUS_R2_BUCKET": "rufous-public-data",
        "RUFOUS_R2_ACCESS_KEY_ID": "synthetic-access-key",
        "RUFOUS_R2_SECRET_ACCESS_KEY": "synthetic-secret-key",
    }
    config = R2Config.from_env(values)

    assert config.endpoint_url == f"https://{'a' * 32}.r2.cloudflarestorage.com"
    assert "synthetic-access-key" not in repr(config)
    assert "synthetic-secret-key" not in repr(config)
    assert repr(config).count("redacted") == 2

    with pytest.raises(PublicReleaseError, match="RUFOUS_R2_SECRET_ACCESS_KEY"):
        R2Config.from_env({key: value for key, value in values.items() if "SECRET" not in key})
    with pytest.raises(PublicReleaseError, match="safe S3 bucket"):
        R2Config.from_env({**values, "RUFOUS_R2_BUCKET": "127.0.0.1"})


class FakeR2Client:
    def __init__(self) -> None:
        self.put_arguments: list[dict[str, Any]] = []
        self.objects: dict[tuple[str, str], dict[str, Any]] = {}

    def put_object(self, **kwargs: Any) -> None:
        body = kwargs["Body"]
        kwargs["Body"] = body.read() if hasattr(body, "read") else body
        current = self.objects.get((kwargs["Bucket"], kwargs["Key"]))
        if kwargs.get("IfNoneMatch") == "*" and current is not None:
            raise RuntimeError("fake conditional write failed")
        if "IfMatch" in kwargs:
            expected = current and current["ETag"]
            if expected != kwargs["IfMatch"]:
                raise RuntimeError("fake conditional write failed")
        etag = hashlib.sha256(kwargs["Body"]).hexdigest()
        self.objects[(kwargs["Bucket"], kwargs["Key"])] = {
            "Body": kwargs["Body"],
            "ContentLength": kwargs["ContentLength"],
            "ContentType": kwargs["ContentType"],
            "CacheControl": kwargs["CacheControl"],
            "Metadata": dict(kwargs["Metadata"]),
            "ETag": etag,
        }
        self.put_arguments.append(kwargs)

    def head_object(self, **kwargs: str) -> dict[str, Any]:
        stored = self.objects[(kwargs["Bucket"], kwargs["Key"])]
        return {name: value for name, value in stored.items() if name != "Body"}

    def get_object(self, **kwargs: str) -> dict[str, Any]:
        stored = self.objects[(kwargs["Bucket"], kwargs["Key"])]
        return {**stored, "Body": io.BytesIO(stored["Body"])}

    def list_objects_v2(self, **kwargs: Any) -> dict[str, Any]:
        bucket = kwargs["Bucket"]
        prefix = kwargs["Prefix"]
        start = int(kwargs.get("ContinuationToken", "0"))
        maximum = kwargs["MaxKeys"]
        matches = sorted(
            (key, value)
            for (object_bucket, key), value in self.objects.items()
            if object_bucket == bucket and key.startswith(prefix)
        )
        page = matches[start : start + maximum]
        next_offset = start + len(page)
        result: dict[str, Any] = {
            "Contents": [{"Key": key, "Size": value["ContentLength"]} for key, value in page],
            "IsTruncated": next_offset < len(matches),
        }
        if result["IsTruncated"]:
            result["NextContinuationToken"] = str(next_offset)
        return result


def test_r2_store_sets_integrity_and_condition_headers_without_credentials(
    tmp_path: Path,
) -> None:
    source = scan_public_release(_source(tmp_path))[0]
    client = FakeR2Client()
    config = R2Config("a" * 32, "rufous-public-data", "access", "secret")
    store = R2ReleaseStore(config, client=client)
    client.objects[(config.bucket, "safe/manifest.json")] = {
        "Body": b"old\n",
        "ContentLength": 4,
        "ContentType": "application/json; charset=utf-8",
        "CacheControl": POINTER_CACHE_CONTROL,
        "Metadata": {"sha256": hashlib.sha256(b"old\n").hexdigest()},
        "ETag": '"existing-etag"',
    }

    store.put_file(
        "safe/releases/file.json",
        source,
        cache_control=IMMUTABLE_CACHE_CONTROL,
        metadata={"sha256": source.sha256},
        if_none_match=True,
    )
    store.put_bytes(
        "safe/manifest.json",
        b"{}\n",
        content_type="application/json; charset=utf-8",
        cache_control=POINTER_CACHE_CONTROL,
        metadata={"sha256": hashlib.sha256(b"{}\n").hexdigest()},
        if_none_match=False,
        if_match='"existing-etag"',
    )

    first, second = client.put_arguments
    assert first["Bucket"] == "rufous-public-data"
    assert first["IfNoneMatch"] == "*"
    assert (
        first["ContentMD5"]
        == base64.b64encode(hashlib.md5(first["Body"], usedforsecurity=False).digest()).decode()
    )
    assert first["ContentType"] == "application/json; charset=utf-8"
    assert second["IfMatch"] == '"existing-etag"'
    assert "access" not in repr(client.put_arguments)
    assert "secret" not in repr(client.put_arguments)
    head = store.head_object("safe/releases/file.json")
    assert head is not None
    assert head.content_type == source.content_type
    assert head.cache_control == IMMUTABLE_CACHE_CONTROL
    assert head.metadata == {"sha256": source.sha256}
    value = store.read_object("safe/manifest.json", maximum=100)
    assert value is not None
    assert value.payload == b"{}\n"
    assert value.head.content_type == "application/json; charset=utf-8"
    assert value.head.cache_control == POINTER_CACHE_CONTROL

    usage = store.prefix_usage("safe", maximum_objects=10, maximum_bytes=1_000)
    assert usage.object_count == 2
    assert usage.total_bytes == len(first["Body"]) + len(second["Body"])
    with pytest.raises(PublicReleaseError, match="safe byte limit"):
        store.prefix_usage("safe", maximum_objects=10, maximum_bytes=1)


def test_local_prefix_usage_is_exact_bounded_and_rejects_links(tmp_path: Path) -> None:
    store = LocalReleaseStore(tmp_path / "store")
    store.put_bytes(
        "media/one.bin",
        b"one",
        content_type="application/octet-stream",
        cache_control=IMMUTABLE_CACHE_CONTROL,
        metadata={"role": "test"},
        if_none_match=True,
    )
    store.put_bytes(
        "media-sibling/two.bin",
        b"two",
        content_type="application/octet-stream",
        cache_control=IMMUTABLE_CACHE_CONTROL,
        metadata={"role": "test"},
        if_none_match=True,
    )

    usage = store.prefix_usage("media", maximum_objects=2, maximum_bytes=10)
    assert usage.object_count == 1
    assert usage.total_bytes == 3
    with pytest.raises(PublicReleaseError, match="positive integers"):
        store.prefix_usage("media", maximum_objects=0, maximum_bytes=10)

    (store.root / "media" / "linked.bin").symlink_to(store.root / "media" / "one.bin")
    with pytest.raises(PublicReleaseError, match="contains a symlink"):
        store.prefix_usage("media", maximum_objects=2, maximum_bytes=10)


def test_invalid_remote_pointer_is_not_overwritten(tmp_path: Path) -> None:
    store = MemoryStore()
    store.objects["rufous-public/manifest.json"] = b"not-json"

    with pytest.raises(PublicReleaseError, match="not valid UTF-8 JSON"):
        publish_public_release(_source(tmp_path), store, published_at=PUBLISHED_AT)

    assert store.puts == []
