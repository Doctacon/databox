Status: open
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

## Blockers

None.
