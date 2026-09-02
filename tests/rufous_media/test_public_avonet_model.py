from __future__ import annotations

from pathlib import Path

import duckdb
import pytest
from databox_sources.avonet.source import _COLUMNS

_MODEL = Path("transforms/main/models/rufous_public/avonet_species_traits.sql")
_TYPE_SQL = {
    "text": "VARCHAR",
    "bigint": "BIGINT",
    "double": "DOUBLE",
    "bool": "BOOLEAN",
    "timestamp": "TIMESTAMP",
}


def _model_query() -> str:
    query = _MODEL.read_text(encoding="utf-8").split(");", maxsplit=1)[1].strip()
    return query.replace("polaris_aws.raw_avonet.", "raw_avonet.")


def test_public_avonet_model_has_an_explicit_final_projection() -> None:
    query = _model_query()

    assert "SELECT n.*" not in query
    assert "n.species_natural_key" in query
    assert "n.loaded_at" in query


def _connection() -> duckdb.DuckDBPyConnection:
    connection = duckdb.connect()
    connection.execute("CREATE SCHEMA raw_avonet")
    columns = [
        f'"{name}" {_TYPE_SQL[definition["data_type"]]}' for name, definition in _COLUMNS.items()
    ]
    columns.extend(('"_dlt_load_id" VARCHAR', '"_dlt_id" VARCHAR'))
    connection.execute(f"CREATE TABLE raw_avonet.species_traits ({', '.join(columns)})")
    connection.execute(
        """
        INSERT INTO raw_avonet.species_traits (
          source_scientific_name, family, order_name, avibase_id,
          total_individuals, female_individuals, male_individuals,
          unknown_sex_individuals, complete_measures, inference,
          habitat_density_code, migration_code, primary_lifestyle,
          dataset_doi, dataset_version, dataset_license, source_file_id,
          source_file_md5, source_url, loaded_at, _dlt_load_id, _dlt_id
        ) VALUES (
          'Cardinalis cardinalis (Linnaeus)', 'Cardinalidae', 'Passeriformes',
          'AVIBASE-CARDINAL', 12, 5, 6, 1, 10, false, 2, 1, 'Insessorial',
          '10.6084/m9.figshare.16586228.v7', 'v7', 'CC BY 4.0', 34480856,
          '1445afdcfb6df784010c2ca034544bc8',
          'https://ndownloader.figshare.com/files/34480856',
          '2026-08-04T12:00:00+00:00', 'load', 'one'
        )
        """
    )
    return connection


@pytest.mark.parametrize(
    "mutation",
    [
        "UPDATE raw_avonet.species_traits SET total_individuals = NULL",
        "UPDATE raw_avonet.species_traits SET habitat_density_code = NULL",
        "UPDATE raw_avonet.species_traits SET dataset_license = NULL",
        "UPDATE raw_avonet.species_traits SET source_file_id = 1",
    ],
)
def test_public_avonet_model_fails_closed_on_null_or_drifted_contract(
    mutation: str,
) -> None:
    connection = _connection()
    try:
        connection.execute(mutation)
        with pytest.raises(duckdb.InvalidInputException, match="source contract is invalid"):
            connection.execute(_model_query()).fetchall()
    finally:
        connection.close()


def test_public_avonet_model_rejects_duplicate_normalized_names() -> None:
    connection = _connection()
    try:
        connection.execute(
            """
            INSERT INTO raw_avonet.species_traits
            SELECT * REPLACE (
              'Cardinalis cardinalis' AS source_scientific_name,
              'AVIBASE-DUPLICATE' AS avibase_id,
              'two' AS _dlt_id
            )
            FROM raw_avonet.species_traits
            """
        )
        with pytest.raises(duckdb.InvalidInputException, match="source contract is invalid"):
            connection.execute(_model_query()).fetchall()
    finally:
        connection.close()
