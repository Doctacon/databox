"""Unit tests for scripts/new_source.py.

Exercises the generator against a synthetic repo root in tmp_path. Uses
monkeypatch to rebind the module's path constants so the real check_source_layout
linter can verify the scaffolded tree.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

NEW_SOURCE_SCRIPT = Path(__file__).parent.parent / "scripts" / "new_source.py"
LAYOUT_SCRIPT = Path(__file__).parent.parent / "scripts" / "check_source_layout.py"


def _load(name: str, path: Path):
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _scaffold_repo(tmp_path: Path) -> Path:
    """Build a minimal repo skeleton the generator can write into."""
    (tmp_path / "packages/databox-sources/databox_sources").mkdir(parents=True)
    (tmp_path / "packages/databox-sources/databox_sources/__init__.py").write_text("")
    (tmp_path / "transforms/main/models").mkdir(parents=True)
    (tmp_path / "soda/contracts").mkdir(parents=True)
    (tmp_path / "packages/databox/databox/orchestration/domains").mkdir(parents=True)
    (tmp_path / "packages/databox/databox/orchestration/domains/__init__.py").write_text("")

    defs_path = tmp_path / "packages/databox/databox/orchestration/definitions.py"
    defs_path.write_text(
        '''"""Dagster definitions — stub for tests."""

from __future__ import annotations

import dagster as dg

from databox.orchestration.domains import analytics, ebird, noaa, usgs

all_pipelines = dg.define_asset_job(
    name="all_pipelines",
    selection=dg.AssetSelection.assets(
        *ebird.dlt_asset_keys,
        *noaa.dlt_asset_keys,
        *usgs.dlt_asset_keys,
        *ebird.sqlmesh_asset_keys,
        *noaa.sqlmesh_asset_keys,
        *usgs.sqlmesh_asset_keys,
        *analytics.sqlmesh_asset_keys,
    ),
)

defs = dg.Definitions(
    asset_checks=[
        *ebird.asset_checks,
        *noaa.asset_checks,
        *usgs.asset_checks,
        *analytics.asset_checks,
    ],
)
'''
    )

    env_example = tmp_path / ".env.example"
    env_example.write_text("EBIRD_API_TOKEN=\n")
    return tmp_path


def _rebind(gen_module, layout_module, root: Path) -> None:
    gen_module.ROOT = root
    gen_module.SOURCES_PKG_DIR = root / "packages/databox-sources/databox_sources"
    gen_module.MODELS_DIR = root / "transforms/main/models"
    gen_module.CONTRACTS_DIR = root / "soda/contracts"
    gen_module.DOMAINS_DIR = root / "packages/databox/databox/orchestration/domains"
    gen_module.DEFINITIONS_PATH = root / "packages/databox/databox/orchestration/definitions.py"
    gen_module.ENV_EXAMPLE_PATH = root / ".env.example"

    layout_module.SOURCES_DIR = gen_module.SOURCES_PKG_DIR
    layout_module.MODELS_DIR = gen_module.MODELS_DIR
    layout_module.CONTRACTS_DIR = gen_module.CONTRACTS_DIR
    layout_module.DOMAINS_DIR = gen_module.DOMAINS_DIR


@pytest.fixture
def env(tmp_path: Path):
    gen = _load("new_source", NEW_SOURCE_SCRIPT)
    layout = _load("check_source_layout", LAYOUT_SCRIPT)
    root = _scaffold_repo(tmp_path)
    _rebind(gen, layout, root)
    return gen, layout, root


def test_validate_name_rejects_uppercase() -> None:
    gen = _load("new_source", NEW_SOURCE_SCRIPT)
    with pytest.raises(ValueError):
        gen.validate_name("Bad")


def test_validate_name_rejects_reserved() -> None:
    gen = _load("new_source", NEW_SOURCE_SCRIPT)
    with pytest.raises(ValueError):
        gen.validate_name("analytics")


@pytest.mark.parametrize("shape", ["rest", "file", "database"])
def test_generated_tree_passes_layout_lint(env, shape: str) -> None:
    gen, layout, _ = env
    assert gen.main(["demo", "--shape", shape]) == 0
    report = layout.check_source("demo")
    assert report.skipped
    assert report.skip_reason == "scaffolded"
    assert report.ok


def test_definitions_wired_idempotently(env) -> None:
    gen, _, root = env
    assert gen.main(["demo"]) == 0
    defs = (root / "packages/databox/databox/orchestration/definitions.py").read_text()
    assert "import analytics, demo, ebird" in defs
    assert "*demo.dlt_asset_keys," in defs
    assert "*demo.sqlmesh_asset_keys," in defs
    assert "*demo.asset_checks," in defs

    # Second call with --force regenerates; wiring stays singular.
    assert gen.main(["demo", "--force"]) == 0
    defs2 = (root / "packages/databox/databox/orchestration/definitions.py").read_text()
    assert defs2.count("*demo.dlt_asset_keys,") == 1
    assert defs2.count("*demo.sqlmesh_asset_keys,") == 1
    assert defs2.count("*demo.asset_checks,") == 1


def test_collision_without_force_refuses(env) -> None:
    gen, _, _ = env
    assert gen.main(["demo"]) == 0
    # Second run without --force must fail.
    assert gen.main(["demo"]) == 1


def test_dry_run_writes_nothing(env, capsys) -> None:
    gen, _, root = env
    assert gen.main(["demo", "--dry-run"]) == 0
    # No source directory should have been created.
    assert not (root / "packages/databox-sources/databox_sources/demo").exists()
    out = capsys.readouterr().out
    assert "Would create" in out
    assert "no files written" in out


def test_rest_shape_adds_env_stub(env) -> None:
    gen, _, root = env
    assert gen.main(["demo", "--shape", "rest"]) == 0
    env_text = (root / ".env.example").read_text()
    assert "API_KEY_DEMO=" in env_text


def test_file_shape_does_not_touch_env_example(env) -> None:
    gen, _, root = env
    assert gen.main(["demo", "--shape", "file"]) == 0
    env_text = (root / ".env.example").read_text()
    assert "API_KEY_DEMO=" not in env_text


def test_generated_source_py_has_skip_marker(env) -> None:
    gen, _, root = env
    assert gen.main(["demo"]) == 0
    src_py = (
        (root / "packages/databox-sources/databox_sources/demo/source.py")
        .read_text()
        .splitlines()[:10]
    )
    assert any("scaffold-lint: skip=scaffolded" in line for line in src_py)


def test_gitkeep_files_present(env) -> None:
    gen, _, root = env
    assert gen.main(["demo"]) == 0
    for relpath in [
        "transforms/main/models/demo/staging/.gitkeep",
        "transforms/main/models/demo/marts/.gitkeep",
        "soda/contracts/demo_staging/.gitkeep",
        "soda/contracts/demo/.gitkeep",
    ]:
        assert (root / relpath).exists(), relpath


def test_domain_stub_is_valid_python(env) -> None:
    gen, _, root = env
    assert gen.main(["demo"]) == 0
    domain = (root / "packages/databox/databox/orchestration/domains/demo.py").read_text()
    compile(domain, "demo.py", "exec")
    assert "dlt_asset_keys: list" in domain
    assert "asset_checks: list" in domain
