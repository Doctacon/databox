"""Compose and verify Rufous's provider-free immutable public-media pin.

The pin contains only the browser-safe media projection and immutable R2 object
URLs.  Upstream image-object URLs, preparation scores, cache metadata, and
unselected candidates never cross this boundary.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import tempfile
from pathlib import Path
from typing import Any

from databox.public_export import PublicExportError, load_public_media_manifest
from databox.public_media_approval import (
    DISQUALIFYING_REJECTION_REASONS,
    MediaApprovalError,
    load_manifest_provenance,
    load_visual_approvals,
    load_visual_rejections,
    require_visual_approvals,
)

PIN_SCHEMA_VERSION = 1
PIN_MODE = "rufous-media-preparation"
PUBLIC_BASE_URL = "https://rufous-data.loughondata.com/rufous-media/v1"
MAX_PIN_BYTES = 25 * 1024 * 1024

_SHA256 = re.compile(r"^[a-f0-9]{64}$")
_SPECIES_CODE = re.compile(r"^[a-z0-9][a-z0-9-]{0,31}$")
_PROVIDERS = frozenset({"inaturalist", "wikimedia"})
_PIN_ROOT_KEYS = frozenset(
    {
        "schema_version",
        "mode",
        "generated_at",
        "source_data_version",
        "public_base_url",
        "counts",
        "items",
    }
)
_PIN_ITEM_KEYS = frozenset(
    {
        "alt_text",
        "attribution_id",
        "caption",
        "common_name",
        "creator",
        "height",
        "hero_score",
        "kind",
        "license",
        "license_url",
        "media_id",
        "mime_type",
        "provider",
        "scientific_name",
        "sha256",
        "source_page_url",
        "species_code",
        "title",
        "url",
        "width",
    }
)


class PublicMediaPinError(RuntimeError):
    """A reviewed media preparation cannot become the committed pin."""


def canonical_media_pin_json(payload: object) -> bytes:
    return (json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode(
        "utf-8"
    )


def compose_public_media_pin(
    *,
    base_manifest_path: Path,
    prepared_media_path: Path,
    approval_path: Path,
    output_path: Path,
    provider: str,
) -> dict[str, int]:
    """Add one selected provider preparation to an existing immutable pin."""
    if provider not in _PROVIDERS:
        raise PublicMediaPinError("media pin provider is not reviewed")
    base = _load_pin(base_manifest_path)
    prepared = _load_json(prepared_media_path, label="prepared-media manifest")
    _validate_manifest_contract(prepared, label="prepared-media manifest")
    _validate_public_projection(base_manifest_path)
    _validate_public_projection(prepared_media_path)

    selections = load_visual_approvals(approval_path)
    base_candidates = load_manifest_provenance(base_manifest_path)
    delta_plan = require_visual_approvals(
        prepared_media_path,
        approval_path,
        provider=provider,
    )
    if delta_plan.summary.excluded_species or (
        delta_plan.summary.selected_species != delta_plan.summary.manifest_species
    ):
        raise PublicMediaPinError("media pin delta must select one image for every species")

    base_items = base["items"]
    prepared_items = prepared["items"]
    assert isinstance(base_items, list)
    assert isinstance(prepared_items, list)
    base_species = {key[0] for key in base_candidates}
    if len(base_candidates) != len(base_items) or len(base_species) != len(base_items):
        raise PublicMediaPinError("base media pin must contain one candidate per species")
    for candidate in base_candidates.values():
        selection = selections.get(candidate.scientific_name.casefold())
        if (
            selection is None
            or selection.sha256 != candidate.sha256
            or not set(candidate.source_page_urls).issubset(selection.source_page_urls)
        ):
            raise PublicMediaPinError(
                "base media pin is not an exact committed selection for "
                + candidate.scientific_name
            )

    selected_delta = delta_plan.selected_sha256_by_species
    selected_raw = [
        item
        for item in prepared_items
        if isinstance(item, dict)
        and selected_delta.get(str(item.get("scientific_name", "")).casefold())
        == item.get("sha256")
    ]
    if len(selected_raw) != len(selected_delta):
        raise PublicMediaPinError("selected media pin delta is not one exact row per species")

    projected_base = [_project_item(item, label="base media pin") for item in base_items]
    projected_delta = [
        _project_item(item, label=f"selected {provider} media") for item in selected_raw
    ]
    combined = sorted(
        [*projected_base, *projected_delta],
        key=lambda item: (
            str(item["scientific_name"]).casefold(),
            str(item["species_code"]),
            str(item["sha256"]),
        ),
    )
    _require_unique_combined_items(combined)
    combined_species = {str(item["scientific_name"]).casefold() for item in combined}
    if set(selections) != combined_species:
        raise PublicMediaPinError(
            "combined media pin does not cover exactly the committed visual selections"
        )
    _reject_disqualified_selected_hashes(combined, approval_path)

    output = {
        "schema_version": PIN_SCHEMA_VERSION,
        "mode": PIN_MODE,
        "generated_at": prepared.get("generated_at", base["generated_at"]),
        "source_data_version": base["source_data_version"],
        "public_base_url": PUBLIC_BASE_URL,
        "counts": {
            "items": len(combined),
            "objects": len({str(item["sha256"]) for item in combined}),
            "species": len(combined_species),
        },
        "items": combined,
    }
    _atomic_write(output_path, output)
    # Re-open through both independent production readers before returning.
    _load_pin(output_path)
    require_visual_approvals(output_path, approval_path)
    _validate_public_projection(output_path)
    return {
        "base_items": len(projected_base),
        "added_items": len(projected_delta),
        "items": len(combined),
        "species": len(combined_species),
    }


def verify_pinned_media_delta(
    *,
    pinned_manifest_path: Path,
    prepared_media_path: Path,
    approval_path: Path,
    provider: str,
) -> int:
    """Prove the committed pin exactly contains a selected provider preparation."""
    if provider not in _PROVIDERS:
        raise PublicMediaPinError("media pin provider is not reviewed")
    pinned = _load_pin(pinned_manifest_path)
    prepared = _load_json(prepared_media_path, label="prepared-media manifest")
    _validate_manifest_contract(prepared, label="prepared-media manifest")
    require_visual_approvals(pinned_manifest_path, approval_path)
    plan = require_visual_approvals(prepared_media_path, approval_path, provider=provider)
    if plan.summary.excluded_species or (
        plan.summary.selected_species != plan.summary.manifest_species
    ):
        raise PublicMediaPinError("prepared media delta is not fully selected")
    _validate_public_projection(pinned_manifest_path)
    _validate_public_projection(prepared_media_path)

    pinned_items = pinned["items"]
    prepared_items = prepared["items"]
    assert isinstance(pinned_items, list)
    assert isinstance(prepared_items, list)
    pinned_by_species = {
        str(item["scientific_name"]).casefold(): _project_item(item, label="media pin")
        for item in pinned_items
        if isinstance(item, dict)
    }
    selected = plan.selected_sha256_by_species
    selected_rows = [
        item
        for item in prepared_items
        if isinstance(item, dict)
        and selected.get(str(item.get("scientific_name", "")).casefold()) == item.get("sha256")
    ]
    if len(selected_rows) != len(selected):
        raise PublicMediaPinError("prepared media delta is not one exact row per species")
    for raw in selected_rows:
        projected = _project_item(raw, label=f"selected {provider} media")
        species_key = str(projected["scientific_name"]).casefold()
        if pinned_by_species.get(species_key) != projected:
            raise PublicMediaPinError(
                "committed media pin differs from prepared selected media for "
                + str(projected["scientific_name"])
            )
    return len(selected_rows)


def _load_pin(path: Path) -> dict[str, Any]:
    payload = _load_json(path, label="media pin")
    if set(payload) != _PIN_ROOT_KEYS:
        raise PublicMediaPinError("media pin has unexpected fields")
    _validate_manifest_contract(payload, label="media pin")
    if (
        payload.get("public_base_url") != PUBLIC_BASE_URL
        or not isinstance(payload.get("source_data_version"), str)
        or _SHA256.fullmatch(str(payload["source_data_version"])) is None
    ):
        raise PublicMediaPinError("media pin has invalid immutable release metadata")
    raw = path.read_bytes()
    if raw != canonical_media_pin_json(payload):
        raise PublicMediaPinError("media pin must use canonical sorted JSON")
    items = payload["items"]
    assert isinstance(items, list)
    projected = [_project_item(item, label="media pin") for item in items]
    if projected != items:
        raise PublicMediaPinError("media pin contains non-public or noncanonical item fields")
    _require_unique_combined_items(projected)
    return payload


def _load_json(path: Path, *, label: str) -> dict[str, Any]:
    if path.is_symlink() or not path.is_file():
        raise PublicMediaPinError(f"{label} is missing or unsafe")
    try:
        raw = path.read_bytes()
    except OSError as exc:
        raise PublicMediaPinError(f"could not read {label}") from exc
    if not raw or len(raw) > MAX_PIN_BYTES:
        raise PublicMediaPinError(f"{label} is empty or exceeds 25 MiB")
    try:
        payload: object = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise PublicMediaPinError(f"{label} is not valid UTF-8 JSON") from None
    if not isinstance(payload, dict):
        raise PublicMediaPinError(f"{label} must be an object")
    return payload


def _validate_manifest_contract(payload: dict[str, Any], *, label: str) -> None:
    items = payload.get("items")
    counts = payload.get("counts")
    if (
        payload.get("schema_version") != PIN_SCHEMA_VERSION
        or payload.get("mode") != PIN_MODE
        or not isinstance(items, list)
        or not items
        or not isinstance(counts, dict)
        or counts.get("items") != len(items)
    ):
        raise PublicMediaPinError(f"{label} has an invalid preparation contract")


def _validate_public_projection(path: Path) -> None:
    try:
        load_public_media_manifest(path)
    except PublicExportError as exc:
        raise PublicMediaPinError(str(exc)) from exc


def _project_item(raw: object, *, label: str) -> dict[str, object]:
    if not isinstance(raw, dict):
        raise PublicMediaPinError(f"{label} contains a malformed item")
    missing = _PIN_ITEM_KEYS - set(raw) - {"kind"}
    if missing:
        raise PublicMediaPinError(f"{label} item is missing required public fields")
    species_code = raw.get("species_code")
    common_name = raw.get("common_name")
    if (
        not isinstance(species_code, str)
        or _SPECIES_CODE.fullmatch(species_code) is None
        or not isinstance(common_name, str)
        or not common_name.strip()
    ):
        raise PublicMediaPinError(f"{label} item has an invalid species identity")
    item = {key: raw.get(key) for key in _PIN_ITEM_KEYS if key not in {"kind", "hero_score"}}
    item["kind"] = "photo"
    item["hero_score"] = 0
    return dict(sorted(item.items()))


def _require_unique_combined_items(items: list[dict[str, object]]) -> None:
    identity_fields = ("scientific_name", "sha256", "media_id", "attribution_id")
    for field in identity_fields:
        values = [str(item[field]).casefold() for item in items]
        if len(values) != len(set(values)):
            raise PublicMediaPinError(f"media pin repeats {field}")


def _reject_disqualified_selected_hashes(
    items: list[dict[str, object]], approval_path: Path
) -> None:
    selected_hashes = {str(item["sha256"]) for item in items}
    disqualified = {
        rejection.sha256
        for rejection in load_visual_rejections(approval_path).values()
        if rejection.reason in DISQUALIFYING_REJECTION_REASONS
    }
    conflict = sorted(selected_hashes.intersection(disqualified))
    if conflict:
        raise PublicMediaPinError(
            "media pin selects pixels carrying a disqualifying visual rejection: " + conflict[0]
        )


def _atomic_write(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        mode="wb", prefix=f".{path.name}-", dir=path.parent, delete=False
    ) as stream:
        temporary = Path(stream.name)
        stream.write(canonical_media_pin_json(payload))
    try:
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--base", type=Path)
    source.add_argument("--verify-pinned", type=Path)
    parser.add_argument("--prepared", required=True, type=Path)
    parser.add_argument("--approvals", required=True, type=Path)
    parser.add_argument("--provider", required=True, choices=sorted(_PROVIDERS))
    parser.add_argument("--output", type=Path)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    try:
        if args.base is not None:
            if args.output is None:
                raise PublicMediaPinError("pin composition requires --output")
            result: object = compose_public_media_pin(
                base_manifest_path=args.base,
                prepared_media_path=args.prepared,
                approval_path=args.approvals,
                output_path=args.output,
                provider=args.provider,
            )
        else:
            if args.output is not None:
                raise PublicMediaPinError("pin verification does not accept --output")
            result = {
                "verified_items": verify_pinned_media_delta(
                    pinned_manifest_path=args.verify_pinned,
                    prepared_media_path=args.prepared,
                    approval_path=args.approvals,
                    provider=args.provider,
                )
            }
    except (MediaApprovalError, PublicMediaPinError) as exc:
        print(f"Rufous media pin failed: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(result, sort_keys=True))
    return 0


__all__ = [
    "PublicMediaPinError",
    "canonical_media_pin_json",
    "compose_public_media_pin",
    "main",
    "verify_pinned_media_delta",
]
