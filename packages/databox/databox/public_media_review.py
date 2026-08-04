# ruff: noqa: E501
"""Build an explicitly local-only Rufous media review application.

This gallery is a human review aid, not a release artifact.  It contains every
species/image candidate plus its complete public attribution, enforces at most
one browser-local selection per species, and stores review notes only in the
reviewer's browser.  It never writes the committed selection ledger.  A
permanent marker in every review bundle lets the production release audit
reject an accidental deployment.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import tempfile
import uuid
from collections import defaultdict
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from databox.public_export import PublicExportError, load_public_media_manifest
from databox.public_media_approval import (
    MAX_APPROVALS,
    NO_SAFE_IMAGE_REASONS,
    MediaApprovalError,
    canonical_approval_json,
    review_candidates,
)
from databox.public_media_release import scan_prepared_media
from databox.public_release import PublicReleaseError

LOCAL_REVIEW_MARKER = "RUF_LOCAL_MEDIA_REVIEW_ONLY_DO_NOT_DEPLOY"
LOCAL_REVIEW_MODE = "rufous-media-local-human-review"
LOCAL_RECOMMENDATION_MODE = "rufous-media-local-review-recommendations"
MAX_REVIEW_JSON_BYTES = 25 * 1024 * 1024
_EXPECTED_ROOT_FILES = {
    "DO_NOT_DEPLOY_LOCAL_MEDIA_REVIEW.txt",
    "index.html",
    "review.css",
    "review.js",
    "review.json",
    "robots.txt",
}


class MediaReviewError(RuntimeError):
    """The local-only review application could not be built safely."""


def build_local_media_review(
    source_dir: Path,
    approval_path: Path,
    output_dir: Path,
    *,
    local_review_only: bool,
    recommendations_path: Path | None = None,
    only_missing_species: bool = False,
) -> dict[str, object]:
    """Build a marked review gallery without granting a production selection."""
    if not local_review_only:
        raise MediaReviewError("local review build requires explicit --local-review-only")
    source = _real_directory(source_dir, label="prepared-media source")
    output = _safe_output_path(output_dir, source)
    existing = _validate_existing_output(output)

    before_approvals = _file_fingerprint(approval_path, label="visual-decision ledger")
    before_recommendations = (
        _file_fingerprint(recommendations_path, label="local recommendation file")
        if recommendations_path is not None
        else None
    )
    try:
        candidates_payload = review_candidates(source / "manifest.json", approval_path)
        scanned_objects = scan_prepared_media(source)
        public_media = load_public_media_manifest(source / "manifest.json")
    except (MediaApprovalError, PublicExportError, PublicReleaseError, OSError, ValueError) as exc:
        raise MediaReviewError(f"could not validate local review inputs: {exc}") from None
    after_approvals = _file_fingerprint(approval_path, label="visual-decision ledger")
    if after_approvals != before_approvals:
        raise MediaReviewError("visual-decision ledger changed during local review build")

    raw_candidates = candidates_payload.get("objects")
    committed_species_exclusions = candidates_payload.get("species_exclusions")
    if not isinstance(raw_candidates, list) or len(raw_candidates) > MAX_APPROVALS:
        raise MediaReviewError("local review candidate list is malformed")
    if not isinstance(committed_species_exclusions, list):
        raise MediaReviewError("local review species-exclusion list is malformed")
    if only_missing_species:
        already_selected = {
            candidate.get("scientific_name")
            for candidate in raw_candidates
            if isinstance(candidate, dict) and candidate.get("decision") == "selected"
        }
        filtered_candidates: list[object] = [
            candidate
            for candidate in raw_candidates
            if isinstance(candidate, dict)
            and candidate.get("scientific_name") not in already_selected
        ]
        raw_candidates = filtered_candidates
        # Existing exclusions attest only to the exact candidates from an
        # earlier provider snapshot. They must not count as a decision for a
        # newly discovered fallback candidate.
        committed_species_exclusions = []
    objects_by_hash = {item.sha256: item for item in scanned_objects}
    attribution_by_candidate: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for species_items in public_media.values():
        for item in species_items:
            digest = item.get("sha256")
            scientific_name = item.get("scientific_name")
            if isinstance(digest, str) and isinstance(scientific_name, str):
                attribution_by_candidate[(scientific_name.casefold(), digest)].append(dict(item))
    manifest_sha256 = hashlib.sha256((source / "manifest.json").read_bytes()).hexdigest()
    if recommendations_path is not None:
        recommended_by_species, recommendation_exclusions = _load_local_recommendations(
            recommendations_path,
            manifest_sha256=manifest_sha256,
            candidates=raw_candidates,
        )
        recommendation_source = "manifest-bound-curated-v1"
    else:
        recommended_by_species = {
            species_key: str(items[0]["sha256"])
            for species_key, items in public_media.items()
            if items
        }
        recommendation_exclusions = []
        recommendation_source = "deterministic-hero-rank-v1"

    review_objects: list[dict[str, object]] = []
    selected_sources: dict[str, Path] = {}
    for index, candidate in enumerate(raw_candidates):
        if not isinstance(candidate, dict):
            raise MediaReviewError(f"local review candidate {index} is malformed")
        digest = candidate.get("sha256")
        scientific_name = candidate.get("scientific_name")
        if not isinstance(digest, str) or digest not in objects_by_hash:
            raise MediaReviewError(f"local review candidate {index} has no verified object")
        if not isinstance(scientific_name, str):
            raise MediaReviewError(f"local review candidate {index} has no species")
        attributions = sorted(
            attribution_by_candidate.get((scientific_name.casefold(), digest), []),
            key=lambda item: (
                str(item.get("source_url", "")),
                str(item.get("media_id", "")),
            ),
        )
        if not attributions:
            raise MediaReviewError(f"local review candidate {index} has no full attribution")
        attribution_pages = sorted({str(item["source_url"]) for item in attributions})
        if candidate.get("source_page_urls") != attribution_pages or any(
            item.get("scientific_name") != scientific_name for item in attributions
        ):
            raise MediaReviewError(
                f"local review candidate {index} attribution does not match provenance"
            )
        image_path = f"objects/{digest[:2]}/{digest}.webp"
        review_objects.append(
            {
                "sha256": digest,
                "image_path": image_path,
                "scientific_name": scientific_name,
                "source_page_urls": candidate.get("source_page_urls"),
                "decision": candidate.get("decision"),
                "reason": candidate.get("reason"),
                "recommended": (recommended_by_species.get(scientific_name.casefold()) == digest),
                "attributions": attributions,
            }
        )
        selected_sources[image_path] = objects_by_hash[digest].path

    attribution_count = 0
    for review_object in review_objects:
        review_attributions = review_object.get("attributions")
        if isinstance(review_attributions, list):
            attribution_count += len(review_attributions)
    review_payload: dict[str, object] = {
        "schema_version": 1,
        "mode": LOCAL_REVIEW_MODE,
        "marker": LOCAL_REVIEW_MARKER,
        "source_manifest_sha256": manifest_sha256,
        "recommendation_source": recommendation_source,
        "recommendations_sha256": (
            before_recommendations[1] if before_recommendations is not None else None
        ),
        "recommendation_exclusions": recommendation_exclusions,
        "committed_species_exclusions": committed_species_exclusions,
        "counts": {
            "candidates": len(review_objects),
            "species": len({str(item["scientific_name"]) for item in review_objects}),
            "recommended_candidates": sum(
                item.get("recommended") is True for item in review_objects
            ),
            "recommendation_excluded_species": len(recommendation_exclusions),
            "selected_species": len(
                {
                    str(item["scientific_name"])
                    for item in review_objects
                    if item.get("decision") == "selected"
                }
            ),
            "rejected_candidates": sum(
                item.get("decision") == "rejected" for item in review_objects
            ),
            "attribution_records": attribution_count,
        },
        "objects": review_objects,
    }
    encoded_review = canonical_approval_json(review_payload)
    if len(encoded_review) > MAX_REVIEW_JSON_BYTES:
        raise MediaReviewError("local review data exceeds 25 MiB")

    output.parent.mkdir(parents=True, exist_ok=True)
    stage = Path(tempfile.mkdtemp(prefix=f".{output.name}.stage-", dir=output.parent))
    try:
        _write_review_application(stage, encoded_review)
        for relative, source_path in selected_sources.items():
            destination = stage / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            try:
                os.link(source_path, destination)
            except OSError:
                shutil.copyfile(source_path, destination)
            expected_hash = destination.stem
            if (
                not destination.is_file()
                or hashlib.sha256(destination.read_bytes()).hexdigest() != expected_hash
            ):
                raise MediaReviewError("local review image changed while linking")
        _validate_built_output(stage, expected_objects=len(selected_sources))
        _replace_review_output(stage, output, existing=existing)
    finally:
        if stage.exists():
            shutil.rmtree(stage)

    if _file_fingerprint(approval_path, label="visual-decision ledger") != before_approvals:
        raise MediaReviewError("visual-decision ledger changed during local review publication")
    if (
        recommendations_path is not None
        and _file_fingerprint(recommendations_path, label="local recommendation file")
        != before_recommendations
    ):
        raise MediaReviewError("local recommendation file changed during review publication")
    return review_payload


def _load_local_recommendations(
    path: Path,
    *,
    manifest_sha256: str,
    candidates: list[object],
) -> tuple[dict[str, str], list[dict[str, object]]]:
    """Load an exact, manifest-bound recommendation for every represented species."""
    if path.is_symlink() or not path.is_file():
        raise MediaReviewError("local recommendation file is missing or unsafe")
    try:
        raw = path.read_bytes()
    except OSError:
        raise MediaReviewError("local recommendation file could not be read") from None
    if not raw or len(raw) > MAX_REVIEW_JSON_BYTES:
        raise MediaReviewError("local recommendation file is empty or exceeds 25 MiB")
    try:
        payload = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise MediaReviewError("local recommendation file is not valid UTF-8 JSON") from None
    if (
        not isinstance(payload, dict)
        or set(payload)
        != {
            "schema_version",
            "mode",
            "source_manifest_sha256",
            "recommendations",
            "excluded_species",
        }
        or payload.get("schema_version") != 1
        or payload.get("mode") != LOCAL_RECOMMENDATION_MODE
        or payload.get("source_manifest_sha256") != manifest_sha256
    ):
        raise MediaReviewError("local recommendation file does not match this prepared manifest")
    if raw != canonical_approval_json(payload):
        raise MediaReviewError("local recommendation file must use canonical sorted JSON")
    rows = payload.get("recommendations")
    raw_exclusions = payload.get("excluded_species")
    if (
        not isinstance(rows, list)
        or not isinstance(raw_exclusions, list)
        or len(rows) + len(raw_exclusions) > MAX_APPROVALS
    ):
        raise MediaReviewError("local recommendation coverage exceeds its limit")

    candidate_by_key: dict[tuple[str, str], dict[str, object]] = {}
    candidates_by_species: dict[str, list[dict[str, object]]] = defaultdict(list)
    represented_species: set[str] = set()
    for index, candidate in enumerate(candidates):
        if not isinstance(candidate, dict):
            raise MediaReviewError(f"local review candidate {index} is malformed")
        scientific_name = candidate.get("scientific_name")
        digest = candidate.get("sha256")
        if not isinstance(scientific_name, str) or not isinstance(digest, str):
            raise MediaReviewError(f"local review candidate {index} has invalid identity")
        key = (scientific_name.casefold(), digest)
        candidate_by_key[key] = candidate
        candidates_by_species[key[0]].append(candidate)
        represented_species.add(key[0])

    recommendations: dict[str, str] = {}
    previous: tuple[str, str] | None = None
    for index, row in enumerate(rows):
        if not isinstance(row, dict) or set(row) != {
            "scientific_name",
            "sha256",
            "source_page_urls",
        }:
            raise MediaReviewError(f"local recommendation {index} has unexpected fields")
        scientific_name = row.get("scientific_name")
        digest = row.get("sha256")
        pages = row.get("source_page_urls")
        if (
            not isinstance(scientific_name, str)
            or not isinstance(digest, str)
            or len(digest) != 64
            or any(character not in "0123456789abcdef" for character in digest)
            or not isinstance(pages, list)
            or not pages
            or pages != sorted(set(pages))
            or any(not isinstance(page, str) for page in pages)
        ):
            raise MediaReviewError(f"local recommendation {index} has invalid identity")
        key = (scientific_name.casefold(), digest)
        if previous is not None and key <= previous:
            raise MediaReviewError("local recommendations must be uniquely sorted")
        previous = key
        if key[0] in recommendations:
            raise MediaReviewError("local recommendations contain duplicate species")
        current = candidate_by_key.get(key)
        if current is None or current.get("source_page_urls") != pages:
            raise MediaReviewError(
                f"local recommendation {index} is not an exact current candidate"
            )
        recommendations[key[0]] = digest

    exclusions: list[dict[str, object]] = []
    excluded_species: set[str] = set()
    previous_species = ""
    for index, row in enumerate(raw_exclusions):
        if not isinstance(row, dict) or set(row) != {
            "scientific_name",
            "decision",
            "reason",
            "candidates",
        }:
            raise MediaReviewError(
                f"local recommendation species exclusion {index} has unexpected fields"
            )
        scientific_name = row.get("scientific_name")
        reason = row.get("reason")
        raw_candidates = row.get("candidates")
        if (
            not isinstance(scientific_name, str)
            or row.get("decision") != "no_safe_image"
            or reason not in NO_SAFE_IMAGE_REASONS
            or not isinstance(raw_candidates, list)
            or not raw_candidates
        ):
            raise MediaReviewError(f"local recommendation species exclusion {index} is invalid")
        species_key = scientific_name.casefold()
        if species_key <= previous_species:
            raise MediaReviewError(
                "local recommendation species exclusions must be uniquely sorted"
            )
        previous_species = species_key
        if species_key in recommendations:
            raise MediaReviewError("one species cannot be both recommended and excluded")
        current_candidates = candidates_by_species.get(species_key)
        if not current_candidates:
            raise MediaReviewError(f"local recommendation species exclusion {index} is stale")
        expected = [
            {
                "sha256": str(candidate["sha256"]),
                "source_page_urls": candidate["source_page_urls"],
            }
            for candidate in sorted(
                current_candidates, key=lambda candidate: str(candidate["sha256"])
            )
        ]
        if raw_candidates != expected:
            raise MediaReviewError(
                f"local recommendation species exclusion {index} provenance is stale"
            )
        excluded_species.add(species_key)
        exclusions.append(
            {
                "scientific_name": scientific_name,
                "decision": "no_safe_image",
                "reason": reason,
                "candidates": expected,
            }
        )

    covered = set(recommendations).union(excluded_species)
    missing = sorted(represented_species - covered)
    extra = sorted(covered - represented_species)
    if missing or extra or len(covered) != len(represented_species):
        detail = missing[0] if missing else extra[0] if extra else "unknown"
        raise MediaReviewError(
            "local recommendations must cover exactly one current candidate per "
            f"represented species; first mismatch: {detail}"
        )
    return recommendations, exclusions


def _write_review_application(stage: Path, encoded_review: bytes) -> None:
    (stage / "index.html").write_text(_INDEX_HTML, encoding="utf-8")
    (stage / "review.css").write_text(_REVIEW_CSS, encoding="utf-8")
    (stage / "review.js").write_text(_REVIEW_JS, encoding="utf-8")
    (stage / "review.json").write_bytes(encoded_review)
    (stage / "robots.txt").write_text("User-agent: *\nDisallow: /\n", encoding="utf-8")
    (stage / "DO_NOT_DEPLOY_LOCAL_MEDIA_REVIEW.txt").write_text(
        f"{LOCAL_REVIEW_MARKER}\nThis bundle is for loopback human review only.\n",
        encoding="utf-8",
    )


def _real_directory(path: Path, *, label: str) -> Path:
    if path.is_symlink():
        raise MediaReviewError(f"{label} must not be a symlink")
    resolved = path.resolve()
    if not resolved.is_dir():
        raise MediaReviewError(f"{label} must be a real directory")
    return resolved


def _safe_output_path(path: Path, source: Path) -> Path:
    if path.is_symlink():
        raise MediaReviewError("local review output must not be a symlink")
    output = path.resolve()
    forbidden = {Path(output.anchor), Path.home().resolve(), Path.cwd().resolve(), output.parent}
    if output in forbidden:
        raise MediaReviewError("local review output path is too broad")
    if output == source or output.is_relative_to(source) or source.is_relative_to(output):
        raise MediaReviewError("local review output must be separate from prepared media")
    return output


def _validate_existing_output(output: Path) -> bool:
    if not output.exists():
        return False
    if output.is_symlink() or not output.is_dir():
        raise MediaReviewError("existing local review output must be a real directory")
    _validate_built_output(output, expected_objects=None)
    return True


def _validate_built_output(output: Path, *, expected_objects: int | None) -> None:
    for path in output.rglob("*"):
        if path.is_symlink():
            raise MediaReviewError("local review output contains a symlink")
    root_files = {path.name for path in output.iterdir() if path.is_file()}
    if root_files != _EXPECTED_ROOT_FILES:
        raise MediaReviewError("local review output has an unexpected root inventory")
    try:
        payload = json.loads((output / "review.json").read_bytes())
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        raise MediaReviewError("local review output has invalid review data") from None
    if (
        not isinstance(payload, dict)
        or payload.get("schema_version") != 1
        or payload.get("mode") != LOCAL_REVIEW_MODE
        or payload.get("marker") != LOCAL_REVIEW_MARKER
        or not isinstance(payload.get("objects"), list)
    ):
        raise MediaReviewError("local review output is missing its non-deployable marker")
    object_paths = (
        sorted((output / "objects").rglob("*.webp")) if (output / "objects").is_dir() else []
    )
    if expected_objects is not None and len(object_paths) != expected_objects:
        raise MediaReviewError("local review output object count does not match")
    allowed = {Path(name) for name in _EXPECTED_ROOT_FILES}
    allowed.update(path.relative_to(output) for path in object_paths)
    actual = {path.relative_to(output) for path in output.rglob("*") if path.is_file()}
    if actual != allowed:
        raise MediaReviewError("local review output contains unexpected files")
    if LOCAL_REVIEW_MARKER not in (output / "index.html").read_text(encoding="utf-8"):
        raise MediaReviewError("local review HTML is missing its non-deployable marker")


def _replace_review_output(stage: Path, output: Path, *, existing: bool) -> None:
    backup: Path | None = None
    if existing:
        backup = output.parent / f".{output.name}.previous-{uuid.uuid4().hex}"
        output.replace(backup)
    try:
        stage.replace(output)
    except OSError:
        if backup is not None and backup.exists() and not output.exists():
            backup.replace(output)
        raise
    if backup is not None:
        shutil.rmtree(backup)


def _file_fingerprint(path: Path, *, label: str) -> tuple[int, str]:
    if path.is_symlink() or not path.is_file():
        raise MediaReviewError(f"{label} is missing or unsafe")
    try:
        payload = path.read_bytes()
    except OSError:
        raise MediaReviewError(f"{label} could not be read") from None
    return len(payload), hashlib.sha256(payload).hexdigest()


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--approvals", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--recommendations", type=Path)
    parser.add_argument("--local-review-only", action="store_true")
    parser.add_argument("--only-missing-species", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    try:
        payload = build_local_media_review(
            args.source,
            args.approvals,
            args.output,
            local_review_only=args.local_review_only,
            recommendations_path=args.recommendations,
            only_missing_species=args.only_missing_species,
        )
    except (MediaReviewError, OSError) as exc:
        print(f"Rufous local media review build failed: {exc}")
        return 1
    counts = payload["counts"]
    if not isinstance(counts, Mapping):
        print("Rufous local media review build failed: invalid result counts")
        return 1
    print(
        f"Built local-only Rufous media review: {counts['candidates']} candidate(s) "
        f"across {counts['species']} species, with {counts['attribution_records']} "
        "attribution record(s)."
    )
    print(f"{LOCAL_REVIEW_MARKER}: this output must never be deployed.")
    return 0


_INDEX_HTML = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <meta name="robots" content="noindex,nofollow,noarchive">
  <meta http-equiv="Content-Security-Policy" content="default-src 'self'; base-uri 'none'; object-src 'none'; form-action 'none'; frame-ancestors 'none'; script-src 'self'; style-src 'self'; img-src 'self'; connect-src 'self'">
  <title>Rufous local media review</title>
  <link rel="stylesheet" href="review.css">
</head>
<body data-review-marker="RUF_LOCAL_MEDIA_REVIEW_ONLY_DO_NOT_DEPLOY">
  <header>
    <p class="eyebrow">RUF_LOCAL_MEDIA_REVIEW_ONLY_DO_NOT_DEPLOY</p>
    <h1>Choose one safe image per bird species</h1>
    <p class="warning">Local review only. Select exactly one live-bird image per species. Never select a dead bird, an image containing a human, or a migration map. Nothing marked here changes the committed decision ledger or can publish an image.</p>
    <div class="progress" id="progress">Loading verified candidates…</div>
    <div class="controls">
      <label>Search <input id="search" type="search" autocomplete="off" placeholder="Species, title, creator, hash"></label>
      <label>View <select id="view"><option value="recommended">Recommended one per species</option><option value="all">All alternatives</option></select></label>
      <label>Status <select id="status"><option value="all">All</option><option value="unreviewed">Unreviewed</option><option value="selected">Selected for species</option><option value="rejected">Rejected</option></select></label>
      <button id="export" type="button">Export local decisions</button>
    </div>
    <section id="no-safe-images" hidden></section>
  </header>
  <main id="gallery" aria-live="polite"></main>
  <template id="card-template">
    <article class="card">
      <a class="image-link" target="_blank" rel="noopener"><img loading="lazy" decoding="async"></a>
      <div class="body">
        <div class="species"></div>
        <h2></h2>
        <p class="creator"></p>
        <p class="license"></p>
        <p class="caption"></p>
        <p class="hash"></p>
        <div class="sources"></div>
        <div class="decisions"><button type="button" data-decision="selected"><span>Use for this species</span></button><label>Reject because <select class="reject-reason"><option value="dead_bird">Dead bird</option><option value="human_present">Human present</option><option value="migration_map">Migration map</option><option value="other" selected>Other</option></select></label><button type="button" data-decision="rejected"><span>Reject</span></button><button type="button" data-decision="unreviewed"><span>Clear</span></button></div>
      </div>
    </article>
  </template>
  <script src="review.js"></script>
</body>
</html>
"""

