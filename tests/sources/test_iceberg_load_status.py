from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace

import pyarrow as pa
import pytest
from databox.destinations import iceberg


class _SourceTable:
    def __init__(self, count: int) -> None:
        self.count = count

    def scan(self, *, row_filter: object, selected_fields: tuple[str, ...]) -> object:
        assert "_dlt_load_id" in str(row_filter)
        assert selected_fields == ("_dlt_load_id",)
        return SimpleNamespace(count=lambda: self.count)


class _StatusTable:
    def __init__(self) -> None:
        self.rows: list[dict[str, object]] = []

    def schema(self) -> object:
        return SimpleNamespace(
            as_arrow=lambda: pa.schema(
                [
                    pa.field("load_id", pa.string(), nullable=False),
                    pa.field("schema_name", pa.string(), nullable=False),
                    pa.field("status", pa.int64(), nullable=False),
                    pa.field("inserted_at", pa.timestamp("us"), nullable=False),
                    pa.field("rows_loaded", pa.int64(), nullable=False),
                ]
            )
        )

    def upsert(self, rows: pa.Table) -> None:
        self.rows.extend(rows.to_pylist())


class _Catalog:
    def __init__(self) -> None:
        self.source_tables = {"raw_test.first": _SourceTable(3), "raw_test.second": _SourceTable(4)}
        self.status_table = _StatusTable()
        self.created_identifier: str | None = None
        self.created_schema: object | None = None

    def load_table(self, identifier: str) -> _SourceTable:
        return self.source_tables[identifier]

    def create_table_if_not_exists(self, identifier: str, *, schema: object) -> _StatusTable:
        self.created_identifier = identifier
        self.created_schema = schema
        return self.status_table


def _pipeline(*, failed: bool = False) -> object:
    package = SimpleNamespace(
        load_id="123.45",
        completed_at=datetime(2026, 9, 2, 4, 0, tzinfo=UTC),
    )
    load_info = SimpleNamespace(
        has_failed_jobs=failed,
        loads_ids=["123.45"],
        load_packages=[package],
    )
    return SimpleNamespace(last_trace=SimpleNamespace(last_load_info=load_info))


def test_publish_dlt_load_status_upserts_dlt_metadata_and_rows(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    catalog = _Catalog()
    monkeypatch.setattr(type(iceberg.settings), "pyiceberg_catalog", lambda self: catalog)

    status = iceberg.publish_dlt_load_status(
        _pipeline(),
        dataset_name="raw_test",
        table_names=("first", "second"),
    )

    assert status == iceberg.DltLoadStatus(
        load_id="123.45",
        dataset_name="raw_test",
        completed_at=datetime(2026, 9, 2, 4, 0),
        rows_loaded=7,
    )
    assert catalog.created_identifier == "raw_test._dlt_load_status"
    assert catalog.created_schema.identifier_field_ids == [1]
    assert catalog.status_table.rows == [
        {
            "load_id": "123.45",
            "schema_name": "raw_test",
            "status": 0,
            "inserted_at": datetime(2026, 9, 2, 4, 0),
            "rows_loaded": 7,
        }
    ]


def test_publish_dlt_load_status_rejects_failed_load(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(type(iceberg.settings), "pyiceberg_catalog", lambda self: _Catalog())
    with pytest.raises(RuntimeError, match="single successful dlt load"):
        iceberg.publish_dlt_load_status(
            _pipeline(failed=True),
            dataset_name="raw_test",
            table_names=("first",),
        )
