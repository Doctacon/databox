Status: done
Created: 2026-07-11
Updated: 2026-07-11
Parent: .10x/tickets/2026-07-11-improve-catalog-and-add-field-map.md
Depends-On: .10x/tickets/done/2026-07-11-implement-catalog-media-enrichment.md

# Expand catalog summary for discovery

## Scope

Add exact nullable `mass_g` and `habitat` fields to the modeled catalog summary query, strict FastAPI response, strict browser validator/types, fixtures, contracts, and tests under `.10x/specs/arizona-catalog-discovery-controls.md`.

## Acceptance criteria

- All 706 summaries expose exact modeled mass/habitat or null; hybrids/unmatched taxa remain null without parent inference.
- Backend/browser reject extra, malformed, non-finite/non-positive mass and overlong/invalid habitat.
- Existing identity/category/media/cardinality/GET no-network/no-write contracts remain unchanged.
- Full API/frontend/SQLMesh/Soda/privacy gates pass and production diff remains clean.

## Exclusions

No controls/UI, map API, new model/provider/source, or warehouse mutation.

## Evidence expectations

Record exact live distribution/null reconciliation, strict attacks, full gates, and independent review.

## Progress and notes

- 2026-07-11: Added exact modeled nullable `mass_g` and `habitat` to the catalog summary query, strict FastAPI/browser contracts, summary types, API/browser fixtures, and malformed/extra/non-finite/non-positive/blank/control/overlong attack tests. Profile responses reuse the same summary fields without duplicate modeled columns. Hybrids remain null without inference.
- 2026-07-11: Live read-only reconciliation found 706 summaries, 600 exact masses and habitats, 106 null masses and habitats, zero hybrid non-null values, and zero invalid mass/habitat values. A network-forbidden live catalog GET returned all 706 exact summaries without changing the warehouse hash.
- 2026-07-11: Focused API passes 20/20; full network-blocked Python passes 674/674 with three snapshots and 86.58% coverage; frontend passes 222/222 plus typecheck/build/bundle audit; SQLMesh 13/13 with clean prod diff; Soda 25/25; lint, format, MyPy, secrets, sources, generated drift, and privacy suites pass. Evidence: `.10x/evidence/2026-07-11-catalog-summary-discovery-fields.md`.
- 2026-07-11: Repaired independent review blockers: backend and browser now reject whitespace-only habitat and enforce `mass_g=null` plus `habitat=null` whenever traits are unavailable or the taxon is a hybrid. Exact unavailable-species and hybrid relationship attacks cover both fields without relying on category-count failure. Focused API passes 25/25; full network-blocked Python passes 679/679 with three snapshots and 86.59% coverage; frontend remains 222/222 with typecheck/build/bundle audit; repository static/privacy gates remain green.
- 2026-07-11: Independent follow-up review passed. Review: `.10x/reviews/2026-07-11-catalog-summary-discovery-fields-review.md`.
- 2026-07-11: Retrospective preserved null relationship and whitespace trust-boundary failures as strict regressions; no additional record is needed.

## Blockers

None.
