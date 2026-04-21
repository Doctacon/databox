"""Unit tests for scripts/check_source_layout.py.

Exercises the linter against a synthetic source tree in tmp_path. Uses
monkeypatch to rebind the module's path constants at the Path level so
the production script logic is exactly what gets exercised.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

SCRIPT = Path(__file__).parent.parent / "scripts" / "check_source_layout.py"


def _load_module():
    if "check_source_layout" in sys.modules:
        return sys.modules["check_source_layout"]
    spec = importlib.util.spec_from_file_location("check_source_layout", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules["check_source_layout"] = module
    spec.loader.exec_module(module)
    return module


def _scaffold_complete_source(root: Path, name: str) -> None:
    src = root / "packages/databox-sources/databox_sources" / name
    src.mkdir(parents=True)
    (src / "source.py").write_text("# dlt source\n")
    (src / "config.yaml").write_text("name: x\n")

    (root / f"transforms/main/models/{name}/staging").mkdir(parents=True)
    (root / f"transforms/main/models/{name}/staging/stg_{name}_x.sql").write_text("-- stg\n")
    (root / f"transforms/main/models/{name}/marts").mkdir(parents=True)
    (root / f"transforms/main/models/{name}/marts/fct_{name}_x.sql").write_text("-- fct\n")

    (root / f"soda/contracts/{name}_staging").mkdir(parents=True)
    (root / f"soda/contracts/{name}_staging/stg_{name}_x.yaml").write_text("dataset: x\n")
    (root / f"soda/contracts/{name}").mkdir(parents=True)
    (root / f"soda/contracts/{name}/fct_{name}_x.yaml").write_text("dataset: x\n")

    (root / "packages/databox/databox/orchestration/domains").mkdir(parents=True, exist_ok=True)
    (root / f"packages/databox/databox/orchestration/domains/{name}.py").write_text("# domain\n")


def _rebind_paths(module, root: Path) -> None:
    module.SOURCES_DIR = root / "packages/databox-sources/databox_sources"
    module.MODELS_DIR = root / "transforms/main/models"
    module.CONTRACTS_DIR = root / "soda/contracts"
    module.DOMAINS_DIR = root / "packages/databox/databox/orchestration/domains"


def test_complete_source_passes(tmp_path: Path) -> None:
    module = _load_module()
    _scaffold_complete_source(tmp_path, "foo")
    _rebind_paths(module, tmp_path)
    assert module.discover_sources(module.SOURCES_DIR) == ["foo"]
    report = module.check_source("foo")
    assert report.ok
    assert report.missing == []


def test_missing_mart_contract_fails(tmp_path: Path) -> None:
    module = _load_module()
    _scaffold_complete_source(tmp_path, "foo")
    _rebind_paths(module, tmp_path)
    # Drop mart contract.
    (tmp_path / "soda/contracts/foo/fct_foo_x.yaml").unlink()
    report = module.check_source("foo")
    assert not report.ok
    assert any("soda/contracts/foo/*.yaml" in m for m in report.missing)


def test_missing_domain_file_fails(tmp_path: Path) -> None:
    module = _load_module()
    _scaffold_complete_source(tmp_path, "foo")
    _rebind_paths(module, tmp_path)
    (tmp_path / "packages/databox/databox/orchestration/domains/foo.py").unlink()
    report = module.check_source("foo")
    assert not report.ok
    assert any("domains/foo.py" in m for m in report.missing)


def test_skip_marker_bypasses_checks(tmp_path: Path) -> None:
    module = _load_module()
    (tmp_path / "packages/databox-sources/databox_sources/expr").mkdir(parents=True)
    (tmp_path / "packages/databox-sources/databox_sources/expr/source.py").write_text(
        "# scaffold-lint: skip=experimental\n# dlt source\n"
    )
    _rebind_paths(module, tmp_path)
    report = module.check_source("expr")
    assert report.ok
    assert report.skipped
    assert report.skip_reason == "experimental"


def test_discover_ignores_private_and_files(tmp_path: Path) -> None:
    module = _load_module()
    base = tmp_path / "packages/databox-sources/databox_sources"
    base.mkdir(parents=True)
    (base / "_shared").mkdir()
    (base / "_shared/source.py").write_text("x")
    (base / "foo").mkdir()
    (base / "foo/source.py").write_text("x")
    (base / "bar.py").write_text("# module, not a source package\n")
    assert module.discover_sources(base) == ["foo"]


def test_stg_glob_matches_any_stg_file(tmp_path: Path) -> None:
    module = _load_module()
    _scaffold_complete_source(tmp_path, "foo")
    _rebind_paths(module, tmp_path)
    # Rename the existing file to a different stg_* name — still matches glob.
    stg_dir = tmp_path / "transforms/main/models/foo/staging"
    (stg_dir / "stg_foo_x.sql").rename(stg_dir / "stg_foo_other.sql")
    assert module.check_source("foo").ok


def test_mart_accepts_dim_file(tmp_path: Path) -> None:
    module = _load_module()
    _scaffold_complete_source(tmp_path, "foo")
    _rebind_paths(module, tmp_path)
    marts_dir = tmp_path / "transforms/main/models/foo/marts"
    (marts_dir / "fct_foo_x.sql").rename(marts_dir / "dim_foo_x.sql")
    assert module.check_source("foo").ok
