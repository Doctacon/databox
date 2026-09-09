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

## Review-blocker repairs

All four initial independent-review blockers were repaired without live effects:

1. Source revision now resolves before Docker or marker access through the validator's single exported registry-byte-coherence contract; malformed or drifted revisions fail before mutation.
2. Both active containers must have no host bindings, exact Compose project/service labels, and exactly the authoritative `databox-iceberg_default` network.
3. Redaction now replaces every backup cipher/session, PostgreSQL password, Polaris client secret, and primary warehouse access/secret/optional-token value before bounding, including unlabeled echoes.
4. A stateful fake runner drives the real `DockerDrillOperations` through preflight, marker SQL, both WAL pushes, existing restore invocation, isolated PostgreSQL/Polaris, validator, cleanup, timing, and retained-artifact assertions.

The repaired focused suite passed 80 tests. Ruff/format, MyPy for both recovery scripts, focused secret scan, Task dry-run, and diff checks passed. No live command ran. Independent re-review remains required before live use.
