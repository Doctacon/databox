"""Validate the canonical registry, source packages, domains, and test profiles.

In-flight scaffolds may carry ``# scaffold-lint: skip=<reason>`` in the first
10 source lines so the report explains why they are incomplete. A skipped
source is still a failed completed contract and therefore cannot enter CI.
"""

from __future__ import annotations

import argparse
import ast
import json
import sys
from collections import Counter
from collections.abc import Sequence
from dataclasses import asdict, dataclass, field
from pathlib import Path

from databox.config.sources import SOURCE_NAME_PATTERN, SOURCES, Source

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SOURCES_DIR = Path("packages/databox-sources/databox_sources")
DOMAINS_DIR = Path("packages/databox/databox/orchestration/domains")
TESTS_DIR = Path("packages/databox-sources/tests")
SKIP_MARKER = "scaffold-lint: skip="
SKIP_HEADER_LINES = 10
VALID_PROFILES = frozenset({"http", "file_snapshot"})
REQUIRED_TEST_FILES = {
    "http": ("test_resources.py", "test_schema.py", "test_smoke.py", "test_idempotency.py"),
    "file_snapshot": (
        "test_resources.py",
        "test_schema.py",
        "test_smoke.py",
        "test_idempotency.py",
        "test_staged_publish.py",
    ),
}
REQUIRED_DOMAIN_EXPORTS = frozenset(
    {"assets", "dlt_asset_keys", "sqlmesh_asset_keys", "asset_checks", "ingest_job"}
)
LEGACY_AUTHORITY_PATHS = (
    "packages/databox-sources/databox_sources/base.py",
    "packages/databox-sources/databox_sources/registry.py",
    "packages/databox/databox/config/pipeline_config.py",
    "packages/databox/databox/quality/engine.py",
    "scripts/templates/source/database/config.yaml.j2",
    "scripts/templates/source/database/source.py.j2",
    "scripts/templates/source/file/config.yaml.j2",
    "scripts/templates/source/rest/config.yaml.j2",
)
LEGACY_AUTHORITY_MODULES = frozenset(
    {
        "databox.config.pipeline_config",
        "databox.quality.engine",
        "databox_sources.base",
        "databox_sources.registry",
    }
)
ACTIVE_IMPORT_ROOTS = ("packages", "scripts", "transforms")
PACKAGE_ROOTS = (
    "packages/databox",
    "packages/databox-sources",
)


@dataclass
class SourceReport:
    name: str
    missing: list[str] = field(default_factory=list)
    skipped: bool = False
    skip_reason: str | None = None

    @property
    def ok(self) -> bool:
        return not self.skipped and not self.missing


@dataclass
class ContractReport:
    registry_errors: list[str]
    sources: list[SourceReport]

    @property
    def errors(self) -> list[str]:
        errors = list(self.registry_errors)
        for report in self.sources:
            if report.skipped:
                errors.append(f"{report.name}: incomplete scaffold ({report.skip_reason})")
            errors.extend(f"{report.name}: {item}" for item in report.missing)
        return errors

    @property
    def ok(self) -> bool:
        return not self.errors


def discover_sources(root: Path | None = None) -> list[str]:
    root = root or SOURCES_DIR
    children = sorted(root.iterdir()) if root.exists() else []
    return [
        child.name
        for child in children
        if child.is_dir()
        and not child.name.startswith(("_", "."))
        and (child / "source.py").exists()
    ]


def discover_domains(root: Path | None = None) -> list[str]:
    root = root or DOMAINS_DIR
    if not root.exists():
        return []
    return sorted(
        path.stem
        for path in root.glob("*.py")
        if path.stem not in {"__init__", "analytics"} and not path.stem.startswith("_")
    )


def _skip_marker(source_py: Path) -> str | None:
    if not source_py.exists():
        return None
    for line in source_py.read_text().splitlines()[:SKIP_HEADER_LINES]:
        idx = line.find(SKIP_MARKER)
        if idx >= 0:
            return line[idx + len(SKIP_MARKER) :].strip().split()[0] or "unspecified"
    return None


def _package_parts(path: Path, root: Path) -> tuple[str, ...]:
    for package_root in PACKAGE_ROOTS:
        base = root / package_root
        try:
            relative = path.relative_to(base).with_suffix("")
        except ValueError:
            continue
        return relative.parts[:-1]
    return ()


