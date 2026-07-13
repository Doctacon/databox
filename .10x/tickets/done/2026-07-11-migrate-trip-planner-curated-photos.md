Status: done
Created: 2026-07-11
Updated: 2026-07-12
Parent: `.10x/tickets/done/2026-07-11-upgrade-representative-bird-photos.md`
Depends-On: `.10x/tickets/done/2026-07-11-implement-curated-photo-selector.md`

# Migrate Trip Planner to curated photos

## Scope

Use the shared curated selector for new Trip Planner recommendation photos, update Python persistence/API and strict TypeScript validation/presentation for the two curated providers, and update the existing explicit recommendation-media backfill to replace every saved recommendation photo.

After code and non-live gates pass, run the explicitly authorized photo-only saved-plan migration with no model call and no call-media refresh.

## Acceptance criteria

- New plans enrich fixed recommendations with the curated selector without changing recommendation identity, rank, confidence, rationale, or model behavior.
- Planner APIs/browser validators accept provider-specific curated photo metadata and reject legacy/mismatched active URLs while preserving separate GBIF occurrence-context evidence.
- Explicit backfill reevaluates all persisted recommendation photos, including currently available GBIF and unavailable rows, and leaves one coherent photo result per recommendation.
- Backfill is resumable/idempotent and never duplicates active photo evidence.
- Saved plan/recommendation IDs, text, rank, confidence, rationale, location, weather, non-photo evidence, calls, creation timestamps, calendar/outbox state, and personal state remain unchanged, supported by pre/post checksums or bounded value comparisons.
- No model call, email, catalog migration, source refresh, call lookup, or image binary request occurs during backfill.
- Focused Python/frontend tests plus strict typing/static/build gates pass.

## Evidence expectations

Record preflight, exact live command, recommendation/photo counts before and after, provider/status counts, saved-plan safe checksum comparisons, model-call absence, unchanged calendar/outbox/personal counts, and limits. Redact personal text where not needed and never store credentials/raw provider payloads.

## Explicit exclusions

No recommendation regeneration, model invocation, call-media replacement, calendar mutation, catalog refresh, map behavior change, or binary caching.

## Progress and notes

- 2026-07-11: User explicitly authorized migration of already-saved planner photos.
- 2026-07-12: Integrated the shared curated selector for production new-plan photos; extended Python/API/TypeScript contracts and provider-aware presentation; added saved-photo-only per-recommendation checkpointing and idempotence coverage. Focused gates passed (86 Python and 88 frontend tests).
- 2026-07-12: Preflight found eight legacy photo targets and no competing writer. Ran exactly one authorized `--curated-photos` command: eight replaced, eight available iNaturalist results, zero calls inserted, zero remaining, zero duplicates.
- 2026-07-12: Protected comparisons passed before and after all gates: 86 non-evidence tables/subsets, 109 non-photo evidence rows, and 19 external files unchanged. Full closure gates passed: 769 Python tests/three snapshots/86.44% coverage, Ruff/format, MyPy over 99 source files, 273 frontend tests, TypeScript, production build/bundle audit, and 13 SQLMesh tests. Evidence: `.10x/evidence/2026-07-12-trip-planner-curated-photo-migration.md`. Review: `.10x/reviews/2026-07-12-trip-planner-curated-photo-migration-review.md`.
- 2026-07-12 retrospective: Photo-only migrations need semantic fingerprints rather than a whole DuckDB file hash because the intended evidence rows change. Hash every protected table, hash the mutable table's excluded rows separately, and repeat comparisons after gates. Per-recommendation commits plus current-curated no-op inspection provide safe resume semantics without destructive counter or evidence resets.

## Blockers

None.
