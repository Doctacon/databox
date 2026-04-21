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
    src = "dataset: databox/ebird/fct_daily_bird_observations\n"
    assert "databox/ebird__dev/fct_daily_bird_observations" in verify_dev.rewrite_for_dev(src)


def test_rewrites_staging_suffix_schema() -> None:
    src = "dataset: databox/ebird_staging/stg_ebird_observations\n"
    out = verify_dev.rewrite_for_dev(src)
    assert "databox/ebird_staging__dev/stg_ebird_observations" in out


def test_leaves_already_dev_alone() -> None:
    src = "dataset: databox/ebird__dev/fct_x\n"
    assert verify_dev.rewrite_for_dev(src) == src


def test_preserves_surrounding_yaml() -> None:
    src = "dataset: databox/analytics/platform_health\ncolumns:\n  - name: region_code\n"
    out = verify_dev.rewrite_for_dev(src)
    assert "databox/analytics__dev/platform_health" in out
    assert "columns:" in out
    assert "region_code" in out
