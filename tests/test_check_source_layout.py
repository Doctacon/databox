"""Executable contract tests for scripts/check_source_layout.py."""

from __future__ import annotations

import importlib.util
import sys
from dataclasses import replace
from pathlib import Path
from typing import Any, cast

import pytest
from databox.config.sources import Source

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


def _entry(
    name: str = "foo",
    *,
    profile: str = "http",
    scheduled: bool = True,
    anchor: bool = False,
    raw_tables: tuple[str, ...] = ("records",),
) -> Source:
    return Source(
        name=name,
        raw_tables=raw_tables,
        scheduled=scheduled,
        analytics_anchor=anchor,
        verification_profile=cast(Any, profile),
    )


def _rebind(module, root: Path) -> None:
    module.PROJECT_ROOT = root
    module.SOURCES_DIR = root / "packages/databox-sources/databox_sources"
    module.DOMAINS_DIR = root / "packages/databox/databox/orchestration/domains"
    module.TESTS_DIR = root / "packages/databox-sources/tests"


def _source(
    root: Path,
    name: str = "foo",
    *,
    scheduled_exports: bool = True,
    builder_count: int = 1,
    required_exports: bool = True,
    resource_names: tuple[str, ...] = ("records",),
    profile: str = "http",
) -> Path:
    source_dir = root / "packages/databox-sources/databox_sources" / name
    source_dir.mkdir(parents=True)
    resource_code = "\n".join(
        f'@dlt.resource(name="{resource}")\ndef {resource}():\n    yield {{"id": 1}}\n'
        for resource in resource_names
    )
    (source_dir / "source.py").write_text("import dlt\n\n" + resource_code)

    domains = root / "packages/databox/databox/orchestration/domains"
    domains.mkdir(parents=True, exist_ok=True)
    builders = "\n".join(
        "def _build_source():\n    return object()\n" for _ in range(builder_count)
    )
    exports = ""
    if required_exports:
        exports = (
            f"@dlt_assets(dlt_source=_build_source())\n"
            f"def {name}_dlt_assets():\n    return _build_source()\n"
            f"assets = [{name}_dlt_assets]\n"
            f"dlt_asset_keys = [spec.key for spec in {name}_dlt_assets.specs]\n"
            "sqlmesh_asset_keys = []\n"
            "asset_checks = []\n"
            "ingest_job = dg.define_asset_job(name='ingest')\n"
        )
    schedule = (
        "daily_pipeline = dg.define_asset_job(name='daily')\n"
        "schedule = dg.ScheduleDefinition(job=daily_pipeline, cron_schedule='0 0 * * *')\n"
        if scheduled_exports
        else ""
    )
    (domains / f"{name}.py").write_text(builders + exports + schedule)

    tests_dir = root / "packages/databox-sources/tests" / name
    tests_dir.mkdir(parents=True)
    files = ["test_resources.py", "test_schema.py", "test_smoke.py", "test_idempotency.py"]
    if profile == "file_snapshot":
        files.append("test_staged_publish.py")
        (source_dir / "config.yaml").write_text("source: {}\n")
    for test_file in files:
        (tests_dir / test_file).write_text("# profile contract\n")
    return source_dir


def test_complete_http_source_passes_every_contract_layer(tmp_path: Path) -> None:
    module = _load_module()
    _rebind(module, tmp_path)
    _source(tmp_path)
    contract = module.validate_sources([_entry()])
    assert contract.ok
    assert module.check_source("foo", [_entry()]).ok


def test_registry_rejects_invalid_and_duplicate_names() -> None:
    module = _load_module()
    for name in ("Bad_Name", "foo__bar", "foo_"):
        invalid = replace(_entry(), name=name)
        assert any(
            "invalid canonical source name" in item for item in module.registry_errors([invalid])
        )
    assert any(
        "duplicate canonical source" in item
        for item in module.registry_errors([_entry(), _entry()])
    )


@pytest.mark.parametrize(
    "relative",
    [
        "packages/databox-sources/databox_sources/base.py",
        "packages/databox-sources/databox_sources/registry.py",
        "packages/databox/databox/config/pipeline_config.py",
        "packages/databox/databox/quality/engine.py",
        "scripts/templates/source/database/config.yaml.j2",
        "scripts/templates/source/database/source.py.j2",
        "scripts/templates/source/file/config.yaml.j2",
        "scripts/templates/source/rest/config.yaml.j2",
    ],
)
def test_contract_rejects_each_retired_legacy_authority_path(tmp_path: Path, relative: str) -> None:
    module = _load_module()
    _rebind(module, tmp_path)
    _source(tmp_path)
    path = tmp_path / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("# retired generic authority\n")

    contract = module.validate_sources([_entry()])
    assert not contract.ok
    assert any(
        f"legacy authority file reintroduced: {relative}" == item for item in contract.errors
    )


