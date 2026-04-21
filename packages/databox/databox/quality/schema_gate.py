"""Classifier for Soda-contract schema changes (additive vs breaking).

Type widening delegates to sqlglot's dialect-aware parser (the same parser
SQLMesh uses internally) instead of a hand-rolled widening table.

Breaking:  contract removed, column removed, dataset renamed, type narrowed.
Additive:  contract added, column added, type widened.
"""

from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml
from sqlglot import exp

CONTRACTS = Path("soda/contracts")
_INT_RANK = {
    exp.DataType.Type.SMALLINT: 1,
    exp.DataType.Type.INT: 2,
    exp.DataType.Type.BIGINT: 3,
}


@dataclass
class ContractChange:
    model: str
    kind: str
    detail: str


@dataclass
class Report:
    breaking: list[ContractChange] = field(default_factory=list)
    additive: list[ContractChange] = field(default_factory=list)

    @property
    def has_breaking(self) -> bool:
        return bool(self.breaking)


def _parse_type(s: str | None) -> exp.DataType.Type | None:
    if not s:
        return None
    try:
        return exp.DataType.build(s).this
    except Exception:
        return None


def widens(old: str | None, new: str | None) -> bool:
    """True when `new` is a safe widening of (or identical to) `old`."""
    if not old or not new or old.strip().lower() == new.strip().lower():
        return True
    a, b = _parse_type(old), _parse_type(new)
    if a is None or b is None:
        return False
    if a == b:
        return True
    if a in _INT_RANK and b in _INT_RANK and _INT_RANK[b] >= _INT_RANK[a]:
        return True
    if a in _INT_RANK and b in exp.DataType.NUMERIC_TYPES and b not in _INT_RANK:
        return True
    if a in exp.DataType.TEXT_TYPES and b in exp.DataType.TEXT_TYPES:
        return True
    return a == exp.DataType.Type.DATE and b == exp.DataType.Type.TIMESTAMP


def _sh(cmd: list[str]) -> str:
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode:
        raise RuntimeError(f"{' '.join(cmd)}: {r.stderr.strip()}")
    return r.stdout


def contracts_at_revision(rev: str) -> dict[str, str]:
    paths = _sh(["git", "ls-tree", "-r", "--name-only", rev, str(CONTRACTS)]).splitlines()
    return {p: _sh(["git", "show", f"{rev}:{p}"]) for p in paths if p.endswith(".yaml")}


def contracts_at_head() -> dict[str, str]:
    return {str(p): p.read_text() for p in CONTRACTS.rglob("*.yaml")}


def _doc(text: str, path: str) -> dict[str, Any]:
    d = yaml.safe_load(text) or {}
    if not isinstance(d, dict):
        raise RuntimeError(f"{path}: root must be a mapping")
    return d


def _cols(d: dict[str, Any]) -> dict[str, str | None]:
    return {
        c["name"]: c.get("data_type")
        for c in (d.get("columns") or [])
        if isinstance(c, dict) and "name" in c
    }


def diff(base: dict[str, str], head: dict[str, str]) -> Report:
    r = Report()
    for p in sorted(set(base) - set(head)):
        model = _doc(base[p], p).get("dataset", p)
        r.breaking.append(ContractChange(model, "model_removed", f"contract {p} was removed"))
    for p in sorted(set(head) - set(base)):
        model = _doc(head[p], p).get("dataset", p)
        r.additive.append(ContractChange(model, "model_added", f"new contract {p}"))
    for p in sorted(set(base) & set(head)):
        b, h = _doc(base[p], p), _doc(head[p], p)
        m = h.get("dataset", p)
        if b.get("dataset") and h.get("dataset") and b["dataset"] != h["dataset"]:
            r.breaking.append(
                ContractChange(
                    m, "model_renamed", f"dataset changed: {b['dataset']} -> {h['dataset']}"
                )
            )
        bc, hc = _cols(b), _cols(h)
        for c in sorted(set(bc) - set(hc)):
            r.breaking.append(ContractChange(m, "column_removed", f"column '{c}' dropped"))
        for c in sorted(set(hc) - set(bc)):
            r.additive.append(ContractChange(m, "column_added", f"new column '{c}'"))
        for c in sorted(set(bc) & set(hc)):
            if not widens(bc[c], hc[c]):
                r.breaking.append(
                    ContractChange(m, "type_narrowed", f"column '{c}': {bc[c]} -> {hc[c]}")
                )
    return r


def acknowledgements(pr_body: str | None, env: str | None) -> set[str]:
    acked = {s.strip() for s in (env or "").split(",") if s.strip()}
    if pr_body:
        acked.update(
            m.group(1)
            for m in re.finditer(r"^\s*accept-breaking-change:\s*(\S+)", pr_body, re.MULTILINE)
        )
    return acked


def format_report(r: Report, acked: set[str]) -> str:
    if not r.breaking and not r.additive:
        return "No contract changes."
    out: list[str] = []
    if r.additive:
        out.append("Additive changes (safe):")
        out += [f"  + [{c.model}] {c.detail}" for c in r.additive]
    if r.breaking:
        if out:
            out.append("")
        out.append("Breaking changes:")
        out += [
            f"  ! [{c.model}]{' (ACKED)' if c.model in acked else ''} {c.kind}: {c.detail}"
            for c in r.breaking
        ]
    return "\n".join(out)
