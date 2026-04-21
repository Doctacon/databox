---
id: ticket:staging-model-codegen
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

Generate trivial-rename staging models from Soda contracts instead of hand-writing them. The 7 existing `stg_*.sql` files that are effectively `SELECT old_col AS new_col` from raw catalogs become a generated artifact. Preserve a hand-written escape hatch for staging models that genuinely need transformation logic.

# Why

Of the 7 staging models today, most are pure column renames and nullability declarations — no joins, no filters, no computed fields. Every one is ~20 lines of SQL that says the same thing as the corresponding Soda contract's column list. At 20 sources (≥40 staging models) this hand-writing becomes the dominant chore of adding a source.

Soda contracts already encode source → target column mappings and types. Generate the staging SQL from them. Non-trivial staging (e.g. `int_observations_by_h3_day`) stays in intermediate models where it belongs.

# In Scope

- `scripts/generate_staging.py`: walks `soda/contracts/*_staging/*.yml`, emits `transforms/main/models/<source>/staging/stg_*.sql`
- Codegen output includes:
  - `MODEL (...)` block with `kind FULL`, `grain` from the contract's unique-key hint, `columns` derived from the contract column list
  - `SELECT` clause mapping raw-catalog columns to staging names, with explicit type casts from contract
  - `FROM <raw_catalog>.<raw_table>` — the raw-catalog name comes from a `source_table:` front-matter key in the Soda contract (add if missing)
- Header comment in generated SQL: `-- Generated from soda/contracts/<source>_staging/<model>.yml by scripts/generate_staging.py`
- Taskfile target `task staging:generate`
- Pre-commit hook or CI step that fails if the committed `stg_*.sql` doesn't match the regenerated output
- Escape hatch: a `# staging-codegen: skip` comment at the top of a `stg_*.sql` file opts it out of regeneration (covered by a separate hand-written case)
- Regenerate all 7 existing staging models; commit generated output and mark as generated in `.gitattributes`

# Out of Scope

- Generating intermediate or mart SQL (only staging)
- Generating Soda contracts from SQLMesh models (reverse direction — explicitly not this ticket)
- Changing the schema-contract gate (ticket:schema-gate-library-refactor)
- Generating dlt source code from API specs

# Acceptance Criteria

- `scripts/generate_staging.py` exists and runs in ≤5s on the current corpus
- `task staging:generate` rewrites all 7 existing `stg_*.sql` to byte-equivalent output given the current Soda contracts
- CI fails if someone hand-edits a generated `stg_*.sql` without adding `# staging-codegen: skip`
- `docs/staging.md` documents how the codegen works, the escape hatch, and when to use it
- Full-refresh on a fresh checkout still succeeds with the generated SQL (SQLMesh plan + Soda contract verify + Dagster materialize, end to end)
- Adding a new column to a Soda staging contract → regen → plan shows the additive change as expected

# Approach Notes

- Use Jinja2 for the template; one template file under `scripts/templates/staging.sql.j2`
- Soda contracts today may not carry `source_table:` — add it as a top-level key during this ticket; update existing contracts
- For the column-map step, prefer explicit CAST over SELECT * to keep the generated SQL order-stable and diff-friendly
- Keep the generated file formatted with `sqlfluff` / `sqlmesh format` so the regen check isn't tripped by whitespace

# Evidence Expectations

- Diff showing 7 hand-written `stg_*.sql` replaced by generated files with header comment
- CI check demonstrating drift detection works (PR that hand-edits a generated file fails)
- Full-refresh run on both backends (local + motherduck) green

# Close Notes

Verified on main 2026-04-21: `scripts/generate_staging.py` present, `task staging:generate` target wired, `docs/staging.md` published. Deliverable landed during earlier scaffold-polish work; ledger reconciled during status audit.
