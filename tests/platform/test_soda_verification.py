"""Tests for gateway-specific Soda datasource construction."""

from types import SimpleNamespace

import pytest
from databox.quality.verification import create_soda_data_source


def test_trino_datasource_uses_contract_catalog_and_no_auth_http() -> None:
    datasource = create_soda_data_source(
        SimpleNamespace(gateway="trino", trino_host="trino.internal", trino_port=8081),
        catalog="polaris_aws",
    )

    assert datasource.data_source_model.name == "databox"
    connection = datasource.data_source_model.connection_properties
    assert str(connection.host) == "trino.internal"
    assert connection.port == 8081
    assert connection.user == "databox"
    assert connection.catalog == "polaris_aws"
    assert connection.http_scheme == "http"
    assert connection.auth_type == "NoAuthentication"
    assert datasource.sql_dialect.get_database_prefix_index() == 0
    assert datasource.sql_dialect.get_schema_prefix_index() == 1


def test_shared_datasource_is_not_used_for_local_gateway() -> None:
    with pytest.raises(ValueError, match="only needed for the Trino gateway"):
        create_soda_data_source(SimpleNamespace(gateway="local"), catalog="databox")
