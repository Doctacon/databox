from __future__ import annotations

import hashlib
import json
import os
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import databox.public_release_hydrate as hydrate_module
import pytest
from databox.public_release import IMMUTABLE_CACHE_CONTROL, PublicReleaseError
from databox.public_release_hydrate import (
    APPROVED_PUBLIC_RELEASE_ROOT,
    PublicHttpsFetcher,
    hydrate_active_public_release,
)

DATA_VERSION = "a" * 64


class FakeHttpsResponse:
    def __init__(
        self, status: int, payload: bytes = b"", headers: Mapping[str, str] | None = None
    ) -> None:
        self.status = status
        self.payload = payload
        self.headers = dict(headers or {})

    def getheader(self, name: str, default: str | None = None) -> str | None:
        return self.headers.get(name, default)

    def read(self, maximum: int) -> bytes:
        return self.payload[:maximum]


class FakeHttpsConnection:
    responses: list[FakeHttpsResponse | Exception] = []
    requests: list[tuple[str, str, dict[str, str]]] = []

    def __init__(self, *_args: object, **_kwargs: object) -> None:
        pass

    def request(self, method: str, path: str, *, headers: dict[str, str]) -> None:
        self.requests.append((method, path, headers))

    def getresponse(self) -> FakeHttpsResponse:
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response

    def close(self) -> None:
        pass


class MemoryFetcher:
    def __init__(self, objects: Mapping[str, bytes | list[bytes]]) -> None:
        self.objects = dict(objects)
        self.calls: list[tuple[str, int]] = []

    def __call__(self, key: str, maximum: int) -> bytes:
        self.calls.append((key, maximum))
        value = self.objects[key]
        if isinstance(value, list):
            payload = value.pop(0)
        else:
            payload = value
        if len(payload) > maximum:
            raise PublicReleaseError("fixture exceeded requested bound")
        return payload


def _json_bytes(value: object) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode()


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _release_id(entries: list[dict[str, Any]]) -> str:
    digest = hashlib.sha256(b"rufous-public-release-v1\0")
    for item in sorted(entries, key=lambda candidate: candidate["path"]):
        digest.update(item["path"].encode("ascii"))
        digest.update(b"\0")
        digest.update(str(item["bytes"]).encode("ascii"))
        digest.update(b"\0")
        digest.update(bytes.fromhex(item["sha256"]))
    return digest.hexdigest()


def _fixture(
    *,
    application_manifest: dict[str, Any] | None = None,
    extra_files: Mapping[str, bytes] | None = None,
) -> tuple[dict[str, bytes], dict[str, Any], dict[str, Any]]:
    manifest = application_manifest or {
        "schema_version": 1,
        "mode": "public",
        "release_mode": "production",
        "data_version": DATA_VERSION,
    }
    files = {
        "data/manifest.json": _json_bytes(manifest),
        "data/attribution.json": _json_bytes({"schema_version": 1}),
        **dict(extra_files or {}),
    }
    entries = [
        {
            "path": path,
            "key": "pending",
            "bytes": len(payload),
            "sha256": _sha256(payload),
            "content_type": "application/json; charset=utf-8",
            "cache_control": IMMUTABLE_CACHE_CONTROL,
        }
        for path, payload in sorted(files.items())
    ]
    release_id = _release_id(entries)
    asset_base = f"rufous-public/releases/{release_id}/objects"
    for entry in entries:
        entry["key"] = f"{asset_base}/{entry['path']}"
    release = {
        "schema_version": 1,
        "release_id": release_id,
        "data_version": DATA_VERSION,
        "manifest_path": f"{asset_base}/data/manifest.json",
        "manifest_sha256": next(
            entry["sha256"] for entry in entries if entry["path"] == "data/manifest.json"
        ),
        "asset_base_key": asset_base,
        "file_count": len(entries),
        "total_bytes": sum(entry["bytes"] for entry in entries),
        "files": entries,
    }
    release_payload = _json_bytes(release)
    release_key = f"rufous-public/releases/{release_id}/release.json"
    pointer = {
        "schema_version": 1,
        "mode": "public-release-pointer",
        "release_id": release_id,
        "data_version": DATA_VERSION,
        "published_at": "2026-08-03T12:00:00Z",
        "manifest_path": release["manifest_path"],
        "manifest_sha256": release["manifest_sha256"],
        "release_manifest_sha256": _sha256(release_payload),
        "release_manifest_key": release_key,
        "asset_base_key": asset_base,
        "file_count": release["file_count"],
        "total_bytes": release["total_bytes"],
        "previous_releases": [],
    }
    objects = {
        "rufous-public/manifest.json": _json_bytes(pointer),
        release_key: release_payload,
        **{f"{asset_base}/{path}": payload for path, payload in files.items()},
    }
    return objects, pointer, release