def _imported_modules(tree: ast.Module, path: Path, root: Path) -> set[str]:
    modules: set[str] = set()
    package = _package_parts(path, root)
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            if node.level == 0:
                if not node.module:
                    continue
                parent = node.module
            else:
                if not package or node.level > len(package) + 1:
                    continue
                base = package[: len(package) - node.level + 1]
                parent = (
                    ".".join((*base, *node.module.split("."))) if node.module else ".".join(base)
                )
            modules.add(parent)
            modules.update(f"{parent}.{alias.name}" for alias in node.names if alias.name != "*")
    return modules


def legacy_authority_errors(root: Path | None = None) -> list[str]:
    """Reject only the retired files/modules that formed the duplicate authority."""
    root = root or PROJECT_ROOT
    errors = [
        f"legacy authority file reintroduced: {relative}"
        for relative in LEGACY_AUTHORITY_PATHS
        if (root / relative).exists()
    ]
    for active_root in ACTIVE_IMPORT_ROOTS:
        directory = root / active_root
        if not directory.exists():
            continue
        for path in sorted(directory.rglob("*.py")):
            if "__pycache__" in path.parts:
                continue
            try:
                tree = ast.parse(path.read_text(), filename=str(path))
            except (OSError, SyntaxError, UnicodeDecodeError):
                continue
            for imported in sorted(_imported_modules(tree, path, root)):
                if any(
                    imported == legacy or imported.startswith(f"{legacy}.")
                    for legacy in LEGACY_AUTHORITY_MODULES
                ):
                    relative = path.relative_to(root)
                    errors.append(f"legacy authority import reintroduced in {relative}: {imported}")
    return errors


def registry_errors(sources: Sequence[Source] = SOURCES) -> list[str]:
    errors = legacy_authority_errors()
    counts = Counter(source.name for source in sources)
    for name, count in sorted(counts.items()):
        if count > 1:
            errors.append(f"duplicate canonical source name {name!r}: {count} entries")
    anchors = [source.name for source in sources if source.analytics_anchor]
    if len(anchors) > 1:
        errors.append(f"multiple analytics anchors: {', '.join(sorted(anchors))}")
    for source in sources:
        if not SOURCE_NAME_PATTERN.fullmatch(source.name):
            errors.append(f"invalid canonical source name: {source.name!r}")
        if source.domain_module != f"databox.orchestration.domains.{source.name}":
            errors.append(f"invalid domain identity for {source.name}: {source.domain_module}")
        if source.verification_profile not in VALID_PROFILES:
            errors.append(
                f"invalid verification profile for {source.name}: {source.verification_profile}"
            )
        if not source.raw_tables:
            errors.append(f"empty raw table inventory for {source.name}")
        table_counts = Counter(source.raw_tables)
        for table, count in sorted(table_counts.items()):
            if not SOURCE_NAME_PATTERN.fullmatch(table):
                errors.append(f"invalid raw table name for {source.name}: {table!r}")
            if count > 1:
                errors.append(f"duplicate raw table for {source.name}: {table}")
    if not sources:
        errors.append("canonical source registry is empty")
    return errors


def _parse(path: Path, report: SourceReport, label: str) -> ast.Module | None:
    try:
        return ast.parse(path.read_text(), filename=str(path))
    except SyntaxError as exc:
        report.missing.append(f"valid {label} Python in {path}: {exc.msg}")
        return None


def _assigned_names(tree: ast.Module) -> set[str]:
    names: set[str] = set()
    for node in tree.body:
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef):
            names.add(node.name)
        elif isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    names.add(target.id)
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            names.add(node.target.id)
    return names


def _assigned_values(tree: ast.Module, name: str) -> list[ast.expr]:
    values: list[ast.expr] = []
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(
            isinstance(target, ast.Name) and target.id == name for target in node.targets
        ):
            values.append(node.value)
        elif (
            isinstance(node, ast.AnnAssign)
            and isinstance(node.target, ast.Name)
            and node.target.id == name
            and node.value is not None
        ):
            values.append(node.value)
    return values


def _top_level_bindings(tree: ast.Module, name: str) -> list[ast.AST]:
    bindings: list[ast.AST] = []
    for node in tree.body:
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef):
            if node.name == name:
                bindings.append(node)
        elif isinstance(node, ast.Assign) and any(
            isinstance(target, ast.Name) and target.id == name for target in node.targets
        ):
            bindings.append(node)
        elif (
            isinstance(node, ast.AnnAssign)
            and isinstance(node.target, ast.Name)
            and node.target.id == name
        ):
            bindings.append(node)
    return bindings


