"""Compose a selected iNaturalist media delta over the active Rufous snapshot.

This path deliberately does not rebuild, download, or otherwise touch USFWS
media.  It treats the hydrated production JSON as an immutable, verified base,
proves that every existing USFWS photo still matches the committed human
selection ledger, and adds only the provider-scoped iNaturalist selections.
"""

from __future__ import annotations

import argparse
import copy
import json
import re
import sys
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from databox.public_export import (
    JsonObject,
    PublicExportError,
    load_public_assets,
    load_public_media_manifest,
    semantic_data_version,
    write_public_assets,
)
from databox.public_media_approval import (
    MediaApprovalError,
    VisualSelection,
    load_visual_approvals,
    require_visual_approvals,
)
from databox.public_media_release import scan_prepared_media
from databox.public_release import PublicReleaseError

EXPECTED_INATURALIST_SELECTIONS = 16

_USFWS_MEDIA_PAGE = re.compile(
    r"^https://www\.fws\.gov/media/[a-z0-9](?:[a-z0-9-]{0,238}[a-z0-9])?$"
)
_INATURALIST_MEDIA_PAGE = re.compile(r"^https://www\.inaturalist\.org/photos/[1-9][0-9]*$")

_USFWS_ATTRIBUTION_SOURCE: JsonObject = {
    "provider": "usfws",
    "title": "U.S. Fish and Wildlife Service Media Library",
    "url": "https://www.fws.gov/search/images",
    "license": "Per-item Public Domain or Creative Commons license",
    "license_url": "https://www.fws.gov/notices",
    "credit": "Individual creators are credited beside each image.",
    "modifications": (
        "Rufous resized, re-encoded, and stripped metadata from web display copies; "
        "each credit links to the original USFWS media page."
    ),
}

_INATURALIST_ATTRIBUTION_SOURCE: JsonObject = {
    "provider": "inaturalist",
    "title": "iNaturalist",
    "url": "https://www.inaturalist.org/",
    "license": "Per-item Creative Commons license",
    "license_url": None,
    "credit": "Individual creators are credited on each media item.",
    "modifications": (
        "Rufous resized, re-encoded, and stripped metadata from reviewed web display "
        "copies; each credit links to the original iNaturalist photo page."
    ),
}


class PublicMediaDeltaError(RuntimeError):
    """The active snapshot cannot safely accept the reviewed media delta."""


@dataclass(frozen=True)
class PublicMediaDeltaResult:
    output_root: Path
    data_version: str
    selected_species: int
    selected_objects: int
    added_species: int
    reused_species: int


@dataclass(frozen=True)
class _SpeciesBinding:
    scientific_name: str
    summary_index: int
    profile_path: str


def compose_public_media_delta(
    *,
    active_root: Path,
    prepared_media_dir: Path,
    approval_path: Path,
    output_dir: Path,
    generated_at: str | None = None,
) -> PublicMediaDeltaResult:
    """Add exactly the reviewed iNaturalist selections to active public JSON.

    The prepared directory remains unchanged so the same provider-scoped input
    can subsequently be passed to the immutable media publisher.  Only its 16
    selected local WebP objects are decoded and hash-verified here.
    """
    try:
        return _compose_public_media_delta(
            active_root=active_root,
            prepared_media_dir=prepared_media_dir,
            approval_path=approval_path,
            output_dir=output_dir,
            generated_at=generated_at,
        )
    except PublicMediaDeltaError:
        raise
    except (MediaApprovalError, PublicExportError, PublicReleaseError) as exc:
        raise PublicMediaDeltaError(str(exc)) from exc