def _site(tmp_path: Path) -> Path:
    site = tmp_path / "site"
    (site / "data").mkdir(parents=True)
    (site / "index.html").write_text("<!doctype html>", encoding="utf-8")
    (site / "data" / "synthetic.json").write_text("{}", encoding="utf-8")
    return site


def test_hydrates_complete_verified_release_and_replaces_synthetic_data(tmp_path: Path) -> None:
    objects, pointer, _ = _fixture(
        extra_files={"data/species/rufhum.json": _json_bytes({"species_code": "rufhum"})}
    )
    fetcher = MemoryFetcher(objects)
    site = _site(tmp_path)

    result = hydrate_active_public_release(site, fetch=fetcher, workers=2)

    assert result.release_id == pointer["release_id"]
    assert result.data_version == DATA_VERSION
    assert result.file_count == 3
    assert not (site / "data" / "synthetic.json").exists()
    assert json.loads((site / "data/species/rufhum.json").read_text()) == {"species_code": "rufhum"}
    assert [key for key, _ in fetcher.calls].count("rufous-public/manifest.json") == 2


@pytest.mark.parametrize(
    "bad_path",
    ["data/../secret.json", "outside/manifest.json", "/data/absolute.json"],
)
def test_rejects_unsafe_release_paths_without_replacing_existing_data(
    tmp_path: Path, bad_path: str
) -> None:
    objects, _, _ = _fixture(extra_files={bad_path: _json_bytes({"unsafe": True})})
    site = _site(tmp_path)

    with pytest.raises(PublicReleaseError, match="unsafe data path"):
        hydrate_active_public_release(site, fetch=MemoryFetcher(objects), workers=1)

    assert (site / "data/synthetic.json").is_file()
    assert not (tmp_path / "secret.json").exists()


def test_rejects_changed_asset_bytes_without_replacing_existing_data(tmp_path: Path) -> None:
    objects, pointer, _ = _fixture()
    asset_key = pointer["manifest_path"]
    objects[asset_key] = b"X" + objects[asset_key][1:]
    site = _site(tmp_path)

    with pytest.raises(PublicReleaseError, match="byte verification"):
        hydrate_active_public_release(site, fetch=MemoryFetcher(objects), workers=1)

    assert (site / "data/synthetic.json").is_file()


def test_rejects_invalid_json_even_when_manifest_hash_matches(tmp_path: Path) -> None:
    objects, _, _ = _fixture(extra_files={"data/cells/n34w113.json": b"not-json"})
    site = _site(tmp_path)

    with pytest.raises(PublicReleaseError, match="not valid UTF-8 JSON"):
        hydrate_active_public_release(site, fetch=MemoryFetcher(objects), workers=1)

    assert (site / "data/synthetic.json").is_file()


def test_rejects_nonproduction_application_manifest(tmp_path: Path) -> None:
    objects, _, _ = _fixture(
        application_manifest={
            "schema_version": 1,
            "mode": "public",
            "release_mode": "synthetic",
            "data_version": DATA_VERSION,
        }
    )

    with pytest.raises(PublicReleaseError, match="matching production snapshot"):
        hydrate_active_public_release(_site(tmp_path), fetch=MemoryFetcher(objects), workers=1)


def test_rejects_pointer_change_during_hydration(tmp_path: Path) -> None:
    objects, pointer, _ = _fixture()
    changed = dict(pointer)
    changed_release = "b" * 64
    changed["release_id"] = changed_release
    changed["asset_base_key"] = f"rufous-public/releases/{changed_release}/objects"
    changed["manifest_path"] = f"{changed['asset_base_key']}/data/manifest.json"
    changed["release_manifest_key"] = f"rufous-public/releases/{changed_release}/release.json"
    objects["rufous-public/manifest.json"] = [_json_bytes(pointer), _json_bytes(changed)]
    site = _site(tmp_path)

    with pytest.raises(PublicReleaseError, match="changed during Pages hydration"):
        hydrate_active_public_release(site, fetch=MemoryFetcher(objects), workers=1)

    assert (site / "data/synthetic.json").is_file()


