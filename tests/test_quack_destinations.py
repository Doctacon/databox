from __future__ import annotations

from pathlib import Path

import duckdb
from databox.destinations import dedupe_quack_raw_tables


def test_dedupe_quack_raw_tables_publishes_raw_views(tmp_path: Path) -> None:
    db_path = tmp_path / "databox.duckdb"
    con = duckdb.connect(str(db_path))
    try:
        con.execute(
            """
            CREATE TABLE main.recent_observations (
                sub_id TEXT,
                value INTEGER,
                _dlt_load_id TEXT,
                _dlt_id TEXT
            )
            """
        )
        con.execute(
            """
            INSERT INTO main.recent_observations VALUES
                ('S1', 1, 'load-1', 'a'),
                ('S1', 2, 'load-2', 'b')
            """
        )
        con.execute("CREATE TABLE main._dlt_loads (schema_name TEXT, load_id TEXT)")
        con.execute(
            """
            INSERT INTO main._dlt_loads VALUES
                ('ebird_source', 'load-2'),
                ('noaa_source', 'load-x')
            """
        )
        con.execute("CREATE TABLE main._dlt_version (schema_name TEXT, version INTEGER)")
        con.execute("INSERT INTO main._dlt_version VALUES ('ebird_source', 1)")
    finally:
        con.close()

    changed = dedupe_quack_raw_tables(str(db_path))

    con = duckdb.connect(str(db_path), read_only=True)
    try:
        assert changed == ["main.recent_observations: 2 -> 1"]
        assert con.execute("SELECT value FROM raw_ebird.recent_observations").fetchone() == (2,)
        assert con.execute("SELECT load_id FROM raw_ebird._dlt_loads").fetchall() == [("load-2",)]
        assert con.execute("SELECT version FROM raw_ebird._dlt_version").fetchall() == [(1,)]
    finally:
        con.close()
