Status: done
Created: 2026-09-02
Updated: 2026-09-02
Parent: None
Depends-On: None

# Reconcile post-Iceberg CI failures

## Scope

Classify and repair the 19 failures exposed by the full merge-gate `task ci` run after the Polaris Iceberg migration. Update tests/snapshots only where active architecture intentionally changed authority or dlt metadata; repair implementation where active behavior regressed. Preserve unrelated product semantics and safety tests.

## Acceptance criteria

- Every initial failure is classified against active records and current source.
- Tests are not weakened to hide product regressions.
- `task ci` passes.
- SQLMesh tests, docs build, pre-commit, and diff checks remain passing.

## Explicit exclusions

- Live provider refreshes.
- New product behavior.
- Public deployment enablement.

## Evidence expectations

Record the initial 19-failure set, classifications, exact repairs, final full gate results, and residual risk.

## Progress and notes

- 2026-09-02: Merge gate found mypy failures; repaired type annotations/keyword arguments, after which mypy passed for 141 files.
- 2026-09-02: Full pytest then reported 19 failures: analytics contract inventory, observation freshness, settings secret repr, AVONET fail-closed model tests, Rufous theme, AVONET catalog-model tests, six dlt schema snapshots, and VCR manifest sanitation.
- 2026-09-02: Classified and repaired the failures without weakening safety checks: platform health intentionally raised modeled asset/contract parity from 22 to 23; isolated DuckDB model tests now rewrite only the authoritative `polaris_aws.raw_*` qualifier to their local fixture schema; the SMTP secret test uses a host value unique from the intentionally public Polaris localhost URL; README again names the stable local DuckDB path; six source snapshots now record intentional Iceberg table format and dlt lineage text precision; the complete 31-artifact privacy manifest was regenerated after those reviewed snapshot changes. The 31 affected focused tests and all six updated snapshots passed.
- 2026-09-02: Final `task ci` passed: Ruff, formatting, MyPy (141 files), 1,508 pytest tests at 84.63% coverage with all seven snapshots passing, secret scan (1,068 files), staging drift, and platform-health drift. SQLMesh 18/18, docs strict build, pre-commit, and diff check passed independently.
- 2026-09-02: Closure evidence and merge-readiness review recorded at `.10x/evidence/2026-09-02-final-merge-gate.md` and `.10x/reviews/2026-09-02-final-merge-readiness-review.md`. No unresolved follow-up or reusable operational procedure remains.

## Blockers

None.
