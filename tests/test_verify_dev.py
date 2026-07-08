"""Smoke tests for scripts/verify_dev.py contract-rewriter."""

from __future__ import annotations

import importlib.util
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "verify_dev.py"
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
