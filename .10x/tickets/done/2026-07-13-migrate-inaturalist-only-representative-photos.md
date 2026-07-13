Status: done
Created: 2026-07-13
Updated: 2026-07-13
Parent: `.10x/tickets/done/2026-07-11-upgrade-representative-bird-photos.md`
Depends-On: `.10x/tickets/done/2026-07-13-implement-inaturalist-only-representative-photos.md`

# Migrate iNaturalist-only representative photos

## Scope

After implementation gates pass, perform exactly one explicit serialized full catalog photo-only re-evaluation and one explicit serialized saved-plan photo-only re-evaluation under the active iNaturalist-only specification. Verify app/API availability and protected state.

## Acceptance criteria

- Preflight proves no competing DuckDB writer and captures exact protected fingerprints/counts and external hashes without copying personal values into records.
- All 706 catalog identities are re-evaluated in stable resumable order through iNaturalist-only logic; non-binomial/hybrid identities persist typed unavailable without network requests.
- Every saved Trip Planner recommendation is re-evaluated photo-only after catalog completion; writers do not overlap.
- Every current catalog identity and planner recommendation has exactly one fully validated iNaturalist available result or typed placeholder; zero Wikimedia/GBIF representative rows remain.
- `task app` API payloads accept typed unavailable rows, `/birds` can load with mixed available/placeholders, and GET/browser paths perform no discovery or writes.
- Calls, recommendation/catalog facts, timestamps, personal observations/Watches, calendar/outbox, credentials, source-refresh state, warehouse/SQLMesh state, external files, and unrelated state remain unchanged within recorded fingerprints.
- No model, email, routine source/catalog-facts/AVONET/call refresh, recommendation regeneration, or binary image/audio download/storage occurs.
- Completion inspection is network/write-free and proves rerun no-op without a second live apply.
- Focused post-migration and aggregate gates pass.

## Explicit exclusions

No source refresh, new provider, direct occurrence fallback, manual SQL deletion/reset, scheduled media refresh, or unrelated data repair.

## Evidence expectations

Record exact commands, request/provider/status/failure counts, checkpoints, before/after fingerprints, 706 catalog and planner cardinality/validation, app/API mixed-placeholder proof, no-op inspection, full gates, and an independent review.

## References

- `.10x/decisions/curated-inaturalist-only-representative-photos.md`
- `.10x/specs/curated-inaturalist-representative-bird-photos.md`
- `.10x/tickets/done/2026-07-13-implement-inaturalist-only-representative-photos.md`
- `.10x/evidence/2026-07-13-curated-selector-wdqs-retry-blocker.md`

## Progress and notes

- 2026-07-13: Opened after explicit user ratification. No live command has run.
- 2026-07-13: Execution began with fresh writer/process preflight and protected-state snapshot preparation.
- 2026-07-13: Bounded production-path iNaturalist v2/v1 probe passed. Exactly one catalog photo refresh completed at 706/706 with 624 queried identities, 622 available iNaturalist photos, and 84 placeholders. Exactly one subsequent saved-plan photo-only apply replaced all eight photos with eight available iNaturalist rows and inserted zero calls.
- 2026-07-13: Post-state strict reconstruction found 706 catalog and eight planner singletons, zero Wikimedia/GBIF representative rows, zero duplicates/missing rows, and a network/write-free planner dry-run with zero targets/lookups. `/api/birds`, `/api/v1/birds`, and `/birds` returned 200; the JSON catalog returned 622 available/84 placeholders without changing the database hash.
- 2026-07-13: Eighty-six protected fingerprints and 19 external hashes matched before, after, and after gates. Focused 159 Python/145 frontend and full 776 Python/295 frontend tests plus all static/security/build/SQLMesh/hooks/diff gates passed. Evidence: `.10x/evidence/2026-07-13-inaturalist-only-representative-photo-migration.md`. Review: `.10x/reviews/2026-07-13-inaturalist-only-representative-photo-migration-review.md`.
- 2026-07-13 retrospective: Full-contract completion validation correctly forced superseded attempted-source rows into the controlled migration while preserving 82 non-queryable placeholders without provider calls. Separating preflight, catalog writer, planner writer, read-only no-op inspection, and final fingerprints made exactly-once ownership auditable. The supported JSON catalog route is `/api/birds`; `/api/v1/birds` currently resolves through compatibility/static routing, which was recorded as a limit rather than silently described as the JSON API. These lessons are captured in the active spec and migration evidence; no separate follow-up is required.

## Blockers

None. Acceptance criteria are satisfied and independent review passes.
