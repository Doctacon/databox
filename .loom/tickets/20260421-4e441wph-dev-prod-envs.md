---
id: ticket:dev-prod-envs
kind: ticket
status: ready
created_at: 2026-04-21T00:00:00Z
updated_at: 2026-04-21T00:00:00Z
scope:
  kind: workspace
links:
  initiative: initiative:scaffold-polish
  plan: plan:scaffold-polish
  phase: 2
depends_on: []
---

# Goal

Document and wire the SQLMesh `dev` → promote → `prod` virtual-environment workflow. Add `task plan:dev`, `task plan:prod`, and `task promote` targets. A forker evolving a model sees the right sequence: propose in dev, verify, promote to prod. Today nothing blocks a forker from running `sqlmesh plan prod` directly on an untested change.

# Why

SQLMesh's virtual environments are one of its strongest features. The scaffold barely uses them — `CLAUDE.md` mentions `sqlmesh plan --auto-apply prod` as the happy path, which discards the separation. A forker who reads this thinks there is only one environment.

The right workflow for any serious use of the scaffold is:

1. `sqlmesh plan dev --skip-tests=false` — propose change in `dev` virtual env
2. Verify: Soda contracts run against dev, sample queries look right
3. `sqlmesh plan prod --from dev` (or `sqlmesh plan prod` which auto-picks up dev changes) — promote what dev validated
4. Both envs live in the same DuckDB file; virtual envs are metadata

That flow needs documenting, task targets, and an integration with the schema-contract gate (the gate already runs against dev; make that explicit).

# In Scope

- `docs/environments.md` explaining:
  - What a SQLMesh virtual environment is (brief, link out to SQLMesh docs)
  - The three-step dev → verify → prod loop
  - How Soda contracts run per environment (they follow the virtual-env table)
  - Per-backend considerations (local DuckDB vs MotherDuck — both support virtual envs cleanly)
- Taskfile targets:
  - `task plan:dev` — runs `sqlmesh plan dev` with interactive prompts
  - `task plan:prod` — runs `sqlmesh plan prod`; fails fast if there are model changes not already in dev
  - `task promote` — shorthand for `task plan:prod` with `--auto-apply` when the only delta is dev→prod promotion
  - `task verify:dev` — runs Soda contracts against the `dev` schema suffix
- Update CI `schema-contract-gate` job to make the dev-plan target explicit (it already uses `plan dev`; add a doc comment)
- Update `CLAUDE.md` memories block with the new canonical flow (remove the `--auto-apply prod` shortcut as default, mention it as an escape-hatch)
- Update `README.md` Quickstart to point at `task plan:dev` for the first real model edit a forker will do

# Out of Scope

- Multi-environment gating on the schema-contract gate beyond dev (dev is enough — prod plans from dev are non-breaking by construction if dev was verified)
- A `staging` env between dev and prod — probably overkill for a single-operator scaffold; leave as a note in `docs/environments.md`
- Automating the promotion step (no — a human should confirm prod promotions)

# Acceptance Criteria

- `docs/environments.md` published to the docs site, linked from README
- `task plan:dev` and `task plan:prod` run end-to-end on a fresh checkout
- `task verify:dev` runs Soda contracts against the dev-schema tables (e.g. `ebird__dev.fct_daily_bird_observations` depending on SQLMesh's schema-suffix convention)
- `task promote` refuses to run if there are unpromoted model changes that were never planned against dev
- Flagship mart successfully flows through the full dev → verify → prod loop in CI on a test branch
- `CLAUDE.md` memories updated

# Approach Notes

- SQLMesh auto-creates environment schemas with `__<env>` suffix on DuckDB; document this pattern because it is load-bearing for verification queries
- MotherDuck handles virtual envs identically — no special-casing needed
- The `sqlmesh run` command can take an environment arg; prefer that over scheduling against prod only
- For Soda contract verification against dev: Soda can take a dataset prefix / suffix override — wire that through `Settings` so the contracts don't need to be duplicated

# Evidence Expectations

- A PR that edits a mart, runs `task plan:dev`, `task verify:dev`, and `task plan:prod` — linked in the ticket close-out
- `docs/environments.md` rendered in deployed docs site
- CI run showing the gate correctly uses dev-plan semantics
