---
id: ticket:source-layout-convention
kind: ticket
status: ready
created_at: 2026-04-21T00:00:00Z
updated_at: 2026-04-21T00:00:00Z
scope:
  kind: workspace
links:
  initiative: initiative:scaffold-polish
  plan: plan:scaffold-polish
  phase: 1
depends_on:
  - ticket:collapse-packages
  - ticket:definitions-split
  - ticket:unify-config-surface
  - ticket:staging-model-codegen
---

# Goal

Codify the per-source directory convention that the simplified Phase 1 shape settles on, and enforce it via `scripts/check_source_layout.py` in CI. Any new source that lands without the full layout fails CI with a clear error.

# Why

Phase 1's collapse-packages, definitions-split, unify-config, and staging-codegen tickets converge on a tidy per-source shape. Without enforcement, entropy returns — someone adds a source with a Dagster domain file but no Soda contract, or with staging SQL but no raw-catalog declaration. At 20 sources the drift becomes invisible until something breaks in production.

A lint script gives the convention teeth. It also doubles as the spec for `ticket:new-source-generator` — whatever the linter requires is what the generator creates.

# In Scope

- `scripts/check_source_layout.py`:
  - walks `packages/databox-sources/databox_sources/*/` for ingest modules
  - for each source, asserts presence of:
    - `packages/databox-sources/databox_sources/<source>/source.py` (dlt source)
    - `packages/databox-sources/databox_sources/<source>/config.yaml`
    - `transforms/main/models/<source>/staging/` with at least one `stg_*.sql`
    - `transforms/main/models/<source>/marts/` with at least one `fct_*.sql` or `dim_*.sql`
    - `soda/contracts/<source>_staging/` with at least one contract
    - `soda/contracts/<source>/` with at least one contract
    - `packages/databox/databox/orchestration/domains/<source>.py`
  - exits non-zero with a clear `missing: <path>` list if any component is absent
  - supports an allowlist of `# scaffold-lint: skip=<reason>` markers for experimental / in-flight sources
- `docs/source-layout.md` documenting the convention
- CI wiring: new required job `source-layout-lint` on every PR
- Taskfile target `task check:layout`
- Update `CLAUDE.md` "Adding a New Data Source" section to reference the convention

# Out of Scope

- Enforcing naming conventions inside each file (model names, column names) — that is a separate concern
- Enforcing content rules (e.g. "every mart must have a primary-key column") — Soda contracts already handle this via their own validation
- Generating the layout (that is ticket:new-source-generator)

# Acceptance Criteria

- `scripts/check_source_layout.py` exists and runs clean on the current 3 sources
- Deleting any required file from a source makes the lint fail with a useful error message
- The `# scaffold-lint: skip=experimental` marker allows an incomplete source through
- CI has a `source-layout-lint` job that runs on every PR
- `docs/source-layout.md` is published to the docs site and linked from `README.md`
- `CLAUDE.md` "Adding a New Data Source" points at the doc + the lint

# Approach Notes

- Prefer `pathlib.Path.glob` + explicit checks over clever schema-driven validation; a 50-line script is better than a dependency on jsonschema
- Output is line-oriented: one missing path per line, plus a summary line at the end — diffable in CI logs
- The allowlist marker lives at the top of `source.py` (the dlt module is the anchor file, always exists)
- Script should pass `--json` for machine-readable output that the generator's test harness can consume

# Evidence Expectations

- Lint output on the current tree (clean)
- Lint output on a deliberately-broken branch (drops a Soda contract — clear error message)
- `docs/source-layout.md` rendered in deployed docs site
