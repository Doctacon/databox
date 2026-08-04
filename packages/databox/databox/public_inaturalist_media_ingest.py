"""Load strict iNaturalist candidates only for Rufous species lacking an image."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path

import duckdb
from databox_sources._public_inaturalist.source import inaturalist_public_photo_source

from databox.config.settings import settings
from databox.destinations import (
    dlt_destination,
    dlt_pipeline,
    prepare_dlt_source,
    quack_ingest_session,
)
from databox.public_export import PublicExportError, load_public_assets
from databox.public_media_approval import (
    MediaApprovalError,
    VisualSelection,
    load_visual_approvals,
)
from databox.public_media_ingest import load_public_species_targets

_USFWS_SELECTION_PAGE = re.compile(
    r"^https://www\.fws\.gov/media/[a-z0-9](?:[a-z0-9-]{0,238}[a-z0-9])?$"
)
_INATURALIST_SELECTION_PAGE = re.compile(r"^https://www\.inaturalist\.org/photos/[1-9][0-9]*$")


@dataclass(frozen=True)
class InaturalistMediaIngestResult:
    missing_species: int
    exact_species: int
    species_with_candidates: int
    candidate_records: int
    completed_runs: int


def load_missing_public_species_targets(
    database_path: Path,
    approval_path: Path,
) -> list[dict[str, str]]:
    """Derive species whose iNaturalist metadata must be present this release.

    A species-level no-safe-USFWS-image decision is intentionally still
    missing: it says nothing about a separately licensed iNaturalist photo.
    An existing iNaturalist selection also remains a target so its source
    metadata and prepared bytes cannot disappear on the next full refresh.
    Only a committed, exact USFWS selection removes a catalog species.
    """
    targets = load_public_species_targets(database_path)
    selections = load_visual_approvals(approval_path)
    catalog_names = {item["scientific_name"].casefold() for item in targets}
    stale = sorted(set(selections) - catalog_names)
    if stale:
        raise PublicExportError(
            "visual approval ledger selects a species outside the current public catalog: "
            f"{stale[0]}"
        )
    usfws_selected = {
        species_name
        for species_name, selection in selections.items()
        if _selection_provider(selection.source_page_urls, species_name=species_name) == "usfws"
    }
    return [item for item in targets if item["scientific_name"].casefold() not in usfws_selected]


def load_selected_public_species_targets(
    public_output_root: Path,
    approval_path: Path,
) -> list[dict[str, str]]:
    """Derive only approved iNaturalist targets from an active public snapshot.

    This is the bounded media-delta path.  It deliberately does not consult the
    GBIF warehouse or infer every currently unpictured species: the committed
    human ledger is the complete target list.  ``load_public_assets`` first
    proves that the hydrated snapshot has an exact inventory and matching
    semantic data version.
    """
    assets = load_public_assets(public_output_root)
    manifest = assets.get("data/manifest.json")
    if not isinstance(manifest, dict) or manifest.get("release_mode") != "production":
        raise PublicExportError("iNaturalist media delta requires a production public snapshot")
    source_policy = manifest.get("source_policy")
    if (
        not isinstance(source_policy, dict)
        or source_policy.get("direct_ebird") != "excluded"
        or source_policy.get("occurrence_source") != "gbif"
    ):
        raise PublicExportError("iNaturalist media delta snapshot violates the source boundary")

    raw_species = manifest.get("species")
    if not isinstance(raw_species, list) or not raw_species:
        raise PublicExportError("iNaturalist media delta snapshot has no species catalog")
    catalog: dict[str, dict[str, str]] = {}
    media_by_name: dict[str, list[object]] = {}
    for summary in raw_species:
        if not isinstance(summary, dict):
            raise PublicExportError("iNaturalist media delta snapshot has malformed species")
        code = summary.get("species_code")
        common_name = summary.get("common_name")
        scientific_name = summary.get("scientific_name")
        profile_path = summary.get("profile_path")
        if (
            not isinstance(code, str)
            or not code
            or not isinstance(common_name, str)
            or not common_name
            or not isinstance(scientific_name, str)
            or not scientific_name
        ):
            raise PublicExportError("iNaturalist media delta snapshot has malformed species")
        expected_profile = f"/data/species/{code}.json"
        if profile_path != expected_profile:
            raise PublicExportError("iNaturalist media delta snapshot has unsafe species profile")
        profile = assets.get(expected_profile.removeprefix("/"))
        if (
            not isinstance(profile, dict)
            or profile.get("species_code") != code
            or profile.get("common_name") != common_name
            or profile.get("scientific_name") != scientific_name
            or not isinstance(profile.get("media"), list)
        ):
            raise PublicExportError("iNaturalist media delta species profile is inconsistent")
        key = scientific_name.casefold()
        if key in catalog:
            raise PublicExportError("iNaturalist media delta repeats a scientific name")
        catalog[key] = {
            "species_code": code,
            "common_name": common_name,
            "scientific_name": scientific_name,
        }
        media_by_name[key] = profile["media"]

    selections = load_visual_approvals(approval_path)
    selected_targets: list[dict[str, str]] = []
    for key, selection in sorted(selections.items()):
        provider = _selection_provider(selection.source_page_urls, species_name=key)
        if provider != "inaturalist":
            continue
        target = catalog.get(key)
        if target is None:
            raise PublicExportError(
                "visual approval ledger selects an iNaturalist species outside the active "
                f"public catalog: {selection.scientific_name}"
            )
        media = media_by_name[key]
        if media and not _is_identical_inaturalist_retry(media, selection):
            raise PublicExportError(
                "iNaturalist media delta refuses to replace existing media for "
                f"{selection.scientific_name}"
            )
        selected_targets.append(target)
    if not selected_targets:
        raise PublicExportError("visual approval ledger contains no iNaturalist selections")
    return sorted(selected_targets, key=lambda item: item["species_code"])


def _is_identical_inaturalist_retry(
    media: list[object],
    selection: VisualSelection,
) -> bool:
    """Allow an idempotent retry only for the exact already-selected object."""
    if len(media) != 1:
        return False
    item = media[0]
    return bool(
        isinstance(item, dict)
        and item.get("provider") == "inaturalist"
        and item.get("sha256") == selection.sha256
        and item.get("source_url") in selection.source_page_urls
    )


def _selection_provider(source_pages: tuple[str, ...], *, species_name: str) -> str:
    """Classify one already-validated ledger selection without guessing."""
    if source_pages and all(_USFWS_SELECTION_PAGE.fullmatch(url) for url in source_pages):
        return "usfws"
    if source_pages and all(_INATURALIST_SELECTION_PAGE.fullmatch(url) for url in source_pages):
        return "inaturalist"
    raise PublicExportError(
        f"visual approval selection has unsupported or mixed provider provenance for {species_name}"
    )


def ingest_public_inaturalist_media(
    database_path: Path,
    approval_path: Path,
    *,
    targets_from_public_output: Path | None = None,
) -> InaturalistMediaIngestResult:
    """Run the normal dlt -> Quack/DuckDB path for proven missing species."""
    missing = (
        load_missing_public_species_targets(database_path, approval_path)
        if targets_from_public_output is None
        else load_selected_public_species_targets(targets_from_public_output, approval_path)
    )
    if not missing:
        return InaturalistMediaIngestResult(0, 0, 0, 0, 0)
    loaded_at = datetime.now(UTC).isoformat()
    run_id = hashlib.sha256(
        json.dumps(
            {"loaded_at": loaded_at, "targets": missing},
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
    ).hexdigest()
    source = inaturalist_public_photo_source(
        missing_species=missing,
        run_id=run_id,
        loaded_at=loaded_at,
    )
    dataset_name = settings.raw_dataset_name("inaturalist")
    pipeline = dlt_pipeline(
        pipeline_name="inaturalist_public_media",
        destination=dlt_destination(str(database_path)),
        dataset_name=dataset_name,
        pipelines_dir=settings.dlt_data_dir,
    )
    with quack_ingest_session(dataset_name, db_path=str(database_path)):
        load_info = pipeline.run(prepare_dlt_source(source))
    if load_info.has_failed_jobs:
        raise PublicExportError("iNaturalist media ingestion has failed dlt load jobs")

    return _validate_ingested_snapshot(
        database_path,
        run_id=run_id,
        expected_target_count=len(missing),
    )


def _validate_ingested_snapshot(
    database_path: Path,
    *,
    run_id: str,
    expected_target_count: int,
) -> InaturalistMediaIngestResult:
    """Require the exact just-requested run and all of its declared rows."""

    connection = duckdb.connect(str(database_path), read_only=True)
    try:
        row = connection.execute(
            """SELECT
              target_species_count,
              exact_species_count,
              species_with_candidates,
              eligible_candidate_count
            FROM raw_inaturalist.photo_discovery_runs
            WHERE status = 'complete' AND run_id = ?""",
            [run_id],
        ).fetchone()
        species_row = connection.execute(
            """SELECT COUNT(*)
            FROM raw_inaturalist.photo_species_results
            WHERE run_id = ?""",
            [run_id],
        ).fetchone()
        candidate_row = connection.execute(
            """SELECT COUNT(*)
            FROM raw_inaturalist.photo_candidates
            WHERE run_id = ?""",
            [run_id],
        ).fetchone()
    finally:
        connection.close()
    if row is None or species_row is None or candidate_row is None:
        raise PublicExportError("iNaturalist media ingestion produced no exact complete snapshot")
    target_count, exact_count, species_with_candidates, candidates = map(int, row)
    if (
        target_count != expected_target_count
        or int(species_row[0]) != expected_target_count
        or int(candidate_row[0]) != candidates
    ):
        raise PublicExportError("iNaturalist media ingestion produced an incomplete snapshot")
    return InaturalistMediaIngestResult(
        missing_species=expected_target_count,
        exact_species=exact_count,
        species_with_candidates=species_with_candidates,
        candidate_records=candidates,
        completed_runs=1,
    )


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", required=True, type=Path)
    parser.add_argument("--approvals", required=True, type=Path)
    parser.add_argument(
        "--targets-from-public-output",
        type=Path,
        help=(
            "hydrate and validate this active production snapshot, then ingest only its "
            "committed iNaturalist selections"
        ),
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    try:
        result = ingest_public_inaturalist_media(
            args.database,
            args.approvals,
            targets_from_public_output=args.targets_from_public_output,
        )
    except (
        OSError,
        PublicExportError,
        MediaApprovalError,
        RuntimeError,
        duckdb.Error,
        ValueError,
    ) as exc:
        print(f"Rufous iNaturalist media ingestion failed: {exc}")
        return 1
    print(json.dumps(asdict(result), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
