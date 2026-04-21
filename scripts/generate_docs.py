"""Generate the data-dictionary MkDocs site from SQLMesh + Soda metadata.

Walks the SQLMesh project at ``transforms/main`` via ``sqlmesh.Context`` and
the Soda contract tree at ``soda/contracts``. Emits one Markdown page per
model plus a global Mermaid lineage page under ``docs/dictionary/``.

The generator is side-effect-free and deterministic: sorted ordering
everywhere, idempotent re-writes, no network calls. Intended to run in
<30 seconds in CI and locally.

Usage:
    uv run python scripts/generate_docs.py
"""

from __future__ import annotations

import os
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml
from sqlmesh import Context

REPO_ROOT = Path(__file__).resolve().parents[1]
TRANSFORMS_PATH = REPO_ROOT / "transforms" / "main"
SODA_ROOT = REPO_ROOT / "soda" / "contracts"
OUT_ROOT = REPO_ROOT / "docs" / "dictionary"
REPO_BLOB_URL = "https://github.com/crlough/databox/blob/main"

SCHEMA_DESCRIPTIONS = {
    "analytics": "Cross-domain marts that join bird, weather, and streamflow signals.",
    "ebird": "eBird bird-observation domain — intermediate and mart models.",
    "ebird_staging": "eBird staging views — raw dlt loads with column renames only.",
    "noaa": "NOAA weather domain — intermediate and mart models.",
    "noaa_staging": "NOAA staging views — raw dlt loads with column renames only.",
    "usgs": "USGS streamflow domain — intermediate and mart models.",
    "usgs_staging": "USGS staging views — raw dlt loads with column renames only.",
}


@dataclass(frozen=True)
class SodaCheck:
    column: str
    kind: str
    detail: str


@dataclass
class SodaContract:
    dataset: str
    column_types: dict[str, str]
    column_checks: dict[str, list[SodaCheck]]
    table_checks: list[SodaCheck]
    path: Path


def load_soda_contracts() -> dict[str, SodaContract]:
    """Parse every Soda contract under soda/contracts/ keyed by model fqn."""
    contracts: dict[str, SodaContract] = {}
    for path in sorted(SODA_ROOT.rglob("*.yaml")):
        doc = yaml.safe_load(path.read_text())
        if not isinstance(doc, dict) or "dataset" not in doc:
            continue
        dataset = doc["dataset"]
        parts = dataset.split("/")
        if len(parts) != 3:
            continue
        _, schema, name = parts
        fqn = f'"databox"."{schema}"."{name}"'

        col_types: dict[str, str] = {}
        col_checks: dict[str, list[SodaCheck]] = {}
        for col in doc.get("columns") or []:
            cname = col.get("name")
            if not cname:
                continue
            col_types[cname] = col.get("data_type", "")
            checks: list[SodaCheck] = []
            for check in col.get("checks") or []:
                checks.extend(_flatten_check(check, cname))
            if checks:
                col_checks[cname] = checks

        table_checks: list[SodaCheck] = []
        for check in doc.get("checks") or []:
            table_checks.extend(_flatten_check(check, column="(table)"))

        contracts[fqn] = SodaContract(
            dataset=dataset,
            column_types=col_types,
            column_checks=col_checks,
            table_checks=table_checks,
            path=path.relative_to(REPO_ROOT),
        )
    return contracts


def _flatten_check(check: Any, column: str) -> list[SodaCheck]:
    if not isinstance(check, dict):
        return []
    out: list[SodaCheck] = []
    for kind, body in check.items():
        detail = _fmt_check_body(body)
        out.append(SodaCheck(column=column, kind=kind, detail=detail))
    return out


def _fmt_check_body(body: Any) -> str:
    if body is None:
        return ""
    if isinstance(body, dict):
        return ", ".join(f"{k}={v}" for k, v in body.items())
    return str(body)


def build_context() -> Context:
    os.environ.setdefault("DATABOX_GATEWAY", "local")
    return Context(paths=[str(TRANSFORMS_PATH)], gateway=os.environ["DATABOX_GATEWAY"])


