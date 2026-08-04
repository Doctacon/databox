"""Committed, species-scoped human media-selection gate tests."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest
from databox.public_media_approval import (
    LOCAL_DECISION_MODE,
    LOCAL_REVIEW_MARKER,
    SELECTION_REASON,
    MediaApprovalError,
    canonical_approval_json,
    empty_approval_ledger,
    load_visual_approvals,
    merge_local_review_decisions,
    require_visual_approvals,
    review_candidates,
)


def _item(
    payload: bytes,
    scientific_name: str,
    slug: str,
) -> dict[str, str]:
    digest = hashlib.sha256(payload).hexdigest()
    return {
        "sha256": digest,
        "scientific_name": scientific_name,
        "source_page_url": f"https://www.fws.gov/media/{slug}",
        "url": (
            "https://rufous-data.loughondata.com/rufous-media/v1/objects/"
            f"{digest[:2]}/{digest}.webp"
        ),
    }


def _inaturalist_item(
    payload: bytes,
    scientific_name: str,
    photo_id: int,
) -> dict[str, str]:
    item = _item(payload, scientific_name, "unused-usfws-slug")
    item["provider"] = "inaturalist"
    item["source_page_url"] = f"https://www.inaturalist.org/photos/{photo_id}"
    return item


def _manifest(tmp_path: Path, items: list[dict[str, str]]) -> Path:
    payload = {
        "schema_version": 1,
        "mode": "rufous-media-preparation",
        "generated_at": "2026-08-03T00:00:00Z",
        "items": items,
        "counts": {
            "items": len(items),
            "objects": len({item["sha256"] for item in items}),
            "species": len({item["scientific_name"].casefold() for item in items}),
        },
    }
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def _selection(item: dict[str, str]) -> dict[str, object]:
    return {
        "sha256": item["sha256"],
        "decision": "selected",
        "reason": SELECTION_REASON,
        "reviewed_at": "2026-08-03",
        "reviewed_by": "Human Reviewer",
        "scientific_name": item["scientific_name"],
        "source_page_urls": [item["source_page_url"]],
    }


def _rejection(item: dict[str, str], reason: str) -> dict[str, object]:
    return {
        "sha256": item["sha256"],
        "decision": "rejected",
        "reason": reason,
        "reviewed_at": "2026-08-03",
        "reviewed_by": "Human Reviewer",
        "scientific_name": item["scientific_name"],
        "source_page_urls": [item["source_page_url"]],
    }


def _ledger(
    tmp_path: Path,
    *,
    selections: list[dict[str, object]] | None = None,
    rejections: list[dict[str, object]] | None = None,
    name: str = "approvals.json",
) -> Path:
    payload = empty_approval_ledger()
    payload["selections"] = selections or []
    payload["rejections"] = rejections or []
    path = tmp_path / name
    path.write_bytes(canonical_approval_json(payload))
    return path


def _local_export(
    manifest: Path,
    decisions: list[dict[str, object]],
    path: Path,
    *,
    species_exclusions: list[dict[str, object]] | None = None,
) -> Path:
    payload = {
        "schema_version": 2,
        "mode": LOCAL_DECISION_MODE,
        "marker": LOCAL_REVIEW_MARKER,
        "source_manifest_sha256": hashlib.sha256(manifest.read_bytes()).hexdigest(),
        "decisions": decisions,
        "species_exclusions": species_exclusions or [],
    }
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return path


def test_empty_committed_ledger_is_valid_but_selects_nothing(tmp_path: Path) -> None:
    approvals = _ledger(tmp_path)

    assert load_visual_approvals(approvals) == {}


def test_exactly_one_current_selection_per_species_passes(tmp_path: Path) -> None:
    rufous = _item(b"rufous", "Selasphorus rufus", "rufous-one")
    anna = _item(b"anna", "Calypte anna", "anna-one")
    manifest = _manifest(tmp_path, [rufous, anna])
    approvals = _ledger(tmp_path, selections=[_selection(anna), _selection(rufous)])

    plan = require_visual_approvals(manifest, approvals)

    assert plan.summary.manifest_species == 2
    assert plan.summary.selected_species == 2
    assert plan.summary.selected_objects == 2
    assert plan.selected_sha256_by_species == {
        "calypte anna": anna["sha256"],
        "selasphorus rufus": rufous["sha256"],
    }


def test_mixed_provider_provenance_accepts_exact_inaturalist_photo_pages(
    tmp_path: Path,
) -> None:
    rufous = _item(b"rufous", "Selasphorus rufus", "rufous-one")
    wigeon = _inaturalist_item(b"wigeon", "Mareca americana", 2498155)
    manifest = _manifest(tmp_path, [rufous, wigeon])
    selections = [_selection(rufous), _selection(wigeon)]
    selections.sort(key=lambda row: (str(row["scientific_name"]).casefold(), str(row["sha256"])))
    approvals = _ledger(tmp_path, selections=selections)

    plan = require_visual_approvals(manifest, approvals)

    assert plan.summary.selected_species == 2
    assert plan.selected_sha256_by_species == {
        "mareca americana": wigeon["sha256"],
        "selasphorus rufus": rufous["sha256"],
    }


@pytest.mark.parametrize(
    ("provider", "source_page_url"),
    [
        ("inaturalist", "https://inaturalist.org/photos/2498155"),
        ("inaturalist", "https://www.inaturalist.org/photos/2498155/"),
        ("inaturalist", "https://www.inaturalist.org/photos/2498155?download=1"),
        ("inaturalist", "https://www.inaturalist.org/observations/2498155"),
        ("inaturalist", "https://www.inaturalist.org.evil.example/photos/2498155"),
        ("usfws", "https://www.inaturalist.org/photos/2498155"),
        ("wikimedia", "https://www.inaturalist.org/photos/2498155"),
    ],
)
def test_manifest_provenance_rejects_inaturalist_impostors(
    tmp_path: Path,
    provider: str,
    source_page_url: str,
) -> None:
    item = _inaturalist_item(b"wigeon", "Mareca americana", 2498155)
    item["provider"] = provider
    item["source_page_url"] = source_page_url
    manifest = _manifest(tmp_path, [item])

    with pytest.raises(MediaApprovalError, match="invalid provenance"):
        require_visual_approvals(manifest, _ledger(tmp_path))


def test_one_candidate_cannot_mix_provider_source_pages(tmp_path: Path) -> None:
    shared_usfws = _item(b"same pixels", "Mareca americana", "american-wigeon")
    shared_inaturalist = {
        **shared_usfws,
        "provider": "inaturalist",
        "source_page_url": "https://www.inaturalist.org/photos/2498155",
    }
    manifest = _manifest(tmp_path, [shared_usfws, shared_inaturalist])
    selection = _selection(shared_usfws)
    selection["source_page_urls"] = sorted(
        [shared_usfws["source_page_url"], shared_inaturalist["source_page_url"]]
    )
    approvals = _ledger(tmp_path, selections=[selection])

    with pytest.raises(MediaApprovalError, match="one reviewed media provider"):
        require_visual_approvals(manifest, approvals)


def test_unselected_candidates_do_not_block_or_enter_the_plan(tmp_path: Path) -> None:
    chosen = _item(b"chosen", "Selasphorus rufus", "rufous-chosen")
    ignored = _item(b"ignored", "Selasphorus rufus", "rufous-ignored")
    manifest = _manifest(tmp_path, [chosen, ignored])
    approvals = _ledger(tmp_path, selections=[_selection(chosen)])

    plan = require_visual_approvals(manifest, approvals)

    assert plan.summary.manifest_candidates == 2
    assert plan.selected_sha256s == {chosen["sha256"]}
    assert ignored["sha256"] not in plan.selected_sha256s


def test_a_represented_species_without_a_selection_fails_closed(tmp_path: Path) -> None:
    rufous = _item(b"rufous", "Selasphorus rufus", "rufous-one")
    anna = _item(b"anna", "Calypte anna", "anna-one")
    manifest = _manifest(tmp_path, [rufous, anna])
    approvals = _ledger(tmp_path, selections=[_selection(rufous)])

    with pytest.raises(MediaApprovalError, match="1 represented species"):
        require_visual_approvals(manifest, approvals)


def test_committed_selection_absent_from_current_manifest_fails_closed(
    tmp_path: Path,
) -> None:
    rufous = _item(b"rufous", "Selasphorus rufus", "rufous-one")
    anna = _item(b"anna", "Calypte anna", "anna-one")
    manifest = _manifest(tmp_path, [anna])
    approvals = _ledger(tmp_path, selections=[_selection(anna), _selection(rufous)])

    with pytest.raises(MediaApprovalError, match="committed selected media is absent"):
        require_visual_approvals(manifest, approvals)


def test_species_without_safe_pixels_has_a_provenance_bound_exclusion(
    tmp_path: Path,
) -> None:
    rufous = _item(b"rufous", "Selasphorus rufus", "rufous-one")
    anna = _item(b"unsafe anna", "Calypte anna", "anna-human")
    manifest = _manifest(tmp_path, [rufous, anna])
    exclusion = {
        "scientific_name": "Calypte anna",
        "decision": "no_safe_image",
        "reason": "user_content_policy",
        "reviewed_at": "2026-08-03",
        "reviewed_by": "Human Reviewer",
        "candidates": [
            {
                "sha256": anna["sha256"],
                "source_page_urls": [anna["source_page_url"]],
            }
        ],
    }
    approvals = _ledger(tmp_path, selections=[_selection(rufous)])
    payload = json.loads(approvals.read_text(encoding="utf-8"))
    payload["species_exclusions"] = [exclusion]
    approvals.write_bytes(canonical_approval_json(payload))

    plan = require_visual_approvals(manifest, approvals)

    assert plan.summary.selected_species == 1
    assert plan.summary.excluded_species == 1
    assert plan.excluded_species == {"calypte anna"}

    changed = _item(b"new safe possibility", "Calypte anna", "anna-new")
    changed_manifest = _manifest(tmp_path, [rufous, anna, changed])
    with pytest.raises(MediaApprovalError, match="does not match every current candidate"):
        require_visual_approvals(changed_manifest, approvals)


def test_changed_pixels_or_new_provenance_require_a_new_decision(tmp_path: Path) -> None:
    old = _item(b"old", "Selasphorus rufus", "rufous-one")
    approvals = _ledger(tmp_path, selections=[_selection(old)])
    changed = _item(b"new", "Selasphorus rufus", "rufous-one")
    changed_manifest = _manifest(tmp_path, [changed])
    with pytest.raises(MediaApprovalError, match="not a current candidate"):
        require_visual_approvals(changed_manifest, approvals)

    manifest = _manifest(
        tmp_path, [old, {**old, "source_page_url": "https://www.fws.gov/media/rufous-two"}]
    )
    with pytest.raises(MediaApprovalError, match="provenance exceeds"):
        require_visual_approvals(manifest, approvals)


@pytest.mark.parametrize("reason", ["dead_bird", "human_present", "migration_map"])
def test_forbidden_pixel_rejection_can_never_be_selected_elsewhere(
    tmp_path: Path,
    reason: str,
) -> None:
    shared_rufous = _item(b"same pixels", "Selasphorus rufus", "rufous-one")
    shared_anna = {
        **shared_rufous,
        "scientific_name": "Calypte anna",
        "source_page_url": "https://www.fws.gov/media/anna-one",
    }
    manifest = _manifest(tmp_path, [shared_rufous, shared_anna])
    approvals = _ledger(
        tmp_path,
        selections=[_selection(shared_anna), _selection(shared_rufous)],
        rejections=[
            _rejection(
                {**shared_rufous, "scientific_name": "Archilochus alexandri"},
                reason,
            )
        ],
    )

    with pytest.raises(MediaApprovalError, match="also carry"):
        require_visual_approvals(manifest, approvals)


def test_ledger_rejects_two_selections_for_one_species(tmp_path: Path) -> None:
    first = _item(b"one", "Selasphorus rufus", "rufous-one")
    second = _item(b"two", "Selasphorus rufus", "rufous-two")
    selections = [_selection(first), _selection(second)]
    selections.sort(key=lambda row: (str(row["scientific_name"]).casefold(), str(row["sha256"])))
    approvals = _ledger(tmp_path, selections=selections)

    with pytest.raises(MediaApprovalError, match="only one image per species"):
        load_visual_approvals(approvals)


def test_review_candidates_include_every_choice_and_committed_state(tmp_path: Path) -> None:
    selected = _item(b"one", "Selasphorus rufus", "rufous-one")
    rejected = _item(b"two", "Selasphorus rufus", "rufous-two")
    unreviewed = _item(b"three", "Selasphorus rufus", "rufous-three")
    manifest = _manifest(tmp_path, [selected, rejected, unreviewed])
    approvals = _ledger(
        tmp_path,
        selections=[_selection(selected)],
        rejections=[_rejection(rejected, "human_present")],
    )

    payload = review_candidates(manifest, approvals)
    by_hash = {item["sha256"]: item for item in payload["objects"]}

    assert len(by_hash) == 3
    assert by_hash[selected["sha256"]]["decision"] == "selected"
    assert by_hash[rejected["sha256"]]["reason"] == "human_present"
    assert by_hash[unreviewed["sha256"]]["decision"] == "unreviewed"


def test_local_export_import_replaces_selection_and_preserves_rejection_audit(
    tmp_path: Path,
) -> None:
    old = _item(b"old", "Selasphorus rufus", "rufous-old")
    replacement = _item(b"new", "Selasphorus rufus", "rufous-new")
    bad = _item(b"bad", "Selasphorus rufus", "rufous-bad")
    manifest = _manifest(tmp_path, [old, replacement, bad])
    approvals = _ledger(tmp_path, selections=[_selection(old)])
    decisions = [
        {
            "sha256": bad["sha256"],
            "decision": "rejected",
            "reason": "dead_bird",
            "scientific_name": bad["scientific_name"],
            "source_page_urls": [bad["source_page_url"]],
        },
        {
            "sha256": replacement["sha256"],
            "decision": "selected",
            "reason": SELECTION_REASON,
            "scientific_name": replacement["scientific_name"],
            "source_page_urls": [replacement["source_page_url"]],
        },
    ]
    decisions.sort(key=lambda row: (str(row["scientific_name"]).casefold(), str(row["sha256"])))
    local = _local_export(manifest, decisions, tmp_path / "local.json")
    updated = tmp_path / "updated.json"

    summary = merge_local_review_decisions(
        manifest,
        approvals,
        local,
        updated,
        reviewed_by="Connor Lough",
        reviewed_at="2026-08-03",
    )
    plan = require_visual_approvals(manifest, updated)
    payload = json.loads(updated.read_text(encoding="utf-8"))

    assert summary.selected_species == 1
    assert plan.selected_sha256s == {replacement["sha256"]}
    assert payload["rejections"][0]["reason"] == "dead_bird"
    assert updated.read_bytes() == canonical_approval_json(payload)


def test_local_export_is_bound_to_the_exact_manifest(tmp_path: Path) -> None:
    item = _item(b"pixels", "Selasphorus rufus", "rufous-one")
    manifest = _manifest(tmp_path, [item])
    approvals = _ledger(tmp_path)
    row = {
        "sha256": item["sha256"],
        "decision": "selected",
        "reason": SELECTION_REASON,
        "scientific_name": item["scientific_name"],
        "source_page_urls": [item["source_page_url"]],
    }
    local = _local_export(manifest, [row], tmp_path / "local.json")
    manifest.write_text(manifest.read_text(encoding="utf-8") + "\n", encoding="utf-8")

    with pytest.raises(MediaApprovalError, match="do not match"):
        merge_local_review_decisions(
            manifest,
            approvals,
            local,
            tmp_path / "updated.json",
            reviewed_by="Human Reviewer",
        )


def test_local_no_safe_image_confirmation_imports_with_human_provenance(
    tmp_path: Path,
) -> None:
    unsafe = _item(b"human handling", "Anas diazi", "mexican-duck-handling")
    manifest = _manifest(tmp_path, [unsafe])
    approvals = _ledger(tmp_path)
    local_exclusion = {
        "scientific_name": "Anas diazi",
        "decision": "no_safe_image",
        "reason": "user_content_policy",
        "candidates": [
            {
                "sha256": unsafe["sha256"],
                "source_page_urls": [unsafe["source_page_url"]],
            }
        ],
    }
    local = _local_export(
        manifest,
        [],
        tmp_path / "local.json",
        species_exclusions=[local_exclusion],
    )
    updated = tmp_path / "updated.json"

    merge_local_review_decisions(
        manifest,
        approvals,
        local,
        updated,
        reviewed_by="Connor Lough",
        reviewed_at="2026-08-03",
    )
    plan = require_visual_approvals(manifest, updated)
    payload = json.loads(updated.read_text(encoding="utf-8"))

    assert plan.summary.excluded_species == 1
    assert plan.summary.selected_species == 0
    assert payload["species_exclusions"][0]["reviewed_by"] == "Connor Lough"


def test_ledger_rejects_noncanonical_or_old_contract(tmp_path: Path) -> None:
    path = tmp_path / "ledger.json"
    payload = empty_approval_ledger()
    path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(MediaApprovalError, match="canonical sorted JSON"):
        load_visual_approvals(path)

    payload["schema_version"] = 1
    path.write_bytes(canonical_approval_json(payload))
    with pytest.raises(MediaApprovalError, match="unsupported contract"):
        load_visual_approvals(path)
