"""Pinned public-audio export and fail-closed contract tests."""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

import pytest
from databox.public_export import (
    PUBLIC_AUDIO_SANITIZATION_NOTICE,
    PublicExportError,
    export_public_data,
    load_public_audio_manifest,
    public_provider_attribution_sources,
)
from databox.public_export_audit import audit_public_site


def _audio_item(*, sha256: str = "a" * 64) -> dict[str, Any]:
    return {
        "species_code": "annhum",
        "common_name": "Anna's Hummingbird",
        "scientific_name": "Calypte anna",
        "provider": "xeno_canto",
        "provider_id": "XC123",
        "source_url": "https://xeno-canto.org/123",
        "creator": "Example Recordist",
        "license": "CC BY 4.0",
        "license_url": "https://creativecommons.org/licenses/by/4.0/",
        "original_url": "https://xeno-canto.org/123/download",
        "url": (
            f"https://rufous-data.loughondata.com/rufous-audio/v1/objects/{sha256[:2]}/{sha256}.mp3"
        ),
        "sha256": sha256,
        "bytes": 12_345,
        "mime_type": "audio/mpeg",
        "duration_seconds": 8.25,
        "vocalization_type": "call",
        "modification_notice": PUBLIC_AUDIO_SANITIZATION_NOTICE,
    }


def _write_manifest(path: Path, items: list[dict[str, Any]]) -> Path:
    payload = {
        "schema_version": 1,
        "generated_at": "2026-08-04T12:00:00Z",
        "counts": {
            "items": len(items),
            "objects": len({item["sha256"] for item in items}),
            "species": len({item["species_code"] for item in items}),
        },
        "items": items,
    }
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def test_audio_manifest_exports_one_optional_call_with_full_attribution(tmp_path: Path) -> None:
    audio_manifest = _write_manifest(tmp_path / "audio.json", [_audio_item()])
    output = tmp_path / "public"

    manifest = export_public_data(
        mode="synthetic",
        output_dir=output,
        audio_manifest_path=audio_manifest,
    )

    assert manifest["counts"] == {
        "species": 2,
        "observations": 2,
        "places": 2,
        "attribution_items": 1,
        "media_items": 0,
        "species_with_media": 0,
        "species_with_traits": 2,
        "audio_items": 1,
        "species_with_audio": 1,
    }
    assert manifest["source_policy"]["audio_source"] == "xeno_canto"
    assert manifest["source_policy"]["audio_delivery"] == "immutable_r2"
    anna = next(item for item in manifest["species"] if item["species_code"] == "annhum")
    cactus = next(item for item in manifest["species"] if item["species_code"] == "cacwre")
    assert cactus["call"] is None
    assert anna["call"] == {
        "provider": "xeno_canto",
        "provider_id": "XC123",
        "source_url": "https://xeno-canto.org/123",
        "creator": "Example Recordist",
        "license": "CC BY 4.0",
        "license_url": "https://creativecommons.org/licenses/by/4.0/",
        "url": (
            "https://rufous-data.loughondata.com/rufous-audio/v1/objects/aa/" + "a" * 64 + ".mp3"
        ),
        "sha256": "a" * 64,
        "bytes": 12_345,
        "mime_type": "audio/mpeg",
        "duration_seconds": 8.25,
        "recording_type": "call",
        "modifications": PUBLIC_AUDIO_SANITIZATION_NOTICE,
        "attribution_id": "audio-attribution-" + "a" * 24,
    }
    profile = json.loads((output / "data/species/annhum.json").read_text(encoding="utf-8"))
    assert profile["call"] == anna["call"]
    attribution = json.loads((output / "data/attribution.json").read_text(encoding="utf-8"))
    audio_credit = next(item for item in attribution["items"] if item["kind"] == "audio")
    assert audio_credit["attribution_id"] == anna["call"]["attribution_id"]
    assert audio_credit["creator"] == "Example Recordist"
    assert audio_credit["source_url"] == "https://xeno-canto.org/123"
    assert audio_credit["modifications"] == PUBLIC_AUDIO_SANITIZATION_NOTICE
    xeno_source = next(
        source for source in attribution["sources"] if source["provider"] == "xeno_canto"
    )
    assert "metadata-free, audio-only container" in xeno_source["modifications"]
    assert audit_public_site(output) == []


def test_release_credit_distinguishes_image_and_audio_handling() -> None:
    sources = public_provider_attribution_sources(
        "inaturalist",
        includes_photos=True,
        includes_audio=True,
    )

    assert [source["provider"] for source in sources] == [
        "inaturalist",
        "inaturalist_audio",
    ]
    assert "reviewed web display copies" in sources[0]["modifications"]
    assert "metadata-free, audio-only container" in sources[1]["modifications"]
    assert "without re-encoding" in sources[1]["modifications"]


