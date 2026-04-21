# Incident runbook

Four scenarios a solo operator is most likely to hit on this stack.
Each section follows the same shape: **symptoms → diagnosis →
recovery → validation → rollback**. Cross-references link to the
deeper docs where relevant.

Pair with [docs/environments.md](environments.md) (dev → prod loop)
and [docs/freshness.md](freshness.md) (post-recovery SLA resume).

---

## 1. Blown DuckDB file (local backend)

### Symptoms

- `duckdb.IOException: Could not read from file` on any Dagster run.
- `dagster asset materialize` exits non-zero immediately; traceback
  points at `databox.config.settings.database_path`.
- `sqlmesh plan` fails with `Catalog Error: Table ... does not exist`
  even though the model code is unchanged.
- `df -h` near 100% on the volume holding `data/`.

### Diagnosis

```bash
# File readable at all?
uv run python -c "import duckdb; duckdb.connect('data/databox.duckdb', read_only=True).execute('SELECT 1').fetchall()"

# Disk space?
df -h data/

# SQLMesh state vs physical tables agree?
cd transforms/main && uv run sqlmesh audit
```

If the connect fails, the file is corrupt. If audit reports
"table missing" but the file opens, SQLMesh state desynced.

### Recovery

**Path A — rebuild from raw dlt state (preferred; most scenarios).**

```bash
# 1. Back up the broken file for forensics.
mv data/databox.duckdb data/databox.duckdb.broken

# 2. Drop SQLMesh state so it does not look for phantom physical tables.
rm -rf transforms/main/.sqlmesh transforms/main/state_sync.db

# 3. Rehydrate raw catalogs + rebuild every mart.
task full-refresh
```

dlt reloads `raw_ebird` / `raw_noaa` / `raw_usgs` from the APIs
(idempotent — primary keys are declared). SQLMesh then rebuilds
every staging view and mart against the fresh raw data.

**Path B — restore from a file backup (if you keep one).**

```bash
mv data/databox.duckdb data/databox.duckdb.broken
cp /path/to/backup/databox.duckdb data/databox.duckdb
cd transforms/main && uv run sqlmesh plan prod --auto-apply
```

The `plan prod` call reconciles SQLMesh state against whatever
table versions are in the restored file.

### Validation

```bash
task verify                         # smoke full-refresh with DATABOX_SMOKE=1
task verify:dev                     # Soda contracts against __dev
cd transforms/main && uv run sqlmesh audit
```

All three must exit zero. Open the Dagster UI and confirm the
freshness checks for `fct_daily_bird_observations` and
`fct_daily_weather` read "ok".

### Rollback

If `full-refresh` itself fails:

```bash
mv data/databox.duckdb data/databox.duckdb.rebuild-failed
mv data/databox.duckdb.broken data/databox.duckdb
```

You are back where you started. Investigate the failure with
`uv run dagster asset materialize --select <failing_asset>` and
the run logs in `.dagster/`.

---

## 2. Partial backfill of a single source

### Symptoms

- One source had a bad ingest window (API returned 500s,
  upstream corrected a prior day, your code had a bug for one run).
- Mart values for those dates are wrong; every other source is fine.
- `analytics.mart_cost_summary` shows a spike or gap for the window.

### Diagnosis

```bash
# Identify the date range.
uv run duckdb data/databox.duckdb "SELECT day_date, COUNT(*)
  FROM ebird.fct_daily_bird_observations
  WHERE day_date BETWEEN DATE '2026-04-18' AND DATE '2026-04-20'
  GROUP BY 1 ORDER BY 1"
```

If row counts are zero / absurdly low / spiking, you have a
window to replace.

### Recovery