@pytest.mark.parametrize(
    "legacy_module",
    [
        "databox.config.pipeline_config",
        "databox.quality.engine",
        "databox_sources.base",
        "databox_sources.registry",
    ],
)
def test_contract_rejects_active_legacy_authority_imports(
    tmp_path: Path, legacy_module: str
) -> None:
    module = _load_module()
    _rebind(module, tmp_path)
    _source(tmp_path)
    consumer = tmp_path / "packages/databox/databox/consumer.py"
    consumer.parent.mkdir(parents=True, exist_ok=True)
    consumer.write_text(f"import {legacy_module}\n")

    contract = module.validate_sources([_entry()])
    assert not contract.ok
    assert any(
        "legacy authority import reintroduced" in item and legacy_module in item
        for item in contract.errors
    )


@pytest.mark.parametrize(
    ("statement", "legacy_module"),
    [
        ("from databox.config import pipeline_config", "databox.config.pipeline_config"),
        ("from databox.quality import engine", "databox.quality.engine"),
        ("from databox_sources import base", "databox_sources.base"),
        ("from databox_sources import registry", "databox_sources.registry"),
    ],
)
def test_contract_rejects_parent_child_legacy_imports(
    tmp_path: Path, statement: str, legacy_module: str
) -> None:
    module = _load_module()
    _rebind(module, tmp_path)
    _source(tmp_path)
    consumer = tmp_path / "packages/databox/databox/consumer.py"
    consumer.parent.mkdir(parents=True, exist_ok=True)
    consumer.write_text(f"{statement}\n")

    errors = module.validate_sources([_entry()]).errors
    assert any(
        "legacy authority import reintroduced" in item and legacy_module in item for item in errors
    )


def test_contract_rejects_relative_legacy_import_but_allows_legitimate_parents_and_factories(
    tmp_path: Path,
) -> None:
    module = _load_module()
    _rebind(module, tmp_path)
    _source(tmp_path)
    factories = tmp_path / "packages/databox/databox/orchestration/_factories.py"
    factories.write_text("def dlt_translator():\n    return object()\n")
    legitimate = tmp_path / "packages/databox/databox/legitimate.py"
    legitimate.write_text(
        "from databox.config import settings\n"
        "from databox.orchestration import _factories\n"
        "from databox_sources import ebird\n"
    )
    assert module.validate_sources([_entry()]).ok

    consumer = tmp_path / "packages/databox-sources/databox_sources/consumer.py"
    consumer.write_text("from .registry import get_registry\n")
    errors = module.validate_sources([_entry()]).errors
    assert any(
        "legacy authority import reintroduced" in item and "databox_sources.registry" in item
        for item in errors
    )


def test_registry_rejects_multiple_analytics_anchors() -> None:
    module = _load_module()
    sources = [_entry("foo", anchor=True), _entry("bar", anchor=True)]
    assert any("multiple analytics anchors" in item for item in module.registry_errors(sources))


def test_registry_rejects_invalid_profile_and_raw_inventory() -> None:
    module = _load_module()
    errors = module.registry_errors(
        [
            _entry(profile="database"),
            _entry("empty", raw_tables=()),
            _entry("duplicate", raw_tables=("records", "records")),
            _entry("invalid_table", raw_tables=("BadTable",)),
        ]
    )
    assert any("invalid verification profile" in item for item in errors)
    assert any("empty raw table inventory" in item for item in errors)
    assert any("duplicate raw table" in item for item in errors)
    assert any("invalid raw table name" in item for item in errors)


@pytest.mark.parametrize("resource_names", [("records", "extra"), ()])
def test_source_resource_inventory_must_match_registry(
    tmp_path: Path, resource_names: tuple[str, ...]
) -> None:
    module = _load_module()
    _rebind(module, tmp_path)
    _source(tmp_path, resource_names=resource_names)
    report = module.check_source("foo", [_entry()])
    assert any("inventory does not match" in item for item in report.missing)


def test_missing_profile_artifact_fails(tmp_path: Path) -> None:
    module = _load_module()
    _rebind(module, tmp_path)
    _source(tmp_path)
    (module.TESTS_DIR / "foo/test_schema.py").unlink()
    assert any("test_schema.py" in item for item in module.check_source("foo", [_entry()]).missing)


