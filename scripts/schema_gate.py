"""Schema-contract gate — compare Soda contract YAMLs at HEAD against a base
revision (usually `main`) and fail on breaking changes unless explicitly
acknowledged.

A "breaking change" is:
  - a Soda contract file removed (model removed)
  - a column removed from a contract (column dropped)
  - a column's declared `data_type` changed to a non-widening type
  - the contract's `dataset` identifier changed (model renamed)

Additive changes (new contract, new column, new check) are always safe.

Usage:
    python scripts/schema_gate.py --base origin/main
    python scripts/schema_gate.py --base origin/main --accept ebird.fct_daily_bird_observations

Exit codes:
  0 — no breaking changes, or all breaking changes acknowledged
  1 — breaking changes found and not acknowledged
  2 — invocation error (missing base ref, git failure, invalid YAML, etc.)
"""

from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

CONTRACTS_DIR = Path("soda/contracts")

# Non-widening type transitions. Keys are current type, values are types the
# column may safely change TO. Everything else is considered breaking.
_SAFE_TYPE_WIDENINGS: dict[str, set[str]] = {
    "int": {"bigint", "decimal", "double", "float"},
    "integer": {"bigint", "decimal", "double", "float"},
    "smallint": {"int", "integer", "bigint", "decimal", "double", "float"},
    "bigint": {"decimal", "double"},
    "float": {"double"},
    "varchar": {"text", "string"},
    "text": {"varchar", "string"},
    "date": {"timestamp"},
}


@dataclass
class ContractChange:
    model: str
    kind: str  # "model_removed", "column_removed", "type_narrowed", "model_renamed"
    detail: str


@dataclass
class Report:
    breaking: list[ContractChange] = field(default_factory=list)
    additive: list[ContractChange] = field(default_factory=list)

    @property
    def has_breaking(self) -> bool:
        return bool(self.breaking)


def _run(cmd: list[str]) -> str:
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"git failed: {' '.join(cmd)}\n{result.stderr.strip()}")
    return result.stdout


def _list_contracts_at(revision: str) -> dict[str, str]:
    """Return {path: yaml_content} for every .yaml under CONTRACTS_DIR at revision."""
    listing = _run(["git", "ls-tree", "-r", "--name-only", revision, str(CONTRACTS_DIR)])
    out: dict[str, str] = {}
    for path in listing.splitlines():
        if not path.endswith(".yaml"):
            continue
        out[path] = _run(["git", "show", f"{revision}:{path}"])
    return out


def _list_contracts_head() -> dict[str, str]:
    out: dict[str, str] = {}
    for path in CONTRACTS_DIR.rglob("*.yaml"):
        out[str(path)] = path.read_text()
    return out


def _parse(text: str, path: str) -> dict[str, Any]:
    try:
        doc = yaml.safe_load(text) or {}
    except yaml.YAMLError as exc:
        raise RuntimeError(f"invalid YAML in {path}: {exc}") from exc
    if not isinstance(doc, dict):
        raise RuntimeError(f"{path}: expected mapping at root")
    return doc


