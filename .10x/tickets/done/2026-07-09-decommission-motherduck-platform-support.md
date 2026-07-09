Status: done
Created: 2026-07-09
Updated: 2026-07-09
Parent: .10x/tickets/done/2026-07-09-build-local-birding-copilot-product.md
Depends-On: None

# Decommission MotherDuck platform support

## Scope

Remove active MotherDuck backend support and Dive artifacts while preserving the local Quack/DuckDB platform.

Required changes include:

- remove MotherDuck settings, backend selection, database URI, SQLMesh gateway, dlt destination, and Dagster database-bootstrap logic,
- collapse supported runtime configuration to the single Quack-backed local warehouse,
- remove MotherDuck-specific tests and replace any local behavior coverage they previously carried,
- remove `dives/` and `.dive-preview/` artifacts,
- remove active MotherDuck commands/config/docs and update `.env.example`, README, runbook, configuration docs, ADR index, and relevant ADR status/rationale,
- remove dependencies/imports that become unused,
- preserve historical changelog and terminal `.10x` records as factual history.

## Explicit exclusions

- Do not implement the new React app in this ticket.
- Do not implement Cloudflare inference in this ticket.
- Do not change Quack source concurrency beyond what is necessary to compile after settings cleanup.
- Do not rewrite historical changelog or terminal evidence to pretend MotherDuck never existed.

## Acceptance criteria

- `.10x/specs/local-only-databox-platform.md` is satisfied for the decommissioned surfaces.
- Runtime settings expose only the supported local Quack data path.
- SQLMesh and dlt cannot select MotherDuck.
- Dagster startup performs no MotherDuck connection/bootstrap.
- MotherDuck Dive/preview artifacts are removed.
- Active docs contain no instruction to configure or run MotherDuck/Dives.
- Historical references are clearly historical/superseded.
- Local settings/destination/registry tests pass.
- `uv lock --check`, CI, docs build, and secret scan pass or any unrelated pre-existing failure is recorded precisely.

## Evidence expectations

Record:

- enumerated removed active surfaces,
- `rg` audit distinguishing active versus historical references,
- relevant test/CI/docs outputs,
- final diff review.

## Progress and notes

- 2026-07-09: Removed active MotherDuck runtime settings, SQLMesh/dlt/Dagster branches, Dive/preview artifacts, tests, commands, configuration, and documentation while preserving the local Quack/DuckDB path and historical records.
- 2026-07-09: Validation passed: `task ci` (141 tests, 78.20% coverage), `uv lock --check`, strict MkDocs build, secret scan, targeted Ruff checks, and the active-versus-historical reference audit.
- 2026-07-09: Runtime review passed. Initial closure review then found stale active Dive references in `.10x/specs/birding-trip-copilot.md` and missing settings regression coverage.
- 2026-07-09: Repaired the active spec references and added `tests/test_settings.py`; `uv run pytest --no-cov -q tests/test_settings.py tests/test_source_registry.py tests/test_quack_destinations.py` passed all 18 focused tests.
- 2026-07-09: Follow-up review inspected both fixes and returned a final verdict of pass.

## Evidence and review

- `.10x/evidence/2026-07-09-motherduck-platform-decommission.md`
- `.10x/reviews/2026-07-09-motherduck-platform-decommission-review.md`

## Blockers

None.
