#!/usr/bin/env python3
"""Registry-derived source CI matrix and isolated coverage runner."""

from __future__ import annotations

import argparse
import importlib.util
import json
import subprocess
import sys
from collections.abc import Sequence
from pathlib import Path
from types import ModuleType
from typing import Any

from databox.config.sources import SOURCES, Source


def _load_layout_module() -> ModuleType:
    path = Path(__file__).with_name("check_source_layout.py")
    spec = importlib.util.spec_from_file_location("_databox_source_layout", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load source contract checker: {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


check_source_layout = _load_layout_module()

ROOT = Path(__file__).resolve().parent.parent


def build_matrix(sources: Sequence[Source] = SOURCES) -> dict[str, list[dict[str, str]]]:
    """Return a deterministic matrix only for a valid canonical registry."""
    errors = check_source_layout.registry_errors(sources)
    if errors:
        raise ValueError("invalid canonical source registry:\n- " + "\n- ".join(errors))
    return {
        "include": [
            {"source": source.name, "profile": source.verification_profile}
            for source in sorted(sources, key=lambda item: item.name)
        ]
    }


def validate_contract(sources: Sequence[Source] = SOURCES) -> dict[str, list[dict[str, str]]]:
    """Validate the complete executable contract, then return the matrix."""
    matrix = build_matrix(sources)
    contract = check_source_layout.validate_sources(sources)
    if contract.errors:
        raise ValueError("source contract validation failed:\n- " + "\n- ".join(contract.errors))
    return matrix


def source_coverage_commands(
    sources: Sequence[Source] = SOURCES,
    *,
    python: str = sys.executable,
    root: Path = ROOT,
) -> list[list[str]]:
    """Build isolated offline coverage commands for shared and per-source tests."""
    matrix = build_matrix(sources)
    commands: list[list[str]] = []
    source_tests = root / "packages/databox-sources/tests"
    shared_tests = [str(path.relative_to(root)) for path in sorted(source_tests.glob("test_*.py"))]
    if shared_tests:
        commands.append(
            [
                python,
                "-m",
                "coverage",
                "run",
                "--append",
                "-m",
                "pytest",
                *shared_tests,
                "-o",
                "testpaths=packages/databox-sources/tests",
                "-o",
                "addopts=-v --tb=short --record-mode=none --block-network",
            ]
        )
    for entry in matrix["include"]:
        source = entry["source"]
        test_path = f"packages/databox-sources/tests/{source}"
        commands.append(
            [
                python,
                "-m",
                "coverage",
                "run",
                "--append",
                "-m",
                "pytest",
                test_path,
                "-o",
                f"testpaths={test_path}",
                "-o",
                "addopts=-v --tb=short --record-mode=none --block-network",
            ]
        )
    return commands


def run_source_coverage() -> None:
    """Validate the contract and execute source suites in isolated processes."""
    validate_contract()
    for command in source_coverage_commands():
        subprocess.run(command, cwd=ROOT, check=True)  # noqa: S603


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    matrix = subparsers.add_parser("matrix", help="validate and print the source matrix")
    matrix.add_argument("--pretty", action="store_true", help="pretty-print JSON")
    subparsers.add_parser(
        "coverage",
        help="run every source suite in an isolated coverage process",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.command == "matrix":
        payload: dict[str, Any] = validate_contract()
        print(json.dumps(payload, indent=2 if args.pretty else None, sort_keys=True))
        return 0
    run_source_coverage()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
