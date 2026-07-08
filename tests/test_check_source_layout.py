"""Unit tests for scripts/check_source_layout.py."""

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

    (root / "packages/databox/databox/orchestration/domains").mkdir(parents=True, exist_ok=True)
    (root / f"packages/databox/databox/orchestration/domains/{name}.py").write_text("# domain\n")


def _rebind_paths(module, root: Path) -> None:
    module.SOURCES_DIR = root / "packages/databox-sources/databox_sources"
    module.DOMAINS_DIR = root / "packages/databox/databox/orchestration/domains"


def test_complete_source_passes(tmp_path: Path) -> None:
    module = _load_module()
    _scaffold_complete_source(tmp_path, "foo")
    _rebind_paths(module, tmp_path)
    assert module.discover_sources(module.SOURCES_DIR) == ["foo"]
    report = module.check_source("foo")
    assert report.ok
    assert report.missing == []


def test_missing_config_fails(tmp_path: Path) -> None:
    module = _load_module()
    _scaffold_complete_source(tmp_path, "foo")
    _rebind_paths(module, tmp_path)
    (tmp_path / "packages/databox-sources/databox_sources/foo/config.yaml").unlink()
    report = module.check_source("foo")
    assert not report.ok
    assert any("config.yaml" in m for m in report.missing)


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
