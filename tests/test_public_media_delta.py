"""Fail-closed active-snapshot tests for the iNaturalist media delta."""

from __future__ import annotations

import copy
import hashlib
import json
from collections import Counter
from io import BytesIO
from pathlib import Path

import databox.public_media_delta as media_delta
import pytest
from databox.public_export import (
    PublicExportError,
    PublicRecords,
    build_public_assets,
    load_public_assets,
    semantic_data_version,
    write_public_assets,
)
from databox.public_media_approval import (
    SELECTION_REASON,
    canonical_approval_json,
    empty_approval_ledger,
)
from databox.public_media_delta import PublicMediaDeltaError, compose_public_media_delta
from PIL import Image

TARGET_NAMES = tuple(f"Avis species{chr(ord('a') + index)}" for index in range(16))
BASE_NAME = "Selasphorus rufus"
GENERATED_AT = "2026-08-03T12:00:00Z"


def _public_url(digest: str) -> str:
    return f"https://rufous-data.loughondata.com/rufous-media/v1/objects/{digest[:2]}/{digest}.webp"


def _usfws_item() -> dict[str, object]:
    digest = "1" * 64
    return {
        "kind": "photo",
        "provider": "usfws",
        "media_id": "usfws-" + "1" * 24,
        "url": _public_url(digest),
        "source_url": "https://www.fws.gov/media/rufous-hummingbird-test",
        "creator": "Test Wildlife Photographer",
        "license": "Public Domain",
        "license_url": "https://www.fws.gov/notices",
        "attribution_id": "usfws-attribution-" + "1" * 24,
        "scientific_name": BASE_NAME,
        "title": "Rufous hummingbird in flight",
        "caption": "A test public-domain bird photograph.",
        "alt_text": "A live Rufous Hummingbird flying.",
        "width": 4,
        "height": 3,
        "mime_type": "image/webp",
        "sha256": digest,
    }


def _base_assets() -> dict[str, dict[str, object]]:
    species: list[dict[str, object]] = [
        {
            "species_code": "rufous",
            "common_name": "Rufous Hummingbird",
            "scientific_name": BASE_NAME,
            "media": [_usfws_item()],
        }
    ]
    species.extend(
        {
            "species_code": f"bird-{index:02d}",
            "common_name": f"Test Bird {index + 1}",
            "scientific_name": scientific_name,
            "media": [],
        }
        for index, scientific_name in enumerate(TARGET_NAMES)
    )
    records = PublicRecords(
        species=species,
        observations=[
            {
                "public_id": "public-observation",
                "species_code": "rufous",
                "observed_at": "2026-08-02",
                "location": {
                    "latitude": 33.45,
                    "longitude": -112.07,
                    "label": "Generalized Phoenix area",
                },
            }
        ],
        places=[
            {
                "public_id": "public-place",
                "name": "Phoenix",
                "kind": "place",
                "latitude": 33.45,
                "longitude": -112.07,
                "timezone": "America/Phoenix",
                "timezone_source": "arizona_no_dst",
            }
        ],
        attribution_items=[],
        rejected=Counter(),
    )
    return build_public_assets(
        records,
        mode="production",
        gnis_sha256="2" * 64,
        generated_at=GENERATED_AT,
    )


def _webp(index: int) -> bytes:
    output = BytesIO()
    Image.new("RGB", (4, 3), (index * 11 % 255, index * 17 % 255, index * 23 % 255)).save(
        output,
        format="WEBP",
        lossless=True,
    )
    return output.getvalue()


