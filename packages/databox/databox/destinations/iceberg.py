"""dlt Iceberg destination configuration for the shared Polaris catalog."""

from __future__ import annotations

import json
import os
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

import dlt
import pyarrow as pa
from pyiceberg.expressions import EqualTo
from pyiceberg.schema import Schema
from pyiceberg.types import LongType, NestedField, StringType, TimestampType

from databox.config.settings import settings

DLT_LOAD_STATUS_TABLE = "_dlt_load_status"


@contextmanager
def polaris_dlt_catalog() -> Iterator[None]:
    """Scope dlt's PyIceberg REST-catalog configuration to one pipeline run."""
    url = settings.polaris_url.rstrip("/")
    values = {
        "ICEBERG_CATALOG__ICEBERG_CATALOG_NAME": settings.iceberg_catalog,
        "ICEBERG_CATALOG__ICEBERG_CATALOG_TYPE": "rest",
        "ICEBERG_CATALOG__ICEBERG_CATALOG_CONFIG": json.dumps(
            {
                "type": "rest",
                "uri": f"{url}/api/catalog",
                "warehouse": settings.iceberg_catalog,
                "credential": (
                    f"{settings.polaris_client_id.get_secret_value()}:"
                    f"{settings.polaris_client_secret.get_secret_value()}"
                ),
                "oauth2-server-uri": f"{url}/api/catalog/v1/oauth/tokens",
                "scope": "PRINCIPAL_ROLE:ALL",
            }
        ),
    }
    previous = {key: os.environ.get(key) for key in values}
    os.environ.update(values)
    try:
        yield
    finally:
        for key, value in previous.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


def iceberg_dlt_pipeline(*args: Any, **kwargs: Any) -> Any:
    """Create a Polaris-backed dlt pipeline with catalog config applied at construction."""
    with polaris_dlt_catalog():
        return dlt.pipeline(*args, **kwargs)


def publish_dlt_load_status(
    pipeline: Any,
    *,
    dataset_name: str,
    table_names: tuple[str, ...],
) -> None:
    """Publish one successful dlt load summary as a Polaris Iceberg row."""
    load_info = pipeline.last_trace.last_load_info if pipeline.last_trace is not None else None
    if load_info is None or load_info.has_failed_jobs or len(load_info.loads_ids) != 1:
        raise RuntimeError("A single successful dlt load is required for load-status publication")
    load_id = load_info.loads_ids[0]
    package = next(
        (item for item in load_info.load_packages if item.load_id == load_id),
        None,
    )
    if package is None or package.completed_at is None:
        raise RuntimeError("Completed dlt load metadata is required for load-status publication")

    catalog = settings.pyiceberg_catalog()
    rows_loaded = 0
    for table_name in table_names:
        table = catalog.load_table(f"{dataset_name}.{table_name}")
        rows_loaded += table.scan(
            row_filter=EqualTo("_dlt_load_id", load_id),
            selected_fields=("_dlt_load_id",),
        ).count()

    status_schema = Schema(
        NestedField(1, "load_id", StringType(), required=True),
        NestedField(2, "schema_name", StringType(), required=True),
        NestedField(3, "status", LongType(), required=True),
        NestedField(4, "inserted_at", TimestampType(), required=True),
        NestedField(5, "rows_loaded", LongType(), required=True),
        identifier_field_ids=[1],
    )
    status_table = catalog.create_table_if_not_exists(
        f"{dataset_name}.{DLT_LOAD_STATUS_TABLE}",
        schema=status_schema,
    )
    completed_at = package.completed_at.replace(tzinfo=None)
    status_table.upsert(
        pa.Table.from_pylist(
            [
                {
                    "load_id": load_id,
                    "schema_name": dataset_name,
                    "status": 0,
                    "inserted_at": completed_at,
                    "rows_loaded": rows_loaded,
                }
            ],
            schema=status_table.schema().as_arrow(),
        )
    )


def iceberg_destination() -> dlt.destinations.filesystem:
    """Create a filesystem destination whose Iceberg tables are Polaris-managed."""
    access_key = settings.aws_access_key_id.get_secret_value()
    secret_key = settings.aws_secret_access_key.get_secret_value()
    if not settings.aws_s3_bucket or not access_key or not secret_key:
        raise ValueError("DATABOX_AWS_S3_BUCKET and AWS writer credentials are required")
    return dlt.destinations.filesystem(
        bucket_url=f"s3://{settings.aws_s3_bucket}/warehouse",
        credentials={
            "aws_access_key_id": access_key,
            "aws_secret_access_key": secret_key,
            "region_name": settings.aws_region,
        },
    )
