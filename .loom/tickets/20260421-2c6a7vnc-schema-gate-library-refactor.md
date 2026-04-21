---
id: ticket:schema-gate-library-refactor
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

Rewrite `scripts/schema_gate.py` as a thin wrapper around SQLMesh's plan-diff JSON and Soda Core's contract-diff primitives. Target ≤80 lines of Python. All existing acceptance criteria from ticket:schema-contract-ci continue to hold.

# Why

The current 288-line gate hand-rolls column and type classification logic on top of SQLMesh plan output. That reimplements capabilities that both SQLMesh (via its `ContextDiff` / plan JSON) and Soda Core (via `ContractVerificationResult` + contract YAML AST) already expose. Hand-rolled diff code is a bug farm — it has to re-learn subtleties like nullable-narrowing, type-widening, and dialect-specific type aliases every time someone touches it.

A 288-line script is also a load-bearing thing that nobody wants to touch. Shrinking it to ~80 lines makes the gate inspectable, the maintenance cost negligible, and the forker's mental model ("the gate classifies SQLMesh diffs using SQLMesh's own primitives") obvious.

# In Scope

- Inventory the current script: what decisions does it make, on what inputs
- For each decision, find the equivalent primitive:
  - SQLMesh plan JSON `changes` section (added / removed / modified models, column deltas)
  - SQLMesh `ContextDiff` snapshot — richer type info than the JSON output
  - Soda Core `ContractVerificationSession` for contract-side schema checks
- Rewrite `scripts/schema_gate.py` to call those primitives and classify additive vs breaking
- Preserve the PR-body escape-hatch token behaviour (`accept-breaking-change: <model>`)
- Preserve the `ACCEPT_BREAKING_CHANGE` env var for local runs
- Keep the classifier output format (what CI reads) identical, so the GitHub Action step doesn't need to change
- Update unit tests to cover: add column, drop column, rename, type change (widening vs narrowing), add model, remove model, PK/grain change

# Out of Scope

- Adding new classifier categories (row-count deltas, data checks) — that is the Soda scan job, not this gate
- Multi-environment gating — single `dev` plan still enough
- Rewriting the CI workflow YAML

# Acceptance Criteria

- `wc -l scripts/schema_gate.py` ≤ 80
- The gate produces identical verdicts on a synthetic set of test PRs (add col / drop col / rename / type widen / type narrow / add model / remove model / with escape-hatch / without)
- All existing unit tests pass; any net-new edge cases get tests
- CI `schema-contract-gate` job stays green on a no-op PR and fails correctly on a drop-column PR
- Escape hatch still works: `accept-breaking-change: ebird.fct_daily_bird_observations` in PR body passes the gate with the override annotation
- `docs/contracts.md` updated to reflect the underlying primitives (short paragraph — forker should know what powers the gate)

# Approach Notes

- SQLMesh's `sqlmesh.core.plan.Plan.context_diff` has `modified_snapshots` with full schema diff — preferable over parsing the human-readable plan output
- Some type-widening rules are dialect-specific (DuckDB `INTEGER → BIGINT` = widening, `BIGINT → INTEGER` = narrowing). Delegate to SQLMesh's dialect-aware comparison rather than re-encoding
- Soda contract diff: `soda_core.contracts.contract.Contract.diff(other)` (or whichever current API surface) provides YAML-level drift detection for contracts that changed independently of model SQL
- Fail closed on unknown cases — if the primitive returns a category the script doesn't recognise, treat as breaking

# Evidence Expectations

- Before/after line count (288 → ≤80)
- Three CI runs linked: additive (green), breaking (red), breaking + escape-hatch (green)
- Unit-test count delta and which edge cases are covered

# Close Notes

Verified on main 2026-04-21: `scripts/schema_gate.py` is 54 lines (target ≤80, met). CI `schema-contract-gate` job active. Deliverable landed during earlier scaffold-polish work; ledger reconciled during status audit.