def _prepared_media(root: Path) -> tuple[Path, list[dict[str, object]]]:
    prepared = root / "inaturalist-prepared"
    items: list[dict[str, object]] = []
    for index, scientific_name in enumerate(TARGET_NAMES, start=1):
        payload = _webp(index)
        digest = hashlib.sha256(payload).hexdigest()
        photo_id = 10_000 + index
        object_path = prepared / "objects" / digest[:2] / f"{digest}.webp"
        object_path.parent.mkdir(parents=True, exist_ok=True)
        object_path.write_bytes(payload)
        items.append(
            {
                "provider": "inaturalist",
                "media_id": f"inaturalist-{photo_id}",
                "attribution_id": f"inaturalist-attribution-{photo_id}",
                "scientific_name": scientific_name,
                "common_name": f"Test Bird {index}",
                "creator": f"Test Photographer {index}",
                "title": f"Wild bird portrait {index}",
                "caption": "Reviewed live bird photograph.",
                "alt_text": f"A live Test Bird {index} outdoors.",
                "source_page_url": f"https://www.inaturalist.org/photos/{photo_id}",
                "url": _public_url(digest),
                "sha256": digest,
                "license": "CC BY 4.0",
                "license_url": "https://creativecommons.org/licenses/by/4.0/",
                "mime_type": "image/webp",
                "width": 4,
                "height": 3,
                "hero_score": 100 - index,
            }
        )
    manifest = {
        "schema_version": 1,
        "mode": "rufous-media-preparation",
        "generated_at": GENERATED_AT,
        "counts": {
            "items": len(items),
            "objects": len({item["sha256"] for item in items}),
            "species": len(TARGET_NAMES),
        },
        "items": items,
    }
    (prepared / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    return prepared, items


def _approval_ledger(root: Path, items: list[dict[str, object]]) -> Path:
    ledger = empty_approval_ledger()
    selections = [
        {
            "sha256": "1" * 64,
            "decision": "selected",
            "reason": SELECTION_REASON,
            "reviewed_at": "2026-08-03",
            "reviewed_by": "Test Human",
            "scientific_name": BASE_NAME,
            "source_page_urls": ["https://www.fws.gov/media/rufous-hummingbird-test"],
        }
    ]
    selections.extend(
        {
            "sha256": item["sha256"],
            "decision": "selected",
            "reason": SELECTION_REASON,
            "reviewed_at": "2026-08-03",
            "reviewed_by": "Test Human",
            "scientific_name": item["scientific_name"],
            "source_page_urls": [item["source_page_url"]],
        }
        for item in items
    )
    ledger["selections"] = sorted(
        selections,
        key=lambda item: (str(item["scientific_name"]).casefold(), str(item["sha256"])),
    )
    path = root / "approvals.json"
    path.write_bytes(canonical_approval_json(ledger))
    return path


def _fixture(
    tmp_path: Path,
) -> tuple[Path, Path, Path, dict[str, dict[str, object]]]:
    site = tmp_path / "site"
    assets = _base_assets()
    write_public_assets(site, assets)
    (site / "index.html").write_text("<!doctype html><title>Rufous</title>", encoding="utf-8")
    prepared, items = _prepared_media(tmp_path)
    approvals = _approval_ledger(tmp_path, items)
    return site, prepared, approvals, assets


def _rewrite_site(site: Path, assets: dict[str, dict[str, object]]) -> None:
    manifest = assets["data/manifest.json"]
    manifest["data_version"] = semantic_data_version(assets)
    expected = set(assets)
    for path in (site / "data").rglob("*.json"):
        relative = path.relative_to(site).as_posix()
        if relative not in expected:
            path.unlink()
    for relative, payload in assets.items():
        destination = site / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(
            json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n",
            encoding="utf-8",
        )


def _binding_for_name(
    assets: dict[str, dict[str, object]], scientific_name: str
) -> tuple[dict[str, object], dict[str, object]]:
    manifest = assets["data/manifest.json"]
    summaries = manifest["species"]
    assert isinstance(summaries, list)
    summary = next(item for item in summaries if item["scientific_name"] == scientific_name)
    assert isinstance(summary, dict)
    profile_path = str(summary["profile_path"]).removeprefix("/")
    return summary, assets[profile_path]


def test_composes_only_selected_inaturalist_delta_without_touching_active_site(
    tmp_path: Path,
) -> None:
    site, prepared, approvals, before = _fixture(tmp_path)
    output = tmp_path / "delta"

    result = compose_public_media_delta(
        active_root=site,
        prepared_media_dir=prepared,
        approval_path=approvals,
        output_dir=output,
        generated_at="2026-08-03T13:00:00Z",
    )

    assert result.added_species == 16
    assert result.reused_species == 0
    assert result.selected_species == result.selected_objects == 16
    assert load_public_assets(site) == before
    assert load_public_assets(site / "data") == before
    after = load_public_assets(output)
    assert after["data/manifest.json"]["source_policy"]["media_source"] == ("usfws+inaturalist")
    assert after["data/manifest.json"]["counts"]["media_items"] == 17
    assert after["data/manifest.json"]["counts"]["species_with_media"] == 17
    assert {source["provider"] for source in after["data/attribution.json"]["sources"]} >= {
        "usfws",
        "inaturalist",
    }
    for path in before:
        if path.startswith("data/cells/") or path.startswith("data/places/"):
            assert after[path] == before[path]
    _base_summary, base_profile = _binding_for_name(after, BASE_NAME)
    _before_summary, before_base_profile = _binding_for_name(before, BASE_NAME)
    assert base_profile == before_base_profile
    for scientific_name in TARGET_NAMES:
        summary, profile = _binding_for_name(after, scientific_name)
        assert summary["photo_count"] == 1
        assert profile["media"] == [summary["hero_photo"]]
        assert profile["media"][0]["provider"] == "inaturalist"


def test_exact_delta_is_idempotent(tmp_path: Path) -> None:
    site, prepared, approvals, _before = _fixture(tmp_path)
    first = tmp_path / "first"
    second = tmp_path / "second"
    first_result = compose_public_media_delta(
        active_root=site,
        prepared_media_dir=prepared,
        approval_path=approvals,
        output_dir=first,
        generated_at="2026-08-03T13:00:00Z",
    )

    second_result = compose_public_media_delta(
        active_root=first,
        prepared_media_dir=prepared,
        approval_path=approvals,
        output_dir=second,
        generated_at="2026-08-03T14:00:00Z",
    )

    assert second_result.added_species == 0
    assert second_result.reused_species == 16
    assert second_result.data_version == first_result.data_version


def test_rejects_active_usfws_selection_drift(tmp_path: Path) -> None:
    site, prepared, approvals, assets = _fixture(tmp_path)
    changed = copy.deepcopy(assets)
    summary, profile = _binding_for_name(changed, BASE_NAME)
    media = profile["media"]
    assert isinstance(media, list) and isinstance(media[0], dict)
    media[0]["sha256"] = "3" * 64
    media[0]["url"] = _public_url("3" * 64)
    summary["hero_photo"] = copy.deepcopy(media[0])
    _rewrite_site(site, changed)

    with pytest.raises(PublicMediaDeltaError, match="drifted from its committed selection"):
        compose_public_media_delta(
            active_root=site,
            prepared_media_dir=prepared,
            approval_path=approvals,
            output_dir=tmp_path / "delta",
        )


def test_rejects_wrong_provider_prepared_manifest(tmp_path: Path) -> None:
    site, prepared, approvals, _assets = _fixture(tmp_path)
    manifest_path = prepared / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["items"][0]["provider"] = "usfws"
    manifest["items"][0]["source_page_url"] = "https://www.fws.gov/media/wrong-provider"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(PublicMediaDeltaError, match="outside the requested inaturalist"):
        compose_public_media_delta(
            active_root=site,
            prepared_media_dir=prepared,
            approval_path=approvals,
            output_dir=tmp_path / "delta",
        )


def test_refuses_to_replace_an_existing_target_image(tmp_path: Path) -> None:
    site, prepared, approvals, assets = _fixture(tmp_path)
    changed = copy.deepcopy(assets)
    summary, profile = _binding_for_name(changed, TARGET_NAMES[0])
    existing = copy.deepcopy(_usfws_item())
    existing["scientific_name"] = TARGET_NAMES[0]
    profile["media"] = [existing]
    summary["hero_photo"] = copy.deepcopy(existing)
    summary["photo_count"] = 1
    changed["data/manifest.json"]["counts"]["media_items"] = 2
    changed["data/manifest.json"]["counts"]["species_with_media"] = 2
    _rewrite_site(site, changed)

    with pytest.raises(PublicMediaDeltaError, match="refusing to replace"):
        compose_public_media_delta(
            active_root=site,
            prepared_media_dir=prepared,
            approval_path=approvals,
            output_dir=tmp_path / "delta",
        )


def test_rejects_an_absent_target_species(tmp_path: Path) -> None:
    site, prepared, approvals, assets = _fixture(tmp_path)
    changed = copy.deepcopy(assets)
    manifest = changed["data/manifest.json"]
    summaries = manifest["species"]
    assert isinstance(summaries, list)
    removed = next(item for item in summaries if item["scientific_name"] == TARGET_NAMES[0])
    summaries.remove(removed)
    changed.pop(str(removed["profile_path"]).removeprefix("/"))
    manifest["counts"]["species"] -= 1
    _rewrite_site(site, changed)

    with pytest.raises(PublicMediaDeltaError, match="target species is absent"):
        compose_public_media_delta(
            active_root=site,
            prepared_media_dir=prepared,
            approval_path=approvals,
            output_dir=tmp_path / "delta",
        )


def test_change_guard_rejects_unexpected_public_json_mutation(tmp_path: Path) -> None:
    _site, _prepared, _approvals, before = _fixture(tmp_path)
    after = copy.deepcopy(before)
    cell_path = next(path for path in after if path.startswith("data/cells/"))
    after[cell_path]["unexpected"] = True

    with pytest.raises(PublicMediaDeltaError, match="unexpectedly changed"):
        media_delta._assert_allowed_asset_changes(
            before,
            after,
            changed_profile_paths=set(),
            changed_summary_indexes=set(),
        )


def test_public_asset_loader_rejects_extra_data_inventory(tmp_path: Path) -> None:
    site, _prepared, _approvals, _assets = _fixture(tmp_path)
    (site / "data" / "unexpected.json").write_text("{}", encoding="utf-8")

    with pytest.raises(PublicExportError, match="exact manifest"):
        load_public_assets(site)
