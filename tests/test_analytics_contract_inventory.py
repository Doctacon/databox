"""SQLMesh modeled assets and Soda contracts have one derived authority."""

from __future__ import annotations

from pathlib import Path

import dagster as dg
import pytest
from databox.orchestration._factories import SODA_DIR, sqlmesh_project
from databox.orchestration.domains import analytics


def _spec(schema: str = "domain", model: str = "records") -> dg.AssetSpec:
    return dg.AssetSpec(key=dg.AssetKey(["sqlmesh", schema, model]))


def _contract(root: Path, schema: str, model: str, dataset: str | None = None) -> Path:
    path = root / schema / f"{model}.yaml"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"dataset: {dataset or f'databox/{schema}/{model}'}\n")
    return path


def test_current_sqlmesh_assets_have_exactly_one_modeled_soda_check() -> None:
    expected_keys = sorted(
        (spec.key for spec in sqlmesh_project.specs), key=lambda key: tuple(key.path)
    )
    assert analytics.sqlmesh_asset_keys == expected_keys
    assert len(expected_keys) == 21

    check_keys = [spec.asset_key for check in analytics.asset_checks for spec in check.check_specs]
    assert sorted(check_keys, key=lambda key: tuple(key.path)) == expected_keys
    assert len(check_keys) == len(set(check_keys)) == 21

    required = {
        dg.AssetKey(["sqlmesh", "birding_agent", "arizona_species_catalog"]),
        dg.AssetKey(["sqlmesh", "environmental_observations", "dim_bird_species_traits"]),
        dg.AssetKey(["sqlmesh", "environmental_observations", "fact_bird_occurrence"]),
        dg.AssetKey(["sqlmesh", "environmental_observations", "fact_bird_sound_recording"]),
        dg.AssetKey(["sqlmesh", "rufous_public", "gbif_eod_occurrence"]),
        dg.AssetKey(["sqlmesh", "rufous_public", "inaturalist_commercial_image"]),
        dg.AssetKey(["sqlmesh", "rufous_public", "usfws_commercial_image"]),
    }
    assert required <= set(check_keys)


def test_current_contract_pairs_are_exact_and_exclude_raw_contracts() -> None:
    pairs = analytics.modeled_soda_contracts(sqlmesh_project.specs, SODA_DIR / "contracts")
    assert len(pairs) == 21
    assert all(not path.parent.name.startswith("raw_") for _, path in pairs)
    assert {path.parent.name for _, path in pairs} == {
        "analytics",
        "birding_agent",
        "environmental_observations",
        "rufous_public",
    }


def test_contract_pairs_are_deterministic(tmp_path: Path) -> None:
    _contract(tmp_path, "zeta", "last")
    _contract(tmp_path, "alpha", "first")
    pairs = analytics.modeled_soda_contracts(
        [_spec("zeta", "last"), _spec("alpha", "first")],
        tmp_path,
    )
    assert [key.path for key, _ in pairs] == [
        ["sqlmesh", "alpha", "first"],
        ["sqlmesh", "zeta", "last"],
    ]


def test_missing_modeled_contract_fails(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="missing modeled Soda contract"):
        analytics.modeled_soda_contracts([_spec()], tmp_path)


def test_extra_modeled_contract_fails(tmp_path: Path) -> None:
    _contract(tmp_path, "domain", "records")
    extra = _contract(tmp_path, "domain", "extra")
    with pytest.raises(ValueError, match=f"extra modeled Soda contract.*{extra}"):
        analytics.modeled_soda_contracts([_spec()], tmp_path)


def test_noncanonical_modeled_contract_path_fails(tmp_path: Path) -> None:
    _contract(tmp_path, "domain", "records")
    yml = tmp_path / "domain/extra.yml"
    yml.write_text("dataset: databox/domain/extra\n")
    with pytest.raises(ValueError, match="must use contracts/<schema>/<model>.yaml"):
        analytics.modeled_soda_contracts([_spec()], tmp_path)


def test_duplicate_modeled_dataset_fails(tmp_path: Path) -> None:
    dataset = "databox/domain/records"
    _contract(tmp_path, "domain", "records", dataset)
    _contract(tmp_path, "other", "duplicate", dataset)
    with pytest.raises(ValueError, match="duplicate modeled Soda contract dataset"):
        analytics.modeled_soda_contracts([_spec()], tmp_path)


def test_mismatched_modeled_contract_identity_fails(tmp_path: Path) -> None:
    path = _contract(tmp_path, "domain", "records", "databox/wrong/records")
    with pytest.raises(ValueError, match=f"identity mismatch.*{path}"):
        analytics.modeled_soda_contracts([_spec()], tmp_path)


def test_raw_contracts_remain_outside_modeled_parity(tmp_path: Path) -> None:
    expected = _contract(tmp_path, "domain", "records")
    _contract(tmp_path, "raw_source", "records", "databox/raw_source/records")
    assert analytics.modeled_soda_contracts([_spec()], tmp_path) == [
        (dg.AssetKey(["sqlmesh", "domain", "records"]), expected)
    ]


def test_duplicate_or_invalid_sqlmesh_asset_keys_fail(tmp_path: Path) -> None:
    _contract(tmp_path, "domain", "records")
    duplicate = [_spec(), _spec()]
    with pytest.raises(ValueError, match="duplicate SQLMesh asset key"):
        analytics.modeled_soda_contracts(duplicate, tmp_path)

    invalid = dg.AssetSpec(key=dg.AssetKey(["domain", "records"]))
    with pytest.raises(ValueError, match="invalid SQLMesh modeled asset key"):
        analytics.modeled_soda_contracts([invalid], tmp_path)
