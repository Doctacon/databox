"""Generate trivial-rename staging SQL from Soda contracts.

A staging contract carries enough shape (source table + per-column source
name + optional cast type) to emit the equivalent `SELECT ... FROM raw_*`.
Non-trivial staging (joins, derivations, UNION, filters) opts out with a
`-- staging-codegen: skip` header on the target SQL file.

Contract extensions (additive — does not break schema-contract-gate):

    dataset: databox/<schema>/<table>
    source_table: raw_<source>.main.<table>
    description: <free text>
    columns:
      - name: target_col
        source_column: raw_col        # optional; defaults to `name`
        data_type: double             # optional; emits CAST if present
        checks: ...
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml
from jinja2 import Environment, FileSystemLoader, StrictUndefined

CONTRACTS_DIR = Path("soda/contracts")
MODELS_DIR = Path("transforms/main/models")
TEMPLATE_DIR = Path("scripts/templates")
SKIP_MARKER = "staging-codegen: skip"


@dataclass
class Column:
    name: str
    source_column: str
    data_type: str | None


@dataclass
class StagingModel:
    contract_path: Path
    target_path: Path
    schema: str
    table: str
    description: str
    source_table: str
    columns: list[Column]


def _template_env() -> Environment:
    return Environment(
        loader=FileSystemLoader(str(TEMPLATE_DIR)),
        keep_trailing_newline=True,
        undefined=StrictUndefined,
    )


def _target_for_dataset(dataset: str) -> tuple[str, str, Path] | None:
    if "/" not in dataset:
        return None
    parts = dataset.split("/")
    if len(parts) < 3 or not parts[1].endswith("_staging"):
        return None
    schema, table = parts[1], parts[2]
    target = MODELS_DIR / schema.split("_staging")[0] / "staging" / f"{table}.sql"
    return schema, table, target


def parse_contract(path: Path) -> StagingModel | None:
    """Parse a staging contract into a StagingModel, or None if it is not a staging contract."""
    doc: dict[str, Any] = yaml.safe_load(path.read_text()) or {}
    target_info = _target_for_dataset(doc.get("dataset", ""))
    if target_info is None:
        return None
    schema, table, target_path = target_info
    source_table = doc.get("source_table")
    if not source_table:
        if is_skipped(target_path):
            return None
        raise ValueError(f"{path}: staging contract missing 'source_table' key")
    cols_raw = doc.get("columns") or []
    columns = [
        Column(
            name=str(c["name"]),
            source_column=str(c.get("source_column") or c["name"]),
            data_type=str(c["data_type"]) if c.get("data_type") else None,
        )
        for c in cols_raw
        if isinstance(c, dict) and "name" in c
    ]
    return StagingModel(
        contract_path=path,
        target_path=target_path,
        schema=schema,
        table=table,
        description=doc.get("description", f"Staging model {schema}.{table}"),
        source_table=source_table,
        columns=columns,
    )


def render(model: StagingModel, env: Environment | None = None) -> str:
    jenv: Environment = env if env is not None else _template_env()
    tmpl = jenv.get_template("staging.sql.j2")
    return tmpl.render(
        contract_path=str(model.contract_path).replace("\\", "/"),
        schema=model.schema,
        table=model.table,
        description=model.description.replace("'", "''"),
        source_table=model.source_table,
        columns=model.columns,
    )


def is_skipped(target: Path) -> bool:
    if not target.exists():
        return False
    head = target.read_text().splitlines()[:3]
    return any(SKIP_MARKER in line for line in head)


def discover_models(contracts_root: Path = CONTRACTS_DIR) -> list[StagingModel]:
    out: list[StagingModel] = []
    for p in sorted(contracts_root.rglob("*.yaml")):
        if "_staging/" not in str(p):
            continue
        model = parse_contract(p)
        if model is not None:
            out.append(model)
    return out


def generate_all(contracts_root: Path = CONTRACTS_DIR) -> list[tuple[Path, str]]:
    """Render every non-skipped staging model. Returns list of (target_path, rendered_sql)."""
    env = _template_env()
    results: list[tuple[Path, str]] = []
    for model in discover_models(contracts_root):
        if is_skipped(model.target_path):
            continue
        results.append((model.target_path, render(model, env)))
    return results


def check_drift(contracts_root: Path = CONTRACTS_DIR) -> list[Path]:
    """Return paths whose committed SQL differs from what the generator would emit."""
    drifted: list[Path] = []
    for target, rendered in generate_all(contracts_root):
        current = target.read_text() if target.exists() else ""
        if current != rendered:
            drifted.append(target)
    return drifted


def write_all(contracts_root: Path = CONTRACTS_DIR) -> list[Path]:
    written: list[Path] = []
    for target, rendered in generate_all(contracts_root):
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(rendered)
        written.append(target)
    return written
