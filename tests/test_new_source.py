"""Unit tests for the canonical-registry source scaffold."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from typing import Any, cast

import pytest
from databox.config.sources import Source

NEW_SOURCE_SCRIPT = Path(__file__).parent.parent / "scripts/new_source.py"
LAYOUT_SCRIPT = Path(__file__).parent.parent / "scripts/check_source_layout.py"


def _load(name: str, path: Path):
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _repo(root: Path) -> None:
    (root / "packages/databox-sources/databox_sources").mkdir(parents=True)
    (root / "packages/databox/databox/orchestration/domains").mkdir(parents=True)
    (root / "transforms/main/models").mkdir(parents=True)
    (root / "soda/contracts").mkdir(parents=True)
    (root / ".env.example").write_text("EBIRD_API_TOKEN=\n")
    config = root / "packages/databox/databox/config"
    config.mkdir(parents=True)
    (config / "sources.py").write_text(
        'SOURCES = [\n    Source(name="ebird", raw_tables=("recent",)),\n]\n'
    )


def _rebind(gen, layout, root: Path) -> None:
    gen.ROOT = root
    gen.SOURCES_PKG_DIR = root / "packages/databox-sources/databox_sources"
    gen.MODELS_DIR = root / "transforms/main/models"
    gen.CONTRACTS_DIR = root / "soda/contracts"
    gen.DOMAINS_DIR = root / "packages/databox/databox/orchestration/domains"
    gen.SOURCES_REGISTRY_PATH = root / "packages/databox/databox/config/sources.py"
    gen.ENV_EXAMPLE_PATH = root / ".env.example"
    layout.PROJECT_ROOT = root
    layout.SOURCES_DIR = gen.SOURCES_PKG_DIR
    layout.DOMAINS_DIR = gen.DOMAINS_DIR
    layout.TESTS_DIR = root / "packages/databox-sources/tests"


@pytest.fixture
def env(tmp_path: Path):
    gen = _load("new_source", NEW_SOURCE_SCRIPT)
    layout = _load("check_source_layout", LAYOUT_SCRIPT)
    _repo(tmp_path)
    _rebind(gen, layout, tmp_path)
    return gen, layout, tmp_path


def test_validate_name_rejects_invalid_names() -> None:
    gen = _load("new_source", NEW_SOURCE_SCRIPT)
    for name in ("Bad", "analytics", "foo__bar", "foo_", "_foo"):
        with pytest.raises(ValueError):
            gen.validate_name(name)


@pytest.mark.parametrize("name", ["foo", "foo2", "foo_bar", "foo2_bar3"])
def test_validate_name_uses_canonical_source_pattern(name: str) -> None:
    gen = _load("new_source", NEW_SOURCE_SCRIPT)
    gen.validate_name(name)


@pytest.mark.parametrize(("shape", "profile"), [("rest", "http"), ("file", "file_snapshot")])
def test_generated_tree_and_registry_profile(env, shape: str, profile: str) -> None:
    gen, layout, root = env
    assert gen.main(["demo", "--shape", shape]) == 0
    source_dir = root / "packages/databox-sources/databox_sources/demo"
    assert not (source_dir / "config.yaml").exists()
    report = layout.check_source("demo")
    assert report.skipped and not report.ok
    incomplete = Source(
        name="demo",
        raw_tables=(),
        verification_profile=cast(Any, profile),
    )
    assert not layout.validate_sources([incomplete]).ok
    registry = (root / "packages/databox/databox/config/sources.py").read_text()
    assert f'verification_profile="{profile}"' in registry
    domain = (root / "packages/databox/databox/orchestration/domains/demo.py").read_text()
    assert "def _build_source()" in domain


def test_file_scaffold_requires_manifest_tests_and_failed_contract(env, capsys) -> None:
    gen, _, _ = env
    assert gen.main(["demo", "--shape", "file"]) == 0
    output = capsys.readouterr().out
    assert "pinned `config.yaml` manifest" in output
    assert "test_staged_publish.py" in output
    assert "CI matrix fail" in output


def test_database_shape_is_not_supported(env) -> None:
    gen, _, _ = env
    with pytest.raises(SystemExit):
        gen.main(["demo", "--shape", "database"])


def test_registry_wiring_is_idempotent(env) -> None:
    gen, _, root = env
    assert gen.main(["demo"]) == 0
    assert gen.main(["demo", "--force"]) == 0
    registry = (root / "packages/databox/databox/config/sources.py").read_text()
    assert registry.count('Source(name="demo"') == 1


def test_collision_and_dry_run(env, capsys) -> None:
    gen, _, root = env
    assert gen.main(["demo", "--dry-run"]) == 0
    assert not (root / "packages/databox-sources/databox_sources/demo").exists()
    assert "no files written" in capsys.readouterr().out
    assert gen.main(["demo"]) == 0
    assert gen.main(["demo"]) == 1


def test_rest_auth_modes(env) -> None:
    gen, _, root = env
    assert gen.main(["demo"]) == 0
    assert "API_KEY_DEMO=" in (root / ".env.example").read_text()
    assert gen.main(["public", "--no-auth"]) == 0
    source = (root / "packages/databox-sources/databox_sources/public/source.py").read_text()
    assert "API_KEY_PUBLIC" not in source


def test_no_auth_requires_rest(env) -> None:
    gen, _, _ = env
    assert gen.main(["demo", "--shape", "file", "--no-auth"]) == 2


def test_generated_stub_is_safe_for_registry_composition(env, monkeypatch) -> None:
    gen, _, root = env
    assert gen.main(["demo"]) == 0
    import types

    source_module = types.ModuleType("databox_sources.demo.source")
    vars(source_module)["demo_source"] = lambda: object()
    monkeypatch.setitem(sys.modules, "databox_sources.demo.source", source_module)
    domain_path = root / "packages/databox/databox/orchestration/domains/demo.py"
    spec = importlib.util.spec_from_file_location("generated_demo_domain", domain_path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert module.assets == []
    assert module.ingest_job.name == "demo_ingest"
    assert list(module.assets) == []


def test_scaffold_avoids_manual_composition_and_model_dirs(env) -> None:
    gen, _, root = env
    assert gen.main(["demo"]) == 0
    assert not (root / "transforms/main/models/demo").exists()
    assert not (root / "soda/contracts/demo").exists()
    assert not hasattr(gen, "wire_definitions")
