"""Load a reviewed, offline Wikimedia Commons media snapshot into DuckDB.

This module deliberately has no network client.  A caller supplies a canonical
JSON file whose Commons metadata was collected and reviewed separately.  The
loader revalidates every row against the public-media contract and the current
production bird catalog, then transactionally replaces only the dedicated
Wikimedia staging table.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import asdict, dataclass
from pathlib import Path

import duckdb

from databox.public_export import PublicExportError, load_public_assets
from databox.public_media import (
    MAX_ELIGIBLE_ROWS,
    SOURCE_COLUMNS,
    PublicMediaError,
    SourceImageRow,
)

SCHEMA_VERSION = 1
MODE = "rufous-wikimedia-curated-media"
PROVIDER = "wikimedia"
DISCOVERY_METHOD = "wikimedia_commons_curated_file"
MAX_INPUT_BYTES = 8 * 1024 * 1024

_ROOT_KEYS = frozenset({"schema_version", "mode", "provider", "items"})
_ITEM_KEYS = frozenset(SOURCE_COLUMNS)
_TABLE = '"rufous_public"."wikimedia_commercial_image"'


@dataclass(frozen=True)
class WikimediaMediaIngestResult:
    input_sha256: str
    items: int
    species: int


def canonical_wikimedia_media_json(payload: object) -> bytes:
    """Return the sole accepted, review-friendly JSON representation."""
    return (json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode(
        "utf-8"
    )


def load_curated_wikimedia_media(
    database_path: str | Path,
    input_path: str | Path,
    *,
    targets_from_public_output: str | Path | None = None,
) -> WikimediaMediaIngestResult:
    """Validate ``input_path`` and replace only the Wikimedia media table."""
    database = _required_regular_file(database_path, label="DuckDB database")
    source = _required_regular_file(input_path, label="Wikimedia metadata input")
    if database == source:
        raise PublicMediaError("Wikimedia metadata input must not be the DuckDB database")

    raw, rows = _load_rows(source)
    public_catalog = (
        None
        if targets_from_public_output is None
        else _production_catalog_from_public_output(Path(targets_from_public_output))
    )
    try:
        connection = duckdb.connect(str(database))
    except duckdb.Error as exc:
        raise PublicMediaError("could not open the Wikimedia media database") from exc

    try:
        connection.execute("BEGIN TRANSACTION")
        if public_catalog is None:
            _require_production_species_identities(connection, rows)
        else:
            _require_species_identities(rows, public_catalog)
        connection.execute('CREATE SCHEMA IF NOT EXISTS "rufous_public"')
        connection.execute(
            f"""CREATE OR REPLACE TABLE {_TABLE} (
              species_code VARCHAR,
              common_name VARCHAR,
              scientific_name VARCHAR,
              source_page_url VARCHAR,
              source_image_url VARCHAR,
              creator VARCHAR,
              license VARCHAR,
              title VARCHAR,
              caption VARCHAR,
              alt_text VARCHAR,
              source_published_at TIMESTAMPTZ,
              source_width BIGINT,
              source_height BIGINT,
              mime_type VARCHAR,
              discovery_method VARCHAR,
              loaded_at TIMESTAMPTZ
            )"""
        )
        placeholders = ", ".join("?" for _column in SOURCE_COLUMNS)
        columns = ", ".join(f'"{column}"' for column in SOURCE_COLUMNS)
        connection.executemany(
            f"INSERT INTO {_TABLE} ({columns}) VALUES ({placeholders})",
            [_database_values(row) for row in rows],
        )
        _verify_replacement(connection, expected_rows=len(rows))
        connection.execute("COMMIT")
    except PublicMediaError:
        connection.execute("ROLLBACK")
        raise
    except duckdb.Error as exc:
        connection.execute("ROLLBACK")
        raise PublicMediaError("could not replace the Wikimedia media table") from exc
    finally:
        connection.close()

    return WikimediaMediaIngestResult(
        input_sha256=hashlib.sha256(raw).hexdigest(),
        items=len(rows),
        species=len({row.species_code for row in rows}),
    )


def _required_regular_file(value: str | Path, *, label: str) -> Path:
    requested = Path(value).expanduser()
    if requested.is_symlink() or not requested.is_file():
        raise PublicMediaError(f"{label} is missing or unsafe")
    return requested.resolve()


def _load_rows(path: Path) -> tuple[bytes, list[SourceImageRow]]:
    try:
        if path.stat().st_size > MAX_INPUT_BYTES:
            raise PublicMediaError("Wikimedia metadata input exceeds the safe size limit")
        raw = path.read_bytes()
    except PublicMediaError:
        raise
    except OSError as exc:
        raise PublicMediaError("could not read the Wikimedia metadata input") from exc
    try:
        decoded: object = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise PublicMediaError("Wikimedia metadata input is not valid UTF-8 JSON") from None
    if not isinstance(decoded, dict) or set(decoded) != _ROOT_KEYS:
        raise PublicMediaError("Wikimedia metadata input has unexpected fields")
    if (
        type(decoded.get("schema_version")) is not int
        or decoded.get("schema_version") != SCHEMA_VERSION
        or decoded.get("mode") != MODE
        or decoded.get("provider") != PROVIDER
    ):
        raise PublicMediaError("Wikimedia metadata input has an unsupported contract")
    if raw != canonical_wikimedia_media_json(decoded):
        raise PublicMediaError("Wikimedia metadata input must use canonical sorted JSON")

    raw_items = decoded.get("items")
    if not isinstance(raw_items, list) or not raw_items or len(raw_items) > MAX_ELIGIBLE_ROWS:
        raise PublicMediaError("Wikimedia metadata input has an invalid item list")

    rows: list[SourceImageRow] = []
    previous_sort_key: tuple[str, str, str] | None = None
    source_pages: set[str] = set()
    source_images: set[str] = set()
    for index, raw_item in enumerate(raw_items):
        if not isinstance(raw_item, dict) or set(raw_item) != _ITEM_KEYS:
            raise PublicMediaError(f"Wikimedia metadata item {index} has unexpected fields")
        values = {column: raw_item.get(column) for column in SOURCE_COLUMNS}
        values["provider"] = PROVIDER
        row = SourceImageRow.from_values(values)
        if row.discovery_method != DISCOVERY_METHOD:
            raise PublicMediaError(
                f"Wikimedia metadata item {index} has an unsupported discovery method"
            )
        if values != _canonical_source_values(row, include_provider=True):
            raise PublicMediaError(
                f"Wikimedia metadata item {index} contains noncanonical field values"
            )
        sort_key = _row_sort_key(row)
        if previous_sort_key is not None and sort_key <= previous_sort_key:
            raise PublicMediaError("Wikimedia metadata items must be uniquely sorted")
        previous_sort_key = sort_key
        if row.source_page_url in source_pages or row.source_image_url in source_images:
            raise PublicMediaError("Wikimedia metadata repeats one Commons file")
        source_pages.add(row.source_page_url)
        source_images.add(row.source_image_url)
        rows.append(row)
    return raw, rows


def _canonical_source_values(
    row: SourceImageRow,
    *,
    include_provider: bool,
) -> dict[str, object]:
    values: dict[str, object] = {
        "species_code": row.species_code,
        "common_name": row.common_name,
        "scientific_name": row.scientific_name,
        "source_page_url": row.source_page_url,
        "source_image_url": row.source_image_url,
        "creator": row.creator,
        "license": row.license,
        "title": row.title,
        "caption": row.caption,
        "alt_text": row.alt_text,
        "source_published_at": row.source_published_at,
        "source_width": row.source_width,
        "source_height": row.source_height,
        "mime_type": row.source_mime_type,
        "discovery_method": row.discovery_method,
        "loaded_at": row.loaded_at,
    }
    if include_provider:
        values["provider"] = row.provider
    return values


def _row_sort_key(row: SourceImageRow) -> tuple[str, str, str]:
    return row.scientific_name.casefold(), row.species_code, row.source_page_url


def _require_production_species_identities(
    connection: duckdb.DuckDBPyConnection,
    rows: list[SourceImageRow],
) -> None:
    try:
        catalog_rows = connection.execute(
            """SELECT DISTINCT
              'gbif-' || CAST(
                COALESCE(accepted_taxon_key, taxon_key, species_key) AS VARCHAR
              ) AS species_code,
              TRIM(common_name) AS common_name,
              TRIM(scientific_name) AS scientific_name
            FROM rufous_public.gbif_eod_occurrence
            WHERE COALESCE(accepted_taxon_key, taxon_key, species_key) IS NOT NULL
              AND NULLIF(TRIM(common_name), '') IS NOT NULL
              AND REGEXP_FULL_MATCH(
                TRIM(scientific_name),
                '^[A-Z][A-Za-z-]+ [a-z][A-Za-z-]+$'
              )"""
        ).fetchall()
    except duckdb.Error as exc:
        raise PublicMediaError(
            "Wikimedia media loading requires the modeled production species catalog"
        ) from exc
    if not catalog_rows:
        raise PublicMediaError("the modeled production species catalog is empty")

    catalog: dict[str, tuple[str, str]] = {}
    for species_code, common_name, scientific_name in catalog_rows:
        identity = (str(common_name), str(scientific_name))
        previous = catalog.get(str(species_code))
        if previous is not None and previous != identity:
            raise PublicMediaError("the production species catalog has conflicting identities")
        catalog[str(species_code)] = identity
    _require_species_identities(rows, catalog)


def _production_catalog_from_public_output(
    public_output_root: Path,
) -> dict[str, tuple[str, str]]:
    """Load the already-audited active catalog without contacting any provider."""
    try:
        assets = load_public_assets(public_output_root)
    except PublicExportError as exc:
        raise PublicMediaError(f"active public catalog is invalid: {exc}") from exc
    manifest = assets.get("data/manifest.json")
    if not isinstance(manifest, dict) or manifest.get("release_mode") != "production":
        raise PublicMediaError("Wikimedia loading requires an active production public catalog")
    source_policy = manifest.get("source_policy")
    if (
        not isinstance(source_policy, dict)
        or source_policy.get("direct_ebird") != "excluded"
        or source_policy.get("occurrence_source") != "gbif"
    ):
        raise PublicMediaError("active public catalog violates the production source boundary")
    summaries = manifest.get("species")
    if not isinstance(summaries, list) or not summaries:
        raise PublicMediaError("active public catalog has no species")
    catalog: dict[str, tuple[str, str]] = {}
    for summary in summaries:
        if not isinstance(summary, dict):
            raise PublicMediaError("active public catalog has a malformed species summary")
        species_code = summary.get("species_code")
        common_name = summary.get("common_name")
        scientific_name = summary.get("scientific_name")
        profile_path = summary.get("profile_path")
        expected_profile = (
            f"/data/species/{species_code}.json" if isinstance(species_code, str) else None
        )
        profile = (
            assets.get(expected_profile.removeprefix("/"))
            if isinstance(expected_profile, str)
            else None
        )
        if (
            not isinstance(species_code, str)
            or not species_code
            or not isinstance(common_name, str)
            or not common_name
            or not isinstance(scientific_name, str)
            or not scientific_name
            or profile_path != expected_profile
            or not isinstance(profile, dict)
            or profile.get("species_code") != species_code
            or profile.get("common_name") != common_name
            or profile.get("scientific_name") != scientific_name
        ):
            raise PublicMediaError("active public catalog has an inconsistent species identity")
        if species_code in catalog:
            raise PublicMediaError("active public catalog repeats a species code")
        catalog[species_code] = (common_name, scientific_name)
    return catalog


def _require_species_identities(
    rows: list[SourceImageRow],
    catalog: dict[str, tuple[str, str]],
) -> None:
    for row in rows:
        if catalog.get(row.species_code) != (row.common_name, row.scientific_name):
            raise PublicMediaError(
                "Wikimedia metadata does not match the production species identity for "
                f"{row.species_code}"
            )


def _database_values(row: SourceImageRow) -> tuple[object, ...]:
    values = _canonical_source_values(row, include_provider=False)
    return tuple(values[column] for column in SOURCE_COLUMNS)


def _verify_replacement(
    connection: duckdb.DuckDBPyConnection,
    *,
    expected_rows: int,
) -> None:
    columns = [
        str(row[0])
        for row in connection.execute(
            """SELECT column_name
            FROM information_schema.columns
            WHERE table_schema = 'rufous_public'
              AND table_name = 'wikimedia_commercial_image'
            ORDER BY ordinal_position"""
        ).fetchall()
    ]
    if columns != list(SOURCE_COLUMNS):
        raise PublicMediaError("Wikimedia media table does not have the exact reviewed schema")
    count_row = connection.execute(f"SELECT COUNT(*) FROM {_TABLE}").fetchone()
    if count_row is None or isinstance(count_row[0], bool) or int(count_row[0]) != expected_rows:
        raise PublicMediaError("Wikimedia media table replacement was incomplete")


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", required=True, type=Path)
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument(
        "--targets-from-public-output",
        type=Path,
        help=(
            "validate curated identities against this hydrated active production snapshot "
            "instead of requiring the local modeled occurrence table"
        ),
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    try:
        result = load_curated_wikimedia_media(
            args.database,
            args.input,
            targets_from_public_output=args.targets_from_public_output,
        )
    except (OSError, PublicMediaError, duckdb.Error, ValueError) as exc:
        print(f"Rufous Wikimedia media loading failed: {exc}")
        return 1
    print(json.dumps(asdict(result), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