def _compose_public_media_delta(
    *,
    active_root: Path,
    prepared_media_dir: Path,
    approval_path: Path,
    output_dir: Path,
    generated_at: str | None,
) -> PublicMediaDeltaResult:
    active_assets = load_public_assets(active_root)
    manifest = active_assets["data/manifest.json"]
    if manifest.get("release_mode") != "production":
        raise PublicMediaDeltaError("active Rufous snapshot must be a production release")

    prepared_manifest = prepared_media_dir / "manifest.json"
    approval_plan = require_visual_approvals(
        prepared_manifest,
        approval_path,
        provider="inaturalist",
    )
    if (
        approval_plan.summary.manifest_species != EXPECTED_INATURALIST_SELECTIONS
        or len(approval_plan.selections) != EXPECTED_INATURALIST_SELECTIONS
        or approval_plan.species_exclusions
    ):
        raise PublicMediaDeltaError(
            "iNaturalist delta must contain exactly 16 human-selected species and no exclusions"
        )
    scanned_objects = scan_prepared_media(
        prepared_media_dir,
        selected_sha256s=approval_plan.selected_sha256s,
    )
    if {item.sha256 for item in scanned_objects} != approval_plan.selected_sha256s:
        raise PublicMediaDeltaError("selected iNaturalist prepared objects failed exact validation")

    selected_media = load_public_media_manifest(
        prepared_manifest,
        selected_sha256_by_species=approval_plan.selected_sha256_by_species,
        excluded_species=approval_plan.excluded_species,
    )
    if set(selected_media) != set(approval_plan.selected_sha256_by_species) or any(
        len(items) != 1 for items in selected_media.values()
    ):
        raise PublicMediaDeltaError("iNaturalist public projection is not exactly one per species")

    bindings, active_providers = _validate_active_species(active_assets)
    targets = set(selected_media)
    missing_targets = sorted(targets - set(bindings))
    if missing_targets:
        raise PublicMediaDeltaError(
            f"iNaturalist target species is absent from the active snapshot: {missing_targets[0]}"
        )
    _validate_target_media_state(active_assets, bindings, selected_media)

    selections = load_visual_approvals(approval_path)
    usfws_selections, ledger_inaturalist = _partition_selections(selections)
    if set(ledger_inaturalist) != set(approval_plan.selected_sha256_by_species):
        raise PublicMediaDeltaError(
            "provider-scoped iNaturalist selections do not match the committed ledger"
        )
    _validate_active_usfws(active_assets, bindings, usfws_selections)
    _validate_active_media_source(manifest, active_providers)

    # A mixed active snapshot is accepted only as an exact idempotent retry of
    # this complete delta.  Partial or foreign iNaturalist state fails closed.
    active_inaturalist = _active_provider_media(active_assets, bindings, "inaturalist")
    if active_inaturalist:
        expected_inaturalist = {
            species: selected_media[species][0] for species in sorted(selected_media)
        }
        if active_inaturalist != expected_inaturalist:
            raise PublicMediaDeltaError(
                "active iNaturalist media is not the exact reviewed idempotent delta"
            )

    timestamp = generated_at or datetime.now(UTC).isoformat()
    _require_aware_timestamp(timestamp)
    updated = copy.deepcopy(active_assets)
    updated_manifest = updated["data/manifest.json"]
    updated_bindings, _providers = _validate_active_species(updated)

    added = 0
    reused = 0
    changed_profile_paths: set[str] = set()
    changed_summary_indexes: set[int] = set()
    for species_key in sorted(selected_media):
        item = copy.deepcopy(selected_media[species_key][0])
        binding = updated_bindings[species_key]
        profile = updated[binding.profile_path]
        current = profile.get("media")
        if current == []:
            profile["media"] = [item]
            added += 1
        elif current == [item]:
            reused += 1
        else:
            raise PublicMediaDeltaError(
                "refusing to replace an existing species image for " + binding.scientific_name
            )
        summary = updated_manifest["species"][binding.summary_index]
        assert isinstance(summary, dict)
        summary["hero_photo"] = copy.deepcopy(item)
        summary["photo_count"] = 1
        changed_profile_paths.add(binding.profile_path)
        changed_summary_indexes.add(binding.summary_index)

    source_policy = updated_manifest.get("source_policy")
    counts = updated_manifest.get("counts")
    if not isinstance(source_policy, dict) or not isinstance(counts, dict):
        raise PublicMediaDeltaError("active Rufous manifest has malformed policy or counts")
    source_policy["media_source"] = "usfws+inaturalist"
    source_policy["media_delivery"] = "immutable_r2"
    updated_manifest["generated_at"] = timestamp
    counts["media_items"] = sum(
        int(summary["photo_count"])
        for summary in updated_manifest["species"]
        if isinstance(summary, dict)
    )
    counts["species_with_media"] = sum(
        int(summary["photo_count"]) > 0
        for summary in updated_manifest["species"]
        if isinstance(summary, dict)
    )

    _update_attribution(updated, timestamp)
    updated_manifest["data_version"] = semantic_data_version(updated)
    _assert_allowed_asset_changes(
        active_assets,
        updated,
        changed_profile_paths=changed_profile_paths,
        changed_summary_indexes=changed_summary_indexes,
    )
    # Re-run structural checks on the exact tree that will be written.
    _updated_bindings, updated_providers = _validate_active_species(updated)
    if updated_providers != {"usfws", "inaturalist"}:
        raise PublicMediaDeltaError("composed Rufous media providers are not exactly mixed")

    write_public_assets(output_dir, updated)
    return PublicMediaDeltaResult(
        output_root=output_dir.resolve(),
        data_version=str(updated_manifest["data_version"]),
        selected_species=len(selected_media),
        selected_objects=len(scanned_objects),
        added_species=added,
        reused_species=reused,
    )


