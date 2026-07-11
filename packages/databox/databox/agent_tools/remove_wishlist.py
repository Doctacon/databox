"""Explicit idempotent removal of the retired personal wishlist table."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import asdict, dataclass
from typing import Any

import duckdb

_SCHEMA = "birding_personal"


@dataclass(frozen=True)
class WishlistRemovalResult:
    table_existed: bool
    wishlist_rows_removed: int
    observation_rows_before: int
    observation_rows_after: int
    watch_rows_before: int
    watch_rows_after: int

    def to_dict(self) -> dict[str, bool | int]:
        return asdict(self)


def _table_exists(connection: duckdb.DuckDBPyConnection, table: str) -> bool:
    return (
        connection.execute(
            """SELECT 1 FROM information_schema.tables
            WHERE table_schema=? AND table_name=?""",
            [_SCHEMA, table],
        ).fetchone()
        is not None
    )


def _row_count(connection: duckdb.DuckDBPyConnection, table: str) -> int:
    if not _table_exists(connection, table):
        return 0
    row = connection.execute(f"SELECT COUNT(*) FROM {_SCHEMA}.{table}").fetchone()
    assert row is not None
    return int(row[0])


def inspect_wishlist_storage(
    connection: duckdb.DuckDBPyConnection,
) -> WishlistRemovalResult:
    """Return aggregate-only table and neighboring-state counts without writing."""

    existed = _table_exists(connection, "wishlist")
    observations = _row_count(connection, "observations")
    watches = _row_count(connection, "watches")
    return WishlistRemovalResult(
        table_existed=existed,
        wishlist_rows_removed=_row_count(connection, "wishlist"),
        observation_rows_before=observations,
        observation_rows_after=observations,
        watch_rows_before=watches,
        watch_rows_after=watches,
    )


def remove_wishlist_storage(
    connection: duckdb.DuckDBPyConnection,
    *,
    before_commit: Callable[[duckdb.DuckDBPyConnection], Any] | None = None,
) -> WishlistRemovalResult:
    """Drop wishlist storage atomically without creating or changing any watch."""

    connection.execute("BEGIN TRANSACTION")
    try:
        before = inspect_wishlist_storage(connection)
        if before.table_existed:
            connection.execute(f"DROP TABLE {_SCHEMA}.wishlist")
        if before_commit is not None:
            before_commit(connection)
        observations_after = _row_count(connection, "observations")
        watches_after = _row_count(connection, "watches")
        if (
            observations_after != before.observation_rows_before
            or watches_after != before.watch_rows_before
        ):
            raise ValueError("wishlist removal changed observation or watch state")
        connection.execute("COMMIT")
        return WishlistRemovalResult(
            table_existed=before.table_existed,
            wishlist_rows_removed=before.wishlist_rows_removed,
            observation_rows_before=before.observation_rows_before,
            observation_rows_after=observations_after,
            watch_rows_before=before.watch_rows_before,
            watch_rows_after=watches_after,
        )
    except Exception:
        connection.execute("ROLLBACK")
        raise
