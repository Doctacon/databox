"""Contract tests for Rufous's provider-free pinned public media input."""

from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path
from typing import Any

from databox.public_export import load_public_media_manifest
from databox.public_media_approval import load_visual_approvals, require_visual_approvals

ROOT = Path(__file__).parents[2]
PINNED_MEDIA = ROOT / "config" / "rufous-pinned-public-media.json"
APPROVALS = ROOT / "config" / "rufous-media-visual-approvals.json"
ACTIVE_DATA_VERSION = "b6120def48ac0135796fd5ba9fc2823a162f39569dcaa20c65de48d5c5959a8e"

_PUBLIC_MEDIA_URL = re.compile(
    r"^https://rufous-data\.loughondata\.com/rufous-media/v1/objects/"
    r"(?P<shard>[a-f0-9]{2})/(?P<sha>[a-f0-9]{64})\.webp$"
)
_PROVIDER_SOURCE_PAGE = {
    "usfws": re.compile(r"^https://www\.fws\.gov/media/[a-z0-9][a-z0-9-]*$"),
    "inaturalist": re.compile(r"^https://www\.inaturalist\.org/photos/[1-9][0-9]*$"),
    "wikimedia": re.compile(r"^https://commons\.wikimedia\.org/wiki/File:[^/?#\s]+$"),
}


def _payload() -> dict[str, Any]:
    value = json.loads(PINNED_MEDIA.read_bytes())
    assert isinstance(value, dict)
    return value


def test_pinned_manifest_contains_exactly_the_active_207_selected_species() -> None:
    payload = _payload()
    items = payload["items"]

    assert payload["schema_version"] == 1
    assert payload["mode"] == "rufous-media-preparation"
    assert payload["source_data_version"] == ACTIVE_DATA_VERSION
    assert payload["public_base_url"] == ("https://rufous-data.loughondata.com/rufous-media/v1")
    assert payload["counts"] == {"items": 207, "objects": 207, "species": 207}
    assert len(items) == 207
    assert len({item["scientific_name"].casefold() for item in items}) == 207
    assert len({item["sha256"] for item in items}) == 207
    assert Counter(item["provider"] for item in items) == {
        "usfws": 167,
        "inaturalist": 16,
        "wikimedia": 24,
    }


def test_every_pinned_item_is_one_exact_committed_selection() -> None:
    items = _payload()["items"]
    selections = load_visual_approvals(APPROVALS)
    by_species = {item["scientific_name"].casefold(): item for item in items}

    assert len(selections) == 207
    assert set(by_species) == set(selections)
    for species_key, selection in selections.items():
        item = by_species[species_key]
        assert item["scientific_name"] == selection.scientific_name
        assert item["sha256"] == selection.sha256
        assert item["source_page_url"] in selection.source_page_urls


def test_pinned_items_reference_only_content_addressed_public_media() -> None:
    payload = _payload()
    serialized = PINNED_MEDIA.read_text(encoding="utf-8")

    assert "source_image_url" not in serialized
    assert "inaturalist-open-data.s3.amazonaws.com" not in serialized
    assert "upload.wikimedia.org" not in serialized
    assert "/sites/default/files/" not in serialized
    for item in payload["items"]:
        match = _PUBLIC_MEDIA_URL.fullmatch(item["url"])
        assert match is not None
        assert match.group("sha") == item["sha256"]
        assert match.group("shard") == item["sha256"][:2]
        assert _PROVIDER_SOURCE_PAGE[item["provider"]].fullmatch(item["source_page_url"])
        assert item["mime_type"] == "image/webp"
        assert item["hero_score"] == 0


def test_existing_public_projection_and_human_approval_gates_accept_the_pin() -> None:
    plan = require_visual_approvals(PINNED_MEDIA, APPROVALS)
    projected = load_public_media_manifest(
        PINNED_MEDIA,
        selected_sha256_by_species=plan.selected_sha256_by_species,
        excluded_species=plan.excluded_species,
    )

    assert plan.summary.manifest_candidates == 207
    assert plan.summary.manifest_species == 207
    assert plan.summary.selected_species == 207
    assert plan.summary.selected_objects == 207
    assert plan.summary.excluded_species == 0
    assert plan.selected_sha256s == {item["sha256"] for item in _payload()["items"]}
    assert len(projected) == 207
    assert all(len(items) == 1 for items in projected.values())
