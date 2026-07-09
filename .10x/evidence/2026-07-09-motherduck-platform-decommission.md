Status: recorded
Created: 2026-07-09
Updated: 2026-07-09
Relates-To: .10x/tickets/done/2026-07-09-decommission-motherduck-platform-support.md, .10x/specs/local-only-databox-platform.md

# MotherDuck platform decommission evidence

## What was observed

Active runtime configuration now has one local warehouse path and one local
SQLMesh gateway. dlt always uses Quack credentials, and Dagster definitions no
longer perform cloud database bootstrap. The former Dive and preview trees and
their executable tests are removed.

Active docs, task commands, environment examples, generated dictionary text,
and source comments no longer present MotherDuck or Dive as supported paths.
ADR-0006 and ADR-0004 retain clearly labeled historical rationale. CHANGELOG
and terminal `.10x` history were not rewritten.

## Removed active surfaces

- Backend selector and cloud token settings.
- Cloud database URI/catalog derivation and SQLMesh cloud gateway.
- dlt cloud destination branch and non-Quack runtime branches.
- Dagster cloud database creation/bootstrap.
- Cloud/bootstrap and Dive SQL tests.
- `dives/birding-trip-plan/` and `.dive-preview/`.
- Environment, Taskfile, README, configuration, secrets, SQLMesh environment,
  incremental-loading, MkDocs navigation, and active code-comment instructions.

## Procedure and results

- `uv run pytest --no-cov -q tests/test_source_registry.py tests/test_quack_destinations.py`
  — 17 passed. A prior focused invocation without `--no-cov` also passed all 17
  tests but exited on the repository-wide 70% coverage threshold; full CI
  subsequently established 78.20% coverage.
- `uv run pytest --no-cov -q tests/test_settings.py tests/test_source_registry.py tests/test_quack_destinations.py`
  — 18 passed after adding the local-only SQLMesh gateway/database-path settings
  regression test requested by closure review.
- `task ci` — passed Ruff check/format, mypy, 141 tests, secret scan, staging
  drift, and platform-health drift; total coverage 78.20%.
- `uv lock --check` — resolved 238 packages successfully.
- `uv run mkdocs build --strict` — documentation built successfully. MkDocs
  reported only the existing informational list of generated dictionary pages
  omitted from explicit navigation.
- `uv run python scripts/check_secrets.py .` — passed with no output.
- Targeted `uv run ruff check ...` and `ruff format --check` — passed.
- A direct settings assertion constructed `settings.sqlmesh_config()` and
  confirmed that its only gateway and default gateway are `local`, with the
  warehouse path ending in `data/databox.duckdb`.
- `git diff --check` — passed.
- Repository reference audit found only explicitly superseded/historical ADR
  index and ADR-body references outside terminal records and CHANGELOG. Stale
  active Dive references in `.10x/specs/birding-trip-copilot.md` were repaired
  to name the local React/API product before closure.
- `git diff --cached --name-only` — empty; no files were staged.

## What this supports

This supports the child ticket acceptance criteria for the decommissioned
surfaces and the local-only platform specification. It also demonstrates that
the implementation did not add React, Cloudflare inference, or shared-server
parallel Quack behavior.

## Limits and residual risk

Focused tests emit a SQLMesh analytics shutdown logging warning after pytest
completes; it does not fail the focused suite or full CI. No live source ingest
or long-running Dagster UI smoke was run because those exercise network and
runtime behavior beyond this decommission ticket's focused validation.