def _validate_active_species(
    assets: Mapping[str, JsonObject],
) -> tuple[dict[str, _SpeciesBinding], set[str]]:
    manifest = assets.get("data/manifest.json")
    if not isinstance(manifest, dict):
        raise PublicMediaDeltaError("active Rufous snapshot has no manifest")
    summaries = manifest.get("species")
    counts = manifest.get("counts")
    if not isinstance(summaries, list) or not isinstance(counts, dict):
        raise PublicMediaDeltaError("active Rufous species manifest is malformed")
    if counts.get("species") != len(summaries):
        raise PublicMediaDeltaError("active Rufous species count does not match its manifest")

    bindings: dict[str, _SpeciesBinding] = {}
    providers: set[str] = set()
    media_items = 0
    species_with_media = 0
    for index, summary in enumerate(summaries):
        if not isinstance(summary, dict):
            raise PublicMediaDeltaError("active Rufous species summary is malformed")
        profile_url = summary.get("profile_path")
        if not isinstance(profile_url, str) or not profile_url.startswith("/data/species/"):
            raise PublicMediaDeltaError("active Rufous species summary has an invalid profile path")
        profile_path = profile_url.removeprefix("/")
        profile = assets.get(profile_path)
        if not isinstance(profile, dict):
            raise PublicMediaDeltaError("active Rufous species profile is missing")
        scientific_name = profile.get("scientific_name")
        media = profile.get("media")
        if (
            not isinstance(scientific_name, str)
            or not scientific_name
            or summary.get("scientific_name") != scientific_name
            or summary.get("common_name") != profile.get("common_name")
            or summary.get("species_code") != profile.get("species_code")
            or not isinstance(media, list)
            or len(media) > 1
            or summary.get("photo_count") != len(media)
            or summary.get("hero_photo") != (media[0] if media else None)
        ):
            raise PublicMediaDeltaError(
                f"active Rufous species summary/profile drift at {profile_path}"
            )
        species_key = scientific_name.casefold()
        if species_key in bindings:
            raise PublicMediaDeltaError("active Rufous scientific names must be unique")
        bindings[species_key] = _SpeciesBinding(
            scientific_name=scientific_name,
            summary_index=index,
            profile_path=profile_path,
        )
        if media:
            item = media[0]
            if not isinstance(item, dict) or item.get("provider") not in {
                "usfws",
                "inaturalist",
            }:
                raise PublicMediaDeltaError("active Rufous media has an unsupported provider")
            if item.get("scientific_name") != scientific_name:
                raise PublicMediaDeltaError("active Rufous media scientific name has drifted")
            providers.add(str(item["provider"]))
            media_items += 1
            species_with_media += 1
    if (
        counts.get("media_items") != media_items
        or counts.get("species_with_media") != species_with_media
    ):
        raise PublicMediaDeltaError("active Rufous media counts do not match species profiles")
    return bindings, providers


def _partition_selections(
    selections: Mapping[str, VisualSelection],
) -> tuple[dict[str, VisualSelection], dict[str, VisualSelection]]:
    usfws: dict[str, VisualSelection] = {}
    inaturalist: dict[str, VisualSelection] = {}
    for species_key, selection in selections.items():
        if all(_USFWS_MEDIA_PAGE.fullmatch(url) for url in selection.source_page_urls):
            usfws[species_key] = selection
        elif all(_INATURALIST_MEDIA_PAGE.fullmatch(url) for url in selection.source_page_urls):
            inaturalist[species_key] = selection
        else:
            raise PublicMediaDeltaError(
                f"visual selection has mixed or unsupported provenance: {selection.scientific_name}"
            )
    return usfws, inaturalist


