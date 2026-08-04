"""Compose one reviewed provider's media delta over the active Rufous snapshot.

This path deliberately does not rebuild, download, or otherwise touch existing
media.  It treats the hydrated production JSON as an immutable, verified base,
proves that every live photo still matches the committed human selection
ledger, and adds only newly selected species from one explicit provider.
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
    ALLOWED_LICENSES,
    JsonObject,
    PublicExportError,
    load_public_assets,
    load_public_media_manifest,
    semantic_data_version,
    write_public_assets,
)
from databox.public_media_approval import (
    DISQUALIFYING_REJECTION_REASONS,
    MediaApprovalError,
    MediaCandidate,
    VisualSelection,
    load_manifest_provenance,
    load_visual_approvals,
    load_visual_rejections,
)
from databox.public_media_release import scan_prepared_media
from databox.public_release import PublicReleaseError

_USFWS_MEDIA_PAGE = re.compile(
    r"^https://www\.fws\.gov/media/[a-z0-9](?:[a-z0-9-]{0,238}[a-z0-9])?$"
)
_INATURALIST_MEDIA_PAGE = re.compile(r"^https://www\.inaturalist\.org/photos/[1-9][0-9]*$")
_WIKIMEDIA_MEDIA_PAGE = re.compile(
    r"^https://commons\.wikimedia\.org/wiki/File:[^/?#\x00-\x20\x7f]+$"
)
_DELTA_PROVIDERS = frozenset({"inaturalist", "wikimedia"})
_IMAGE_PROVIDERS = frozenset({"usfws", *_DELTA_PROVIDERS})
_PROVIDER_LABEL = {
    "usfws": "USFWS",
    "inaturalist": "iNaturalist",
    "wikimedia": "Wikimedia",
}
_MEDIA_SOURCE_MARKERS = {
    frozenset({"usfws"}): "usfws",
    frozenset({"usfws", "inaturalist"}): "usfws+inaturalist",
    frozenset({"usfws", "wikimedia"}): "usfws+wikimedia",
    frozenset({"usfws", "inaturalist", "wikimedia"}): ("usfws+inaturalist+wikimedia"),
}
_CURRENT_LICENSE_ALLOWLIST = {
    provider: sorted(values) for provider, values in ALLOWED_LICENSES.items()
}
_PRE_WIKIMEDIA_LICENSE_ALLOWLIST = {
    provider: values
    for provider, values in _CURRENT_LICENSE_ALLOWLIST.items()
    if provider != "wikimedia"
}

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

_WIKIMEDIA_ATTRIBUTION_SOURCE: JsonObject = {
    "provider": "wikimedia",
    "title": "Wikimedia Commons",
    "url": "https://commons.wikimedia.org/",
    "license": "Per-item Public Domain or Creative Commons license",
    "license_url": None,
    "credit": "Individual creators are credited on each media item.",
    "modifications": (
        "Rufous resized, re-encoded, and stripped metadata from reviewed web display "
        "copies; each credit links to the original Wikimedia Commons File page."
    ),
}

_ATTRIBUTION_SOURCE_BY_PROVIDER = {
    "usfws": _USFWS_ATTRIBUTION_SOURCE,
    "inaturalist": _INATURALIST_ATTRIBUTION_SOURCE,
    "wikimedia": _WIKIMEDIA_ATTRIBUTION_SOURCE,
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


@dataclass(frozen=True)
class _PendingMediaState:
    assets: dict[str, JsonObject]
    bindings: dict[str, _SpeciesBinding]
    active_providers: frozenset[str]
    pending: dict[str, VisualSelection]


def load_pending_public_media_selections(
    active_root: Path,
    approval_path: Path,
    *,
    provider: str,
) -> tuple[VisualSelection, ...]:
    """Return only committed, not-yet-live selections for one explicit provider.

    Loading the count is itself a release gate: the active snapshot, its source
    marker, every live image, and the complete approval ledger are validated
    before a provider can be contacted.
    """
    try:
        state = _pending_media_state(
            load_public_assets(active_root),
            approval_path=approval_path,
            provider=provider,
        )
    except PublicMediaDeltaError:
        raise
    except (MediaApprovalError, PublicExportError) as exc:
        raise PublicMediaDeltaError(str(exc)) from exc
    return tuple(state.pending[key] for key in sorted(state.pending))


def compose_public_media_delta(
    *,
    active_root: Path,
    prepared_media_dir: Path,
    approval_path: Path,
    output_dir: Path,
    provider: str = "inaturalist",
    generated_at: str | None = None,
) -> PublicMediaDeltaResult:
    """Add exactly the reviewed provider selections to active public JSON.

    The prepared directory remains unchanged so the same provider-scoped input
    can subsequently be passed to the immutable media publisher.  Only objects
    for selections that are not already live are decoded and hash-verified.
    """
    try:
        return _compose_public_media_delta(
            active_root=active_root,
            prepared_media_dir=prepared_media_dir,
            approval_path=approval_path,
            output_dir=output_dir,
            provider=provider,
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
    provider: str,
    generated_at: str | None,
) -> PublicMediaDeltaResult:
    state = _pending_media_state(
        load_public_assets(active_root),
        approval_path=approval_path,
        provider=provider,
    )
    active_assets = state.assets
    pending = state.pending
    if not pending:
        label = _PROVIDER_LABEL[provider]
        raise PublicMediaDeltaError(
            f"no pending {label} selections; every committed selection is already live"
        )

    prepared_manifest = prepared_media_dir / "manifest.json"
    candidates = load_manifest_provenance(prepared_manifest, provider=provider)
    _validate_pending_prepared_selections(
        candidates,
        pending,
        approval_path=approval_path,
        provider=provider,
    )
    selected_sha256_by_species = {
        species_key: selection.sha256 for species_key, selection in pending.items()
    }
    selected_sha256s = frozenset(selected_sha256_by_species.values())
    scanned_objects = scan_prepared_media(
        prepared_media_dir,
        selected_sha256s=selected_sha256s,
    )
    if {item.sha256 for item in scanned_objects} != selected_sha256s:
        raise PublicMediaDeltaError(f"selected {provider} prepared objects failed exact validation")

    selected_media = load_public_media_manifest(
        prepared_manifest,
        selected_sha256_by_species=selected_sha256_by_species,
    )
    if set(selected_media) != set(pending) or any(
        len(items) != 1 for items in selected_media.values()
    ):
        raise PublicMediaDeltaError(
            f"pending {provider} public projection is not exactly one per species"
        )

    timestamp = generated_at or datetime.now(UTC).isoformat()
    _require_aware_timestamp(timestamp)
    updated = copy.deepcopy(active_assets)
    updated_manifest = updated["data/manifest.json"]
    updated_bindings, _providers = _validate_active_species(updated)

    added = 0
    changed_profile_paths: set[str] = set()
    changed_summary_indexes: set[int] = set()
    for species_key in sorted(selected_media):
        item = copy.deepcopy(selected_media[species_key][0])
        binding = updated_bindings[species_key]
        profile = updated[binding.profile_path]
        current = profile.get("media")
        if current != []:
            raise PublicMediaDeltaError(
                "refusing to replace an existing species image for " + binding.scientific_name
            )
        profile["media"] = [item]
        added += 1
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
    expected_providers = set(state.active_providers).union({provider})
    marker = _MEDIA_SOURCE_MARKERS.get(frozenset(expected_providers))
    if marker is None:
        raise PublicMediaDeltaError("composed Rufous media provider combination is unsupported")
    source_policy["media_source"] = marker
    source_policy["media_delivery"] = "immutable_r2"
    _update_license_policy(updated_manifest)
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

    _update_attribution(
        updated,
        timestamp,
        active_providers=set(state.active_providers),
        updated_providers=expected_providers,
    )
    updated_manifest["data_version"] = semantic_data_version(updated)
    _assert_allowed_asset_changes(
        active_assets,
        updated,
        changed_profile_paths=changed_profile_paths,
        changed_summary_indexes=changed_summary_indexes,
    )
    # Re-run structural checks on the exact tree that will be written.
    _updated_bindings, updated_providers = _validate_active_species(updated)
    if updated_providers != expected_providers:
        raise PublicMediaDeltaError(
            "composed Rufous media providers do not match the bounded delta"
        )

    write_public_assets(output_dir, updated)
    return PublicMediaDeltaResult(
        output_root=output_dir.resolve(),
        data_version=str(updated_manifest["data_version"]),
        selected_species=len(selected_media),
        selected_objects=len(scanned_objects),
        added_species=added,
        reused_species=0,
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
            if not isinstance(item, dict) or item.get("provider") not in _IMAGE_PROVIDERS:
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
) -> dict[str, dict[str, VisualSelection]]:
    partitioned: dict[str, dict[str, VisualSelection]] = {
        provider: {} for provider in _IMAGE_PROVIDERS
    }
    for species_key, selection in selections.items():
        if all(_USFWS_MEDIA_PAGE.fullmatch(url) for url in selection.source_page_urls):
            provider = "usfws"
        elif all(_INATURALIST_MEDIA_PAGE.fullmatch(url) for url in selection.source_page_urls):
            provider = "inaturalist"
        elif all(_WIKIMEDIA_MEDIA_PAGE.fullmatch(url) for url in selection.source_page_urls):
            # The approval reader already applies the stricter decoded Commons
            # File-page validation before a selection reaches this function.
            provider = "wikimedia"
        else:
            raise PublicMediaDeltaError(
                f"visual selection has mixed or unsupported provenance: {selection.scientific_name}"
            )
        partitioned[provider][species_key] = selection
    return partitioned


def _pending_media_state(
    assets: dict[str, JsonObject],
    *,
    approval_path: Path,
    provider: str,
) -> _PendingMediaState:
    if provider not in _DELTA_PROVIDERS:
        raise PublicMediaDeltaError("media delta provider is not reviewed")
    manifest = assets.get("data/manifest.json")
    if not isinstance(manifest, dict) or manifest.get("release_mode") != "production":
        raise PublicMediaDeltaError("active Rufous snapshot must be a production release")

    bindings, active_providers = _validate_active_species(assets)
    selections_by_provider = _partition_selections(load_visual_approvals(approval_path))
    _validate_active_provider(
        assets,
        bindings,
        committed=selections_by_provider["usfws"],
        provider="usfws",
        require_exact=True,
    )
    for optional_provider in sorted(_DELTA_PROVIDERS):
        _validate_active_provider(
            assets,
            bindings,
            committed=selections_by_provider[optional_provider],
            provider=optional_provider,
            require_exact=False,
        )
    _validate_active_media_source(manifest, active_providers)
    _validate_license_policy_for_delta(manifest)

    active_selected_provider = _active_provider_media(assets, bindings, provider)
    pending = {
        species_key: selection
        for species_key, selection in selections_by_provider[provider].items()
        if species_key not in active_selected_provider
    }
    missing_targets = sorted(set(pending) - set(bindings))
    if missing_targets:
        raise PublicMediaDeltaError(
            f"pending {provider} species is absent from the active snapshot: "
            + pending[missing_targets[0]].scientific_name
        )
    _validate_pending_target_media_state(assets, bindings, pending, provider=provider)
    return _PendingMediaState(
        assets=assets,
        bindings=bindings,
        active_providers=frozenset(active_providers),
        pending=pending,
    )


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


def _validate_pending_target_media_state(
    assets: Mapping[str, JsonObject],
    bindings: Mapping[str, _SpeciesBinding],
    pending: Mapping[str, VisualSelection],
    *,
    provider: str,
) -> None:
    for species_key, selection in pending.items():
        binding = bindings[species_key]
        current = assets[binding.profile_path].get("media")
        if selection.scientific_name != binding.scientific_name:
            raise PublicMediaDeltaError(
                f"pending {provider} selection scientific name has drifted for "
                + binding.scientific_name
            )
        if current != []:
            raise PublicMediaDeltaError(
                "refusing to replace an existing species image for " + binding.scientific_name
            )


def _validate_pending_prepared_selections(
    candidates: Mapping[tuple[str, str], MediaCandidate],
    pending: Mapping[str, VisualSelection],
    *,
    approval_path: Path,
    provider: str,
) -> None:
    candidate_species = {species_key for species_key, _sha256 in candidates}
    if candidate_species != set(pending):
        unexpected = sorted(candidate_species - set(pending))
        missing = sorted(set(pending) - candidate_species)
        detail = (
            f"unexpected already-live or unselected species {unexpected[0]}"
            if unexpected
            else f"missing pending species {pending[missing[0]].scientific_name}"
        )
        raise PublicMediaDeltaError(
            f"prepared {provider} manifest must contain exactly the pending species; " + detail
        )

    for selection in pending.values():
        candidate = candidates.get(selection.key)
        if candidate is None:
            raise PublicMediaDeltaError(
                "pending selected pixels are absent from prepared media for "
                + selection.scientific_name
            )
        if not set(candidate.source_page_urls).issubset(selection.source_page_urls):
            raise PublicMediaDeltaError(
                "pending prepared provenance exceeds its committed selection for "
                + selection.scientific_name
            )

    disqualified_hashes = {
        rejection.sha256
        for rejection in load_visual_rejections(approval_path).values()
        if rejection.reason in DISQUALIFYING_REJECTION_REASONS
    }
    conflict = sorted(
        {selection.sha256 for selection in pending.values()}.intersection(disqualified_hashes)
    )
    if conflict:
        raise PublicMediaDeltaError(
            "pending selected pixels also carry a dead-bird, human-present, or "
            f"migration-map rejection: {conflict[0]}"
        )


def _validate_active_provider(
    assets: Mapping[str, JsonObject],
    bindings: Mapping[str, _SpeciesBinding],
    *,
    committed: Mapping[str, VisualSelection],
    provider: str,
    require_exact: bool,
) -> None:
    active = _active_provider_media(assets, bindings, provider)
    if require_exact and (not active or set(active) != set(committed)):
        label = _PROVIDER_LABEL[provider]
        raise PublicMediaDeltaError(
            f"active {label} species do not exactly match committed {label} selections"
        )
    uncommitted = sorted(set(active) - set(committed))
    if uncommitted:
        label = _PROVIDER_LABEL[provider]
        raise PublicMediaDeltaError(
            f"active {label} image has no committed selection for "
            + bindings[uncommitted[0]].scientific_name
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
            label = _PROVIDER_LABEL[provider]
            raise PublicMediaDeltaError(
                f"active {label} image drifted from its committed selection for "
                + binding.scientific_name
            )


def _validate_active_media_source(manifest: JsonObject, providers: set[str]) -> None:
    source_policy = manifest.get("source_policy")
    if not isinstance(source_policy, dict):
        raise PublicMediaDeltaError("active Rufous source policy is malformed")
    marker = source_policy.get("media_source")
    delivery = source_policy.get("media_delivery")
    expected_marker = _MEDIA_SOURCE_MARKERS.get(frozenset(providers))
    if expected_marker is None or marker != expected_marker or delivery != "immutable_r2":
        raise PublicMediaDeltaError(
            "active snapshot must contain the approved USFWS base and only pinned media"
        )


def _validate_license_policy_for_delta(manifest: JsonObject) -> bool:
    """Accept only the current policy or its exact pre-Wikimedia predecessor."""
    policy = manifest.get("license_policy")
    if (
        not isinstance(policy, dict)
        or set(policy) != {"version", "allowed", "rejected_counts"}
        or policy.get("version") != 1
        or not isinstance(policy.get("rejected_counts"), dict)
        or any(
            not isinstance(name, str)
            or not name
            or isinstance(count, bool)
            or not isinstance(count, int)
            or count < 0
            for name, count in policy["rejected_counts"].items()
        )
    ):
        raise PublicMediaDeltaError("active Rufous license policy is malformed")
    allowed = policy.get("allowed")
    if allowed == _CURRENT_LICENSE_ALLOWLIST:
        return False
    if allowed == _PRE_WIKIMEDIA_LICENSE_ALLOWLIST:
        return True
    raise PublicMediaDeltaError(
        "active Rufous license allowlist is neither current nor the exact pre-Wikimedia policy"
    )


def _update_license_policy(manifest: JsonObject) -> None:
    if not _validate_license_policy_for_delta(manifest):
        return
    policy = manifest["license_policy"]
    assert isinstance(policy, dict)
    policy["allowed"] = copy.deepcopy(_CURRENT_LICENSE_ALLOWLIST)


def _update_attribution(
    assets: dict[str, JsonObject],
    timestamp: str,
    *,
    active_providers: set[str],
    updated_providers: set[str],
) -> None:
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
    image_indexes = sorted(
        index
        for provider_name in _IMAGE_PROVIDERS
        for index in provider_indexes.get(provider_name, [])
    )
    if not image_indexes:
        raise PublicMediaDeltaError("active Rufous attribution has no image provider source")
    for provider_name in _IMAGE_PROVIDERS:
        indexes = provider_indexes.get(provider_name, [])
        if indexes and (
            len(indexes) != 1
            or sources[indexes[0]] != _ATTRIBUTION_SOURCE_BY_PROVIDER[provider_name]
        ):
            raise PublicMediaDeltaError(f"active {provider_name} attribution source has drifted")
    existing_image_providers = {
        provider_name for provider_name in _IMAGE_PROVIDERS if provider_indexes.get(provider_name)
    }
    if existing_image_providers != active_providers:
        raise PublicMediaDeltaError("active Rufous image attribution providers are inconsistent")

    insertion_index = image_indexes[0]
    non_image_sources = [
        source
        for source in sources
        if not isinstance(source.get("provider"), str)
        or source.get("provider") not in _IMAGE_PROVIDERS
    ]
    sources[:] = [
        *non_image_sources[:insertion_index],
        *(
            copy.deepcopy(_ATTRIBUTION_SOURCE_BY_PROVIDER[name])
            for name in sorted(updated_providers)
        ),
        *non_image_sources[insertion_index:],
    ]
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
                ("license_policy", "allowed"),
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
        description="Apply one reviewed provider's photos to an active Rufous public snapshot."
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
        help="Provider-only preparation containing manifest.json and objects/.",
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
    parser.add_argument(
        "--provider",
        required=True,
        choices=sorted(_DELTA_PROVIDERS),
        help="Exact reviewed provider represented by the prepared media directory.",
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
            provider=args.provider,
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
    "PublicMediaDeltaError",
    "PublicMediaDeltaResult",
    "compose_public_media_delta",
    "load_pending_public_media_selections",
    "main",
]