@pytest.mark.parametrize(
    ("provider", "provider_id", "source_url", "original_url", "license", "license_url"),
    [
        (
            "xeno_canto",
            "XC123",
            "https://xeno-canto.org/123",
            "https://xeno-canto.org/123/download",
            "CC BY 4.0",
            "https://creativecommons.org/licenses/by/4.0/",
        ),
        (
            "inaturalist",
            "sound-456",
            "https://www.inaturalist.org/observations/789",
            "https://static.inaturalist.org/sounds/456.mp3",
            "CC BY 4.0",
            "https://creativecommons.org/licenses/by/4.0/",
        ),
        (
            "wikimedia",
            "File:Bird_call.ogg",
            "https://commons.wikimedia.org/wiki/File:Bird_call.ogg",
            "https://upload.wikimedia.org/wikipedia/commons/a/ab/Bird_call.ogg",
            "CC BY-SA 4.0",
            "https://creativecommons.org/licenses/by-sa/4.0/",
        ),
        (
            "usfws",
            "bird-call",
            "https://www.fws.gov/media/bird-call",
            "https://www.fws.gov/sites/default/files/audio/bird-call.mp3",
            "Public Domain",
            "https://www.fws.gov/notices",
        ),
    ],
)
def test_audio_manifest_accepts_exact_supported_provider_sources(
    tmp_path: Path,
    provider: str,
    provider_id: str,
    source_url: str,
    original_url: str,
    license: str,
    license_url: str,
) -> None:
    item = _audio_item()
    item.update(
        provider=provider,
        provider_id=provider_id,
        source_url=source_url,
        original_url=original_url,
        license=license,
        license_url=license_url,
    )

    loaded = load_public_audio_manifest(_write_manifest(tmp_path / f"{provider}.json", [item]))

    assert loaded["annhum"]["call"]["provider"] == provider


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        (lambda item: item.update(license="CC BY-NC 4.0"), "fails the public contract"),
        (lambda item: item.update(source_url="https://evil.example/123"), "fails"),
        (lambda item: item.update(url=item["url"].replace("/aa/", "/bb/")), "fails"),
        (lambda item: item.update(mime_type="audio/aac"), "fails"),
        (lambda item: item.update(bytes=0), "fails"),
        (lambda item: item.update(duration_seconds=float("inf")), "fails"),
        (lambda item: item.update(original_url="https://evil.example/call.mp3"), "fails"),
        (
            lambda item: item.update(modification_notice="Original bytes are unmodified."),
            "fails",
        ),
        (lambda item: item.update(unexpected=True), "malformed"),
    ],
)
def test_audio_manifest_rejects_unsafe_or_noncanonical_items(
    tmp_path: Path,
    mutation: Any,
    message: str,
) -> None:
    item = _audio_item()
    mutation(item)
    path = _write_manifest(tmp_path / "audio.json", [item])

    with pytest.raises(PublicExportError, match=message):
        load_public_audio_manifest(path)


def test_audio_manifest_rejects_count_tampering_and_duplicate_identities(tmp_path: Path) -> None:
    first = _audio_item()
    second = copy.deepcopy(first)
    second.update(
        species_code="cacwre",
        common_name="Cactus Wren",
        scientific_name="Campylorhynchus brunneicapillus",
        sha256="b" * 64,
        url=("https://rufous-data.loughondata.com/rufous-audio/v1/objects/bb/" + "b" * 64 + ".mp3"),
    )
    duplicate_source = _write_manifest(tmp_path / "duplicate.json", [first, second])
    with pytest.raises(PublicExportError, match="repeats an audio identity"):
        load_public_audio_manifest(duplicate_source)

    valid = _write_manifest(tmp_path / "counts.json", [first])
    payload = json.loads(valid.read_text(encoding="utf-8"))
    payload["counts"]["items"] = 2
    valid.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(PublicExportError, match="counts do not match"):
        load_public_audio_manifest(valid)


def test_audio_manifest_must_match_catalog_identity_but_need_not_cover_catalog(
    tmp_path: Path,
) -> None:
    item = _audio_item()
    item["common_name"] = "Wrong bird"
    path = _write_manifest(tmp_path / "wrong-species.json", [item])

    with pytest.raises(PublicExportError, match="does not exactly match catalog species"):
        export_public_data(
            mode="synthetic",
            output_dir=tmp_path / "public",
            audio_manifest_path=path,
        )


def test_audit_rejects_call_or_audio_attribution_tampering(tmp_path: Path) -> None:
    output = tmp_path / "public"
    export_public_data(
        mode="synthetic",
        output_dir=output,
        audio_manifest_path=_write_manifest(tmp_path / "audio.json", [_audio_item()]),
    )
    profile_path = output / "data/species/annhum.json"
    profile = json.loads(profile_path.read_text(encoding="utf-8"))
    profile["call"]["license"] = "CC BY-NC 4.0"
    profile_path.write_text(json.dumps(profile), encoding="utf-8")

    findings = audit_public_site(output)

    assert any("audio call fails the public contract" in finding for finding in findings)
