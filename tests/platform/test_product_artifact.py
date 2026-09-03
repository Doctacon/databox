"""Credential-free contract tests for the Rufous input artifact."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import duckdb
import pytest
from databox.product_artifact import (
    DATA_SCHEMA,
    RELATIONS,
    ProductArtifactError,
    attach_rufous_product,
    export_rufous_product,
    require_distinct_database_paths,
    validate_rufous_product,
)


def _source(tmp_path: Path) -> duckdb.DuckDBPyConnection:
    source = duckdb.connect(str(tmp_path / "source.duckdb"))
    lake_path = tmp_path / "lake.duckdb"
    lake = duckdb.connect(str(lake_path))
    schema_sql = Path("tests/platform/fixtures/rufous_product_source_schema.sql").read_text()
    for statement in schema_sql.split(";"):
        if not statement.strip() or statement.lstrip().startswith("--"):
            continue
        target = lake if '"raw_' in statement else source
        target.execute(statement)
    source.execute(
        "INSERT INTO environmental_observations.fact_bird_observation "
        "(source_observation_id, is_valid, is_reviewed, is_location_private) VALUES "
        "('visible', TRUE, TRUE, FALSE), ('private', TRUE, TRUE, TRUE), "
        "('unreviewed', TRUE, FALSE, FALSE)"
    )
    lake.execute(
        "INSERT INTO raw_ebird.species_list "
        "(species_code, region, _loaded_at, _dlt_load_id, _dlt_id) VALUES "
        "('rufhum', 'US-AZ', TIMESTAMP '2026-01-01', 'load', 'id1')"
    )
    lake.execute(
        "INSERT INTO raw_ebird.taxonomy "
        "(species_code, com_name, _loaded_at, _dlt_load_id, _dlt_id) VALUES "
        "('rufhum', 'Rufous Hummingbird', TIMESTAMP '2026-01-01', 'load', 'id2')"
    )
    lake.close()
    source.execute(f"ATTACH '{lake_path}' AS polaris_aws (READ_ONLY)")
    return source


def test_export_is_bounded_private_safe_and_read_only(tmp_path: Path) -> None:
    source = _source(tmp_path)
    destination = tmp_path / "rufous-inputs.duckdb"
    export_rufous_product(
        source,
        destination,
        generated_at=datetime(2026, 1, 1, tzinfo=UTC),
        producer_revision="a" * 40,
    )
    source.close()

    validate_rufous_product(destination)
    consumer = duckdb.connect()
    attach_rufous_product(consumer, destination)
    assert consumer.execute(
        f"SELECT source_observation_id FROM databox_product.{DATA_SCHEMA}.public_bird_observation"
    ).fetchall() == [("visible",)]
    inventory = consumer.execute(
        "SELECT relation_name, snapshot_id "
        "FROM databox_product.databox_product_meta.relations ORDER BY 1"
    ).fetchall()
    assert [row[0] for row in inventory] == sorted(spec.name for spec in RELATIONS)
    assert dict(inventory)["ebird_arizona_species_snapshot"].startswith("provenance-sha256:")
    assert dict(inventory)["dim_species"] is None
    with pytest.raises(duckdb.Error):
        consumer.execute(f"INSERT INTO databox_product.{DATA_SCHEMA}.dim_species VALUES (2)")
    consumer.close()


def test_source_and_destination_must_differ_before_open(tmp_path: Path) -> None:
    database = tmp_path / "same.duckdb"
    database.write_bytes(b"source")
    with pytest.raises(ProductArtifactError, match="must differ"):
        require_distinct_database_paths(database, tmp_path / "." / "same.duckdb")
    assert database.read_bytes() == b"source"


def test_export_is_atomic_on_missing_input(tmp_path: Path) -> None:
    destination = tmp_path / "existing.duckdb"
    destination.write_bytes(b"unchanged")
    source = duckdb.connect()
    with pytest.raises(duckdb.Error):
        export_rufous_product(source, destination, producer_revision="a" * 40)
    source.close()
    assert destination.read_bytes() == b"unchanged"
    assert not list(tmp_path.glob(".existing.duckdb.*"))


def test_validator_rejects_tampered_metadata_and_non_files(tmp_path: Path) -> None:
    with pytest.raises(ProductArtifactError, match="regular file"):
        validate_rufous_product(tmp_path)
    source = _source(tmp_path)
    destination = tmp_path / "artifact.duckdb"
    export_rufous_product(source, destination, producer_revision="a" * 40)
    source.close()
    writable = duckdb.connect(str(destination))
    writable.execute("UPDATE databox_product_meta.contract SET schema_version = 2")
    writable.close()
    with pytest.raises(ProductArtifactError, match="Unsupported"):
        validate_rufous_product(destination)


def test_validator_rejects_views_and_incomplete_metadata(tmp_path: Path) -> None:
    source = _source(tmp_path)
    destination = tmp_path / "artifact.duckdb"
    export_rufous_product(source, destination, producer_revision="a" * 40)
    source.close()
    writable = duckdb.connect(str(destination))
    writable.execute("CREATE VIEW rufous_inputs_v1.unexpected AS SELECT 1")
    writable.close()
    with pytest.raises(ProductArtifactError, match="unexpected relations"):
        validate_rufous_product(destination)

    destination.unlink()
    second = tmp_path / "second"
    second.mkdir()
    source = _source(second)
    export_rufous_product(source, destination, producer_revision="a" * 40)
    source.close()
    writable = duckdb.connect(str(destination))
    writable.execute("UPDATE databox_product_meta.contract SET producer_revision = ''")
    writable.close()
    with pytest.raises(ProductArtifactError, match="metadata is incomplete"):
        validate_rufous_product(destination)


def test_validator_rejects_tampered_snapshot_and_metadata_schema(tmp_path: Path) -> None:
    source = _source(tmp_path)
    destination = tmp_path / "artifact.duckdb"
    export_rufous_product(source, destination, producer_revision="a" * 40)
    source.close()
    writable = duckdb.connect(str(destination))
    writable.execute(
        "UPDATE databox_product_meta.relations SET snapshot_id = ? "
        "WHERE relation_name = 'ebird_arizona_species_snapshot'",
        ["provenance-sha256:" + "0" * 64],
    )
    writable.close()
    with pytest.raises(ProductArtifactError, match="relation validation failed"):
        validate_rufous_product(destination)

    destination.unlink()
    second = tmp_path / "second"
    second.mkdir()
    source = _source(second)
    export_rufous_product(source, destination, producer_revision="a" * 40)
    source.close()
    writable = duckdb.connect(str(destination))
    writable.execute("ALTER TABLE databox_product_meta.relations ADD COLUMN extra VARCHAR")
    writable.close()
    with pytest.raises(ProductArtifactError, match="metadata schema does not match"):
        validate_rufous_product(destination)
