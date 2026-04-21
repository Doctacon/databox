---
id: ticket:collapse-packages
kind: ticket
status: closed
created_at: 2026-04-21T00:00:00Z
updated_at: 2026-04-21T19:30:00Z
scope:
  kind: workspace
links:
  initiative: initiative:scaffold-polish
  plan: plan:scaffold-polish
  phase: 1
depends_on: []
---

# Goal

Fold the three cross-cutting uv packages (`databox-config`, `databox-quality`, `databox-orchestration`) into a single `databox` package with internal submodules. Keep `databox-sources` separate because its registry pattern genuinely scales with source count.

# Why

Today: 4 packages, 35 Python files, 4 per-package `pyproject.toml` files (14–23 lines each). The split is organizational overhead, not architectural boundary — the three shared packages import each other freely and always version-lock together. A fresh reader has to chase imports across four package roots to understand how a single Dagster asset materialises. At 20 sources this multiplies into an archaeology problem.

Collapsing into `databox/{config,quality,orchestration}/` with `databox-sources` remaining as the registry-bearing package gives one import root for everything shared, preserves the genuinely pluggable boundary (sources), and removes four `pyproject.toml` files' worth of config drift.

# In Scope

- Create a new top-level `packages/databox/` package
- Move contents:
  - `packages/databox-config/databox_config/*` → `packages/databox/databox/config/*`
  - `packages/databox-quality/databox_quality/*` → `packages/databox/databox/quality/*`
  - `packages/databox-orchestration/databox_orchestration/*` → `packages/databox/databox/orchestration/*`
- Rewrite imports everywhere in the repo:
  - `from databox_config` → `from databox.config`
  - `from databox_quality` → `from databox.quality`
  - `from databox_orchestration` → `from databox.orchestration`
- Collapse three `pyproject.toml` files into one at `packages/databox/pyproject.toml`; merge dependency lists; dedupe
- Update root `pyproject.toml` workspace members list
- Delete the three old package directories after the move + import rewrite land green
- Update Dagster module entry (`databox_orchestration.definitions:defs` → `databox.orchestration.definitions:defs`) in `pyproject.toml` and any Taskfile / workflow references
- Update `CLAUDE.md` project structure block

# Out of Scope

- Touching `databox-sources` — it stays separate
- Splitting `definitions.py` per domain — that is ticket:definitions-split
- Unifying config objects across surfaces — that is ticket:unify-config-surface
- Renaming the `databox` CLI entry point (there isn't one; ADR-0005 retired it)

# Acceptance Criteria

- `packages/databox/` exists with `config/`, `quality/`, `orchestration/` submodules
- `packages/databox-config/`, `packages/databox-quality/`, `packages/databox-orchestration/` directories are removed from the tree
- `rg -n '^from databox_(config|quality|orchestration)'` returns no matches in any committed file
- `uv sync` works from a clean lock
- `uv run mypy packages/` passes
- `uv run pytest` — full existing suite is green (30 tests today)
- `uv run dagster definitions list -m databox.orchestration.definitions` lists every current asset and asset check
- Taskfile targets that invoke Dagster still work (`task dagster:dev`, `task dagster:materialize`)
- SQLMesh + Soda still run (`uv run sqlmesh plan --no-prompts dev --skip-tests`, `task quality:report`)
- MkDocs strict build still clean

# Approach Notes

- One mechanical PR, not trickled — trying to land this piecewise would leave the codebase in a broken import-graph state between PRs
- Use `sed -i '' 's/from databox_config/from databox.config/g'` (or `ripgrep --files-with-matches` + `sed`) for the bulk rewrite. Hand-check diff before commit
- Preserve git history of moved files with `git mv`
- Merge `pyproject.toml` deps conservatively — union, not intersection; dedupe at the end
- Keep the per-submodule `__init__.py` exports minimal (re-export only what is actually imported externally)

# Evidence Expectations

- Single PR link
- `git log --stat` showing file moves, not copy-then-delete
- CI green on the PR
- Post-merge: `find packages -name pyproject.toml` shows exactly two (`databox/`, `databox-sources/`)

# Close Notes

Verified on main 2026-04-21: `packages/` contains only `databox/` + `databox-sources/`. No `databox-config/`, `databox-quality/`, `databox-orchestration/` top-level packages. Deliverable landed during earlier scaffold-polish work; ledger reconciled during status audit.
