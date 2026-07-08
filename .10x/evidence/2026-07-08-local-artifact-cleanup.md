Status: recorded
Created: 2026-07-08
Updated: 2026-07-08
Relates-To: .10x/tickets/done/2026-07-08-remove-stale-local-artifacts.md

# Evidence: local/generated artifact cleanup

## What was observed

The project contained ignored and untracked local/generated artifacts from prior iterations, including tool caches, package-local dlt state, SQLMesh cache/output, docs build output, preview `node_modules`, empty state directories, and root logs.

An active `task dagster:dev` process was using `.dagster/`, so `.dagster/` was intentionally preserved.

## Procedure

Inspected cleanup candidates with:

```bash
git clean -ndX
git clean -nd
find . -maxdepth 2 -type d -empty
du -sh .dagster .dagster_state .dlt_state .duckdb_state .sqlmesh_state .dive-preview data .logs logs site transforms/_shared docs/images packages/databox/data transforms/main/data transforms/main/.cache
pgrep -fl "dagster|dg dev|quack|duckdb|sqlmesh"
```

Removed only safe generated/local artifacts outside `.venv`, `.env`, `data`, `.dagster`, `.logs`, `.schema`, `.10x`, `.pi/skills`, source, tests, docs source, Soda contracts, and SQLMesh source models.

Updated:

- `.gitignore` to ignore `node_modules/`, `.dlt_state/`, `.duckdb_state/`, `.sqlmesh_state/`, and `.dagster_state/`.
- `Taskfile.yaml` `clean` to remove safe generated artifacts while pruning `.git`, `.venv`, `data`, `.dagster`, and `.logs`.
- `Taskfile.yaml` `clean-all` description to match the preserved `.dagster/` and `.logs/` boundary; it continues to drop only `.venv` and `data/` after `clean`.

Validation commands:

```bash
task clean
task ci
task clean
git clean -ndX
git clean -nd
git status --short --ignored
```

## Results

`task ci` passed:

```text
ruff check: passed
ruff format --check: passed
mypy packages/: passed
pytest: 119 passed
scripts/check_secrets.py .: passed
scripts/generate_staging.py --check: passed
scripts/generate_platform_health.py --check: passed
```

After the final `task clean`, ignored dry-run cleanup reported only intentionally preserved local state:

```text
Would remove .dagster/
Would remove .env
Would remove .logs/
Would remove .venv/
Would remove data/
```

Untracked dry-run cleanup reported only new durable `.10x` records from this work:

```text
Would remove .10x/evidence/2026-07-08-local-artifact-cleanup.md
Would remove .10x/tickets/done/2026-07-08-remove-stale-local-artifacts.md
```

`git status --short --ignored` showed only source changes, new durable `.10x` records, and intentionally preserved ignored local state:

```text
 M .gitignore
 M Taskfile.yaml
?? .10x/evidence/2026-07-08-local-artifact-cleanup.md
?? .10x/tickets/done/2026-07-08-remove-stale-local-artifacts.md
!! .dagster/
!! .env
!! .logs/
!! .venv/
!! data/
```

## What this supports

- Stale generated artifacts from prior iterations were removed.
- Cleanup is repeatable with `task clean`.
- Validation still passes after cleanup rule changes.
- Preserved local state is intentional rather than accidental.

## Limits

- `.dagster/` was not removed because `task dagster:dev` was active.
- `.logs/` was not removed because recent `.10x` evidence references a full-refresh log there.
- `data/` was not removed because it contains the current local database and dlt state.