def _is_builder_call(node: ast.AST) -> bool:
    return (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "_build_source"
    )


def _builder_call_count(nodes: Sequence[ast.AST]) -> int:
    return sum(1 for root in nodes for node in ast.walk(root) if _is_builder_call(node))


class _ExecutableBuilderCallVisitor(ast.NodeVisitor):
    """Count calls in executable statements without entering nested definitions."""

    def __init__(self) -> None:
        self.count = 0

    def visit_Call(self, node: ast.Call) -> None:
        if _is_builder_call(node):
            self.count += 1
        self.generic_visit(node)

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        return

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        return

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        return

    def visit_Lambda(self, node: ast.Lambda) -> None:
        return


def _executable_builder_call_count(function: ast.FunctionDef) -> int:
    visitor = _ExecutableBuilderCallVisitor()
    for statement in function.body:
        visitor.visit(statement)
    return visitor.count


def _is_dagster_call(value: ast.expr, attribute: str) -> bool:
    return (
        isinstance(value, ast.Call)
        and isinstance(value.func, ast.Attribute)
        and isinstance(value.func.value, ast.Name)
        and value.func.value.id == "dg"
        and value.func.attr == attribute
    )


def _is_specs_derived_key_list(value: ast.expr, dlt_assets_name: str) -> bool:
    if not isinstance(value, ast.ListComp) or len(value.generators) != 1:
        return False
    generator = value.generators[0]
    return (
        isinstance(generator.target, ast.Name)
        and not generator.ifs
        and isinstance(generator.iter, ast.Attribute)
        and generator.iter.attr == "specs"
        and isinstance(generator.iter.value, ast.Name)
        and generator.iter.value.id == dlt_assets_name
        and isinstance(value.elt, ast.Attribute)
        and value.elt.attr == "key"
        and isinstance(value.elt.value, ast.Name)
        and value.elt.value.id == generator.target.id
    )


def _dlt_assets_decorators(function: ast.FunctionDef) -> list[ast.Call]:
    decorators: list[ast.Call] = []
    for decorator in function.decorator_list:
        if not isinstance(decorator, ast.Call):
            continue
        target = decorator.func
        if isinstance(target, ast.Name) and target.id == "dlt_assets":
            decorators.append(decorator)
    return decorators


class _BuilderBoundaryVisitor(ast.NodeVisitor):
    def __init__(self, factory_name: str) -> None:
        self.factory_name = factory_name
        self.function: str | None = None
        self.factory_calls_outside_builder: set[str] = set()
        self.builder_smoke_limits = 0

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        previous = self.function
        self.function = node.name
        self.generic_visit(node)
        self.function = previous

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        previous = self.function
        self.function = node.name
        self.generic_visit(node)
        self.function = previous

    def visit_Call(self, node: ast.Call) -> None:
        if (
            isinstance(node.func, ast.Name)
            and node.func.id == self.factory_name
            and self.function != "_build_source"
        ):
            self.factory_calls_outside_builder.add(node.func.id)
        if (
            isinstance(node.func, ast.Attribute)
            and node.func.attr == "add_limit"
            and self.function == "_build_source"
        ):
            self.builder_smoke_limits += 1
        self.generic_visit(node)


def _resource_names(tree: ast.Module) -> set[str]:
    resources: set[str] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            continue
        for decorator in node.decorator_list:
            call = decorator if isinstance(decorator, ast.Call) else None
            target = call.func if call is not None else decorator
            is_resource = (
                isinstance(target, ast.Attribute)
                and target.attr == "resource"
                and isinstance(target.value, ast.Name)
                and target.value.id == "dlt"
            )
            if not is_resource:
                continue
            name = node.name
            if call is not None:
                for keyword in call.keywords:
                    if keyword.arg == "name" and isinstance(keyword.value, ast.Constant):
                        if isinstance(keyword.value.value, str):
                            name = keyword.value.value
            resources.add(name)
    return resources


