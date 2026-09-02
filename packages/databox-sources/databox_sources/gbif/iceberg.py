"""GBIF ingestion into an existing Polaris Iceberg catalog."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

import pyarrow as pa
from pyiceberg.catalog.rest import RestCatalog
from pyiceberg.exceptions import NamespaceAlreadyExistsError, NoSuchTableError
from pyiceberg.schema import Schema
from pyiceberg.types import DoubleType, LongType, NestedField, StringType, TimestamptzType

from databox_sources.gbif.source import _OCCURRENCE_COLUMNS, gbif_source


@dataclass(frozen=True)
class GbifIcebergLoadResult:
    row_count: int
    rows_inserted: int
    rows_updated: int
    snapshot_id: int


def _schemas() -> tuple[Schema, pa.Schema]:
    iceberg_fields = []
    arrow_fields = []
    for field_id, (name, definition) in enumerate(_OCCURRENCE_COLUMNS.items(), 1):
        data_type = definition["data_type"]
        required = name == "key"
        if data_type == "bigint":
            iceberg_type, arrow_type = LongType(), pa.int64()
        elif data_type == "double":
            iceberg_type, arrow_type = DoubleType(), pa.float64()
        elif data_type == "timestamp":
            iceberg_type, arrow_type = TimestamptzType(), pa.timestamp("us", tz="UTC")
        else:
            iceberg_type, arrow_type = StringType(), pa.string()
        iceberg_fields.append(NestedField(field_id, name, iceberg_type, required=required))
        arrow_fields.append(pa.field(name, arrow_type, nullable=not required))
    return Schema(*iceberg_fields, identifier_field_ids={1}), pa.schema(arrow_fields)


def load_gbif_occurrences(
    *,
    catalog: RestCatalog,
    max_records: int,
) -> GbifIcebergLoadResult:
    """Fetch the configured GBIF slice and upsert it by GBIF occurrence key."""
    namespace, table_name = "raw_gbif", "occurrences"
    try:
        catalog.create_namespace(namespace)
    except NamespaceAlreadyExistsError:
        pass

    iceberg_schema, arrow_schema = _schemas()
    identifier = f"{namespace}.{table_name}"
    try:
        table = catalog.load_table(identifier)
    except NoSuchTableError:
        table = catalog.create_table(identifier, schema=iceberg_schema)

    rows = list(gbif_source(max_records=max_records))
    for row in rows:
        loaded_at = row.get("_loaded_at")
        if isinstance(loaded_at, str):
            row["_loaded_at"] = datetime.fromisoformat(loaded_at.replace("Z", "+00:00"))
    result = table.upsert(pa.Table.from_pylist(rows, schema=arrow_schema), join_cols=["key"])
    refreshed = catalog.load_table(identifier)
    snapshot = refreshed.current_snapshot()
    if snapshot is None:
        raise RuntimeError("GBIF Iceberg upsert did not create a snapshot")
    return GbifIcebergLoadResult(
        row_count=refreshed.scan().count(),
        rows_inserted=result.rows_inserted,
        rows_updated=result.rows_updated,
        snapshot_id=snapshot.snapshot_id,
    )