def _active_provider_media(
    assets: Mapping[str, JsonObject],
    bindings: Mapping[str, _SpeciesBinding],
    provider: str,
) -> dict[str, JsonObject]:
    result: dict[str, JsonObject] = {}
    for species_key, binding in bindings.items():
        profile = assets[binding.profile_path]
        media = profile["media"]
        assert isinstance(media, list)
        if media and isinstance(media[0], dict) and media[0].get("provider") == provider:
            result[species_key] = media[0]
    return result


def _validate_target_media_state(
    assets: Mapping[str, JsonObject],
    bindings: Mapping[str, _SpeciesBinding],
    selected_media: Mapping[str, list[JsonObject]],
) -> None:
    for species_key, items in selected_media.items():
        binding = bindings[species_key]
        current = assets[binding.profile_path].get("media")
        expected = items[0]
        if current not in ([], [expected]):
            raise PublicMediaDeltaError(
                "refusing to replace an existing species image for " + binding.scientific_name
            )


def _validate_active_usfws(
    assets: Mapping[str, JsonObject],
    bindings: Mapping[str, _SpeciesBinding],
    committed: Mapping[str, VisualSelection],
) -> None:
    active = _active_provider_media(assets, bindings, "usfws")
    if not active or set(active) != set(committed):
        raise PublicMediaDeltaError(
            "active USFWS species do not exactly match committed USFWS selections"
        )
    for species_key, item in active.items():
        selection = committed[species_key]
        binding = bindings[species_key]
        source_url = item.get("source_url")
        if (
            selection.scientific_name != binding.scientific_name
            or item.get("sha256") != selection.sha256
            or not isinstance(source_url, str)
            or source_url not in selection.source_page_urls
        ):
            raise PublicMediaDeltaError(
                "active USFWS image drifted from its committed selection for "
                + binding.scientific_name
            )


def _validate_active_media_source(manifest: JsonObject, providers: set[str]) -> None:
    source_policy = manifest.get("source_policy")
    if not isinstance(source_policy, dict):
        raise PublicMediaDeltaError("active Rufous source policy is malformed")
    marker = source_policy.get("media_source")
    delivery = source_policy.get("media_delivery")
    expected_marker = (
        "usfws"
        if providers == {"usfws"}
        else "usfws+inaturalist"
        if providers == {"usfws", "inaturalist"}
        else None
    )
    if expected_marker is None or marker != expected_marker or delivery != "immutable_r2":
        raise PublicMediaDeltaError(
            "active snapshot must contain only the approved USFWS base or exact retry media"
        )


def _update_attribution(assets: dict[str, JsonObject], timestamp: str) -> None:
    attribution = assets.get("data/attribution.json")
    if not isinstance(attribution, dict) or not isinstance(attribution.get("sources"), list):
        raise PublicMediaDeltaError("active Rufous attribution is malformed")
    sources = attribution["sources"]
    assert isinstance(sources, list)
    provider_indexes: dict[str, list[int]] = {}
    for index, source in enumerate(sources):
        if not isinstance(source, dict):
            raise PublicMediaDeltaError("active Rufous attribution source is malformed")
        provider = source.get("provider")
        if isinstance(provider, str):
            provider_indexes.setdefault(provider, []).append(index)
    usfws_indexes = provider_indexes.get("usfws", [])
    if len(usfws_indexes) != 1:
        raise PublicMediaDeltaError("active Rufous attribution must have one USFWS source")
    usfws_index = usfws_indexes[0]
    if sources[usfws_index] != _USFWS_ATTRIBUTION_SOURCE:
        raise PublicMediaDeltaError("active USFWS attribution source has drifted")
    inaturalist_indexes = provider_indexes.get("inaturalist", [])
    if not inaturalist_indexes:
        sources.insert(usfws_index, copy.deepcopy(_INATURALIST_ATTRIBUTION_SOURCE))
    elif (
        len(inaturalist_indexes) != 1
        or sources[inaturalist_indexes[0]] != _INATURALIST_ATTRIBUTION_SOURCE
    ):
        raise PublicMediaDeltaError("active iNaturalist attribution source has drifted")
    attribution["generated_at"] = timestamp