def check_source(name: str, sources: Sequence[Source] = SOURCES) -> SourceReport:
    src_pkg = SOURCES_DIR / name
    source_py = src_pkg / "source.py"
    report = SourceReport(name=name)
    marker = _skip_marker(source_py)
    if marker is not None:
        report.skipped = True
        report.skip_reason = marker
        return report

    matches = [source for source in sources if source.name == name]
    source = matches[0] if matches else None
    if source is None:
        report.missing.append(f"canonical registry entry for {name}")

    if not source_py.exists():
        report.missing.append(str(source_py))
        source_tree = None
    else:
        source_tree = _parse(source_py, report, "source")

    if source is not None:
        profile = source.verification_profile
        if profile in REQUIRED_TEST_FILES:
            for test_file in REQUIRED_TEST_FILES[profile]:
                path = TESTS_DIR / name / test_file
                if not path.exists():
                    report.missing.append(str(path))
        if source_tree is not None:
            resources = _resource_names(source_tree)
            if resources != set(source.raw_tables):
                report.missing.append(
                    "raw table inventory does not match declared dlt resources: "
                    f"registry={sorted(source.raw_tables)}, source={sorted(resources)}"
                )

    domain_file = DOMAINS_DIR / f"{name}.py"
    if not domain_file.exists():
        report.missing.append(str(domain_file))
    else:
        domain_tree = _parse(domain_file, report, "domain")
        if domain_tree is not None and source is not None:
            names = _assigned_names(domain_tree)
            for required in sorted(REQUIRED_DOMAIN_EXPORTS):
                if required not in names:
                    report.missing.append(f"required domain export {required!r} in {domain_file}")

            builder_bindings = _top_level_bindings(domain_tree, "_build_source")
            if len(builder_bindings) != 1 or not isinstance(builder_bindings[0], ast.FunctionDef):
                report.missing.append(
                    f"exactly one callable unshadowed source builder in {domain_file}"
                )

            dlt_assets_name = f"{name}_dlt_assets"
            dlt_bindings = _top_level_bindings(domain_tree, dlt_assets_name)
            dlt_function = (
                dlt_bindings[0]
                if len(dlt_bindings) == 1 and isinstance(dlt_bindings[0], ast.FunctionDef)
                else None
            )
            if dlt_function is None:
                report.missing.append(
                    f"exactly one callable domain asset {dlt_assets_name!r} in {domain_file}"
                )
            else:
                decorators = _dlt_assets_decorators(dlt_function)
                definition_calls = [
                    keyword.value
                    for decorator in decorators
                    for keyword in decorator.keywords
                    if keyword.arg == "dlt_source" and _is_builder_call(keyword.value)
                ]
                if len(decorators) != 1 or len(definition_calls) != 1:
                    report.missing.append(
                        f"{dlt_assets_name} must have one @dlt_assets decorator whose "
                        f"dlt_source calls _build_source in {domain_file}"
                    )
                execution_calls = _executable_builder_call_count(dlt_function)
                if execution_calls != 1:
                    report.missing.append(
                        f"{dlt_assets_name} must call _build_source exactly once at "
                        f"execution time in {domain_file}"
                    )
                if _builder_call_count(domain_tree.body) != 2:
                    report.missing.append(
                        f"_build_source must have exactly one definition-time and one "
                        f"execution-time call in {domain_file}"
                    )

            asset_values = _assigned_values(domain_tree, "assets")
            assets_valid = (
                len(_top_level_bindings(domain_tree, "assets")) == 1
                and len(asset_values) == 1
                and isinstance(asset_values[0], ast.List)
                and len(asset_values[0].elts) == 1
                and isinstance(asset_values[0].elts[0], ast.Name)
                and asset_values[0].elts[0].id == dlt_assets_name
            )
            if not assets_valid:
                report.missing.append(
                    f"assets must list {dlt_assets_name} exactly once in {domain_file}"
                )

            asset_check_values = _assigned_values(domain_tree, "asset_checks")
            if (
                len(_top_level_bindings(domain_tree, "asset_checks")) != 1
                or len(asset_check_values) != 1
                or not isinstance(asset_check_values[0], ast.List)
            ):
                report.missing.append(
                    f"asset_checks must be assigned a list expression in {domain_file}"
                )

            dlt_key_values = _assigned_values(domain_tree, "dlt_asset_keys")
            if (
                len(_top_level_bindings(domain_tree, "dlt_asset_keys")) != 1
                or len(dlt_key_values) != 1
                or not _is_specs_derived_key_list(dlt_key_values[0], dlt_assets_name)
            ):
                report.missing.append(
                    "dlt_asset_keys must be a list comprehension derived from "
                    f"{dlt_assets_name}.specs in {domain_file}"
                )

            sqlmesh_key_values = _assigned_values(domain_tree, "sqlmesh_asset_keys")
            if (
                len(_top_level_bindings(domain_tree, "sqlmesh_asset_keys")) != 1
                or len(sqlmesh_key_values) != 1
                or not isinstance(sqlmesh_key_values[0], ast.List | ast.ListComp)
            ):
                report.missing.append(
                    f"sqlmesh_asset_keys must be assigned a list expression in {domain_file}"
                )

            ingest_values = _assigned_values(domain_tree, "ingest_job")
            if (
                len(_top_level_bindings(domain_tree, "ingest_job")) != 1
                or len(ingest_values) != 1
                or not _is_dagster_call(ingest_values[0], "define_asset_job")
            ):
                report.missing.append(
                    f"ingest_job must be assigned from dg.define_asset_job in {domain_file}"
                )

            daily_bindings = _top_level_bindings(domain_tree, "daily_pipeline")
            schedule_bindings = _top_level_bindings(domain_tree, "schedule")
            if source.scheduled:
                daily_values = _assigned_values(domain_tree, "daily_pipeline")
                if (
                    len(daily_bindings) != 1
                    or len(daily_values) != 1
                    or not _is_dagster_call(daily_values[0], "define_asset_job")
                ):
                    report.missing.append(
                        "scheduled source daily_pipeline must be assigned from "
                        f"dg.define_asset_job in {domain_file}"
                    )
                schedule_values = _assigned_values(domain_tree, "schedule")
                if (
                    len(schedule_bindings) != 1
                    or len(schedule_values) != 1
                    or not _is_dagster_call(schedule_values[0], "ScheduleDefinition")
                ):
                    report.missing.append(
                        "scheduled source schedule must be assigned from "
                        f"dg.ScheduleDefinition in {domain_file}"
                    )
            elif daily_bindings or schedule_bindings:
                report.missing.append(
                    f"unscheduled source omits daily_pipeline and schedule in {domain_file}"
                )

            boundary = _BuilderBoundaryVisitor(f"{name}_source")
            boundary.visit(domain_tree)
            if boundary.factory_calls_outside_builder:
                report.missing.append(
                    "source factory calls must be owned by _build_source in "
                    f"{domain_file}: {sorted(boundary.factory_calls_outside_builder)}"
                )
            if boundary.builder_smoke_limits:
                report.missing.append(f"smoke limiting must remain execution-only in {domain_file}")

    if source is not None and source.verification_profile == "file_snapshot":
        manifest = src_pkg / "config.yaml"
        if not manifest.exists():
            report.missing.append(str(manifest))
    elif (src_pkg / "config.yaml").exists():
        report.missing.append(f"retired generic config {src_pkg / 'config.yaml'}")

    return report


