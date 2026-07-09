Status: recorded
Created: 2026-07-09
Updated: 2026-07-09
Relates-To: .10x/tickets/done/2026-07-09-fix-sqlmesh-prod-restate-with-new-models.md

# Evidence: SQLMesh prod restatement with new models

## What was observed

After adding the Birding Trip Copilot SQLMesh models, `task verify` failed on an existing `data/sqlmesh_state.duckdb` prod environment even though all source ingest jobs and SQLMesh tests succeeded.

Failure:

```text
Error: Cannot restate model '"databox"."birding_agent"."recent_observation_evidence"'. Model does not exist.
```

The script `scripts/sqlmesh_plan_prod.sh` detected an existing prod environment and immediately ran:

```bash
sqlmesh plan prod --auto-apply --restate-model "*" --no-prompts
```

That is invalid when code introduces new models that do not yet exist in the existing prod environment.

## Procedure and results

1. Updated `scripts/sqlmesh_plan_prod.sh` so existing prod environments first apply metadata/snapshot changes without restatement, then run a second plan with `--restate-model "*"`.

2. Re-ran:

   ```bash
   task verify
   ```

   Result:

   ```text
   ✓ verify done — .logs/verify-20260708-203153.log
   ```

3. Inspected local DuckDB state after the passed verify:

   ```text
   raw_xeno_canto.recordings=5
   birding_agent.xeno_canto_media_evidence=5
   birding_agent.species_lookup=17896
   raw_xeno_canto._dlt_loads BASE TABLE
   raw_xeno_canto._dlt_version BASE TABLE
   main._dlt* relations=0
   ```

## What this supports

- `task verify` now handles an existing SQLMesh prod state when code adds new models.
- The fix remains compatible with the intended restatement behavior because the script still restates all models after new snapshots exist in prod.
- Live Xeno-canto smoke data flows through raw and planner SQL interfaces.

## Limits

- This was validated against the current existing local SQLMesh state, not a freshly deleted `data/sqlmesh_state.duckdb` in this turn.
- `task full-refresh` was not run separately; it uses the same `scripts/sqlmesh_plan_prod.sh` path.
