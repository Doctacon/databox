Status: recorded
Created: 2026-07-15
Updated: 2026-07-15
Target: .10x/tickets/done/2026-07-12-verify-unified-source-contract-and-ci.md
Verdict: fail

# Unified source contract correctness review

## Findings

Current registry, Dagster inventory, source suites, raw-table/codegen/docs, CI matrix, isolated coverage, statuses, and aggregate commands are broadly coherent.

Closure blockers:

1. The executable checker/matrix can accept invalid future contracts prohibited by the active canonical spec because duplicate/name/anchor/schedule/export/builder invariants are not all enforced there.
2. Canonical builder behavior is specifically established for GBIF/Xeno-canto but not equivalently mapped for every HTTP source; USGS Earthquakes profile tests visibly bypass its domain builder.
3. Standalone scaffold/layout behavior is weaker than the specification's fail-until-complete contract.

`.10x/tickets/done/2026-07-15-repair-source-contract-enforcement.md` owns these findings.

## Verdict

Fail for closure pending repair and aggregate re-review.

## Residual risk

GitHub-hosted expression/path-filter/matrix transport remains a bounded integration limit.
