"""Tests for `ensure_motherduck_databases()` in orchestration._factories."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from databox.orchestration import _factories


def test_noop_when_backend_is_local() -> None:
    with patch.object(_factories.settings, "backend", "local"):
        assert _factories.ensure_motherduck_databases() == []


def test_noop_when_token_missing() -> None:
    with (
        patch.object(_factories.settings, "backend", "motherduck"),
        patch.object(_factories.settings, "motherduck_token", ""),
    ):
        assert _factories.ensure_motherduck_databases() == []


def test_issues_create_database_for_each_name() -> None:
    fake_con = MagicMock()
    names = ["databox", "raw_ebird", "raw_usgs_earthquakes"]

    with (
        patch.object(_factories.settings, "backend", "motherduck"),
        patch.object(_factories.settings, "motherduck_token", "tok123"),
        patch.object(type(_factories.settings), "motherduck_database_names", names),
        patch("duckdb.connect", return_value=fake_con) as connect,
    ):
        result = _factories.ensure_motherduck_databases()

    assert result == names
    connect.assert_called_once_with("md:?motherduck_token=tok123")
    executed = [call.args[0] for call in fake_con.execute.call_args_list]
    assert executed == [
        'CREATE DATABASE IF NOT EXISTS "databox"',
        'CREATE DATABASE IF NOT EXISTS "raw_ebird"',
        'CREATE DATABASE IF NOT EXISTS "raw_usgs_earthquakes"',
    ]
    fake_con.close.assert_called_once()


def test_motherduck_database_names_includes_known_sources() -> None:
    names = _factories.settings.motherduck_database_names
    assert "databox" in names
    assert "raw_ebird" in names
    assert "raw_noaa" in names
    assert "raw_usgs" in names
    assert "raw_usgs_earthquakes" in names