```bash
# 1. Drop the affected raw window so dlt reloads it.
uv run duckdb data/databox.duckdb "DELETE FROM raw_ebird.observations
  WHERE observation_date BETWEEN DATE '2026-04-18' AND DATE '2026-04-20'"

# 2. Rerun the dlt source for that window (set DATABOX_BACKFILL_START/END
#    if the source honours them; otherwise bounded full reload is fine).
uv run dagster asset materialize \
  --select 'ebird_dlt_assets' \
  -f packages/databox/databox/orchestration/definitions.py

# 3. Restate the affected SQLMesh models for the window only.
cd transforms/main
uv run sqlmesh plan prod \
  --start 2026-04-18 \
  --end 2026-04-20 \
  --restate-model 'ebird.fct_daily_bird_observations' \
  --restate-model 'analytics.fct_species_environment_daily' \
  --auto-apply
```

SQLMesh recomputes only the affected partitions of the restated
models. Other sources and other dates are untouched.

### Validation

```bash
# Row counts in the restated window should now match expectations.
uv run duckdb data/databox.duckdb "SELECT day_date, COUNT(*)
  FROM ebird.fct_daily_bird_observations
  WHERE day_date BETWEEN DATE '2026-04-18' AND DATE '2026-04-20'
  GROUP BY 1 ORDER BY 1"

# Re-run Soda contracts against prod.
uv run dagster asset-check execute \
  --select '*' \
  -f packages/databox/databox/orchestration/definitions.py
```

Every Soda check for `ebird.*` and `analytics.*` must pass.

### Rollback

`sqlmesh` plan history is your undo. List prior plan IDs and
restore:

```bash
cd transforms/main
uv run sqlmesh state list        # find the previous plan ID
uv run sqlmesh plan prod --restore-from <previous-plan-id> --auto-apply
```