def test_restores_existing_data_when_atomic_install_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    objects, _, _ = _fixture()
    site = _site(tmp_path)
    original_replace = os.replace

    def fail_new_install(source: str | Path, destination: str | Path) -> None:
        source_path = Path(source)
        if source_path.name == "data" and source_path.parent.name.startswith(".rufous-pages-data-"):
            raise OSError("injected install failure")
        original_replace(source, destination)

    monkeypatch.setattr("databox.public_release_hydrate.os.replace", fail_new_install)

    with pytest.raises(PublicReleaseError, match="could not be replaced"):
        hydrate_active_public_release(site, fetch=MemoryFetcher(objects), workers=1)

    assert (site / "data/synthetic.json").is_file()
    assert not list(tmp_path.glob(".rufous-pages-backup-*"))


def test_preserves_backup_if_install_and_recovery_both_fail(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    objects, _, _ = _fixture()
    site = _site(tmp_path)
    original_replace = os.replace

    def fail_install_and_restore(source: str | Path, destination: str | Path) -> None:
        source_path = Path(source)
        if (
            source_path.name == "previous-data"
            or source_path.name == "data"
            and source_path.parent.name.startswith(".rufous-pages-data-")
        ):
            raise OSError("injected replacement failure")
        original_replace(source, destination)

    monkeypatch.setattr("databox.public_release_hydrate.os.replace", fail_install_and_restore)

    with pytest.raises(PublicReleaseError, match="previous data is preserved"):
        hydrate_active_public_release(site, fetch=MemoryFetcher(objects), workers=1)

    backups = list(tmp_path.glob(".rufous-pages-backup-*/previous-data"))
    assert len(backups) == 1
    assert (backups[0] / "synthetic.json").is_file()


def test_requires_built_site_and_exact_reviewed_origin(tmp_path: Path) -> None:
    with pytest.raises(PublicReleaseError, match="existing built static site"):
        hydrate_active_public_release(tmp_path)
    with pytest.raises(PublicReleaseError, match="reviewed public origin"):
        PublicHttpsFetcher("https://example.com/rufous-public")
    assert PublicHttpsFetcher(APPROVED_PUBLIC_RELEASE_ROOT)


def test_https_fetcher_retries_only_bounded_transient_failures(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    payload = b"{}\n"
    FakeHttpsConnection.responses = [
        FakeHttpsResponse(503, headers={"Retry-After": "1"}),
        OSError("temporary reset"),
        FakeHttpsResponse(
            200,
            payload,
            headers={
                "Content-Type": "application/json; charset=utf-8",
                "Content-Length": str(len(payload)),
            },
        ),
    ]
    FakeHttpsConnection.requests = []
    sleeps: list[float] = []
    monkeypatch.setattr(hydrate_module.http.client, "HTTPSConnection", FakeHttpsConnection)
    monkeypatch.setattr(hydrate_module, "_MIN_REQUEST_INTERVAL_SECONDS", 0)
    monkeypatch.setattr(hydrate_module.time, "sleep", sleeps.append)

    result = PublicHttpsFetcher()("rufous-public/manifest.json", 100)

    assert result == payload
    assert len(FakeHttpsConnection.requests) == 3
    assert sleeps == [1.0, 1.0]
    assert all("Authorization" not in headers for _, _, headers in FakeHttpsConnection.requests)


def test_https_fetcher_does_not_retry_permanent_http_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    FakeHttpsConnection.responses = [FakeHttpsResponse(404)]
    FakeHttpsConnection.requests = []
    monkeypatch.setattr(hydrate_module.http.client, "HTTPSConnection", FakeHttpsConnection)
    monkeypatch.setattr(hydrate_module, "_MIN_REQUEST_INTERVAL_SECONDS", 0)

    with pytest.raises(PublicReleaseError, match="HTTP 404"):
        PublicHttpsFetcher()("rufous-public/manifest.json", 100)

    assert len(FakeHttpsConnection.requests) == 1
