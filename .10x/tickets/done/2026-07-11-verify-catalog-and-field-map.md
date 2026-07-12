Status: done
Created: 2026-07-11
Updated: 2026-07-11
Parent: .10x/tickets/done/2026-07-11-improve-catalog-and-add-field-map.md
Depends-On: .10x/tickets/done/2026-07-11-build-catalog-sort-and-filters.md, .10x/tickets/done/2026-07-11-fix-bird-profile-information-layout.md, .10x/tickets/done/2026-07-11-alphabetize-text-dropdown-options.md, .10x/tickets/done/2026-07-11-build-rufous-field-map-ui.md

# Verify catalog discovery and Field Map

## Scope

Run aggregate correctness, privacy/source-authority, architecture/open-source, map network, and UX/accessibility verification across all children and preserved Rufous behavior.

## Acceptance criteria

- Full network-blocked Python/frontend/SQLMesh/Soda/type/build/bundle/docs/static/hooks gates pass with warehouse hashes unchanged.
- Live 706 summary and map eligible counts reconcile to strict source authority; no parent inference, private evidence, personal data, remote request, or excess geometry.
- All sort/filter/bucket/dropdown/layout/map interaction and accessible-list matrices pass.
- Independent architecture, correctness, privacy/security, and UX/accessibility reviews pass.
- Records/specs/decisions/tickets/evidence/reviews/retrospectives are coherent before parent closure.

## Exclusions

No new behavior, source refresh, live delivery/model/provider call, or unrelated refactor.

## Evidence expectations

One aggregate evidence record and focused independent reviews mapping every criterion.

## Progress and notes

- 2026-07-11: Inspected the governing decision/four focused specs, all implementation/repair/investigation tickets and evidence, and all ten non-aggregate child pass reviews. Child graph and done dependencies are coherent.
- 2026-07-11: Captured the live warehouse hash, mtime, size, personal observation safe checksum/count, Watch count, and cancellation count before verification. No loopback Uvicorn writer was running. After every gate and final reconciliation, all values matched exactly: warehouse `87d45e…`, one coherent personal observation, zero Watches/cancellations.
- 2026-07-11: Full network-blocked Python passed 702/702, three snapshots, 86.63% coverage. Full frontend initially exposed one nondeterministic lazy-route focus assertion; the separately authorized test-only stabilization `.10x/tickets/done/2026-07-11-stabilize-field-map-heading-focus-test.md` changed only immediate assertion timing. Focused map tests then passed three consecutive 4/4 runs and full frontend passed 249/249 plus typecheck/build/bundle audit.
- 2026-07-11: SQLMesh passed 13/13, lint, and clean prod diff; Soda passed 25/25 contracts and 125 checks; Ruff/format/MyPy/secrets/seven-source/generated/docs/MkDocs/pre-commit/diff/no-stage gates passed. Data and SQLMesh state hashes remained unchanged.
- 2026-07-11: Live read-only/network-forbidden reconciliation returned 706 unique summaries (624 species/82 hybrids), 600 exact mass/habitat values, 106 null, zero hybrid trait leaks; 1,575 unique strict map encounters across 152 taxa/208 locations, three access warnings, all exact Arizona polygon; and exact 16-feature/30,927-byte local artifact hash. Aggregate evidence: `.10x/evidence/2026-07-11-catalog-and-field-map-aggregate-verification.md`.

- 2026-07-11: Independent architecture, correctness, privacy/security/source, and UX/accessibility reviews passed. Reviews: `.10x/reviews/2026-07-11-catalog-field-map-architecture-review.md`, `.10x/reviews/2026-07-11-catalog-field-map-correctness-review.md`, `.10x/reviews/2026-07-11-catalog-field-map-privacy-security-review.md`, and `.10x/reviews/2026-07-11-catalog-field-map-ux-accessibility-review.md`.
- 2026-07-11: Retrospective preserved concurrent-user-state reconciliation, map local-resource boundaries, exact data eligibility, and lazy focus timing in focused evidence/tests. Physical GPU/screenshot/assistive-technology validation remains an accepted evidence limit with no action.

## Blockers

None.