See [docs/environments.md#escape-hatches](environments.md#escape-hatches).

---

## 3. MotherDuck point-in-time recovery

### Symptoms

- Bad write landed on prod MotherDuck (mass delete, wrong restate window,
  accidental DROP). You want the database back to a known-good moment.
- `analytics.*` rows are missing or mutated where they should be stable.

### Diagnosis

```sql
-- Run in MotherDuck UI or via uv run duckdb md:
SELECT snapshot_id, snapshot_name, created_at
FROM md_information_schema.database_snapshots
WHERE database_name = 'databox'
ORDER BY created_at DESC
LIMIT 20;
```

Snapshots are automatic (Business plan default 7d retention, up to 90d;
Lite paid 1d; Lite free none — confirm your plan in the MotherDuck UI).
Named snapshots persist until removed regardless of retention.

### Recovery

Two options. Prefer **Path A** — it leaves the broken state inspectable.

**Path A — clone to a new database, validate, then repoint.**

```sql
-- 1. Clone a historical state to a new database.
CREATE DATABASE databox_restored FROM databox
  (SNAPSHOT_TIME '2026-04-20 12:00:00');

-- 2. Spot-check row counts against your last-known-good date.
SELECT COUNT(*) FROM databox_restored.ebird.fct_daily_bird_observations
  WHERE day_date = DATE '2026-04-19';

-- 3. Rename databases to swap. Keep the broken one for forensics.
ALTER DATABASE databox RENAME TO databox_broken;
ALTER DATABASE databox_restored RENAME TO databox;
```

**Path B — overwrite in place (destructive; only after forensics).**

```sql
ALTER DATABASE databox SET SNAPSHOT TO
  (SNAPSHOT_TIME '2026-04-20 12:00:00');
```

### Validation

```bash
# Point local tooling at the restored MotherDuck database.
export DATABOX_BACKEND=motherduck

# Smoke + contracts.
task verify
task verify:dev
```

Confirm Dagster freshness checks pass and `mart_cost_summary` looks
sane post-restore (no synthetic gap beyond the restore point).

### Rollback

Path A is reversible because the broken DB is still named
`databox_broken`:

```sql
ALTER DATABASE databox RENAME TO databox_bad_restore;
ALTER DATABASE databox_broken RENAME TO databox;
```

Path B is reversible only if you cloned a forensic copy **before**
running it. Always prefer Path A on prod data.

### Retention gotcha

Named snapshots persist until you drop them. Anonymous
(auto) snapshots age out per `snapshot_retention_days`. If you
know a window is load-bearing, create a named snapshot before
any destructive operation:

```sql
CREATE SNAPSHOT 'pre_mart_rewrite_20260421' OF databox;
```

---

## 4. Paused-schedule resumption

### Symptoms

- Dagster daemon was stopped for hours / days.
- Freshness checks red across every source.
- `analytics.mart_cost_summary` missing recent rows.

### Diagnosis

```bash
# Daemon status?
uv run dagster instance show

# When did each schedule last tick?
uv run dagster schedule list
```

If daemon is stopped or last-tick timestamps are stale, the
schedule is paused.

### Recovery

```bash
# 1. Start the daemon (dagster:dev does both UI + daemon for local use;
#    use --workspace + `dagster-daemon run` in a prod deployment).
task dagster:dev           # local
# or
uv run dagster-daemon run  # prod

# 2. Do NOT rely on missed-tick catch-up — Dagster's default is to
#    skip missed cron fires. Trigger an explicit backfill for the
#    missed window instead.
uv run dagster job backfill \
  --job all_pipelines \
  --partition-set-name '*' \
  --from 2026-04-18 --to 2026-04-20 \
  -f packages/databox/databox/orchestration/definitions.py
```

For non-partitioned assets (`mart_cost_summary`), just materialize
once — the per-day upsert is idempotent:

```bash
uv run dagster asset materialize \
  --select 'analytics/mart_cost_summary' \
  -f packages/databox/databox/orchestration/definitions.py
```

### Validation

```bash
# Every freshness check must return to green within its SLA window
# (see docs/freshness.md for the per-asset deadlines).
task verify
```

Open the Dagster UI → Assets → filter by `last_materialized` and
confirm every mart's latest materialization is within its SLA
`timedelta`.

### Rollback

Nothing to undo — these operations are additive / idempotent. If
a resumed run itself fails, treat it as a fresh incident and use
scenario 2 (partial backfill) for the affected window.

---

## Prevention appendix

Each scenario maps to the pre-commit / CI / runtime checks that
would catch (or have caught) its underlying class of error.

| Scenario | Catching check | Where |
|---|---|---|
| Blown DuckDB file | `check-added-large-files` pre-commit | blocks accidental commit of a 10 GB `.duckdb` |
| Blown DuckDB file (disk full) | `df` monitoring + ADR-0001 note on DuckDB as file | **gap** — no alert today; see follow-up below |
| Partial backfill | `schema-contract-ci` (`scripts/schema_gate.py`) | blocks contract changes that would silently drop rows |
| Partial backfill | Soda `row_count` + `freshness` checks | asset-check failures block downstream materialization |
| MotherDuck PIT | Named snapshot before destructive ops | **gap** — no automation today; documented above |
| MotherDuck PIT | Soda contracts on every mart | fails fast if a restore produces wrong shape |
| Paused schedule | `freshness_violation_sensor` | logs a warning line per missed SLA ([docs/freshness.md](freshness.md)) |
| Paused schedule | Dagster daemon health check | **gap** — no external heartbeat today |

### Known gaps (follow-up tickets)

- **Disk-space alerting**: no automation; a `df -h` cron writing to
  `analytics.mart_cost_summary` would close this. Low priority for
  a single-operator scaffold.
- **Pre-destructive named snapshot**: a wrapper around risky SQLMesh
  restates that auto-creates `CREATE SNAPSHOT` on MotherDuck would
  remove a common footgun.
- **Daemon heartbeat**: today, a stopped daemon is only noticed when
  freshness checks fire. An external uptime ping against the Dagster
  webserver would catch it faster.

None of these are in scope for the scaffold-polish initiative — they
are called out here so a forker knows what trust boundaries exist.