_REVIEW_CSS = """*{box-sizing:border-box}body{margin:0;background:#f7edc3;color:#201c2d;font:16px/1.45 ui-monospace,SFMono-Regular,Menlo,monospace}header{position:static;padding:1rem 1.5rem;background:#f7edc3;border-bottom:4px solid #201c2d}h1{margin:.15rem 0}.eyebrow{margin:0;color:#006b72;font-weight:800;font-size:.75rem;letter-spacing:.12em}.warning{max-width:80rem;padding:.65rem;background:#fff4b0;border:2px solid #9b2c20;font-weight:800}.controls{display:flex;gap:1rem;align-items:end;flex-wrap:wrap}.controls label{display:grid;gap:.25rem}.controls input{min-width:24rem}.controls input,.controls select,.controls button,.decisions button,.decisions select,#no-safe-images button{font:inherit;border:2px solid #201c2d;background:#fffdf4;padding:.45rem .6rem}.progress{font-weight:800;margin:.5rem 0}#no-safe-images{margin-top:.75rem;padding:.6rem;background:#fff4b0;border:2px solid #9b2c20}#no-safe-images h2{font-size:1rem;margin:.1rem 0}.exclusion-row{display:flex;gap:.5rem;align-items:center;flex-wrap:wrap;margin:.4rem 0}.exclusion-row[data-confirmed=true]{color:#19754a;font-weight:800}main{display:grid;grid-template-columns:repeat(auto-fill,minmax(310px,1fr));gap:1rem;padding:1rem}.card{background:#fffdf4;border:3px solid #201c2d;border-radius:10px;overflow:hidden;box-shadow:5px 5px 0 #201c2d}.card[data-decision=selected]{outline:6px solid #19754a}.card[data-decision=rejected]{outline:6px solid #a83225}.image-link{display:grid;place-items:center;background:#ddd2ad;min-height:260px}.image-link img{display:block;max-width:100%;width:100%;height:320px;object-fit:contain}.body{padding:1rem}.species{color:#006b72;font-weight:800}.body h2{font-size:1.1rem}.creator,.license,.caption,.hash{overflow-wrap:anywhere}.hash{font-size:.72rem}.sources{display:grid;gap:.35rem}.sources a{color:#006b72;font-weight:700}.decisions{display:flex;gap:.5rem;align-items:end;flex-wrap:wrap;margin-top:1rem}.decisions label{display:grid;gap:.2rem;font-size:.8rem}.decisions button[data-decision=selected]{background:#d7f5e5}.decisions button[data-decision=rejected]{background:#ffd9d4}@media(max-width:600px){.controls input{min-width:0;width:100%}main{grid-template-columns:1fr;padding:.65rem}.image-link img{height:auto;max-height:80vh}}
"""

