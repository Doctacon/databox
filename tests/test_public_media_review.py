"""Explicitly non-deployable local Rufous media-review application tests."""

from __future__ import annotations

import hashlib
import io
import json
import shutil
import subprocess
from pathlib import Path

import pytest
from databox.public_media_approval import (
    SELECTION_REASON,
    canonical_approval_json,
    empty_approval_ledger,
)
from databox.public_media_review import (
    LOCAL_RECOMMENDATION_MODE,
    LOCAL_REVIEW_MARKER,
    MediaReviewError,
    build_local_media_review,
)
from PIL import Image


def _source(tmp_path: Path) -> tuple[Path, str, dict[str, object]]:
    buffer = io.BytesIO()
    Image.new("RGB", (8, 6), (192, 78, 34)).save(buffer, format="WEBP", quality=85, method=6)
    image = buffer.getvalue()
    digest = hashlib.sha256(image).hexdigest()
    source = tmp_path / "prepared"
    object_path = source / "objects" / digest[:2] / f"{digest}.webp"
    object_path.parent.mkdir(parents=True)
    object_path.write_bytes(image)
    item: dict[str, object] = {
        "species_code": "rufhum",
        "common_name": "Rufous Hummingbird",
        "scientific_name": "Selasphorus rufus",
        "media_id": "usfws-" + "a" * 24,
        "source_page_url": "https://www.fws.gov/media/rufous-hummingbird-review",
        "source_image_url": "https://www.fws.gov/sites/default/files/rufous.jpg",
        "creator": "Human Photographer/USFWS",
        "license": "Public Domain",
        "license_url": "https://www.fws.gov/notices",
        "title": "Rufous Hummingbird perched at flowers",
        "caption": "An adult Rufous Hummingbird at orange flowers.",
        "alt_text": "A Rufous Hummingbird perched beside orange flowers.",
        "width": 8,
        "height": 6,
        "mime_type": "image/webp",
        "sha256": digest,
        "url": (
            "https://rufous-data.loughondata.com/rufous-media/v1/objects/"
            f"{digest[:2]}/{digest}.webp"
        ),
        "attribution_id": "usfws-attribution-" + "b" * 24,
        "hero_score": 42.0,
    }
    manifest = {
        "schema_version": 1,
        "mode": "rufous-media-preparation",
        "generated_at": "2026-08-03T00:00:00Z",
        "items": [item],
        "counts": {"items": 1, "objects": 1, "species": 1},
    }
    (source / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    return source, digest, item


def _approvals(tmp_path: Path, payload: object | None = None) -> Path:
    path = tmp_path / "approvals.json"
    path.write_bytes(canonical_approval_json(payload or empty_approval_ledger()))
    return path


def _approved_ledger(digest: str, item: dict[str, object]) -> dict[str, object]:
    payload = empty_approval_ledger()
    payload["selections"] = [
        {
            "sha256": digest,
            "decision": "selected",
            "reason": SELECTION_REASON,
            "reviewed_at": "2026-08-03",
            "reviewed_by": "Test Human",
            "scientific_name": item["scientific_name"],
            "source_page_urls": [item["source_page_url"]],
        }
    ]
    return payload


def test_review_build_requires_explicit_local_only_acknowledgement(tmp_path: Path) -> None:
    source, _, _ = _source(tmp_path)
    approvals = _approvals(tmp_path)

    with pytest.raises(MediaReviewError, match="--local-review-only"):
        build_local_media_review(
            source,
            approvals,
            tmp_path / "review",
            local_review_only=False,
        )


def test_review_build_contains_every_species_candidate_and_full_attribution(
    tmp_path: Path,
) -> None:
    source, digest, item = _source(tmp_path)
    approvals = _approvals(tmp_path)
    approval_bytes = approvals.read_bytes()
    output = tmp_path / "review"

    payload = build_local_media_review(
        source,
        approvals,
        output,
        local_review_only=True,
    )

    assert approvals.read_bytes() == approval_bytes
    assert payload["marker"] == LOCAL_REVIEW_MARKER
    assert payload["counts"] == {
        "candidates": 1,
        "species": 1,
        "recommended_candidates": 1,
        "recommendation_excluded_species": 0,
        "selected_species": 0,
        "rejected_candidates": 0,
        "attribution_records": 1,
    }
    reviewed = payload["objects"][0]
    assert reviewed["sha256"] == digest
    assert reviewed["recommended"] is True
    assert reviewed["attributions"][0] == {
        "kind": "photo",
        "provider": "usfws",
        "media_id": item["media_id"],
        "url": item["url"],
        "source_url": item["source_page_url"],
        "creator": item["creator"],
        "license": "Public Domain",
        "license_url": "https://www.fws.gov/notices",
        "attribution_id": item["attribution_id"],
        "scientific_name": "Selasphorus rufus",
        "title": item["title"],
        "caption": item["caption"],
        "alt_text": item["alt_text"],
        "width": 8,
        "height": 6,
        "mime_type": "image/webp",
        "sha256": digest,
    }
    local_image = output / reviewed["image_path"]
    assert hashlib.sha256(local_image.read_bytes()).hexdigest() == digest
    assert LOCAL_REVIEW_MARKER in (output / "index.html").read_text(encoding="utf-8")
    assert "Disallow: /" in (output / "robots.txt").read_text(encoding="utf-8")
    assert "Nothing marked here changes the committed decision ledger" in (
        output / "index.html"
    ).read_text(encoding="utf-8")
    review_js = (output / "review.js").read_text(encoding="utf-8")
    assert r"JSON.stringify(data,null,2)+'\n'" in review_js
    assert "JSON.stringify(data,null,2)+'\n'" not in review_js
    assert "function itemKey(item){return `${item.scientific_name}::${item.sha256}`;}" in review_js
    assert "\\u0000" not in review_js
    assert "\x00" not in review_js


def test_rendered_descendant_clicks_bubble_to_gallery_decision_handler(
    tmp_path: Path,
) -> None:
    node = shutil.which("node")
    app_dir = Path(__file__).resolve().parents[1] / "app"
    if node is None or not (app_dir / "node_modules" / "jsdom").is_dir():
        pytest.skip("Node.js with the app's jsdom dependency is required")
    source, _, _ = _source(tmp_path)
    output = tmp_path / "review"
    build_local_media_review(
        source,
        _approvals(tmp_path),
        output,
        local_review_only=True,
    )
    script = r"""
const fs = require("fs");
const {JSDOM} = require("jsdom");
const root = process.argv[1] + "/";
const dom = new JSDOM(fs.readFileSync(root + "index.html", "utf8"), {
  url: "http://127.0.0.1:4174/",
  runScripts: "outside-only"
});
const window = dom.window;
const payload = JSON.parse(fs.readFileSync(root + "review.json", "utf8"));
window.fetch = async () => ({ok: true, json: async () => payload});
window.URL.createObjectURL = () => "blob:test";
window.URL.revokeObjectURL = () => {};
window.eval(fs.readFileSync(root + "review.js", "utf8"));
setTimeout(() => {
  const card = window.document.querySelector(".card:not([hidden])");
  const selected = card.querySelector("button[data-decision=selected] span");
  selected.dispatchEvent(new window.MouseEvent("click", {bubbles: true}));
  if (card.dataset.decision !== "selected" ||
      !window.document.querySelector("#progress").textContent.startsWith("1 species")) {
    process.exit(2);
  }
  const rejected = card.querySelector("button[data-decision=rejected] span");
  rejected.dispatchEvent(new window.MouseEvent("click", {bubbles: true}));
  if (card.dataset.decision !== "rejected" ||
      !window.document.querySelector("#progress").textContent.includes("1 candidates rejected")) {
    process.exit(3);
  }
  process.exit(0);
}, 0);
"""

    result = subprocess.run(
        [node, "-e", script, str(output)],
        cwd=app_dir,
        capture_output=True,
        text=True,
        timeout=15,
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr


def test_review_build_includes_committed_selection_for_replacement_review(tmp_path: Path) -> None:
    source, digest, item = _source(tmp_path)
    approvals = _approvals(tmp_path, _approved_ledger(digest, item))
    output = tmp_path / "review"

    payload = build_local_media_review(
        source,
        approvals,
        output,
        local_review_only=True,
    )

    assert payload["counts"]["selected_species"] == 1
    assert payload["objects"][0]["decision"] == "selected"
    assert payload["objects"][0]["reason"] == SELECTION_REASON
    assert payload["objects"][0]["recommended"] is True
    assert (output / "objects" / digest[:2] / f"{digest}.webp").is_file()


def test_review_can_show_only_species_without_a_current_selection(tmp_path: Path) -> None:
    source, digest, item = _source(tmp_path)
    second_buffer = io.BytesIO()
    Image.new("RGB", (8, 6), (30, 90, 140)).save(second_buffer, format="WEBP", quality=85, method=6)
    second_image = second_buffer.getvalue()
    second_digest = hashlib.sha256(second_image).hexdigest()
    second_path = source / "objects" / second_digest[:2] / f"{second_digest}.webp"
    second_path.parent.mkdir(parents=True)
    second_path.write_bytes(second_image)
    second_item = {
        **item,
        "species_code": "mexjay",
        "common_name": "Mexican Jay",
        "scientific_name": "Aphelocoma wollweberi",
        "media_id": "usfws-" + "c" * 24,
        "source_page_url": "https://www.fws.gov/media/mexican-jay-review",
        "source_image_url": "https://www.fws.gov/sites/default/files/mexican-jay.jpg",
        "title": "Mexican Jay perched",
        "caption": "A live Mexican Jay perched on a branch.",
        "alt_text": "A live Mexican Jay perched on a branch.",
        "sha256": second_digest,
        "url": (
            "https://rufous-data.loughondata.com/rufous-media/v1/objects/"
            f"{second_digest[:2]}/{second_digest}.webp"
        ),
        "attribution_id": "usfws-attribution-" + "d" * 24,
    }
    manifest_path = source / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["items"].append(second_item)
    manifest["counts"] = {"items": 2, "objects": 2, "species": 2}
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    approvals_payload = _approved_ledger(digest, item)
    approvals_payload["species_exclusions"] = [
        {
            "scientific_name": "Aphelocoma wollweberi",
            "decision": "no_safe_image",
            "reason": "user_content_policy",
            "reviewed_at": "2026-08-03",
            "reviewed_by": "Test Human",
            "candidates": [
                {
                    "sha256": "0" * 64,
                    "source_page_urls": ["https://www.fws.gov/media/old-mexican-jay-candidate"],
                }
            ],
        }
    ]

    payload = build_local_media_review(
        source,
        _approvals(tmp_path, approvals_payload),
        tmp_path / "review",
        local_review_only=True,
        only_missing_species=True,
    )

    assert payload["counts"]["species"] == 1
    assert payload["counts"]["candidates"] == 1
    assert payload["objects"][0]["scientific_name"] == "Aphelocoma wollweberi"
    assert payload["committed_species_exclusions"] == []


def test_review_defaults_to_one_deterministic_recommendation_per_species(
    tmp_path: Path,
) -> None:
    source, first_digest, first_item = _source(tmp_path)
    buffer = io.BytesIO()
    Image.new("RGB", (8, 6), (20, 120, 180)).save(buffer, format="WEBP", quality=85, method=6)
    second_image = buffer.getvalue()
    second_digest = hashlib.sha256(second_image).hexdigest()
    second_path = source / "objects" / second_digest[:2] / f"{second_digest}.webp"
    second_path.parent.mkdir(parents=True)
    second_path.write_bytes(second_image)
    manifest_path = source / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["items"].append(
        {
            **first_item,
            "media_id": "usfws-" + "c" * 24,
            "attribution_id": "usfws-attribution-" + "d" * 24,
            "source_page_url": "https://www.fws.gov/media/rufous-better",
            "source_image_url": "https://www.fws.gov/sites/default/files/rufous-better.jpg",
            "title": "Higher-ranked Rufous Hummingbird",
            "sha256": second_digest,
            "url": (
                "https://rufous-data.loughondata.com/rufous-media/v1/objects/"
                f"{second_digest[:2]}/{second_digest}.webp"
            ),
            "hero_score": 100.0,
        }
    )
    manifest["counts"].update(items=2, objects=2)
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    output = tmp_path / "review"

    payload = build_local_media_review(
        source,
        _approvals(tmp_path),
        output,
        local_review_only=True,
    )
    candidates = {item["sha256"]: item for item in payload["objects"]}

    assert payload["counts"]["recommended_candidates"] == 1
    assert candidates[second_digest]["recommended"] is True
    assert candidates[first_digest]["recommended"] is False
    assert '<option value="recommended">Recommended one per species</option>' in (
        output / "index.html"
    ).read_text(encoding="utf-8")


def test_manifest_bound_curated_recommendation_overrides_raw_hero_rank(
    tmp_path: Path,
) -> None:
    source, digest, item = _source(tmp_path)
    manifest_path = source / "manifest.json"
    recommendations = tmp_path / "recommendations.json"
    recommendations.write_bytes(
        canonical_approval_json(
            {
                "schema_version": 1,
                "mode": LOCAL_RECOMMENDATION_MODE,
                "source_manifest_sha256": hashlib.sha256(manifest_path.read_bytes()).hexdigest(),
                "recommendations": [
                    {
                        "scientific_name": item["scientific_name"],
                        "sha256": digest,
                        "source_page_urls": [item["source_page_url"]],
                    }
                ],
                "excluded_species": [],
            }
        )
    )

    payload = build_local_media_review(
        source,
        _approvals(tmp_path),
        tmp_path / "review",
        local_review_only=True,
        recommendations_path=recommendations,
    )

    assert payload["recommendation_source"] == "manifest-bound-curated-v1"
    assert (
        payload["recommendations_sha256"]
        == hashlib.sha256(recommendations.read_bytes()).hexdigest()
    )
    assert payload["objects"][0]["recommended"] is True


def test_curated_input_can_explicitly_mark_a_species_without_safe_pixels(
    tmp_path: Path,
) -> None:
    source, digest, item = _source(tmp_path)
    manifest_path = source / "manifest.json"
    recommendations = tmp_path / "recommendations.json"
    recommendations.write_bytes(
        canonical_approval_json(
            {
                "schema_version": 1,
                "mode": LOCAL_RECOMMENDATION_MODE,
                "source_manifest_sha256": hashlib.sha256(manifest_path.read_bytes()).hexdigest(),
                "recommendations": [],
                "excluded_species": [
                    {
                        "scientific_name": item["scientific_name"],
                        "decision": "no_safe_image",
                        "reason": "user_content_policy",
                        "candidates": [
                            {
                                "sha256": digest,
                                "source_page_urls": [item["source_page_url"]],
                            }
                        ],
                    }
                ],
            }
        )
    )

    payload = build_local_media_review(
        source,
        _approvals(tmp_path),
        tmp_path / "review",
        local_review_only=True,
        recommendations_path=recommendations,
    )

    assert payload["counts"]["recommended_candidates"] == 0
    assert payload["counts"]["recommendation_excluded_species"] == 1
    assert payload["recommendation_exclusions"][0]["reason"] == "user_content_policy"
    assert payload["objects"][0]["recommended"] is False


@pytest.mark.parametrize("mutation", ["missing", "stale", "noncanonical"])
def test_curated_recommendations_fail_closed(
    tmp_path: Path,
    mutation: str,
) -> None:
    source, digest, item = _source(tmp_path)
    manifest_path = source / "manifest.json"
    payload = {
        "schema_version": 1,
        "mode": LOCAL_RECOMMENDATION_MODE,
        "source_manifest_sha256": hashlib.sha256(manifest_path.read_bytes()).hexdigest(),
        "recommendations": [
            {
                "scientific_name": item["scientific_name"],
                "sha256": digest,
                "source_page_urls": [item["source_page_url"]],
            }
        ],
        "excluded_species": [],
    }
    if mutation == "missing":
        payload["recommendations"] = []
    elif mutation == "stale":
        payload["recommendations"][0]["sha256"] = "f" * 64
    recommendations = tmp_path / "recommendations.json"
    if mutation == "noncanonical":
        recommendations.write_text(json.dumps(payload), encoding="utf-8")
    else:
        recommendations.write_bytes(canonical_approval_json(payload))

    with pytest.raises(MediaReviewError, match="cover exactly|exact current|canonical"):
        build_local_media_review(
            source,
            _approvals(tmp_path),
            tmp_path / "review",
            local_review_only=True,
            recommendations_path=recommendations,
        )


def test_review_build_replaces_only_a_prior_marked_review_output(tmp_path: Path) -> None:
    source, _, _ = _source(tmp_path)
    approvals = _approvals(tmp_path)
    output = tmp_path / "review"
    build_local_media_review(source, approvals, output, local_review_only=True)
    (output / "unexpected.txt").write_text("keep me", encoding="utf-8")

    with pytest.raises(MediaReviewError, match="unexpected root inventory"):
        build_local_media_review(source, approvals, output, local_review_only=True)
    assert (output / "unexpected.txt").read_text(encoding="utf-8") == "keep me"

    (output / "unexpected.txt").unlink()
    second = build_local_media_review(source, approvals, output, local_review_only=True)
    assert second["counts"]["candidates"] == 1


def test_review_output_cannot_overlap_prepared_media_or_broad_paths(tmp_path: Path) -> None:
    source, _, _ = _source(tmp_path)
    approvals = _approvals(tmp_path)
    for output in (source / "review", source.parent, Path.cwd()):
        with pytest.raises(MediaReviewError, match="separate|too broad"):
            build_local_media_review(source, approvals, output, local_review_only=True)
