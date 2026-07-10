Status: done
Created: 2026-07-09
Updated: 2026-07-09
Parent: None
Depends-On: None

# Add recommendation-card photos and calls

## Aggregate outcome

Replace the standalone Call and Media Examples section with one persisted licensed photo and one persisted representative call result inside every high-likelihood and uncommon-plausible recommendation card. Reorder the plan so Weather and Elevation follows Field Plan and Evidence and Provenance is final with Agent Workflow inside it.

This is a parent plan and is not executable directly.

## Governing records

- `.10x/decisions/request-time-recommendation-media-enrichment.md`
- `.10x/research/2026-07-09-recommendation-card-media-enrichment.md`
- `.10x/specs/recommendation-media-enrichment.md`
- `.10x/specs/recommendation-card-media-layout.md`
- `.10x/specs/xeno-canto-inline-audio.md`
- `.10x/specs/birding-agent-data-integrations.md`
- `.10x/specs/local-birding-trip-copilot-app.md`

## Child sequence

1. `.10x/tickets/done/2026-07-09-implement-request-time-recommendation-media.md`
2. `.10x/tickets/done/2026-07-09-integrate-media-into-recommendation-cards.md`
3. `.10x/tickets/done/2026-07-09-backfill-existing-plan-media.md`
4. `.10x/tickets/done/2026-07-09-verify-recommendation-card-media.md`

The UI depends on the stable recommendation-centric media API. Backfill follows both implementation children so existing plans can be inspected through the final UI. Verification follows all implementation and data-mutation work.

## Aggregate acceptance criteria

- Every recommendation persists exactly one photo result and one call result, including explicit unavailable states.
- GBIF photo lookup is exact-species and Arizona-scoped, preserves license/creator/source attribution, and activates only safe eligible media.
- Xeno-canto selection prefers Arizona, falls back globally only when necessary, and labels scope.
- Media lookup failure never removes, changes, reorders, or fails a factual recommendation.
- `data/databox.duckdb` remains the only database and stores all selected metadata, attribution, unavailable states, and traces; no media binary is stored or proxied.
- Every species card displays one lazy photo or placeholder and one native call player or placeholder with attribution/source/license.
- The standalone Call and Media Examples section is absent.
- Result order is Field Plan; Weather and Elevation; High-likelihood Species; Uncommon but Plausible Targets; Evidence and Provenance.
- Agent Workflow remains accessible inside the final Evidence and Provenance section.
- Existing plans are backfilled exactly once through an explicit idempotent command; GET endpoints remain read-only.
- SQLMesh/warehouse, planner/API, React/accessibility, licensing/URL security, CI, docs, bundle/secret, and no-binary-media checks pass.
- Independent aggregate review finds no unowned defect.

## Progress and notes

- 2026-07-09: User requested recommendation-centric photos/calls, removal of the standalone media section, and result reordering.
- 2026-07-09: Read-only investigation found the Queen Valley plan has eight recommendations; the current 1,000-row Xeno-canto slice covers calls for two, full Arizona data covers six, and global exact fallback covers all eight. Exact GBIF Arizona image searches returned licensed candidates for all eight.
- 2026-07-09: User ratified exact request-time lookup with persisted DuckDB metadata, Arizona-first/global call fallback, one photo plus one native call per card, non-blocking placeholders, recognized Creative Commons including noncommercial variants, no binary storage, and explicit existing-plan backfill.
- 2026-07-09: User ratified full Weather and Elevation as the second section and Agent Workflow inside the final Evidence and Provenance section.
- 2026-07-09: User explicitly authorized execution of all children.
- 2026-07-09: Request-time media enrichment child completed after independent repair/review of license, URL, geography, transport, fixture, and deterministic-selection boundaries.
- 2026-07-09: Recommendation-card UI child completed after independent repair/review of runtime media trust, mismatch suppression, license consistency, accessibility, section order, and responsive containment.
- 2026-07-09: Existing-plan backfill child completed after live 16/16 photo/call enrichment, Queen Valley 8/8, idempotent no-op, and independent transaction/repair-boundary review.
- 2026-07-09: Aggregate verification passed 100 focused tests, 50 React tests, 2 DeepEval tests, 11 SQLMesh tests, full 258-test CI at 84.09% coverage, strict docs, pre-commit, bundle/secret/binary/discovery audits, current warehouse/API checks, Quack architecture checks, and graph/diff checks. Evidence: `.10x/evidence/2026-07-09-recommendation-card-media-aggregate-verification.md`.
- 2026-07-09: Independent aggregate review returned pass with no unowned defect: `.10x/reviews/2026-07-09-recommendation-card-media-aggregate-review.md`.
- 2026-07-09: Retrospective: three boundaries dominate durable media correctness—validate cross-field source identity/license/geography before activation, treat browser JSON as untrusted runtime data, and make compatibility/backfill repairs exact-version and transaction-bounded. Focused selectors, rendered adversarial tests, and v2-only rollback/idempotency tests preserve these lessons; no additional knowledge or skill record is needed.

## Blockers

None.
