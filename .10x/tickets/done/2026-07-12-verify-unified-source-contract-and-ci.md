Status: done
Created: 2026-07-12
Updated: 2026-07-15
Parent: .10x/tickets/done/2026-07-12-unify-dlt-source-contract-and-ci.md
Depends-On: .10x/tickets/done/2026-07-12-consolidate-canonical-dlt-source-registry.md, .10x/tickets/done/2026-07-12-reconcile-canonical-raw-table-inventory.md, .10x/tickets/done/2026-07-12-complete-source-contract-test-suites.md, .10x/tickets/done/2026-07-12-derive-source-ci-from-registry.md, .10x/tickets/done/2026-07-15-repair-source-dictionary-drift.md, .10x/tickets/done/2026-07-15-repair-source-contract-enforcement.md, .10x/tickets/done/2026-07-15-sanitize-ebird-private-location-fixtures.md

# Verify unified source contract and CI

## Scope

Perform aggregate, non-mutating verification and adversarial review after all implementation children complete. Reconcile the parent graph only when every governing criterion is supported.

## Acceptance criteria

- Re-read both active specifications and map every scenario/criterion to evidence.
- Confirm exactly seven canonical registry sources, domain modules, and verification profiles with no duplicate legacy authority.
- Confirm Dagster definitions load and expose the same source assets/jobs/schedules without a manual active-source list.
- Confirm the shared refresh eligible set remains unchanged without running a refresh.
- Run all profile suites offline with recording disabled and provider network forbidden.
- Run source contract/layout/scaffold tests, registry-derived matrix/path-classification tests, aggregate coverage, full Python tests, Ruff, formatting, MyPy, secret scan, docs checks, and `git diff --check`.
- Validate workflow YAML and action pins using repository-native checks.
- Confirm captured fixture hashes are stable and fixtures contain no credential values.
- Confirm AVONET manifest hash and source invariants are unchanged.
- Obtain independent architecture, correctness, and privacy/security/source reviews; resolve blockers or leave tickets open.
- Perform retrospective extraction and ensure all follow-ups have durable owners before closure.

## Evidence expectations

Create one aggregate evidence record with commands, exact counts/results, criterion mapping, network/warehouse limits, hashes where relevant, and raw output paths when too large. Create review records for independent reviews.

## Explicit exclusions

- `task full-refresh`, `task verify`, live source jobs, SQLMesh apply, or shared warehouse writes
- New provider fixture capture unless a separately ratified blocker is returned to the Outer Loop
- Repair outside the three implementation-child scopes
- Closing the parent without coherent evidence and passing review

## Progress and notes

