"""Versioned, local DuckDB data-product export for Rufous consumers."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import tempfile
from dataclasses import dataclass
from datetime import UTC, datetime
from importlib.metadata import version
from pathlib import Path

import duckdb

CONTRACT_NAME = "rufous-inputs"
SCHEMA_VERSION = 1
META_SCHEMA = "databox_product_meta"
DATA_SCHEMA = "rufous_inputs_v1"
MAX_RELATION_ROWS = 2_000_000
SNAPSHOT_ID_RELATIONS = frozenset(
    {
        "ebird_arizona_species_snapshot",
        "avonet_species_traits_snapshot",
        "gbif_occurrence_snapshot",
        "xeno_canto_recording_snapshot",
        "usfws_image_records",
        "usfws_image_search_runs",
    }
)


class ProductArtifactError(RuntimeError):
    """Raised when an export or consumer contract is invalid."""


@dataclass(frozen=True)
class RelationSpec:
    name: str
    query: str
    privacy: str


FROZEN_SCHEMA_HASHES = {
    "avonet_species_traits_snapshot": (
        "244badbf4928ad515cca3445360a4420d4e9ae70099aaf64237a8f970c63a319"
    ),
    "dim_bird_hotspot": "276eea881a254ba12b131a98988752ca1310ca57e88080c9b6e77286674827fd",
    "dim_bird_species_traits": "cf2eaff06803f64fbb8aaa857f98a87c96581d2770a572406acbfbc304d59cf0",
    "dim_species": "948dd6378d201f8e093b157943af25e95db18e20161e9e0b8dab26c096d97364",
    "ebird_arizona_species_snapshot": (
        "eb7704f11f608f94c21d781aeec27ac17acf504a222c62feaf6e9c21ce540e2f"
    ),
    "fact_bird_occurrence": "3947d48cf6b437c7dbbdbc15ced9bdae059f8a03d6f9b7e40dd8ebcd7ad7e823",
    "fact_bird_sound_recording": "430d64423b47d9a46be0fcc74445451062e75e9bda006d9cd62faf79f70b1ee0",
    "gbif_occurrence_snapshot": "b140497cb37f6413021635a1f71dde9f60e336888f446dec5abda625b331bbe1",
    "public_bird_observation": "16562dd64ae444b011cd9ba7d41c7e009c60e0d6d2b18a7a48d40aa6934cf233",
    "usfws_image_records": "c89194cf8f76e9ed6a5addd27c86d45faa1e2a1b6abe0360ba8b5824e44bbe7c",
    "usfws_image_search_runs": "d9db9e4fce4b733d536a8d2fb90fc2050ed01f8f8a72800523dbf3cd9950a1a6",
    "xeno_canto_recording_snapshot": (
        "7318e0a16f65f65e1313fb87b8f49255b571ca867c86ea7e23ac497ee75cec8e"
    ),
}

RELATIONS = (
    RelationSpec("dim_species", "SELECT * FROM environmental_observations.dim_species", "public"),
    RelationSpec(
        "dim_bird_hotspot", "SELECT * FROM environmental_observations.dim_bird_hotspot", "public"
    ),
    RelationSpec(
        "dim_bird_species_traits",
        "SELECT * FROM environmental_observations.dim_bird_species_traits",
        "public",
    ),
    RelationSpec(
        "public_bird_observation",
        "SELECT * FROM environmental_observations.fact_bird_observation "
        "WHERE source_observation_id IS NOT NULL AND is_valid IS TRUE AND is_reviewed IS TRUE "
        "AND is_location_private IS FALSE",
        "public-safe-location",
    ),
    RelationSpec(
        "fact_bird_occurrence",
        "SELECT * FROM environmental_observations.fact_bird_occurrence",
        "public",
    ),
    RelationSpec(
        "fact_bird_sound_recording",
        "SELECT * FROM environmental_observations.fact_bird_sound_recording",
        "public",
    ),
    RelationSpec(
        "ebird_arizona_species_snapshot",
        "WITH s AS (SELECT * FROM polaris_aws.raw_ebird.species_list WHERE region = 'US-AZ' "
        "QUALIFY DENSE_RANK() OVER (ORDER BY _loaded_at DESC, _dlt_load_id DESC) = 1), "
        "t AS (SELECT * FROM polaris_aws.raw_ebird.taxonomy "
        "QUALIFY DENSE_RANK() OVER (ORDER BY _loaded_at DESC, _dlt_load_id DESC) = 1) "
        "SELECT s.*, t.* EXCLUDE (species_code, _dlt_load_id, _dlt_id, _loaded_at) "
        "FROM s LEFT JOIN t USING (species_code)",
        "public",
    ),
    RelationSpec(
        "avonet_species_traits_snapshot",
        "SELECT * FROM polaris_aws.raw_avonet.species_traits",
        "public",
    ),
    RelationSpec(
        "gbif_occurrence_snapshot", "SELECT * FROM polaris_aws.raw_gbif.occurrences", "public"
    ),
    RelationSpec(
        "xeno_canto_recording_snapshot",
        "SELECT * FROM polaris_aws.raw_xeno_canto.recordings",
        "public",
    ),
    RelationSpec(
        "usfws_image_records",
        "SELECT * FROM polaris_aws.raw_usfws.image_records",
        "public-media-metadata",
    ),
    RelationSpec(
        "usfws_image_search_runs",
        "SELECT * FROM polaris_aws.raw_usfws.image_search_runs",
        "public-media-metadata",
    ),
)


def _canonical_contract() -> str:
    payload = {
        "contract_name": CONTRACT_NAME,
        "schema_version": SCHEMA_VERSION,
        "relations": [
            {
                "name": item.name,
                "privacy": item.privacy,
                "query": item.query,
                "ordered_schema_sha256": FROZEN_SCHEMA_HASHES[item.name],
            }
            for item in RELATIONS
        ],
    }
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()


CONTRACT_SHA256 = _canonical_contract()


def _schema_hash(connection: duckdb.DuckDBPyConnection, table: str) -> str:
    rows = connection.execute(
        'SELECT name, type, "notnull" FROM pragma_table_info(?) ORDER BY cid', [table]
    ).fetchall()
    return hashlib.sha256(json.dumps(rows, separators=(",", ":")).encode()).hexdigest()


def _snapshot_id(connection: duckdb.DuckDBPyConnection, table: str) -> str | None:
    columns = {
        row[0]
        for row in connection.execute("SELECT name FROM pragma_table_info(?)", [table]).fetchall()
    }
    provenance = [name for name in ("_dlt_load_id", "run_id") if name in columns]
    if not provenance:
        return None
    expression = " || '|' || ".join(
        f"COALESCE(CAST(\"{name}\" AS VARCHAR), '')" for name in provenance
    )
    values = connection.execute(
        f"SELECT DISTINCT {expression} AS identity FROM {table} ORDER BY identity"
    ).fetchall()
    if not values:
        return None
    payload = json.dumps([row[0] for row in values], separators=(",", ":"))
    return "provenance-sha256:" + hashlib.sha256(payload.encode()).hexdigest()


def require_distinct_database_paths(source: Path, destination: Path) -> None:
    """Reject source/output aliasing before either database is opened."""
    if source.resolve() == destination.resolve():
        raise ProductArtifactError("Source and destination database paths must differ")


def _git_revision() -> str:
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"], capture_output=True, check=True, text=True
    )
    return result.stdout.strip()


def export_rufous_product(
    source: duckdb.DuckDBPyConnection,
    destination: Path,
    *,
    generated_at: datetime | None = None,
    producer_revision: str | None = None,
) -> Path:
    """Atomically export the bounded v1 Rufous input contract."""
    destination = destination.resolve()
    destination.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary_name = tempfile.mkstemp(prefix=f".{destination.name}.", dir=destination.parent)
    os.close(fd)
    temporary = Path(temporary_name)
    temporary.unlink()
    generated = (generated_at or datetime.now(UTC)).astimezone(UTC)
    revision = producer_revision or _git_revision()
    source.execute("BEGIN TRANSACTION")
    try:
        output = duckdb.connect(str(temporary))
        try:
            output.execute(f"CREATE SCHEMA {META_SCHEMA}")
            output.execute(f"CREATE SCHEMA {DATA_SCHEMA}")
            relation_rows: list[tuple[str, str, int, str, str | None, str]] = []
            for spec in RELATIONS:
                source.execute('DROP TABLE IF EXISTS "_product_source_schema"')
                source.execute(
                    f'CREATE TEMP TABLE "_product_source_schema" AS '
                    f"SELECT * FROM ({spec.query}) LIMIT 0"
                )
                source_schema_hash = _schema_hash(source, '"_product_source_schema"')
                if source_schema_hash != FROZEN_SCHEMA_HASHES[spec.name]:
                    raise ProductArtifactError(
                        f"{spec.name} source schema does not match the frozen v1 contract"
                    )
                count_row = source.execute(f"SELECT COUNT(*) FROM ({spec.query})").fetchone()
                if count_row is None:
                    raise ProductArtifactError(f"Could not count {spec.name}")
                count = int(count_row[0])
                if count > MAX_RELATION_ROWS:
                    raise ProductArtifactError(
                        f"{spec.name} has {count} rows; limit is {MAX_RELATION_ROWS}"
                    )
                arrow = source.execute(
                    f"SELECT * FROM ({spec.query}) ORDER BY ALL"
                ).to_arrow_table()
                output.register("_product_rows", arrow)
                output.execute(
                    f'CREATE TABLE {DATA_SCHEMA}."{spec.name}" AS SELECT * FROM _product_rows'
                )
                output.unregister("_product_rows")
                qualified = f'{DATA_SCHEMA}."{spec.name}"'
                schema_hash = _schema_hash(output, qualified)
                if schema_hash != FROZEN_SCHEMA_HASHES[spec.name]:
                    raise ProductArtifactError(
                        f"{spec.name} ordered schema does not match the frozen v1 contract"
                    )
                snapshot_id = _snapshot_id(output, qualified)
                if spec.name in SNAPSHOT_ID_RELATIONS and count > 0 and snapshot_id is None:
                    raise ProductArtifactError(f"{spec.name} is missing required provenance")
                if spec.name not in SNAPSHOT_ID_RELATIONS and snapshot_id is not None:
                    raise ProductArtifactError(f"{spec.name} has uncontracted provenance")
                relation_rows.append(
                    (DATA_SCHEMA, spec.name, count, schema_hash, snapshot_id, spec.privacy)
                )
            output.execute(
                f"CREATE TABLE {META_SCHEMA}.contract (contract_name VARCHAR NOT NULL, "
                "schema_version INTEGER NOT NULL, producer_revision VARCHAR NOT NULL, "
                "generated_at TIMESTAMPTZ NOT NULL, producer_version VARCHAR NOT NULL, "
                "contract_sha256 VARCHAR NOT NULL)"
            )
            output.execute(
                f"INSERT INTO {META_SCHEMA}.contract VALUES (?, ?, ?, ?, ?, ?)",
                [
                    CONTRACT_NAME,
                    SCHEMA_VERSION,
                    revision,
                    generated,
                    version("databox"),
                    CONTRACT_SHA256,
                ],
            )
            output.execute(
                f"CREATE TABLE {META_SCHEMA}.relations (schema_name VARCHAR NOT NULL, "
                "relation_name VARCHAR NOT NULL, row_count BIGINT NOT NULL, "
                "ordered_schema_sha256 VARCHAR NOT NULL, snapshot_id VARCHAR, "
                "privacy_classification VARCHAR NOT NULL)"
            )
            output.executemany(
                f"INSERT INTO {META_SCHEMA}.relations VALUES (?, ?, ?, ?, ?, ?)", relation_rows
            )
            output.execute("CHECKPOINT")
        finally:
            output.close()
        validate_rufous_product(temporary)
        os.replace(temporary, destination)
        source.execute("COMMIT")
        return destination
    except Exception:
        source.execute("ROLLBACK")
        temporary.unlink(missing_ok=True)
        raise


def validate_rufous_product(path: Path) -> None:
    """Fail closed unless *path* is exactly the supported read-only v1 artifact."""
    if not path.is_file() or path.is_symlink():
        raise ProductArtifactError("Rufous product artifact must be a regular file")
    connection = duckdb.connect(str(path), read_only=True)
    try:
        contract = connection.execute(f"SELECT * FROM {META_SCHEMA}.contract").fetchall()
        if len(contract) != 1 or contract[0][0:2] != (CONTRACT_NAME, SCHEMA_VERSION):
            raise ProductArtifactError("Unsupported or duplicate Rufous product contract")
        _, _, revision, generated_at, producer_version, contract_hash = contract[0]
        if (
            not isinstance(revision, str)
            or len(revision) != 40
            or any(character not in "0123456789abcdef" for character in revision.lower())
            or generated_at is None
            or not producer_version
            or contract_hash != CONTRACT_SHA256
        ):
            raise ProductArtifactError("Rufous product contract metadata is incomplete or invalid")
        actual_tables = set(
            connection.execute(
                "SELECT table_schema, table_name, table_type FROM information_schema.tables "
                "WHERE table_schema NOT IN ('information_schema', 'pg_catalog')"
            ).fetchall()
        )
        expected_tables = {
            (META_SCHEMA, "contract", "BASE TABLE"),
            (META_SCHEMA, "relations", "BASE TABLE"),
            *((DATA_SCHEMA, item.name, "BASE TABLE") for item in RELATIONS),
        }
        if actual_tables != expected_tables:
            raise ProductArtifactError("Rufous product artifact contains unexpected relations")
        actual_schemas = {
            row[0]
            for row in connection.execute(
                "SELECT schema_name FROM duckdb_schemas() WHERE NOT internal"
            ).fetchall()
        }
        if actual_schemas != {META_SCHEMA, DATA_SCHEMA}:
            raise ProductArtifactError("Rufous product artifact contains unexpected schemas")
        expected_metadata_columns = {
            "contract": [
                ("contract_name", "VARCHAR", "NO"),
                ("schema_version", "INTEGER", "NO"),
                ("producer_revision", "VARCHAR", "NO"),
                ("generated_at", "TIMESTAMP WITH TIME ZONE", "NO"),
                ("producer_version", "VARCHAR", "NO"),
                ("contract_sha256", "VARCHAR", "NO"),
            ],
            "relations": [
                ("schema_name", "VARCHAR", "NO"),
                ("relation_name", "VARCHAR", "NO"),
                ("row_count", "BIGINT", "NO"),
                ("ordered_schema_sha256", "VARCHAR", "NO"),
                ("snapshot_id", "VARCHAR", "YES"),
                ("privacy_classification", "VARCHAR", "NO"),
            ],
        }
        for table_name, expected_columns in expected_metadata_columns.items():
            actual_columns = connection.execute(
                "SELECT column_name, data_type, is_nullable FROM information_schema.columns "
                "WHERE table_schema = ? AND table_name = ? ORDER BY ordinal_position",
                [META_SCHEMA, table_name],
            ).fetchall()
            if actual_columns != expected_columns:
                raise ProductArtifactError(
                    f"Rufous product metadata schema does not match: {table_name}"
                )
        metadata = connection.execute(
            f"SELECT schema_name, relation_name, row_count, ordered_schema_sha256, "
            f"snapshot_id, privacy_classification FROM {META_SCHEMA}.relations"
        ).fetchall()
        if len(metadata) != len(RELATIONS) or {row[1] for row in metadata} != {
            item.name for item in RELATIONS
        }:
            raise ProductArtifactError("Rufous product relation inventory does not match")
        privacy_by_name = {item.name: item.privacy for item in RELATIONS}
        for schema_name, name, row_count, schema_hash, snapshot_id, privacy in metadata:
            expected_snapshot = name in SNAPSHOT_ID_RELATIONS and row_count > 0
            if (
                schema_name != DATA_SCHEMA
                or not isinstance(row_count, int)
                or not 0 <= row_count <= MAX_RELATION_ROWS
                or privacy != privacy_by_name[name]
                or not isinstance(schema_hash, str)
                or len(schema_hash) != 64
                or (
                    expected_snapshot
                    and (
                        not isinstance(snapshot_id, str)
                        or len(snapshot_id) != len("provenance-sha256:") + 64
                        or not snapshot_id.startswith("provenance-sha256:")
                        or any(
                            character not in "0123456789abcdef"
                            for character in snapshot_id.removeprefix("provenance-sha256:")
                        )
                    )
                )
                or (not expected_snapshot and snapshot_id is not None)
            ):
                raise ProductArtifactError(
                    f"Rufous product metadata validation failed: {name} "
                    f"({schema_name=}, {row_count=}, {snapshot_id=}, {privacy=})"
                )
            qualified = f'{DATA_SCHEMA}."{name}"'
            count_row = connection.execute(f"SELECT COUNT(*) FROM {qualified}").fetchone()
            if count_row is None:
                raise ProductArtifactError(f"Could not count Rufous product relation: {name}")
            actual_count = count_row[0]
            if (
                schema_hash != FROZEN_SCHEMA_HASHES[name]
                or actual_count != row_count
                or _schema_hash(connection, qualified) != schema_hash
                or (expected_snapshot and _snapshot_id(connection, qualified) != snapshot_id)
            ):
                raise ProductArtifactError(f"Rufous product relation validation failed: {name}")
    except duckdb.Error as error:
        raise ProductArtifactError(f"Invalid Rufous product artifact: {error}") from error
    finally:
        connection.close()


def attach_rufous_product(
    connection: duckdb.DuckDBPyConnection, path: Path, *, alias: str = "databox_product"
) -> None:
    """Validate and attach an artifact read-only to a Rufous-owned connection."""
    validate_rufous_product(path)
    escaped = str(path.resolve()).replace("'", "''")
    escaped_alias = alias.replace('"', '""')
    connection.execute(f"ATTACH '{escaped}' AS \"{escaped_alias}\" (READ_ONLY)")
