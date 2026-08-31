"""Canonical, approval-bound Rufous public-media pin tests."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from databox.public_media_approval import (
    SELECTION_REASON,
    MediaApprovalError,
    canonical_approval_json,
    empty_approval_ledger,
)
from databox.public_media_pin import (
    PublicMediaPinError,
    canonical_media_pin_json,
    compose_public_media_pin,
    verify_pinned_media_delta,
)


def _url(digest: str) -> str:
    return f"https://rufous-data.loughondata.com/rufous-media/v1/objects/{digest[:2]}/{digest}.webp"


def _item(provider: str, *, digest: str) -> dict[str, object]:
    if provider == "usfws":
        token = "1" * 24
        return {
            "alt_text": "A live Rufous Hummingbird perched outdoors.",
            "attribution_id": f"usfws-attribution-{token}",
            "caption": "A live Rufous Hummingbird perched outdoors.",
            "common_name": "Rufous Hummingbird",
            "creator": "Test Wildlife Photographer",
            "height": 400,
            "hero_score": 0,
            "kind": "photo",
            "license": "Public Domain",
            "license_url": "https://www.fws.gov/notices",
            "media_id": f"usfws-{token}",
            "mime_type": "image/webp",
            "provider": "usfws",
            "scientific_name": "Selasphorus rufus",
            "sha256": digest,
            "source_page_url": "https://www.fws.gov/media/rufous-hummingbird-test",
            "species_code": "gbif-2476855",
            "title": "Rufous Hummingbird perched",
            "url": _url(digest),
            "width": 600,
        }
    token = "2" * 24
    return {
        "alt_text": "A live Elegant Trogon perched in a tree.",
        "attribution_id": f"wikimedia-attribution-{token}",
        "caption": "A live Elegant Trogon perched in a tree.",
        "common_name": "Elegant Trogon",
        "creator": "Commons Bird Photographer",
        "height": 500,
        "hero_score": 87,
        "license": "CC BY-SA 4.0",
        "license_url": "https://creativecommons.org/licenses/by-sa/4.0/",
        "media_id": f"wikimedia-{token}",
        "mime_type": "image/webp",
        "provider": "wikimedia",
        "scientific_name": "Trogon elegans",
        "sha256": digest,
        "source_image_url": (
            "https://upload.wikimedia.org/wikipedia/commons/1/12/Trogon_elegans.jpg"
        ),
        "source_page_url": "https://commons.wikimedia.org/wiki/File:Trogon_elegans.jpg",
        "species_code": "gbif-2480916",
        "title": "Elegant Trogon perched",
        "url": _url(digest),
        "width": 650,
    }


def _write_fixture(tmp_path: Path) -> tuple[Path, Path, Path]:
    base = tmp_path / "base.json"
    prepared = tmp_path / "prepared.json"
    approvals = tmp_path / "approvals.json"
    base_item = _item("usfws", digest="1" * 64)
    delta_item = _item("wikimedia", digest="2" * 64)
    base.write_bytes(
        canonical_media_pin_json(
            {
                "schema_version": 1,
                "mode": "rufous-media-preparation",
                "generated_at": "2026-08-03T12:00:00Z",
                "source_data_version": "3" * 64,
                "public_base_url": "https://rufous-data.loughondata.com/rufous-media/v1",
                "counts": {"items": 1, "objects": 1, "species": 1},
                "items": [base_item],
            }
        )
    )
    prepared.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "mode": "rufous-media-preparation",
                "generated_at": "2026-08-04T12:00:00Z",
                "counts": {"items": 1, "objects": 1, "species": 1},
                "items": [delta_item],
            }
        ),
        encoding="utf-8",
    )
    ledger = empty_approval_ledger()
    ledger["selections"] = [
        {
            "decision": "selected",
            "reason": SELECTION_REASON,
            "reviewed_at": "2026-08-04",
            "reviewed_by": "Test Human",
            "scientific_name": str(item["scientific_name"]),
            "sha256": str(item["sha256"]),
            "source_page_urls": [str(item["source_page_url"])],
        }
        for item in (base_item, delta_item)
    ]
    ledger["selections"].sort(key=lambda item: str(item["scientific_name"]).casefold())
    approvals.write_bytes(canonical_approval_json(ledger))
    return base, prepared, approvals


def test_composes_canonical_public_only_pin_and_verifies_delta(tmp_path: Path) -> None:
    base, prepared, approvals = _write_fixture(tmp_path)
    output = tmp_path / "combined.json"

    result = compose_public_media_pin(
        base_manifest_path=base,
        prepared_media_path=prepared,
        approval_path=approvals,
        output_path=output,
        provider="wikimedia",
    )

    payload = json.loads(output.read_text(encoding="utf-8"))
    assert result == {"added_items": 1, "base_items": 1, "items": 2, "species": 2}
    assert payload["counts"] == {"items": 2, "objects": 2, "species": 2}
    assert output.read_bytes() == canonical_media_pin_json(payload)
    assert "source_image_url" not in output.read_text(encoding="utf-8")
    assert [item["scientific_name"] for item in payload["items"]] == [
        "Selasphorus rufus",
        "Trogon elegans",
    ]
    assert all(item["hero_score"] == 0 for item in payload["items"])
    assert (
        verify_pinned_media_delta(
            pinned_manifest_path=output,
            prepared_media_path=prepared,
            approval_path=approvals,
            provider="wikimedia",
        )
        == 1
    )


def test_refuses_unapproved_delta_without_writing_output(tmp_path: Path) -> None:
    base, prepared, approvals = _write_fixture(tmp_path)
    payload = json.loads(approvals.read_text(encoding="utf-8"))
    payload["selections"] = payload["selections"][:1]
    approvals.write_bytes(canonical_approval_json(payload))
    output = tmp_path / "combined.json"

    with pytest.raises((MediaApprovalError, PublicMediaPinError), match="selection|selected"):
        compose_public_media_pin(
            base_manifest_path=base,
            prepared_media_path=prepared,
            approval_path=approvals,
            output_path=output,
            provider="wikimedia",
        )

    assert not output.exists()
