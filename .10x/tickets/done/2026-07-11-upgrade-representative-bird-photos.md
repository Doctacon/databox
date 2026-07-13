Status: done
Created: 2026-07-11
Updated: 2026-07-13
Parent: None
Depends-On: `.10x/tickets/done/2026-07-11-upgrade-map-catalog-and-refresh-controls.md`

# Upgrade representative bird photos

## Outcome

Replace arbitrary occurrence photos and the superseded Wikimedia dependency with exact curated iNaturalist taxon photos across catalog, profile, Field Map, new Trip Planner results, and saved Trip Planner results.

## Governing records

- `.10x/decisions/curated-inaturalist-only-representative-photos.md`
- `.10x/decisions/inaturalist-curated-photo-api-split.md`
- `.10x/specs/curated-inaturalist-representative-bird-photos.md`
- `.10x/decisions/superseded/globally-curated-catalog-bird-photos.md` (history)
- `.10x/specs/superseded/curated-representative-bird-photos.md` (history)
- `.10x/research/2026-07-11-bird-photo-source-quality.md`
- `.10x/specs/arizona-catalog-media.md`
- `.10x/specs/recommendation-media-enrichment.md`
- `.10x/specs/field-map-encounter-photo-preview.md`

## Child plan

1. `.10x/tickets/done/2026-07-11-implement-curated-photo-selector.md`
2. `.10x/tickets/done/2026-07-11-migrate-catalog-and-map-curated-photos.md` (depends on 1)
3. `.10x/tickets/done/2026-07-11-migrate-trip-planner-curated-photos.md` (depends on 1; code work may proceed separately from 2, but live DuckDB migration must be serialized)
4. `.10x/tickets/done/2026-07-13-implement-inaturalist-only-representative-photos.md` (supersedes the cancelled Wikimedia repair)
5. `.10x/tickets/done/2026-07-13-migrate-inaturalist-only-representative-photos.md` (depends on 4; catalog and planner writes serialized)
6. `.10x/tickets/done/2026-07-11-verify-curated-representative-photos.md` (aggregate verification after 4–5; includes final operational hardening and reconciliation children)

Before child 1 starts, close the existing map/wheel/refresh aggregate and parent so this change does not contaminate their acceptance baseline.

## Aggregate acceptance

- Exact active species-rank curated iNaturalist taxon photos are the only representative-photo source and use the ratified 1,000×750 quality floor.
- Wikimedia/Wikidata and GBIF/direct observations are absent from representative-photo discovery and activation.
- No GBIF/direct-observation fallback remains for representative photos; unavailable uses the Rufous placeholder.
- Catalog/profile/Field Map and new/saved planner results expose only validated curated metadata and bounded URLs.
- All 706 catalog rows and every persisted planner recommendation photo are explicitly and resumably migrated without model calls or unrelated state changes.
- GETs remain network-free/read-only; binaries remain remote and unstored.
- Full backend/frontend/static/privacy/secret gates and independent architecture, correctness, privacy/security/source, and UX/accessibility reviews pass.

## Exclusions

No call-media changes, encounter-evidence changes, Macaulay, proprietary source, fuzzy taxonomy, direct occurrence fallback, computer vision, human moderation UI, binary proxy/cache, scheduled media refresh, or map-only media store.

## Progress and notes

- 2026-07-11: Research measured exact Wikidata P18 presence for 616/624 catalog species and found curated eligible iNaturalist fallback photos for all ten sampled species.
- 2026-07-11: User ratified global curated source order, catalog + planner surfaces, Field Map inheritance, 1,000×750 floor, placeholder stopping rule, stop-on-Wikimedia-outage behavior, complete catalog migration, and saved-plan migration.
- 2026-07-12: Map/wheel/refresh aggregate and parent closed. `.10x/specs/superseded/curated-representative-bird-photos.md` activated. No semantic or dependency blocker remains.
- 2026-07-12: Execution could not launch child 1 because the prior harness process reached its subagent spawn limit; the user raised the limit and restarted Pi.
- 2026-07-12: Parent resumed active with no semantic, dependency, or operational blocker. Child 1 delegation began.

- 2026-07-12: User ratified the narrow v2 exact-resolution plus v1 curated-shortlist split. Decision/spec updated; child 1 resumed without changing any other semantics.
- 2026-07-12: Child 1 implemented and closed with 70 focused tests and passing adversarial review. Evidence: `.10x/evidence/2026-07-12-curated-photo-selector-implementation.md`. Child 2 catalog/Field Map integration and live migration began.
- 2026-07-12: Child 2 completed 706/706 current curated catalog rows with zero missing and passing full gates/review after resumability repairs. Evidence: `.10x/evidence/2026-07-12-catalog-photo-final-live-resume-and-verification.md`. Child 3 Trip Planner integration and saved-plan migration began.
- 2026-07-12: Child 3 completed the one authorized photo-only saved-plan migration: 8/8 available curated photos, zero calls or duplicates, all protected fingerprints unchanged, and full gates/review passed. Evidence: `.10x/evidence/2026-07-12-trip-planner-curated-photo-migration.md`.
- 2026-07-12: Aggregate non-review gates passed, but all four independent aggregate reviews failed with material source-integrity, persistence-ownership, planner-resume/backend, and frontend/UX findings. Four bounded repair tickets now own resolution under `.10x/tickets/done/2026-07-11-verify-curated-representative-photos.md`.
- 2026-07-13: Three repair tickets completed and all combined deterministic/full gates passed. Two bounded WDQS confirmations failed safely without data mutation. The user then explicitly superseded Wikimedia-first behavior with curated iNaturalist-only representative photos after observing the catalog `invalid unavailable photo` failure. Active decision/spec and two replacement child tickets were created; the WDQS repair ticket was cancelled as superseded.
- 2026-07-13: iNaturalist-only implementation child closed with 776 Python and 295 frontend tests plus all static/build/security gates passing. Evidence: `.10x/evidence/2026-07-13-inaturalist-only-representative-photo-implementation.md`. Serialized migration is the remaining implementation child before aggregate verification.
- 2026-07-13: Exactly-once serialized migration child closed with 706/706 strict catalog results (622 available/84 placeholders), eight/eight saved-plan photos available, zero calls inserted, all protected state unchanged, and all gates passing. Evidence: `.10x/evidence/2026-07-13-inaturalist-only-representative-photo-migration.md`. Aggregate verification is active.
- 2026-07-13: Final operational hardening and campaign reconciliation closed all review findings. The authoritative run owns all 706 rows with 624 lookups, 1,248 requests, and reconciled outcomes; eight planner singletons remain valid; all protected fingerprints and repository-visible durable artifacts validate. Architecture, correctness, privacy/security/source, and UX/accessibility final reviews pass. Parent closure review: `.10x/reviews/2026-07-13-inaturalist-only-representative-photo-parent-closure-review.md`.
- 2026-07-13: Retrospective learning preserved in `.10x/knowledge/curated-photo-operation-invariants.md`; remote-provider/physical-browser/assistive-technology limits have recorded no-action rationale. Parent closed.

## Blockers

None. All child tickets, aggregate acceptance, review gates, evidence, dependencies, and retrospective obligations are satisfied.
