"""Load a bounded USFWS media snapshot for the modeled public bird catalog."""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from pathlib import Path

import duckdb
from databox_sources.usfws.source import USFWS_MAX_TARGET_SPECIES, usfws_source
from pyiceberg.expressions import EqualTo

from databox.config.settings import settings
from databox.destinations.iceberg import (
    iceberg_destination,
    iceberg_dlt_pipeline,
    polaris_dlt_catalog,
    publish_dlt_load_status,
)
from databox.public_export import GBIF_EBIRD_EOD_TABLE, PublicExportError


@dataclass(frozen=True)
class MediaIngestResult:
    target_species: int
    raw_records: int
    completed_runs: int


def load_public_species_targets(database_path: Path) -> list[dict[str, str]]:
    """Derive exact target identities only from the modeled public relation."""
    if database_path.is_symlink() or not database_path.is_file():
        raise PublicExportError("public media target database is missing or unsafe")
    connection = duckdb.connect(str(database_path), read_only=True)
    try:
        exists = connection.execute(
            """SELECT 1 FROM information_schema.tables
            WHERE table_schema = 'rufous_public'
              AND table_name = 'gbif_eod_occurrence'"""
        ).fetchone()
        if exists is None:
            raise PublicExportError(f"public media targets require {GBIF_EBIRD_EOD_TABLE}")
        rows = connection.execute(
            f"""SELECT DISTINCT
              'gbif-' || CAST(
                COALESCE(accepted_taxon_key, taxon_key, species_key) AS VARCHAR
              ) AS species_code,
              TRIM(common_name) AS common_name,
              TRIM(scientific_name) AS scientific_name
            FROM {GBIF_EBIRD_EOD_TABLE}
            WHERE COALESCE(accepted_taxon_key, taxon_key, species_key) IS NOT NULL
              AND NULLIF(TRIM(common_name), '') IS NOT NULL
              AND REGEXP_FULL_MATCH(
                TRIM(scientific_name),
                '^[A-Z][A-Za-z-]+ [a-z][A-Za-z-]+$'
              )
            ORDER BY
              CASE WHEN LOWER(TRIM(scientific_name)) = 'selasphorus rufus' THEN 0 ELSE 1 END,
              common_name,
              species_code"""
        ).fetchall()
    finally:
        connection.close()
    targets = [
        {
            "species_code": str(row[0]),
            "common_name": str(row[1]),
            "scientific_name": str(row[2]),
        }
        for row in rows
    ]
    if not targets:
        raise PublicExportError("public media target catalog is empty")
    if len(targets) > USFWS_MAX_TARGET_SPECIES:
        raise PublicExportError(
            f"public media target catalog exceeds {USFWS_MAX_TARGET_SPECIES} species"
        )
    if not any(item["scientific_name"].casefold() == "selasphorus rufus" for item in targets):
        raise PublicExportError("public media targets are missing Rufous Hummingbird")
    return targets


def ingest_public_usfws_media(
    database_path: Path,
    *,
    max_images_per_target: int = 500,
) -> MediaIngestResult:
    """Run the dlt → Polaris Iceberg path with explicit public targets."""
    targets = load_public_species_targets(database_path)
    source = usfws_source(
        target_species=targets,
        max_images_per_target=max_images_per_target,
    )
    pipeline = iceberg_dlt_pipeline(
        pipeline_name="usfws_media_iceberg",
        destination=iceberg_destination(),
        dataset_name="raw_usfws",
        pipelines_dir=settings.dlt_data_dir,
    )
    with polaris_dlt_catalog():
        pipeline.run(source)
        publish_dlt_load_status(
            pipeline,
            dataset_name="raw_usfws",
            table_names=("image_search_runs", "image_records"),
        )

    catalog = settings.pyiceberg_catalog()
    raw_records = catalog.load_table("raw_usfws.image_records").scan().count()
    completed_runs = (
        catalog.load_table("raw_usfws.image_search_runs")
        .scan(row_filter=EqualTo("status", "complete"), selected_fields=("run_id",))
        .count()
    )
    if raw_records <= 0 or completed_runs <= 0:
        raise PublicExportError("USFWS media ingestion did not produce a complete snapshot")
    return MediaIngestResult(
        target_species=len(targets),
        raw_records=raw_records,
        completed_runs=completed_runs,
    )


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", required=True, type=Path)
    parser.add_argument("--max-images-per-target", type=int, default=500)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    try:
        result = ingest_public_usfws_media(
            args.database,
            max_images_per_target=args.max_images_per_target,
        )
    except (OSError, PublicExportError, duckdb.Error, ValueError) as exc:
        print(f"Rufous USFWS media ingestion failed: {exc}")
        return 1
    print(json.dumps(asdict(result), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
