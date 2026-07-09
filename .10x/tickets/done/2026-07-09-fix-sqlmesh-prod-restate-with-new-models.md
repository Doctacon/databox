Status: done
Created: 2026-07-09
Updated: 2026-07-09

# Fix SQLMesh prod restatement when new models are added

## Scope

Repair `scripts/sqlmesh_plan_prod.sh` so `task verify` / `task full-refresh` can handle an existing SQLMesh prod environment when the codebase adds new SQLMesh models.

In scope:

- Adjust the SQLMesh prod planning script to avoid invalid `--restate-model "*"` against models that are not yet present in prod.
- Preserve the intended behavior that refreshed raw data restates existing prod models.
- Validate with `task verify` after the Xeno-canto key is available.

Out of scope:

- Changing SQLMesh model semantics.
- Changing source ingestion behavior.
- Changing the Birding Trip Copilot product scope.

## Acceptance criteria

- `task verify` can run successfully with the current existing `data/sqlmesh_state.duckdb` after adding the new `birding_agent` models: satisfied.
- The fix remains compatible with fresh SQLMesh state bootstrapping: satisfied by preserving the existing no-prod branch unchanged.
- The result is recorded in evidence: `.10x/evidence/2026-07-09-sqlmesh-prod-restate-new-models.md`.

## Progress and notes

- 2026-07-09: `task verify` failed after successful source ingests and SQLMesh tests with: `Cannot restate model '"databox"."birding_agent"."recent_observation_evidence"'. Model does not exist.` This happened because existing prod state did not yet contain new `birding_agent` models, while the script tried to restate `*` immediately.
- 2026-07-09: Updated `scripts/sqlmesh_plan_prod.sh` to apply prod metadata/snapshot changes first, then restate `*` in a second plan when prod already exists.
- 2026-07-09: Re-ran `task verify`; it passed and wrote `.logs/verify-20260708-203153.log`.

## Evidence

- `.10x/evidence/2026-07-09-sqlmesh-prod-restate-new-models.md`

## Blockers

None.
