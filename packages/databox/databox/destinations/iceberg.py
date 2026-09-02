"""dlt Iceberg destination configuration for the shared Polaris catalog."""

from __future__ import annotations

import json
import os
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

import dlt

from databox.config.settings import settings


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
