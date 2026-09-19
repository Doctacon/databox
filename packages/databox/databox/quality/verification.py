"""Shared Soda datasource construction for contract verification."""

from __future__ import annotations

from typing import Any


def create_soda_data_source(settings: Any, *, catalog: str) -> Any:
    """Create Soda's named Trino datasource against the selected catalog.

    In ``databox/schema/table``, Soda treats ``databox`` as the datasource
    name. The schema and table are resolved relative to this connection's
    catalog, which differs for raw inputs and analytics outputs.
    """
    if settings.gateway != "trino":
        raise ValueError("A shared Soda datasource is only needed for the Trino gateway")

    try:
        # Load Soda's plugin registry before importing the implementation
        # directly; doing this in the opposite order triggers entry-point
        # discovery while soda_trino is only partially initialized.
        from soda_core.common.data_source_impl import (
            DataSourceImpl as _DataSourceImpl,  # noqa: F401
        )
        from soda_trino.common.data_sources.trino_data_source import (  # type: ignore[import-untyped]
            TrinoDataSourceImpl,
        )
        from soda_trino.common.data_sources.trino_data_source_connection import (  # type: ignore[import-untyped]
            TrinoDataSource,
        )
    except ImportError as exc:
        raise RuntimeError(
            "Trino Soda verification requires the 'soda-trino>=3.0.0' dependency"
        ) from exc

    model = TrinoDataSource.model_validate(
        {
            "name": "databox",
            "type": "trino",
            "connection": {
                "host": settings.trino_host,
                "port": settings.trino_port,
                "user": "databox",
                "catalog": catalog,
                "http_scheme": "http",
                # Authentication mode enum, not a credential.
                "auth_type": "NoAuthentication",  # secret-scan: allow
            },
        }
    )
    return TrinoDataSourceImpl(data_source_model=model)
