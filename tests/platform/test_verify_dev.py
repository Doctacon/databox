"""Smoke tests for scripts/platform/verify_dev.py contract-rewriter."""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import SimpleNamespace

import pytest

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "platform" / "verify_dev.py"
spec = importlib.util.spec_from_file_location("verify_dev", SCRIPT)
assert spec and spec.loader
verify_dev = importlib.util.module_from_spec(spec)
spec.loader.exec_module(verify_dev)


def test_rewrites_bare_schema() -> None:
    src = "dataset: databox/environmental_observations/fact_bird_observation\n"
    assert (
        "databox/environmental_observations__dev/fact_bird_observation"
        in verify_dev.rewrite_for_dev(src)
    )


def test_rewrites_cdm_dimension_schema() -> None:
    src = "dataset: databox/environmental_observations/dim_species\n"
    out = verify_dev.rewrite_for_dev(src)
    assert "databox/environmental_observations__dev/dim_species" in out


def test_leaves_already_dev_alone() -> None:
    src = "dataset: databox/environmental_observations__dev/fct_x\n"
    assert verify_dev.rewrite_for_dev(src) == src


def test_preserves_surrounding_yaml() -> None:
    src = "dataset: databox/analytics/platform_health\ncolumns:\n  - name: source\n"
    out = verify_dev.rewrite_for_dev(src)
    assert "databox/analytics/platform_health" in out
    assert "columns:" in out
    assert "source" in out


def test_leaves_raw_contracts_on_raw_schema() -> None:
    src = "dataset: databox/raw_ebird/recent_observations\n"
    assert verify_dev.rewrite_for_dev(src) == src


def test_main_selects_trino_catalog_and_keeps_dev_rewrite(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from soda_core.contracts.contract_verification import ContractVerificationSession

    output = tmp_path / "soda/contracts/environmental_observations/fact_bird.yaml"
    output.parent.mkdir(parents=True)
    output.write_text("dataset: databox/environmental_observations/fact_bird\n")
    raw = tmp_path / "soda/contracts/raw_ebird/taxonomy.yaml"
    raw.parent.mkdir(parents=True)
    raw.write_text("dataset: databox/raw_ebird/taxonomy\n")
    calls: list[dict[str, object]] = []
    catalogs: list[str] = []

    def make_datasource(actual: object, *, catalog: str) -> SimpleNamespace:
        catalogs.append(catalog)
        return SimpleNamespace(catalog=catalog, close_connection=lambda: None)

    monkeypatch.setattr(verify_dev, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(verify_dev, "CONTRACTS_DIR", tmp_path / "soda/contracts")
    monkeypatch.setattr(
        verify_dev,
        "settings",
        SimpleNamespace(gateway="trino", trino_host="trino", trino_port=8081),
    )
    monkeypatch.setattr(verify_dev, "create_soda_data_source", make_datasource)
    monkeypatch.setattr(
        ContractVerificationSession,
        "execute",
        staticmethod(
            lambda **kwargs: (
                calls.append(kwargs) or SimpleNamespace(is_failed=False, get_errors_str=lambda: "")
            )
        ),
    )

    assert verify_dev.main() == 0
    assert catalogs == ["databox", "polaris_aws"]
    assert [call["data_source_impls"][0].catalog for call in calls] == catalogs  # type: ignore[index, union-attr]
    sources = [call["contract_yaml_sources"][0].yaml_str for call in calls]  # type: ignore[index, union-attr]
    assert "databox/environmental_observations__dev/fact_bird" in sources[0]
    assert "databox/raw_ebird/taxonomy" in sources[1]
