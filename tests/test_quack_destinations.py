from __future__ import annotations

import os
from pathlib import Path

import duckdb
from databox.destinations import dedupe_quack_raw_tables
from databox.destinations.quack import (
    _drop_legacy_raw_views,
    _drop_quack_metadata_read_views,
    _publish_quack_metadata_read_views,
    _quack_dlt_env,
)


def test_dedupe_quack_raw_tables_keeps_physical_raw_tables(tmp_path: Path) -> None:
    db_path = tmp_path / "databox.duckdb"
    con = duckdb.connect(str(db_path))
    try:
        con.execute("CREATE SCHEMA raw_ebird")
        con.execute(
            """
            CREATE TABLE raw_ebird.recent_observations (
                sub_id TEXT,
                value INTEGER,
                _dlt_load_id TEXT,
                _dlt_id TEXT
            )
            """
        )
        con.execute(
            """
            INSERT INTO raw_ebird.recent_observations VALUES
                ('S1', 1, 'load-1', 'a'),
                ('S1', 2, 'load-2', 'b')
            """
        )
        con.execute("CREATE TABLE raw_ebird._dlt_loads (schema_name TEXT, load_id TEXT)")
        con.execute("INSERT INTO raw_ebird._dlt_loads VALUES ('ebird_source', 'load-2')")
        con.execute("CREATE TABLE raw_ebird._dlt_version (schema_name TEXT, version INTEGER)")
        con.execute("INSERT INTO raw_ebird._dlt_version VALUES ('ebird_source', 1)")
        con.execute(
            """
            CREATE TABLE raw_ebird._dlt_pipeline_state (
                pipeline_name TEXT,
                state TEXT
            )
            """
        )
    finally:
        con.close()

    changed = dedupe_quack_raw_tables(str(db_path))

    con = duckdb.connect(str(db_path), read_only=True)
    try:
        assert changed == ["raw_ebird.recent_observations: 2 -> 1"]
        assert con.execute("SELECT value FROM raw_ebird.recent_observations").fetchone() == (2,)
        assert con.execute("SELECT load_id FROM raw_ebird._dlt_loads").fetchall() == [("load-2",)]
        assert con.execute("SELECT version FROM raw_ebird._dlt_version").fetchall() == [(1,)]
        table_types = dict(
            con.execute(
                """
                SELECT table_name, table_type
                FROM information_schema.tables
                WHERE table_schema = 'raw_ebird'
                """
            ).fetchall()
        )
        assert table_types["recent_observations"] == "BASE TABLE"
        assert table_types["_dlt_loads"] == "BASE TABLE"
        assert table_types["_dlt_version"] == "BASE TABLE"
        assert table_types["_dlt_pipeline_state"] == "BASE TABLE"
    finally:
        con.close()


def test_drop_legacy_raw_views_preserves_base_tables(tmp_path: Path) -> None:
    db_path = tmp_path / "databox.duckdb"
    con = duckdb.connect(str(db_path))
    try:
        con.execute("CREATE SCHEMA raw_ebird")
        con.execute("CREATE SCHEMA raw_usgs")
        con.execute("CREATE TABLE raw_ebird.recent_observations (sub_id TEXT)")
        con.execute("CREATE TABLE main.daily_values (site_no TEXT)")
        con.execute("CREATE VIEW raw_usgs.daily_values AS SELECT * FROM main.daily_values")
        con.execute("CREATE TABLE main._dlt_loads (schema_name TEXT)")
        con.execute(
            """
            CREATE VIEW raw_usgs._dlt_loads AS
            SELECT * FROM main._dlt_loads WHERE schema_name = 'usgs_source'
            """
        )

        _drop_legacy_raw_views(con)

        relations = dict(
            con.execute(
                """
                SELECT table_schema || '.' || table_name, table_type
                FROM information_schema.tables
                WHERE table_schema IN ('raw_ebird', 'raw_usgs')
                """
            ).fetchall()
        )
        assert relations == {"raw_ebird.recent_observations": "BASE TABLE"}
    finally:
        con.close()


def test_quack_dlt_env_disables_destination_state_restore(monkeypatch) -> None:
    monkeypatch.delenv("PIPELINES__RESTORE_FROM_DESTINATION", raising=False)

    with _quack_dlt_env():
        assert os.environ["PIPELINES__RESTORE_FROM_DESTINATION"] == "false"
    assert "PIPELINES__RESTORE_FROM_DESTINATION" not in os.environ

    monkeypatch.setenv("PIPELINES__RESTORE_FROM_DESTINATION", "true")
    with _quack_dlt_env():
        assert os.environ["PIPELINES__RESTORE_FROM_DESTINATION"] == "false"
    assert os.environ["PIPELINES__RESTORE_FROM_DESTINATION"] == "true"


def test_quack_metadata_read_views_are_transient(tmp_path: Path) -> None:
    db_path = tmp_path / "databox.duckdb"
    con = duckdb.connect(str(db_path))
    try:
        con.execute("CREATE SCHEMA raw_ebird")
        con.execute("CREATE TABLE raw_ebird._dlt_version (version_hash TEXT)")
        con.execute("INSERT INTO raw_ebird._dlt_version VALUES ('v1')")
        con.execute("CREATE TABLE raw_ebird._dlt_loads (load_id TEXT)")
        con.execute("CREATE TABLE raw_ebird._dlt_pipeline_state (pipeline_name TEXT)")

        _publish_quack_metadata_read_views(con, "raw_ebird")

        relations = dict(
            con.execute(
                """
                SELECT table_name, table_type
                FROM information_schema.tables
                WHERE table_schema = 'main' AND table_name LIKE '\\_dlt%' ESCAPE '\\'
                """
            ).fetchall()
        )
        assert relations == {
            "_dlt_loads": "VIEW",
            "_dlt_pipeline_state": "VIEW",
            "_dlt_version": "VIEW",
        }
        assert con.execute("SELECT version_hash FROM main._dlt_version").fetchall() == [("v1",)]

        _drop_quack_metadata_read_views(con)

        assert con.execute(
            """
                SELECT COUNT(*)
                FROM information_schema.tables
                WHERE table_schema = 'main' AND table_name LIKE '\\_dlt%' ESCAPE '\\'
                """
        ).fetchone() == (0,)
        assert con.execute("SELECT version_hash FROM raw_ebird._dlt_version").fetchall() == [
            ("v1",)
        ]
    finally:
        con.close()