- 2026-07-12: Verification ticket opened during shaping. No verification commands that mutate runtime state were run.
- 2026-07-15: Aggregate verification completed without implementation repair. Full Python tests passed 810/810 at 87.81% coverage; offline source profiles passed 58/58 with network blocked; focused registry/scaffold/routing/refresh tests passed 64/64; definitions, Ruff, formatting, MyPy, workflow/action pins, staging/platform-health codegen, strict MkDocs build, fixture/privacy/secret scans, hashes, diff, and empty staging passed.
- 2026-07-15: `scripts/generate_docs.py --check` failed because `docs/dictionary/analytics/platform_health.md` omits the newly modeled raw dependencies `raw_ebird.region_stats`, `raw_ebird.taxonomy`, and `raw_noaa.datasets`. Evidence: `.10x/evidence/2026-07-15-unified-source-contract-aggregate-verification.md`.
- 2026-07-15: Independent aggregate reviews and retrospective/closure were deferred until the generated dictionary drift was repaired. No repair was performed under this verification-only ticket.
- 2026-07-15: The exact blocker was repaired and independently reviewed under `.10x/tickets/done/2026-07-15-repair-source-dictionary-drift.md`. Bounded aggregate rerun confirmed 20 generated docs in sync, strict MkDocs, exact one-page/three-bullet scope, platform-health codegen, diff check, empty staging, and unchanged AVONET/fixture/warehouse hashes.
- 2026-07-15: Aggregate evidence now passes every implementation/verification criterion and is ready for independent architecture, correctness, and privacy/security/source reviews. The prior 810-test/87.81%, 58 offline-source, 64 focused, static, privacy, fixture, workflow, and preservation results remain valid because the repair changed only one generated Markdown page. Evidence: `.10x/evidence/2026-07-15-unified-source-contract-aggregate-verification.md`.
- 2026-07-15: Three independent aggregate reviews were launched. Architecture/correctness reviews failed closure on incomplete MUST-level checker enforcement, canonical builder mapping, scaffold guidance, and unguarded Quack dedupe membership parity. Privacy/source review failed closure on exact private-location data in mature eBird cassettes and aggregate scanning of only 12/24 cassettes. Reviews: `.10x/reviews/2026-07-15-unified-source-contract-architecture-review.md`, `.10x/reviews/2026-07-15-unified-source-contract-correctness-review.md`, and `.10x/reviews/2026-07-15-unified-source-contract-privacy-security-source-review.md`.
- 2026-07-15: Opened bounded repair children `.10x/tickets/done/2026-07-15-repair-source-contract-enforcement.md` and `.10x/tickets/done/2026-07-15-sanitize-ebird-private-location-fixtures.md`. Ticket returned to blocked; no repair was performed under verification scope.
- 2026-07-15: Both repair children passed independent reviews and closed. Verification resumed for a final affected aggregate rerun and fresh architecture/correctness/privacy reviews.
- 2026-07-15: Final aggregate rerun passed: 844 full-suite tests at 87.81% coverage; 60 complete offline source tests/seven snapshots; 60 registry-derived source tests across one shared plus seven isolated processes; 118 focused checker/builder/scaffold/Quack tests; 7/7 layout/matrix and Dagster definitions; 24/24 SHA-pinned workflow actions; Ruff/177-file format/110-file MyPy; all codegen/docs/secret checks; 31/31 fixture hashes; structured 24-cassette/44-interaction privacy scan; unchanged AVONET/warehouse hashes; diff check and empty staging. Clean final-state evidence: `.10x/evidence/2026-07-15-unified-source-contract-aggregate-verification.md`.
- 2026-07-15: Fresh privacy/source review passed. Fresh architecture review failed closure because the checker still omitted the spec's legacy-authority reintroduction MUST; correctness review raised the bounded scaffold/canonical name-pattern mismatch. Reopened `.10x/tickets/done/2026-07-15-repair-source-contract-enforcement.md`; verification returned to blocked.
- 2026-07-15: Reopened enforcement work passed final review after exact retired paths and 20/20 standard import combinations failed checker/matrix, legitimate imports remained allowed, and scaffold/checker name validation was unified.
- 2026-07-15: Final post-repair aggregate rerun passed 871 tests at 87.82%, 60 offline source tests/seven snapshots, 60 isolated source tests, 145 focused tests, and every static/codegen/docs/privacy/integrity/protected-state gate. Final architecture, correctness, and privacy/source reviews passed with no blocker.
- 2026-07-15 retrospective: Durable lessons were extracted in the enforcement and eBird sanitization child records/tests. Verification added no separate operational procedure: complete fixture enumeration, canonical executable-shape checking, and standard import-form adversarial coverage now live in the executable test contract. Ticket closed.
- 2026-07-15: Final post-enforcement aggregate rerun passed without implementation changes: 871 full-suite tests at 87.82% coverage; 60 complete offline source tests/seven snapshots; 60 registry-derived isolated source tests; 145 focused checker/matrix/scaffold/builder/Quack tests; live 7/7 checker/matrix and Dagster definitions; 24/24 pinned workflow actions; Ruff/177-file format/110-file MyPy; all codegen/docs/secret checks; 31/31 fixture hashes; 24-cassette/44-interaction privacy scan with 50 conforming private placeholders and zero violations; unchanged AVONET/fixture-manifest/warehouse hashes; clean diff check and empty staging. Evidence: `.10x/evidence/2026-07-15-unified-source-contract-aggregate-verification.md`. Passing privacy review remains applicable because no privacy-owned implementation changed; closure remains parent-owned.

## Blockers

None.

## References

- `.10x/tickets/done/2026-07-12-unify-dlt-source-contract-and-ci.md`
- `.10x/specs/canonical-dlt-source-registry.md`
- `.10x/specs/registry-derived-source-verification.md`
- `.10x/knowledge/dlt-vcr-http-client-isolation.md`
