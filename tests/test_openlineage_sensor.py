"""Tests for `openlineage_sensor_or_none()` + `_openlineage_emit_tick()`.

Covers the factory's three branches plus the emit loop itself:

- OPENLINEAGE_URL unset → returns None (default, no emitter cost)
- OPENLINEAGE_URL set but openlineage-python not installed → None + warn
- OPENLINEAGE_URL set and package present → returns a SensorDefinition
- Invoking `_openlineage_emit_tick` with a fabricated ASSET_MATERIALIZATION
  record emits exactly one OpenLineage RunEvent with the expected shape
"""

from __future__ import annotations

import sys
from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

import dagster as dg
from databox.orchestration import _factories


def test_none_when_url_unset() -> None:
    with patch.object(_factories.settings, "openlineage_url", ""):
        assert _factories.openlineage_sensor_or_none() is None


def test_none_when_url_set_but_import_fails(caplog) -> None:
    """Install not done: factory must not crash the stack — just warn + None."""
    with (
        patch.object(_factories.settings, "openlineage_url", "http://marquez:5000"),
        patch.dict(sys.modules, {"openlineage.client": None}),
    ):
        with caplog.at_level("WARNING", logger=_factories.log.name):
            result = _factories.openlineage_sensor_or_none()
    assert result is None
    assert any("openlineage-python" in rec.message for rec in caplog.records)


def test_returns_sensor_when_url_set_and_installed() -> None:
    """URL set + package present: factory returns a real Dagster sensor."""
    with (
        patch.object(_factories.settings, "openlineage_url", "http://marquez:5000"),
        patch.object(_factories.settings, "openlineage_namespace", "databox"),
        patch.object(_factories.settings, "openlineage_api_key", ""),
    ):
        result = _factories.openlineage_sensor_or_none()
    assert isinstance(result, dg.SensorDefinition)
    assert result.name == "openlineage_sensor"


def _fabricate_materialization_record(
    asset_key: dg.AssetKey, storage_id: int, ts_epoch: float
) -> MagicMock:
    fake_dagster_event = MagicMock()
    fake_dagster_event.asset_key = asset_key
    record = MagicMock()
    record.storage_id = storage_id
    record.event_log_entry.dagster_event = fake_dagster_event
    record.event_log_entry.timestamp = ts_epoch
    return record


def test_emit_tick_emits_one_runevent_per_materialization() -> None:
    """Ticket acceptance: mocked OL emitter records at least one event."""
    asset_key = dg.AssetKey(["sqlmesh", "ebird", "stg_ebird_observations"])
    ts = datetime(2026, 4, 21, 12, 0, tzinfo=UTC).timestamp()
    record = _fabricate_materialization_record(asset_key, storage_id=42, ts_epoch=ts)

    mock_client = MagicMock()
    fake_instance = MagicMock()
    fake_instance.get_event_records.return_value = [record]

    fake_context = MagicMock()
    fake_context.cursor = None
    fake_context.instance = fake_instance
    fake_context.log = MagicMock()

    result = _factories._openlineage_emit_tick(fake_context, mock_client, namespace="databox")

    assert mock_client.emit.call_count == 1
    emitted = mock_client.emit.call_args[0][0]
    assert emitted.job.namespace == "databox"
    assert emitted.job.name == "sqlmesh/ebird/stg_ebird_observations"
    assert len(emitted.outputs) == 1
    assert emitted.outputs[0].namespace == "databox"
    assert emitted.outputs[0].name == "sqlmesh/ebird/stg_ebird_observations"
    assert result.cursor == "42"


def test_emit_tick_advances_cursor_over_many_records() -> None:
    """Cursor must track the highest storage_id seen so next tick resumes cleanly."""
    records = [
        _fabricate_materialization_record(
            dg.AssetKey(["sqlmesh", "ebird", f"t{i}"]),
            storage_id=100 + i,
            ts_epoch=1_700_000_000 + i,
        )
        for i in range(3)
    ]

    mock_client = MagicMock()
    fake_instance = MagicMock()
    fake_instance.get_event_records.return_value = records

    fake_context = MagicMock()
    fake_context.cursor = "50"
    fake_context.instance = fake_instance
    fake_context.log = MagicMock()

    result = _factories._openlineage_emit_tick(fake_context, mock_client, namespace="databox")

    assert mock_client.emit.call_count == 3
    assert result.cursor == "102"


def test_emit_tick_survives_client_exception() -> None:
    """A flaky OL backend must not crash Dagster — warn and continue."""
    records = [
        _fabricate_materialization_record(
            dg.AssetKey(["sqlmesh", "ebird", "a"]),
            storage_id=1,
            ts_epoch=1_700_000_000,
        ),
        _fabricate_materialization_record(
            dg.AssetKey(["sqlmesh", "ebird", "b"]),
            storage_id=2,
            ts_epoch=1_700_000_001,
        ),
    ]

    mock_client = MagicMock()
    mock_client.emit.side_effect = [RuntimeError("connection refused"), None]

    fake_instance = MagicMock()
    fake_instance.get_event_records.return_value = records

    fake_context = MagicMock()
    fake_context.cursor = None
    fake_context.instance = fake_instance
    fake_context.log = MagicMock()

    result = _factories._openlineage_emit_tick(fake_context, mock_client, namespace="databox")

    assert mock_client.emit.call_count == 2
    fake_context.log.warning.assert_called_once()
    assert "openlineage emit failed" in fake_context.log.warning.call_args[0][0]
    assert result.cursor == "2"