def short_name(fqn: str) -> str:
    """Return ``schema.name`` from a fully-qualified ``"db"."schema"."name"``."""
    clean = fqn.replace('"', "")
    parts = clean.split(".")
    if len(parts) >= 2:
        return ".".join(parts[-2:])
    return clean


def page_path_for(fqn: str) -> Path:
    """docs/dictionary/<schema>/<name>.md — deterministic path per model."""
    short = short_name(fqn)
    schema, _, name = short.partition(".")
    return OUT_ROOT / schema / f"{name}.md"


def relative_model_link(from_fqn: str, to_fqn: str) -> str:
    """Relative markdown link from one model page to another."""
    src = page_path_for(from_fqn).parent
    dst = page_path_for(to_fqn)
    try:
        return os.path.relpath(dst, src)
    except ValueError:
        return str(dst)


def render_model_page(
    ctx: Context,
    fqn: str,
    contracts: dict[str, SodaContract],
) -> str:
    model = ctx.models[fqn]
    short = short_name(fqn)
    schema, _, name = short.partition(".")

    upstream = sorted(getattr(model, "depends_on", None) or set())
    downstream = sorted(
        d for d, m in ctx.models.items() if fqn in (getattr(m, "depends_on", None) or set())
    )

    contract = contracts.get(fqn)

    lines: list[str] = []
    lines.append(f"# {short}")
    lines.append("")
    desc = (getattr(model, "description", None) or "").strip()
    lines.append(desc if desc else "_No model-level description._")
    lines.append("")

    lines.append("## Overview")
    lines.append("")
    lines.append("| Field | Value |")
    lines.append("| --- | --- |")
    lines.append(f"| Schema | `{schema}` |")
    lines.append(f"| Name | `{name}` |")
    lines.append(f"| Kind | `{model.kind.name}` |")
    grains = getattr(model, "grains", None) or []
    if grains:
        grain_str = ", ".join(f"`{g.sql(dialect='duckdb')}`" for g in grains)
        lines.append(f"| Grain | {grain_str} |")
    if contract:
        url = f"{REPO_BLOB_URL}/{contract.path}"
        lines.append(f"| Soda contract | [`{contract.path}`]({url}) |")
    else:
        lines.append("| Soda contract | _none_ |")
    lines.append("")

    lines.append("## Columns")
    lines.append("")
    lines.append("| Column | Type | Checks | Notes |")
    lines.append("| --- | --- | --- | --- |")
    col_descriptions = getattr(model, "column_descriptions", None) or {}
    cols = getattr(model, "columns_to_types", None) or {}
    all_col_names = set(cols.keys())
    if contract:
        all_col_names.update(contract.column_types.keys())
    for col_name in sorted(all_col_names):
        sql_type = cols[col_name].sql(dialect="duckdb") if col_name in cols else "UNKNOWN"
        soda_type = contract.column_types.get(col_name, "") if contract else ""
        if sql_type == "UNKNOWN" and soda_type:
            dtype = soda_type
        else:
            dtype = sql_type
        checks = []
        if contract:
            for c in contract.column_checks.get(col_name, []):
                checks.append(f"{c.kind}" + (f" ({c.detail})" if c.detail else ""))
        note = (col_descriptions.get(col_name) or "").strip().replace("|", "\\|")
        lines.append(f"| `{col_name}` | `{dtype}` | {', '.join(checks) or '—'} | {note or '—'} |")
    if contract and contract.table_checks:
        lines.append("")
        lines.append("## Table-level checks")
        lines.append("")
        for c in contract.table_checks:
            suffix = f" — {c.detail}" if c.detail else ""
            lines.append(f"- **{c.kind}**{suffix}")
    lines.append("")

    lines.append("## Lineage")
    lines.append("")
    if upstream:
        lines.append("**Upstream**")
        lines.append("")
        for u in upstream:
            if u in ctx.models:
                lines.append(f"- [`{short_name(u)}`]({relative_model_link(fqn, u)})")
            else:
                lines.append(f"- `{short_name(u)}` (external)")
        lines.append("")
    if downstream:
        lines.append("**Downstream**")
        lines.append("")
        for d in downstream:
            if d in ctx.models:
                lines.append(f"- [`{short_name(d)}`]({relative_model_link(fqn, d)})")
        lines.append("")
    if not upstream and not downstream:
        lines.append("_No declared dependencies._")
        lines.append("")

    lines.append("## Example query")
    lines.append("")
    lines.append("```sql")
    lines.append(f"SELECT * FROM {schema}.{name} LIMIT 100;")
    lines.append("```")
    lines.append("")
    return "\n".join(lines)


