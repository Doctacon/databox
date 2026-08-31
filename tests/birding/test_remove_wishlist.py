"""Explicit idempotent migration away from retired wishlist storage."""

from __future__ import annotations

from pathlib import Path

import duckdb
import pytest
from databox.agent_tools.remove_wishlist import (
    inspect_wishlist_storage,
    remove_wishlist_storage,
)


def _database(tmp_path: Path) -> Path:
    path = tmp_path / "wishlist-removal.duckdb"
    connection = duckdb.connect(str(path))
    connection.execute("CREATE SCHEMA birding_personal")
    connection.execute(
        "CREATE TABLE birding_personal.wishlist (species_code TEXT, created_at TEXT)"
    )
    connection.execute(
        "INSERT INTO birding_personal.wishlist VALUES ('one', '2026-07-11'), ('two', '2026-07-11')"
    )
    connection.execute("CREATE TABLE birding_personal.observations (observation_id TEXT)")
    connection.execute("INSERT INTO birding_personal.observations VALUES ('observation-one')")
    connection.execute("CREATE TABLE birding_personal.watches (species_code TEXT)")
    connection.execute("INSERT INTO birding_personal.watches VALUES ('existing-watch')")
    connection.close()
    return path


def test_remove_wishlist_drops_rows_without_watch_conversion_and_is_idempotent(
    tmp_path: Path,
) -> None:
    connection = duckdb.connect(str(_database(tmp_path)))
    before = inspect_wishlist_storage(connection)
    assert before.to_dict() == {
        "table_existed": True,
        "wishlist_rows_removed": 2,
        "observation_rows_before": 1,
        "observation_rows_after": 1,
        "watch_rows_before": 1,
        "watch_rows_after": 1,
    }

    applied = remove_wishlist_storage(connection)
    assert applied.to_dict() == before.to_dict()
    assert connection.execute(
        "SELECT COUNT(*) FROM information_schema.tables "
        "WHERE table_schema='birding_personal' AND table_name='wishlist'"
    ).fetchone() == (0,)
    assert connection.execute("SELECT * FROM birding_personal.watches").fetchall() == [
        ("existing-watch",)
    ]
    assert connection.execute("SELECT * FROM birding_personal.observations").fetchall() == [
        ("observation-one",)
    ]

    rerun = remove_wishlist_storage(connection)
    assert rerun.table_existed is False
    assert rerun.wishlist_rows_removed == 0
    assert rerun.watch_rows_before == rerun.watch_rows_after == 1
    assert rerun.observation_rows_before == rerun.observation_rows_after == 1
    connection.close()


def test_remove_wishlist_rolls_back_drop_rows_and_neighbor_state(tmp_path: Path) -> None:
    connection = duckdb.connect(str(_database(tmp_path)))

    def fail(db: duckdb.DuckDBPyConnection) -> None:
        db.execute("INSERT INTO birding_personal.watches VALUES ('forbidden-conversion')")
        raise RuntimeError("injected rollback")

    with pytest.raises(RuntimeError, match="injected rollback"):
        remove_wishlist_storage(connection, before_commit=fail)
    assert inspect_wishlist_storage(connection).wishlist_rows_removed == 2
    assert connection.execute("SELECT * FROM birding_personal.watches").fetchall() == [
        ("existing-watch",)
    ]
    assert connection.execute("SELECT COUNT(*) FROM birding_personal.observations").fetchone() == (
        1,
    )
    connection.close()


def test_remove_wishlist_no_schema_is_safe_noop(tmp_path: Path) -> None:
    connection = duckdb.connect(str(tmp_path / "empty.duckdb"))
    result = remove_wishlist_storage(connection)
    assert result.to_dict() == {
        "table_existed": False,
        "wishlist_rows_removed": 0,
        "observation_rows_before": 0,
        "observation_rows_after": 0,
        "watch_rows_before": 0,
        "watch_rows_after": 0,
    }
    connection.close()