def _columns(doc: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Return {column_name: {data_type: ...}} for each declared column."""
    cols = doc.get("columns") or []
    out: dict[str, dict[str, Any]] = {}
    for col in cols:
        if not isinstance(col, dict) or "name" not in col:
            continue
        out[col["name"]] = {"data_type": col.get("data_type")}
    return out


def _is_breaking_type_change(old: str | None, new: str | None) -> bool:
    if old is None or new is None:
        return False  # can't classify without both
    old_n, new_n = old.lower().strip(), new.lower().strip()
    if old_n == new_n:
        return False
    safe_targets = _SAFE_TYPE_WIDENINGS.get(old_n, set())
    return new_n not in safe_targets


def diff(base_contracts: dict[str, str], head_contracts: dict[str, str]) -> Report:
    report = Report()

    base_paths = set(base_contracts)
    head_paths = set(head_contracts)

    for removed_path in sorted(base_paths - head_paths):
        base_doc = _parse(base_contracts[removed_path], removed_path)
        model = base_doc.get("dataset", removed_path)
        report.breaking.append(
            ContractChange(
                model=model,
                kind="model_removed",
                detail=f"contract {removed_path} was removed",
            )
        )

    for added_path in sorted(head_paths - base_paths):
        head_doc = _parse(head_contracts[added_path], added_path)
        model = head_doc.get("dataset", added_path)
        report.additive.append(
            ContractChange(model=model, kind="model_added", detail=f"new contract {added_path}")
        )

    for path in sorted(base_paths & head_paths):
        base_doc = _parse(base_contracts[path], path)
        head_doc = _parse(head_contracts[path], path)
        model = head_doc.get("dataset", path)

        base_dataset = base_doc.get("dataset")
        head_dataset = head_doc.get("dataset")
        if base_dataset and head_dataset and base_dataset != head_dataset:
            report.breaking.append(
                ContractChange(
                    model=model,
                    kind="model_renamed",
                    detail=f"dataset changed: {base_dataset} -> {head_dataset}",
                )
            )

        base_cols = _columns(base_doc)
        head_cols = _columns(head_doc)

        for removed_col in sorted(set(base_cols) - set(head_cols)):
            report.breaking.append(
                ContractChange(
                    model=model,
                    kind="column_removed",
                    detail=f"column '{removed_col}' dropped",
                )
            )

        for added_col in sorted(set(head_cols) - set(base_cols)):
            report.additive.append(
                ContractChange(
                    model=model,
                    kind="column_added",
                    detail=f"new column '{added_col}'",
                )
            )

        for col in sorted(set(base_cols) & set(head_cols)):
            old_type = base_cols[col]["data_type"]
            new_type = head_cols[col]["data_type"]
            if _is_breaking_type_change(old_type, new_type):
                report.breaking.append(
                    ContractChange(
                        model=model,
                        kind="type_narrowed",
                        detail=f"column '{col}': {old_type} -> {new_type}",
                    )
                )

    return report


def acknowledgements(pr_body: str | None, env_override: str | None) -> set[str]:
    """Collect models whose breaking changes the author has explicitly accepted."""
    acked: set[str] = set()
    if env_override:
        acked.update(part.strip() for part in env_override.split(",") if part.strip())
    if pr_body:
        for match in re.finditer(r"^\s*accept-breaking-change:\s*([^\s]+)", pr_body, re.MULTILINE):
            acked.add(match.group(1).strip())
    return acked


def format_report(report: Report, acknowledged: set[str]) -> str:
    lines: list[str] = []
    if report.additive:
        lines.append("Additive changes (safe):")
        for change in report.additive:
            lines.append(f"  + [{change.model}] {change.detail}")
        lines.append("")
    if report.breaking:
        lines.append("Breaking changes:")
        for change in report.breaking:
            status = " (ACKED)" if change.model in acknowledged else ""
            lines.append(f"  ! [{change.model}]{status} {change.kind}: {change.detail}")
        lines.append("")
    if not report.additive and not report.breaking:
        lines.append("No contract changes.")
    return "\n".join(lines).rstrip()


def run_gate(base: str, pr_body: str | None, env_override: str | None) -> int:
    base_contracts = _list_contracts_at(base)
    head_contracts = _list_contracts_head()
    report = diff(base_contracts, head_contracts)
    acked = acknowledgements(pr_body, env_override)
    print(format_report(report, acked))

    if not report.has_breaking:
        return 0

    unacked = [c for c in report.breaking if c.model not in acked]
    if not unacked:
        print("\nAll breaking changes acknowledged via accept-breaking-change.")
        return 0

    print("\nFAIL: unacknowledged breaking changes.", file=sys.stderr)
    print(
        "To acknowledge, add `accept-breaking-change: <model>` to the PR body "
        "(one line per model).",
        file=sys.stderr,
    )
    return 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--base", default="origin/main", help="git revision to compare HEAD against"
    )
    parser.add_argument(
        "--pr-body-file",
        default=None,
        help="path to a file containing the PR body (for ack-token parsing)",
    )
    parser.add_argument(
        "--accept",
        default=None,
        help=(
            "comma-separated list of models whose breaking change is acknowledged"
            " (overrides ACCEPT_BREAKING_CHANGE env var)"
        ),
    )
    args = parser.parse_args(argv)

    pr_body: str | None = None
    if args.pr_body_file:
        pr_body = Path(args.pr_body_file).read_text()

    env_override = args.accept or os.environ.get("ACCEPT_BREAKING_CHANGE")

    try:
        return run_gate(args.base, pr_body, env_override)
    except RuntimeError as exc:
        print(f"schema-gate error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