def validate_sources(sources: Sequence[Source] = SOURCES) -> ContractReport:
    discovered = set(discover_sources()) | set(discover_domains())
    names = sorted(discovered | {source.name for source in sources})
    reports = [check_source(name, sources) for name in names]
    return ContractReport(registry_errors=registry_errors(sources), sources=reports)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    args = parser.parse_args(argv)

    contract = validate_sources()
    if args.json:
        print(
            json.dumps(
                {
                    "registry_errors": contract.registry_errors,
                    "sources": [asdict(report) for report in contract.sources],
                },
                indent=2,
            )
        )
    else:
        for error in contract.registry_errors:
            print(f"  ✗ registry: {error}")
        for report in contract.sources:
            if report.skipped:
                print(f"  ~ {report.name} (incomplete: {report.skip_reason})")
            elif report.ok:
                print(f"  ✓ {report.name}")
            else:
                print(f"  ✗ {report.name}")
            for missing in report.missing:
                print(f"      missing: {missing}")
        skipped = sum(1 for report in contract.sources if report.skipped)
        failed = len([report for report in contract.sources if report.missing])
        passed = len(contract.sources) - skipped - failed
        print(
            f"\n{passed} ok · {skipped} incomplete · {failed} failing "
            f"(of {len(contract.sources)}) · {len(contract.registry_errors)} registry errors"
        )
    return 0 if contract.ok else 1


if __name__ == "__main__":
    sys.exit(main())
