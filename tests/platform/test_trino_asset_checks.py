"""Dagster contract checks must follow the selected Trino catalog."""

from types import SimpleNamespace
from unittest.mock import MagicMock

import dagster as dg
import pytest
from databox.orchestration import _factories
from databox.quality import verification


@pytest.mark.parametrize(
    ("schema", "catalog"), [("raw_ebird", "polaris_aws"), ("environmental_observations", "databox")]
)
def test_asset_check_uses_trino_catalog(tmp_path, monkeypatch, schema, catalog):
    from soda_core.contracts.contract_verification import ContractVerificationSession

    contract = tmp_path / schema / "example.yaml"
    contract.parent.mkdir()
    contract.write_text(f"dataset: databox/{schema}/example\n")
    monkeypatch.setattr(_factories, "settings", SimpleNamespace(gateway="trino"))
    datasource = MagicMock()
    factory = MagicMock(return_value=datasource)
    monkeypatch.setattr(verification, "create_soda_data_source", factory)
    execute = MagicMock(
        return_value=SimpleNamespace(
            number_of_checks=1,
            number_of_checks_passed=1,
            number_of_checks_failed=0,
            is_failed=False,
        )
    )
    monkeypatch.setattr(ContractVerificationSession, "execute", execute)
    check = _factories.soda_check(dg.AssetKey([schema, "example"]), contract)
    result = check.node_def.compute_fn.decorated_fn()
    assert result.passed
    assert factory.call_args.kwargs == {"catalog": catalog}
    assert execute.call_args.kwargs["data_source_impls"] == [datasource]
    datasource.close_connection.assert_called_once()
