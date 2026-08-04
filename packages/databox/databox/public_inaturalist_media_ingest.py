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
from databox.public_export import PublicExportError
from databox.public_media_approval import MediaApprovalError, load_visual_approvals
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
) -> InaturalistMediaIngestResult:
    """Run the normal dlt -> Quack/DuckDB path for proven missing species."""
    missing = load_missing_public_species_targets(database_path, approval_path)
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
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    try:
        result = ingest_public_inaturalist_media(args.database, args.approvals)
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
