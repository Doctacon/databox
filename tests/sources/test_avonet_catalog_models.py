from __future__ import annotations

from pathlib import Path

import duckdb
import pytest
import sqlglot
from databox_sources.avonet.source import _COLUMNS
from sqlglot import exp

_MODEL = Path(
    "transforms/main/models/environmental_observations/dimensions/dim_bird_species_traits.sql"
)
_TYPE_SQL = {
    "text": "VARCHAR",
    "bigint": "BIGINT",
    "double": "DOUBLE",
    "bool": "BOOLEAN",
    "timestamp": "TIMESTAMP",
}


def _model_query() -> str:
    return _MODEL.read_text().split(");", maxsplit=1)[1].strip()


def _connection() -> duckdb.DuckDBPyConnection:
    connection = duckdb.connect()
    connection.execute("CREATE SCHEMA raw_avonet")
    connection.execute("CREATE SCHEMA environmental_observations")
    columns = [
        f'"{name}" {_TYPE_SQL[definition["data_type"]]}' for name, definition in _COLUMNS.items()
    ]
    columns.extend(('"_dlt_load_id" VARCHAR', '"_dlt_id" VARCHAR'))
    connection.execute(f"CREATE TABLE raw_avonet.species_traits ({', '.join(columns)})")
    connection.execute(
        """
        CREATE TABLE environmental_observations.dim_species (
            species_sk VARCHAR,
            species_natural_key VARCHAR,
            source_pipeline VARCHAR
        )
        """
    )
    return connection


def test_avonet_normalization_projection_has_exact_columns_and_no_star() -> None:
    query = sqlglot.parse_one(_model_query(), dialect="duckdb")
    normalized = next(
        cte.this for cte in query.find_all(exp.CTE) if cte.alias_or_name == "avonet_normalized"
    )
    assert isinstance(normalized, exp.Select)
    assert not any(
        expression.is_star
        for select in query.find_all(exp.Select)
        for expression in select.expressions
    )
    assert not any(isinstance(node, exp.Star) for node in normalized.walk())
    assert [expression.alias_or_name for expression in normalized.expressions] == [
        "species_natural_key",
        *_COLUMNS,
        "_dlt_load_id",
        "_dlt_id",
    ]


def test_duplicate_normalized_avonet_keys_fail_even_when_unmatched() -> None:
    connection = _connection()
    try:
        connection.execute(
            """
            INSERT INTO raw_avonet.species_traits
                (source_scientific_name, avibase_id, _dlt_load_id, _dlt_id)
            VALUES
                ('Duplicate bird', 'AVIBASE-ONE', 'load', 'one'),
                ('Duplicate bird (Author)', 'AVIBASE-TWO', 'load', 'two')
            """
        )
        with pytest.raises(duckdb.InvalidInputException, match="must be unique"):
            connection.execute(_model_query()).fetchall()
    finally:
        connection.close()


def test_multiple_conformed_species_rows_for_one_trait_fail() -> None:
    connection = _connection()
    try:
        connection.execute(
            """
            INSERT INTO raw_avonet.species_traits
                (source_scientific_name, avibase_id, _dlt_load_id, _dlt_id)
            VALUES ('Exact bird', 'AVIBASE-ONE', 'load', 'one')
            """
        )
        connection.execute(
            """
            INSERT INTO environmental_observations.dim_species VALUES
                ('species-one', 'exact bird', 'ebird_api'),
                ('species-two', 'exact bird', 'gbif_api')
            """
        )
        with pytest.raises(duckdb.InvalidInputException, match="one row per conformed species"):
            connection.execute(_model_query()).fetchall()
    finally:
        connection.close()
