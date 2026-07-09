# SQLMesh environments

Databox uses SQLMesh virtual environments to separate **proposed** changes
from **accepted** production state. The single local
`data/databox.duckdb` file holds both; environments are metadata, not separate
databases.

## The loop

```
┌────────────┐    plan dev     ┌────────────┐  verify  ┌─────────────┐  plan prod  ┌────────────┐
│ model edit ├────────────────▶│    dev     ├─────────▶│ dev Soda OK ├────────────▶│    prod    │
└────────────┘                 └────────────┘          └─────────────┘             └────────────┘
```

1. Edit a model in `transforms/main/models/`.
2. `task plan:dev` — SQLMesh materializes the change into the `dev` virtual
   environment. Schemas get a `__dev` suffix.
3. `task verify:dev` — Soda contracts run against the `__dev` schemas.
4. `task plan:prod` — SQLMesh promotes verified changes to `prod`.

## Why this matters

Without virtual environments, every model edit directly mutates prod. With the
loop, dev acts as quarantine, contracts can fail without affecting prod, and
promotion can reuse already-materialized snapshots.

## Task targets

| Task | What it runs |
|---|---|
| `task plan:dev` | `sqlmesh plan dev` — interactive model-change plan |
| `task verify:dev` | `scripts/verify_dev.py` — Soda contracts against `__dev` schemas |
| `task plan:prod` | `sqlmesh plan prod` — interactive production plan |
| `task promote` | `sqlmesh plan prod --auto-apply` — verified dev-to-prod promotion |

All four target `transforms/main/` and use the single local SQLMesh gateway.
Virtual environments share the local DuckDB file and buffer pool.

## Soda contracts and schema suffixes

Every Soda contract under `soda/contracts/` names a production dataset.
`scripts/verify_dev.py` rewrites that name to the corresponding `__dev` schema
in memory before passing YAML to Soda. Committed contract files are unchanged.

## Schema-contract gate vs SQLMesh environments

The schema-contract gate (`scripts/schema_gate.py`) checks contract files in
git without running SQLMesh. It catches incompatible contract changes before a
dev plan. `task verify:dev` separately confirms that dev materializations
satisfy those contracts.

## Staging environment?

A staging environment would add friction without payoff for this
single-operator local platform. The dev → verify → prod loop is sufficient.

## Escape hatch

`sqlmesh plan --auto-apply prod` from `transforms/main/` remains available for
one-off backfills or first-time setup. Treat it as the exception, not the
default.