def _require_aware_timestamp(value: str) -> None:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        raise PublicMediaDeltaError("generated_at must be an ISO 8601 timestamp") from None
    if parsed.tzinfo is None:
        raise PublicMediaDeltaError("generated_at must include a timezone")


def _assert_allowed_asset_changes(
    before: Mapping[str, JsonObject],
    after: Mapping[str, JsonObject],
    *,
    changed_profile_paths: set[str],
    changed_summary_indexes: set[int],
) -> None:
    """Fail if composition changed anything beyond the narrow media projection."""
    if set(before) != set(after):
        raise PublicMediaDeltaError("media delta changed the public JSON inventory")
    for asset_path in sorted(before):
        changes = _changed_paths(before[asset_path], after[asset_path])
        if not changes:
            continue
        allowed: tuple[tuple[str | int, ...], ...]
        if asset_path in changed_profile_paths:
            allowed = (("media",),)
        elif asset_path == "data/attribution.json":
            allowed = (("generated_at",), ("sources",))
        elif asset_path == "data/manifest.json":
            allowed = (
                ("generated_at",),
                ("data_version",),
                ("source_policy", "media_source"),
                ("source_policy", "media_delivery"),
                ("counts", "media_items"),
                ("counts", "species_with_media"),
                *tuple(
                    ("species", index, field)
                    for index in sorted(changed_summary_indexes)
                    for field in ("hero_photo", "photo_count")
                ),
            )
        else:
            allowed = ()
        unexpected = [
            change
            for change in changes
            if not any(change[: len(prefix)] == prefix for prefix in allowed)
        ]
        if unexpected:
            rendered = "/".join(str(part) for part in unexpected[0])
            raise PublicMediaDeltaError(
                f"media delta unexpectedly changed {asset_path} at {rendered or '<root>'}"
            )


def _changed_paths(
    before: object,
    after: object,
    prefix: tuple[str | int, ...] = (),
) -> list[tuple[str | int, ...]]:
    if type(before) is not type(after):
        return [prefix]
    if isinstance(before, dict) and isinstance(after, dict):
        if set(before) != set(after):
            return [prefix]
        changes: list[tuple[str | int, ...]] = []
        for key in sorted(before):
            changes.extend(_changed_paths(before[key], after[key], (*prefix, key)))
        return changes
    if isinstance(before, list) and isinstance(after, list):
        if len(before) != len(after):
            return [prefix]
        changes = []
        for index, (left, right) in enumerate(zip(before, after, strict=True)):
            changes.extend(_changed_paths(left, right, (*prefix, index)))
        return changes
    return [] if before == after else [prefix]


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Apply reviewed iNaturalist photos to an active Rufous public snapshot."
    )
    parser.add_argument(
        "--active-root",
        type=Path,
        required=True,
        help="Hydrated static-site root or its data directory.",
    )
    parser.add_argument(
        "--prepared-media-dir",
        type=Path,
        required=True,
        help="iNaturalist-only preparation containing manifest.json and objects/.",
    )
    parser.add_argument(
        "--approvals",
        type=Path,
        required=True,
        help="Committed Rufous visual-approval ledger.",
    )
    parser.add_argument(
        "--output-root",
        type=Path,
        required=True,
        help="Dedicated public-export root to atomically write as data/... JSON.",
    )
    parser.add_argument("--generated-at", help=argparse.SUPPRESS)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    try:
        result = compose_public_media_delta(
            active_root=args.active_root,
            prepared_media_dir=args.prepared_media_dir,
            approval_path=args.approvals,
            output_dir=args.output_root,
            generated_at=args.generated_at,
        )
    except PublicMediaDeltaError as exc:
        print(f"Rufous media delta failed: {exc}", file=sys.stderr)
        return 2
    print(
        json.dumps(
            {
                "added_species": result.added_species,
                "data_version": result.data_version,
                "output_root": str(result.output_root),
                "reused_species": result.reused_species,
                "selected_objects": result.selected_objects,
                "selected_species": result.selected_species,
            },
            sort_keys=True,
        )
    )
    return 0


__all__ = [
    "EXPECTED_INATURALIST_SELECTIONS",
    "PublicMediaDeltaError",
    "PublicMediaDeltaResult",
    "compose_public_media_delta",
    "main",
]