def render_lineage_page(ctx: Context) -> str:
    """One Mermaid graph of all internal models; nodes link to their pages."""
    models = sorted(ctx.models.keys())
    node_ids: dict[str, str] = {}
    for i, fqn in enumerate(models):
        node_ids[fqn] = f"n{i}"

    lines: list[str] = []
    lines.append("# Lineage")
    lines.append("")
    lines.append(
        "Full model dependency graph across all SQLMesh projects. "
        "Each node links to its data-dictionary page."
    )
    lines.append("")
    lines.append("```mermaid")
    lines.append("graph LR")
    for fqn in models:
        lines.append(f'    {node_ids[fqn]}["{short_name(fqn)}"]')
    for fqn in models:
        direct_deps = getattr(ctx.models[fqn], "depends_on", None) or set()
        for up in sorted(direct_deps):
            if up in node_ids:
                lines.append(f"    {node_ids[up]} --> {node_ids[fqn]}")
    lines.append("")
    for fqn in models:
        short = short_name(fqn)
        schema, _, name = short.partition(".")
        href = f"{schema}/{name}.md"
        lines.append(f'    click {node_ids[fqn]} "{href}"')
    lines.append("```")
    lines.append("")
    return "\n".join(lines)


def render_index_page(ctx: Context, contracts: dict[str, SodaContract]) -> str:
    by_schema: dict[str, list[str]] = {}
    for fqn in ctx.models:
        short = short_name(fqn)
        schema, _, _ = short.partition(".")
        by_schema.setdefault(schema, []).append(fqn)

    lines: list[str] = []
    lines.append("# Data dictionary")
    lines.append("")
    lines.append(
        "Auto-generated from SQLMesh model metadata and Soda contracts. "
        "Regenerate with `uv run python scripts/generate_docs.py`."
    )
    lines.append("")
    lines.append(f"- **Models:** {len(ctx.models)}")
    lines.append(f"- **Soda contracts:** {len(contracts)}")
    lines.append("- **Lineage:** [browse the dependency graph](lineage.md)")
    lines.append("")

    for schema in sorted(by_schema):
        desc = SCHEMA_DESCRIPTIONS.get(schema, "")
        lines.append(f"## `{schema}`")
        lines.append("")
        if desc:
            lines.append(desc)
            lines.append("")
        lines.append("| Model | Contract | Description |")
        lines.append("| --- | --- | --- |")
        for fqn in sorted(by_schema[schema]):
            short = short_name(fqn)
            _, _, name = short.partition(".")
            model = ctx.models[fqn]
            model_desc = (getattr(model, "description", None) or "").strip()
            first_sentence = model_desc.split(". ")[0] if model_desc else "—"
            has_contract = "yes" if fqn in contracts else "—"
            link = f"{schema}/{name}.md"
            lines.append(f"| [`{short}`]({link}) | {has_contract} | {first_sentence} |")
        lines.append("")
    return "\n".join(lines)


def write_file(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not content.endswith("\n"):
        content = content + "\n"
    path.write_text(content)


def main() -> int:
    if OUT_ROOT.exists():
        shutil.rmtree(OUT_ROOT)
    OUT_ROOT.mkdir(parents=True)

    ctx = build_context()
    contracts = load_soda_contracts()

    n_pages = 0
    for fqn in sorted(ctx.models):
        page = render_model_page(ctx, fqn, contracts)
        write_file(page_path_for(fqn), page)
        n_pages += 1

    write_file(OUT_ROOT / "lineage.md", render_lineage_page(ctx))
    write_file(OUT_ROOT / "index.md", render_index_page(ctx, contracts))

    print(
        f"Generated {n_pages} model pages + lineage + index "
        f"under {OUT_ROOT.relative_to(REPO_ROOT)}/"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