def test_file_snapshot_requires_manifest_and_staged_publish_test(tmp_path: Path) -> None:
    module = _load_module()
    _rebind(module, tmp_path)
    source_dir = _source(tmp_path, profile="file_snapshot")
    entry = _entry(profile="file_snapshot")
    assert module.check_source("foo", [entry]).ok
    (source_dir / "config.yaml").unlink()
    (module.TESTS_DIR / "foo/test_staged_publish.py").unlink()
    report = module.check_source("foo", [entry])
    assert any("config.yaml" in item for item in report.missing)
    assert any("test_staged_publish.py" in item for item in report.missing)


def test_builder_must_be_singular_callable_and_used_at_exact_boundaries(tmp_path: Path) -> None:
    module = _load_module()
    entry = _entry()
    for count in (0, 2):
        root = tmp_path / f"count-{count}"
        _rebind(module, root)
        _source(root, builder_count=count)
        assert any(
            "exactly one callable" in item for item in module.check_source("foo", [entry]).missing
        )

    noncallable_root = tmp_path / "noncallable"
    _rebind(module, noncallable_root)
    _source(noncallable_root)
    noncallable_domain = module.DOMAINS_DIR / "foo.py"
    noncallable_domain.write_text(
        noncallable_domain.read_text().replace(
            "def _build_source():\n    return object()",
            "_build_source = object()",
        )
    )
    assert any(
        "exactly one callable" in item for item in module.check_source("foo", [entry]).missing
    )

    rebound_root = tmp_path / "rebound"
    _rebind(module, rebound_root)
    _source(rebound_root)
    rebound_domain = module.DOMAINS_DIR / "foo.py"
    rebound_domain.write_text(rebound_domain.read_text() + "\n_build_source = None\n")
    assert any(
        "unshadowed source builder" in item for item in module.check_source("foo", [entry]).missing
    )

    misplaced_root = tmp_path / "misplaced"
    _rebind(module, misplaced_root)
    _source(misplaced_root)
    misplaced_domain = module.DOMAINS_DIR / "foo.py"
    text = misplaced_domain.read_text()
    text = text.replace(
        "@dlt_assets(dlt_source=_build_source())",
        "@dlt_assets()",
    ).replace("    return _build_source()", "    return object()", 1)
    misplaced_domain.write_text(text + "\n_build_source()\n_build_source()\n")
    missing = module.check_source("foo", [entry]).missing
    assert any("dlt_source calls _build_source" in item for item in missing)
    assert any("execution time" in item for item in missing)

    nested_root = tmp_path / "nested"
    _rebind(module, nested_root)
    _source(nested_root)
    nested_domain = module.DOMAINS_DIR / "foo.py"
    nested_domain.write_text(
        nested_domain.read_text().replace(
            "def foo_dlt_assets():\n    return _build_source()",
            "def foo_dlt_assets():\n"
            "    def dead_branch():\n"
            "        return _build_source()\n"
            "    return object()",
        )
    )
    assert any("execution time" in item for item in module.check_source("foo", [entry]).missing)


def test_source_factory_and_smoke_limit_stay_inside_correct_boundaries(tmp_path: Path) -> None:
    module = _load_module()
    _rebind(module, tmp_path)
    _source(tmp_path)
    domain = module.DOMAINS_DIR / "foo.py"
    domain.write_text(
        domain.read_text()
        + "\ndef bypass():\n    return foo_source()\n"
        + "\ndef _bad_smoke():\n    source = object()\n    source.add_limit(max_items=1)\n"
    )
    # Move the smoke call into the canonical builder to exercise that invariant.
    text = domain.read_text().replace(
        "def _build_source():\n    return object()",
        "def _build_source():\n"
        "    source = object()\n"
        "    source.add_limit(max_items=1)\n"
        "    return source",
    )
    domain.write_text(text)
    missing = module.check_source("foo", [_entry()]).missing
    assert any("source factory calls must be owned" in item for item in missing)
    assert any("smoke limiting must remain execution-only" in item for item in missing)


def test_required_domain_exports_are_enforced(tmp_path: Path) -> None:
    module = _load_module()
    _rebind(module, tmp_path)
    _source(tmp_path, required_exports=False)
    missing = module.check_source("foo", [_entry()]).missing
    assert any("required domain export 'assets'" in item for item in missing)
    assert any("callable domain asset 'foo_dlt_assets'" in item for item in missing)