_REVIEW_JS = """'use strict';
const MARKER='RUF_LOCAL_MEDIA_REVIEW_ONLY_DO_NOT_DEPLOY';
const SELECTION_REASON='live_bird_without_human_or_migration_map';
const gallery=document.querySelector('#gallery');
const template=document.querySelector('#card-template');
const progress=document.querySelector('#progress');
const search=document.querySelector('#search');
const viewFilter=document.querySelector('#view');
const statusFilter=document.querySelector('#status');
const exclusionsPanel=document.querySelector('#no-safe-images');
let payload;let decisions={};let speciesExclusions={};let itemsByKey={};
function text(node,value){node.textContent=typeof value==='string'?value:'';}
function itemKey(item){return `${item.scientific_name}::${item.sha256}`;}
function storageKey(){return `rufous-local-media-review:species-v2:${payload.source_manifest_sha256}`;}
function save(){localStorage.setItem(storageKey(),JSON.stringify({decisions,speciesExclusions}));renderExclusions();updateProgress();applyFilter();}
function updateProgress(){const species=new Set(payload.objects.map(item=>item.scientific_name));const selected=new Set();let rejected=0;for(const [key,value] of Object.entries(decisions)){const item=itemsByKey[key];if(!item)continue;if(value.decision==='selected')selected.add(item.scientific_name);if(value.decision==='rejected')rejected++;}const excluded=new Set(Object.keys(speciesExclusions));const covered=new Set([...selected,...excluded]);progress.textContent=`${selected.size} species have one selected image · ${excluded.size} confirmed without a safe image · ${rejected} candidates rejected · ${species.size-covered.size} species still need a decision`;}
function applyFilter(){const q=search.value.trim().toLowerCase();const wanted=statusFilter.value;const recommendedOnly=viewFilter.value==='recommended'&&!q;for(const card of gallery.children){const value=decisions[card.dataset.key];const decision=value?value.decision:'unreviewed';card.dataset.decision=decision;card.hidden=(recommendedOnly&&card.dataset.recommended!=='true')||(wanted!=='all'&&decision!==wanted)||(q&&!card.dataset.search.includes(q));}}
function addLink(container,label,url){const a=document.createElement('a');a.textContent=label;a.href=url;a.target='_blank';a.rel='noopener';container.append(a);}
function choose(item,decision,reason){const key=itemKey(item);if(decision==='selected'){for(const candidate of payload.objects){const otherKey=itemKey(candidate);if(candidate.scientific_name===item.scientific_name&&decisions[otherKey]?.decision==='selected')delete decisions[otherKey];}delete speciesExclusions[item.scientific_name];decisions[key]={decision:'selected',reason:SELECTION_REASON};}else if(decision==='rejected'){decisions[key]={decision:'rejected',reason};if(item.recommended&&viewFilter.value==='recommended'){viewFilter.value='all';search.value=item.scientific_name;}}else{delete decisions[key];}save();}
function decisionButton(label,decision){const button=document.createElement('button');button.type='button';button.dataset.decision=decision;const span=document.createElement('span');span.textContent=label;button.append(span);return button;}
function addDecisionControls(card,item){const panel=card.querySelector('.decisions');panel.replaceChildren();const use=decisionButton('Use for this species','selected');const rejectLabel=document.createElement('label');rejectLabel.append(document.createTextNode('Reject because '));const reason=document.createElement('select');reason.className='reject-reason';for(const [value,label] of [['dead_bird','Dead bird'],['human_present','Human present'],['migration_map','Migration map'],['other','Other']]){const option=document.createElement('option');option.value=value;option.textContent=label;option.selected=value==='other';reason.append(option);}rejectLabel.append(reason);const reject=decisionButton('Reject','rejected');const clear=decisionButton('Clear','unreviewed');for(const button of [use,reject,clear])button.addEventListener('click',()=>choose(item,button.dataset.decision,reason.value));panel.append(use,rejectLabel,reject,clear);}
function render(item){const card=template.content.firstElementChild.cloneNode(true);const key=itemKey(item);card.dataset.key=key;card.dataset.recommended=String(item.recommended===true);const first=item.attributions[0];const img=card.querySelector('img');img.src=item.image_path;img.alt=first.alt_text;const imageLink=card.querySelector('.image-link');imageLink.href=item.image_path;text(card.querySelector('.species'),item.recommended?`${item.scientific_name} · Recommended starting point`:item.scientific_name);text(card.querySelector('h2'),first.title);text(card.querySelector('.creator'),`Creator: ${first.creator}`);text(card.querySelector('.license'),`License: ${first.license}`);text(card.querySelector('.caption'),first.caption||first.alt_text);text(card.querySelector('.hash'),`SHA-256 ${item.sha256}`);const sources=card.querySelector('.sources');for(const attribution of item.attributions){addLink(sources,`${attribution.scientific_name}: source and credit`,attribution.source_url);addLink(sources,attribution.license,attribution.license_url);}card.dataset.search=JSON.stringify(item).toLowerCase();addDecisionControls(card,item);gallery.append(card);}
function renderExclusions(){const rows=Array.isArray(payload.recommendation_exclusions)?payload.recommendation_exclusions:[];exclusionsPanel.replaceChildren();exclusionsPanel.hidden=rows.length===0;if(rows.length===0)return;const heading=document.createElement('h2');heading.textContent='Species with no compliant candidate';exclusionsPanel.append(heading);for(const row of rows){const wrapper=document.createElement('div');wrapper.className='exclusion-row';wrapper.dataset.confirmed=String(Boolean(speciesExclusions[row.scientific_name]));const label=document.createElement('span');label.textContent=`${row.scientific_name}: ${row.reason.replaceAll('_',' ')}`;const confirm=document.createElement('button');confirm.type='button';confirm.textContent=speciesExclusions[row.scientific_name]?'Confirmed — no safe image':'Confirm no safe image';confirm.addEventListener('click',()=>{for(const item of payload.objects){if(item.scientific_name===row.scientific_name&&decisions[itemKey(item)]?.decision==='selected')delete decisions[itemKey(item)];}speciesExclusions[row.scientific_name]={scientific_name:row.scientific_name,decision:'no_safe_image',reason:row.reason,candidates:row.candidates};save();});const clear=document.createElement('button');clear.type='button';clear.textContent='Clear';clear.addEventListener('click',()=>{delete speciesExclusions[row.scientific_name];save();});wrapper.append(label,confirm,clear);exclusionsPanel.append(wrapper);}}
function exportDecisions(){const rows=[];for(const [key,value] of Object.entries(decisions)){const item=itemsByKey[key];if(!item||!['selected','rejected'].includes(value.decision))continue;rows.push({sha256:item.sha256,decision:value.decision,reason:value.reason,scientific_name:item.scientific_name,source_page_urls:item.source_page_urls});}rows.sort((a,b)=>a.scientific_name.toLowerCase().localeCompare(b.scientific_name.toLowerCase())||a.sha256.localeCompare(b.sha256));const exclusions=Object.values(speciesExclusions).sort((a,b)=>a.scientific_name.toLowerCase().localeCompare(b.scientific_name.toLowerCase()));const data={schema_version:2,mode:'rufous-media-local-review-decisions-not-selections',marker:MARKER,source_manifest_sha256:payload.source_manifest_sha256,decisions:rows,species_exclusions:exclusions};const blob=new Blob([JSON.stringify(data,null,2)+'\\n'],{type:'application/json'});const a=document.createElement('a');a.href=URL.createObjectURL(blob);a.download='rufous-local-review-decisions-NOT-YET-COMMITTED.json';a.click();URL.revokeObjectURL(a.href);}
fetch('./review.json',{cache:'no-store'}).then(r=>{if(!r.ok)throw new Error('review data unavailable');return r.json();}).then(data=>{if(data.marker!==MARKER||data.mode!=='rufous-media-local-human-review'||!Array.isArray(data.objects)||!Array.isArray(data.recommendation_exclusions)||!Array.isArray(data.committed_species_exclusions))throw new Error('unsafe review contract');payload=data;for(const item of data.objects){const key=itemKey(item);itemsByKey[key]=item;if(item.decision==='selected'||item.decision==='rejected')decisions[key]={decision:item.decision,reason:item.reason};}for(const item of data.committed_species_exclusions)speciesExclusions[item.scientific_name]={scientific_name:item.scientific_name,decision:item.decision,reason:item.reason,candidates:item.candidates};const stored=localStorage.getItem(storageKey());if(stored!==null){try{const parsed=JSON.parse(stored);if(parsed&&typeof parsed==='object'&&!Array.isArray(parsed)){if(parsed.decisions&&parsed.speciesExclusions){decisions=parsed.decisions;speciesExclusions=parsed.speciesExclusions;}else{decisions=parsed;}}}catch{decisions={};speciesExclusions={};}}for(const item of data.objects)render(item);renderExclusions();updateProgress();applyFilter();}).catch(error=>{progress.textContent=`Review app failed closed: ${error.message}`;});
search.addEventListener('input',applyFilter);viewFilter.addEventListener('change',applyFilter);statusFilter.addEventListener('change',applyFilter);document.querySelector('#export').addEventListener('click',exportDecisions);
"""


if __name__ == "__main__":
    raise SystemExit(main())
