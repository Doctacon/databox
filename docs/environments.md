# SQLMesh environments

Databox uses SQLMesh virtual environments to separate **proposed** changes
from **accepted** production state. One DuckDB file (or one MotherDuck
account) holds both — environments are metadata, not separate databases.

## The loop

```
┌────────────┐    plan dev     ┌────────────┐  verify  ┌─────────────┐  plan prod  ┌────────────┐
│ model edit ├────────────────▶│    dev     ├─────────▶│ dev Soda OK ├────────────▶│    prod    │
└────────────┘                 └────────────┘          └─────────────┘             └────────────┘
```

1. Edit a model in `transforms/main/models/`.
2. `task plan:dev` — SQLMesh materializes the change into the `dev` virtual
   env. Schemas get `__dev` suffix: `ebird.fct_daily_bird_observations`
   becomes `ebird__dev.fct_daily_bird_observations`.
3. `task verify:dev` — Soda contracts run against the `__dev` schemas.
   Sample queries against `ebird__dev.*` confirm the change looks right.
4. `task plan:prod` — SQLMesh promotes the dev changes to `prod`. Because
   the tables already exist (they were materialized for dev), promotion is
   a metadata-only switch — near-instant, no recompute.

## Why this matters

Without virtual envs, every model edit directly mutates prod. A broken
change is only caught after downstream consumers see it. With the loop:

- dev is the quarantine. Break it freely.
- Soda contracts can fail on dev without blocking prod.
- Promotion is cheap — no recompute on the prod side.
- Rollback is a `sqlmesh plan prod --restore-from <previous-plan-id>` away.

## Task targets

| Task | What it runs |
|---|---|
| `task plan:dev` | `sqlmesh plan dev` — interactive, prompts for model changes |
| `task verify:dev` | `scripts/verify_dev.py` — runs every Soda contract against the `__dev` schemas |
| `task plan:prod` | `sqlmesh plan prod` — interactive; fails if prod is ahead of dev |
| `task promote` | `sqlmesh plan prod --auto-apply` — shorthand when the only delta is a verified dev→prod promotion |

All four target `transforms/main/`. They inherit the `DATABOX_BACKEND`
setting, so `task plan:dev` works identically on local DuckDB and
MotherDuck.

## Per-backend notes

**Local DuckDB.** Virtual envs live in the same file. `__dev` schemas
share buffer pool with `prod` schemas — dev queries are as fast as prod.

**MotherDuck.** Same story. Virtual envs are a SQLMesh construct, not a
DuckDB feature; the implementation is identical across backends. Cost
implication: dev materializations do consume MotherDuck storage until
`sqlmesh janitor` runs (default: 7-day TTL on dev snapshots).

## Soda contracts and schema suffixes

Every Soda contract under `soda/contracts/` hard-codes a dataset path like
`databox/ebird/fct_daily_bird_observations`. `scripts/verify_dev.py`
rewrites that to `databox/ebird__dev/fct_daily_bird_observations` in
memory before handing the YAML to Soda. The committed contract files are
never edited.

If you add a new source, its contracts automatically pick up the rewrite —
the script walks every file under `soda/contracts/` and applies a regex.

## Schema-contract gate vs SQLMesh envs

The schema-contract gate (`scripts/schema_gate.py`) operates on Soda
contract **files** in git — it does not run SQLMesh. It catches breaking
column changes before `plan dev` ever runs. The two checks are
complementary:

- **schema-contract gate** — did someone change a contract in a way that
  would break downstream consumers? (static, PR-time)
- **`task verify:dev`** — does the dev materialization satisfy every
  contract check? (runtime, post-plan)

## Staging environment?

A `staging` env between `dev` and `prod` would make sense for a team with
multiple developers or a formal release cadence. For a single-operator
scaffold, it adds friction without payoff. The dev → verify → prod loop
is enough.

## Escape hatches

`sqlmesh plan --auto-apply prod` from the `transforms/main/` directory
still works and remains useful for one-off backfills or first-time
setup. Treat it as the exception, not the default.