@pytest.mark.parametrize(
    ("valid", "invalid", "message"),
    [
        (
            "@dlt_assets(dlt_source=_build_source())\n"
            "def foo_dlt_assets():\n    return _build_source()",
            "foo_dlt_assets = None",
            "callable domain asset",
        ),
        ("assets = [foo_dlt_assets]", "assets = None", "assets must list"),
        (
            "assets = [foo_dlt_assets]",
            "assets = [foo_dlt_assets, object()]",
            "assets must list",
        ),
        ("asset_checks = []", "asset_checks = None", "asset_checks must be assigned"),
        (
            "dlt_asset_keys = [spec.key for spec in foo_dlt_assets.specs]",
            "dlt_asset_keys = None",
            "dlt_asset_keys must be a list comprehension",
        ),
        (
            "dlt_asset_keys = [spec.key for spec in foo_dlt_assets.specs]",
            "dlt_asset_keys = [None for spec in foo_dlt_assets.specs]",
            "dlt_asset_keys must be a list comprehension",
        ),
        (
            "sqlmesh_asset_keys = []",
            "sqlmesh_asset_keys = None",
            "sqlmesh_asset_keys must be assigned",
        ),
        (
            "ingest_job = dg.define_asset_job(name='ingest')",
            "ingest_job = None",
            "ingest_job must be assigned",
        ),
        (
            "daily_pipeline = dg.define_asset_job(name='daily')",
            "daily_pipeline = None",
            "daily_pipeline must be assigned",
        ),
        (
            "schedule = dg.ScheduleDefinition(job=daily_pipeline, cron_schedule='0 0 * * *')",
            "schedule = None",
            "schedule must be assigned",
        ),
    ],
)
def test_dagster_exports_require_executable_ast_shapes(
    tmp_path: Path, valid: str, invalid: str, message: str
) -> None:
    module = _load_module()
    _rebind(module, tmp_path)
    _source(tmp_path)
    domain = module.DOMAINS_DIR / "foo.py"
    domain.write_text(domain.read_text().replace(valid, invalid))
    assert any(message in item for item in module.check_source("foo", [_entry()]).missing)


def test_schedule_exports_must_match_registry_flag(tmp_path: Path) -> None:
    module = _load_module()
    scheduled_root = tmp_path / "scheduled"
    _rebind(module, scheduled_root)
    _source(scheduled_root, scheduled_exports=False)
    missing = module.check_source("foo", [_entry(scheduled=True)]).missing
    assert any("daily_pipeline must be assigned" in item for item in missing)
    assert any("schedule must be assigned" in item for item in missing)

    static_root = tmp_path / "static"
    _rebind(module, static_root)
    _source(static_root, scheduled_exports=True)
    assert any(
        "unscheduled source omits" in item
        for item in module.check_source("foo", [_entry(scheduled=False)]).missing
    )


def test_unregistered_source_or_domain_fails(tmp_path: Path) -> None:
    module = _load_module()
    _rebind(module, tmp_path)
    _source(tmp_path)
    contract = module.validate_sources([])
    assert not contract.ok
    assert any("registry entry" in item for item in contract.errors)


def test_skip_marker_is_visible_but_fails_completed_contract(tmp_path: Path) -> None:
    module = _load_module()
    _rebind(module, tmp_path)
    source_dir = _source(tmp_path)
    (source_dir / "source.py").write_text("# scaffold-lint: skip=experimental\n")
    report = module.check_source("foo", [_entry()])
    assert report.skipped and not report.ok and report.skip_reason == "experimental"
    contract = module.validate_sources([_entry()])
    assert not contract.ok
    assert any("incomplete scaffold" in item for item in contract.errors)


def test_discover_ignores_private_files_and_analytics_domain(tmp_path: Path) -> None:
    module = _load_module()
    base = tmp_path / "packages/databox-sources/databox_sources"
    (base / "_shared").mkdir(parents=True)
    (base / "_shared/source.py").write_text("x")
    (base / "foo").mkdir()
    (base / "foo/source.py").write_text("x")
    (base / "bar.py").write_text("x")
    domains = tmp_path / "packages/databox/databox/orchestration/domains"
    domains.mkdir(parents=True)
    (domains / "foo.py").write_text("x")
    (domains / "analytics.py").write_text("x")
    assert module.discover_sources(base) == ["foo"]
    assert module.discover_domains(domains) == ["foo"]
