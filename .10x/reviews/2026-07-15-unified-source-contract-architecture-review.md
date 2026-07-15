Status: recorded
Created: 2026-07-15
Updated: 2026-07-15
Target: .10x/tickets/done/2026-07-12-verify-unified-source-contract-and-ci.md
Verdict: fail

# Unified source contract architecture review

## Findings

The canonical registry, registry-derived Dagster composition/CI, dependency direction, Quack lifecycle boundary, and retired legacy configuration are sound. Aggregate evidence also supports current seven-source behavior.

Closure blockers remain:

1. `scripts/check_source_layout.py` does not enforce several MUST-level canonical-contract invariants: valid names, duplicate names, analytics-anchor cardinality, required domain exports/callable singular builder, and schedule/export conflicts.
2. Quack `_RAW_DEDUPE_KEYS` legitimately owns primary keys but duplicates registry schema/table membership without an executable parity invariant.
3. File-source scaffold and skip-marker guidance is inconsistent with completed matrix validation.

These findings are owned by `.10x/tickets/done/2026-07-15-repair-source-contract-enforcement.md`.

## Verdict

Fail for closure pending the bounded enforcement repair.

## Residual risk

Hosted GitHub matrix/path behavior remains unproven until the first real CI run. Provider fixtures prove captured shapes only; historical warehouses may lack newly inventoried tables until a future authorized refresh.
