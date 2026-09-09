Status: recorded
Created: 2026-09-09
Updated: 2026-09-09
Relates-To: .10x/tickets/2026-09-09-add-interactive-catalog-recovery-drill-command.md

# Interactive drill state-machine slice

## Implementation

Added the dependency-injected timed-drill state machine to the existing `catalog_recovery.py`; no new script or operator command was exposed. It derives one unique marker/volume/network/PostgreSQL/Polaris resource set, requires read-only preflight before marker mutation, brackets a database-clock target with before/after commits, archives marker WAL, starts the monotonic RTO clock immediately before restore, orders restore/PostgreSQL validation/Polaris validation/registry validation, measures RPO/RTO, and always attempts active-marker cleanup plus cleanup-WAL archival. It never has a recovery-resource deletion or cutover operation.

Failure handling preserves the primary bounded stage error, records cleanup failure without exposing its diagnostic, and leaves recovery artifacts intact. Unbracketed timestamps stop before restore.

## Validation

- `uv run pytest --no-cov -q tests/platform/test_catalog_recovery.py` — 51 passed.
- Focused Ruff check/format — passed.
- `MYPYPATH=packages/databox uv run mypy scripts/platform/catalog_recovery.py` — passed.
- Focused secret scan and `git diff --check` — passed.

No AWS CLI, Docker, marker, catalog, warehouse, restore, or live drill operation ran.

## Remainder

The concrete Docker/PostgreSQL/Polaris/WAL/validator operations adapter, backward-compatible `drill` CLI dispatch, thin Task target, docs, and concrete-adapter hermetic tests remain required before live use. The state machine is intentionally not operator-accessible until those pieces pass review.
