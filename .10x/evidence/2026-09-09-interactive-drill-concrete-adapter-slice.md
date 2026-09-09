Status: recorded
Created: 2026-09-09
Updated: 2026-09-09
Relates-To: .10x/tickets/2026-09-09-add-interactive-catalog-recovery-drill-command.md

# Interactive drill concrete adapter slice

## Scope completed

Extended the existing `scripts/platform/catalog_recovery.py`; no new orchestration script was created. Added a concrete Docker/PostgreSQL/Polaris adapter, backward-compatible `drill` CLI dispatch, a thin `catalog:recovery-drill` Task target, concise runbook usage, and hermetic adapter command-shape tests.

The adapter composes the already reviewed restore runner and registry validator. It checks pinned healthy active containers, the exact active PostgreSQL volume, collision-free generated resource names, and successful pgBackRest repository metadata before marker mutation. Marker identifiers/phases are closed generated values. Fresh role credentials reach only Docker child environments by variable name. WAL is switched and explicitly archive-pushed without restarting active PostgreSQL. Recovery PostgreSQL/Polaris use unique labels, one isolated network, no host ports, restart policy `no`, archive mode off, no bootstrap, and only the new recovery volume. Catalog validation requires pass/25 expected/25 validated/zero failed. Marker cleanup and cleanup-WAL archival remain unconditional; recovery resources are preserved and cutover is absent.

No AWS, Docker, PostgreSQL, Polaris, marker, backup, restore, validation, or cleanup operation ran in this implementation slice.

## Changed files

- `scripts/platform/catalog_recovery.py`
- `tests/platform/test_catalog_recovery.py`
- `Taskfile.yaml`
- `docs/runbook.md`

## Validation

- `uv run pytest --no-cov -q tests/platform/test_catalog_recovery.py tests/platform/test_catalog_recovery_validate.py` — 74 passed.
- `uv run ruff check scripts/platform/catalog_recovery.py tests/platform/test_catalog_recovery.py` — passed.
- `uv run ruff format --check scripts/platform/catalog_recovery.py tests/platform/test_catalog_recovery.py` — passed.
- `MYPYPATH=packages/databox uv run mypy scripts/platform/catalog_recovery.py` — passed.
- `uv run python scripts/platform/check_secrets.py scripts/platform/catalog_recovery.py tests/platform/test_catalog_recovery.py Taskfile.yaml docs/runbook.md` — passed, four eligible files.
- `task --list` — includes `catalog:recovery-drill`.
- `task --dry catalog:recovery-drill -- --catalog databox_lake --source-revision 17c45b0` — renders only the existing recovery entrypoint.
- `git diff --check` — passed.

## Remaining review gaps

Independent review is required before live use. The bounded slice intentionally stops with these exact items for review rather than widening further:

1. Source-revision provenance is enforced by the reused validator at the final stage, but is not yet preflighted before active marker mutation.
2. Active preflight proves pinned health and PostgreSQL volume identity but does not yet assert the exact active Docker network and port bindings named by the acceptance text.
3. Direct-value redaction enumerates backup secrets; primary-warehouse and Polaris secret values are passed only by environment-variable name but are not all enumerated for direct-value replacement if a hostile child diagnostic echoes them.
4. Concrete tests cover preflight and container command shapes, SQL rejection, exact validator result, CLI dispatch, and Task rendering, but do not yet drive one fully integrated fake concrete-adapter drill across every stage.

These are review blockers, not accepted residual risks. No live command is authorized until they are resolved or explicitly accepted and independent review passes.
