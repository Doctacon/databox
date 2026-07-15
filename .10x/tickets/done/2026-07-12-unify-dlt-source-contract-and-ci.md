Status: done
Created: 2026-07-12
Updated: 2026-07-15
Parent: None
Depends-On: None

# Unify dlt source contract and CI

## Plan outcome

Make the canonical Python source registry the one executable ingestion-source contract and ensure every registered source receives profile-appropriate offline tests and registry-derived CI coverage.

This is a parent plan, not an executable ticket.

## Governing records

- `.10x/decisions/python-source-registry-as-canonical-contract.md`
- `.10x/specs/canonical-dlt-source-registry.md`
- `.10x/specs/registry-derived-source-verification.md`
- `.10x/research/2026-07-12-dlt-sqlmesh-dagster-improvement-assessment.md`
- `.10x/research/2026-07-12-single-source-contract-and-ci-architecture.md`
- `.10x/knowledge/dlt-vcr-http-client-isolation.md`
- `.10x/specs/parallel-quack-local-refresh.md`

## Child sequence

1. `.10x/tickets/done/2026-07-12-consolidate-canonical-dlt-source-registry.md`
   - Make the Python registry and domain builders authoritative.
   - Retire the unused generic configuration/registry path.
2. `.10x/tickets/done/2026-07-12-reconcile-canonical-raw-table-inventory.md`
   - Add the three source-observed eBird/NOAA raw-table omissions and regenerate only required platform-health/inspection coherence.
3. `.10x/tickets/done/2026-07-12-complete-source-contract-test-suites.md`
   - Bring all seven sources to their declared offline verification profiles.
   - Capture the three authorized missing provider fixture families safely.
4. `.10x/tickets/done/2026-07-12-derive-source-ci-from-registry.md`
   - Replace hand-maintained source CI enumeration with registry-derived matrix and aggregate coverage.
5. `.10x/tickets/done/2026-07-15-repair-source-dictionary-drift.md`
   - Repair the exact generated dictionary drift exposed by aggregate verification.
6. `.10x/tickets/done/2026-07-15-repair-source-contract-enforcement.md`
   - Enforce every canonical checker/builder/schedule/scaffold invariant and Quack membership parity found by final review.
7. `.10x/tickets/done/2026-07-15-sanitize-ebird-private-location-fixtures.md`
   - Remove mature eBird private-location fixture data and expand aggregate fixture integrity coverage.
8. `.10x/tickets/done/2026-07-12-verify-unified-source-contract-and-ci.md`
   - Rerun affected aggregate gates, obtain passing independent reviews, and reconcile closure.

Registry consolidation precedes both bounded raw-table reconciliation and test construction. CI follows complete source suites. Aggregate verification depends on every implementation child, including raw-table/codegen/documentation coherence.

## Aggregate acceptance criteria

- Exactly seven current sources have one canonical registry owner, one explicit verification profile, and a source-complete raw-table inventory.
- Dagster source composition and CI source enumeration contain no hand-maintained active-source list outside the registry.
- Generic dead pipeline config/registry/quality code is removed without affecting AVONET's pinned manifest.
- All HTTP sources pass resource, schema, smoke, idempotency, and offline VCR requirements.
- AVONET passes its pinned-file snapshot profile.
- GBIF, Xeno-canto, USGS Earthquakes, and AVONET-only changes trigger the registry-derived complete source matrix.
- Aggregate coverage includes all seven source suites in isolated pytest processes.
- Default tests are network-free; sanitized captured fixtures contain no credentials.
- Existing Quack refresh, Dagster definitions, source behavior, raw schemas, and protected local data remain unchanged.
- Final evidence maps every criterion and independent review has no unresolved blocker.

## Explicit exclusions

- dlt runtime schema-evolution policy changes
- SQLMesh model or Dagster refresh redesign
- source addition/removal, cadence changes, or provider query expansion
- full source refresh, SQLMesh apply, or shared warehouse mutation
- AVONET live refresh/download

## Progress and notes

- 2026-07-12: Repository and official documentation research completed.
- 2026-07-12: User selected the canonical Python registry architecture.
- 2026-07-12: User authorized bounded metadata-only fixture capture for GBIF, Xeno-canto, and USGS Earthquakes. No full refresh or warehouse mutation was authorized.
- 2026-07-12: Governing decision and two focused specifications activated; implementation intentionally deferred to child-ticket execution.
- 2026-07-15: Initial aggregate verification passed implementation, tests, coverage, static, privacy, integrity, and warehouse-preservation gates but found stale generated platform-health dictionary dependencies. Opened and closed `.10x/tickets/done/2026-07-15-repair-source-dictionary-drift.md` after exact repair/review.
- 2026-07-15: Final aggregate reviews then found incomplete MUST-level checker enforcement/builder mapping/Quack parity and mature eBird private-location leakage missed by the partial fixture scan. Opened repair children; eBird sanitization passed review and closed at `.10x/tickets/done/2026-07-15-sanitize-ebird-private-location-fixtures.md`.
- 2026-07-15: Source-contract enforcement initially passed bounded review, and a clean aggregate rerun passed 844 tests at 87.81% plus all offline/static/integrity gates. Fresh privacy/source review passed. Fresh architecture/correctness review found one remaining active-spec omission—legacy-authority reintroduction was not executable-checker enforced—and a scaffold name-pattern mismatch. Reopened and re-closed `.10x/tickets/done/2026-07-15-repair-source-contract-enforcement.md` after exact repair and passing final review.
- 2026-07-15: Final aggregate rerun passed 871 tests at 87.82%, 60 offline source tests, 60 isolated source tests, 145 focused contract tests, 7/7 live contract/matrix, and every static/codegen/docs/privacy/integrity/protected-state gate. Architecture, correctness, and privacy/source closure reviews passed. Verification closed at `.10x/tickets/done/2026-07-12-verify-unified-source-contract-and-ci.md`.
- 2026-07-15 retrospective: The work hardened three durable practices directly in executable artifacts: contract checkers validate canonical executable/import shapes rather than names, fixture privacy/integrity scans enumerate the full tracked inventory, and scaffold validation shares the canonical identity rule. Child records/tests own those lessons; no additional skill or knowledge record is needed. Parent closure review: `.10x/reviews/2026-07-15-unified-source-contract-parent-closure-review.md`.

## Blockers

None.
