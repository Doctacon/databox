---
id: ticket:schema-contract-ci
kind: ticket
status: complete_pending_acceptance
created_at: 2026-04-20T00:00:00Z
updated_at: 2026-04-20T23:25:00Z
scope:
  kind: workspace
links:
  initiative: initiative:staff-portfolio-readiness
  plan: plan:staff-portfolio-readiness
  phase: 2
depends_on:
  - ticket:ci-github-actions
---

# Goal

Turn SQLMesh plan output and Soda contracts into a hard gate: any breaking schema change (column drop, type narrowing, renamed primary key) fails CI unless explicitly acknowledged in the PR body via a recognized token.

# Why

This is the single most credible data-governance signal a recruiter can see. "Breaking changes require explicit opt-in" demonstrates lived contract discipline, not just the existence of contracts. Today, a careless SQL edit could silently drop a downstream column.

# In Scope

- CI job `schema-contract-gate` that:
  - runs `sqlmesh plan dev --no-auto-apply --skip-tests` and parses the plan output
  - classifies model changes as additive vs breaking
  - runs `soda contract verify` in schema-only mode to catch Soda-level breakage
  - succeeds on additive changes; fails on breaking changes
- Escape hatch: PR body containing `accept-breaking-change: <model-name>` lets the change through for that specific model, logged as an annotation
- A short doc `docs/contracts.md` explaining the gate, the escape hatch, and when to use it
- Classifier lives in `scripts/schema_gate.py` with its own unit tests

# Out of Scope

- Fine-grained impact analysis across downstream marts (SQLMesh already shows this in plan output; don't re-implement)
- Rewriting Soda contracts — use as-is
- Blocking on row-count regressions or data-quality changes (that is the Soda scan job, not this gate)
- Multi-environment gating (single `dev` plan is enough)

# Acceptance Criteria

- CI has a `schema-contract-gate` job, required on `main`
- A test branch dropping a column from `ebird.fct_daily_bird_observations` fails the gate with a readable error
- The same branch with `accept-breaking-change: ebird.fct_daily_bird_observations` in the PR body passes the gate
- Classifier has unit tests covering: add column, drop column, rename column, change type, add model, remove model
- `docs/contracts.md` is linked from the root README

# Approach Notes

- SQLMesh plan JSON output is the authoritative source — parse it, don't diff raw SQL
- "Breaking" definition: column removed, type changed in a non-widening way, primary-key/grain changed, model removed
- The PR-body token check uses the GitHub event payload; locally-run `schema-contract-gate` can be bypassed with `ACCEPT_BREAKING_CHANGE=model` env var
- Keep the classifier narrow — if uncertain, fail closed

# Evidence Expectations

- Three CI runs linked: additive (green), breaking (red), breaking with opt-in (green with annotation)
- Link to `docs/contracts.md`
