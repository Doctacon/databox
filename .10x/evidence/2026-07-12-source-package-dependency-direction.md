Status: recorded
Created: 2026-07-12
Updated: 2026-07-12
Relates-To: .10x/tickets/done/2026-07-12-break-source-package-dependency-cycle.md, .10x/tickets/done/2026-07-12-warehouse-repository-cleanup.md

# Source package dependency direction

## What was observed

Package metadata formed an unsupported runtime cycle:

- `databox` depended on `databox-sources`, matching the runtime import direction;
- `databox-sources` also depended on `databox`, although no runtime module under
  `packages/databox-sources/databox_sources/**` imports `databox`.

Source-package tests intentionally import canonical builders from `databox`, but
the workspace root already installs both packages for repository tests. Test
composition therefore does not justify a source-package runtime dependency.

## Change

- Removed `databox` from `packages/databox-sources/pyproject.toml` dependencies.
- Removed the now-unused source-package `[tool.uv.sources]` entry for `databox`.
- Preserved `databox` → `databox-sources` in `packages/databox/pyproject.toml`.
- Updated the `databox` description from the deleted generic “quality engine” to
  current config, quality/codegen tooling, and Dagster orchestration.
- Ran `uv lock --offline`. The lock removed the reverse edge and synchronized
  the three workspace package versions from stale `0.5.0` lock entries to their
  existing `0.6.0` project metadata.

No runtime source, public Python API, provider behavior, or test layout changed.

## Procedure and results

- Runtime import scan under `databox_sources/**` — zero `databox` imports.
- Isolated import probe inserted an import blocker for `databox` and imported
  17 imports successfully: the `databox_sources` package root plus 16 discovered submodules.
- Metadata/lock assertion — direction is exactly `databox` →
  `databox-sources`; both lock entries match package version `0.6.0`.
- `uv lock --check --offline` — passed, 241 packages resolved from local state.
- Complete source profiles — **60 passed**, seven snapshots passed, recording
  disabled and network blocked.
- Canonical source builder/registry tests — **30 passed**.
- Workspace imports (`databox`, `databox_sources`, Definitions module) — passed.
- `.venv/bin/dg check defs --use-active-venv` — all definitions loaded.
- Ruff check and format over both runtime packages/relevant tests — passed;
  73 files already formatted.
- MyPy over both runtime packages — success for 71 source files.
- Shared warehouse SHA-256 was byte-identical before/after definitions loading:
  `3f7ad93d93682d5012496599cdcab94b07526aa2b70e8d1ec7982f6ff55f25e4`.
- `git diff --check` — passed.
- `git diff --cached --name-only` — empty.

## What this supports

This supports removal of only the unsupported reverse metadata edge, preserved
source behavior and Dagster composition, independently importable source
runtime modules, coherent lock/workspace metadata, and the corrected current
package description.

## Limits

The isolation probe used the installed dependency environment while actively
blocking any `databox` import; it did not publish/install a wheel into a fresh
networked environment. This proves first-party dependency direction without
introducing network or build side effects.

No provider request, source refresh, SQLMesh command/apply, shared warehouse
query/write, model call, email, stage, commit, or push occurred.
