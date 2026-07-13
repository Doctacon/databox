Status: done
Created: 2026-07-11
Updated: 2026-07-11
Parent: `.10x/tickets/done/2026-07-11-upgrade-representative-bird-photos.md`
Depends-On: `.10x/tickets/done/2026-07-11-upgrade-map-catalog-and-refresh-controls.md`

# Implement curated representative-photo selector

## Scope

Implement the shared server-side metadata-only selector governed by `.10x/specs/superseded/curated-representative-bird-photos.md`:

- exact Wikidata P225 / P18 discovery;
- Commons `imageinfo` validation, attribution sanitation, bounded thumbnail URLs, quality floor, and deterministic ranking;
- exact active species-rank iNaturalist v2 resolution followed by v1 `/v1/taxa/{id}` curated `taxon_photos` metadata;
- provider-specific safe URL/license/identity validators;
- typed available/unavailable evidence with `wikimedia_commons` and `inaturalist` sources;
- bounded HTTP, response size, candidate counts, user agent, rate limits, and injectable transports for tests.

Preserve GBIF occurrence helper behavior needed by non-representative evidence until inspected consumers prove it removable. Do not run live catalog/planner migration in this ticket.

## Acceptance criteria

- Source order, stopping behavior, exact identity, 1,000×750 floor, license/attribution, URL, and ranking scenarios from the governing spec have deterministic tests.
- Wikimedia candidate selection is invariant under provider response reordering.
- iNaturalist fallback chooses the first eligible curated position and rejects static-host/null-license photos.
- Wikimedia transport/malformed response stops unavailable and does not call iNaturalist.
- Successful no-eligible Wikimedia result may call iNaturalist exactly once per taxon within bounded policy.
- Neither selector downloads image bytes or uses model/browser discovery.
- Existing Xeno-canto call selection and GBIF occurrence evidence remain unchanged.
- Strict typing, Ruff, formatting, MyPy, focused Python tests, and secret/static checks pass.

## Evidence expectations

Record commands, test counts, source/URL adversarial cases, no-binary/no-model limits, and diff scope in a dedicated evidence record. No live provider call is required for unit evidence; a bounded read-only smoke may be performed only after implementation with no persistence.

## Explicit exclusions

No DuckDB migration, browser UI change, map behavior change, call-media change, Macaulay, direct iNaturalist observation fallback, fuzzy identity, or binary handling.

## Progress and notes

- 2026-07-11: Opened from ratified decision/spec after source research.
- 2026-07-12: Read all governing records and inspected existing GBIF/Xeno-canto/catalog media code before editing.
- 2026-07-12: Bounded authorized live metadata probes found that public iNaturalist API v2 exact taxon routes do not expose the ordered curated `taxon_photos` shortlist, including with `fields=all`; candidate v2 shortlist routes returned 404. Evidence: `.10x/evidence/2026-07-12-inaturalist-v2-taxon-photo-gap.md`.
- 2026-07-12: No implementation file or test was created. Parent directed this worker to block rather than silently use the v1 taxon representation.
- 2026-07-12: User ratified v2 exact taxon resolution followed by v1 `/v1/taxa/{id}` curated-shortlist metadata. Active authority: `.10x/decisions/inaturalist-curated-photo-api-split.md` and updated governing spec. Execution resumed.
- 2026-07-12: Implemented the shared metadata-only selector and strict offline validators in `packages/databox/databox/curated_photo.py`; added 26 deterministic tests in `tests/test_curated_photo.py`.
- 2026-07-12: Final focused regression set passed 70/70. Full Ruff/format/MyPy plus secret/static/diff/no-staged gates passed. Evidence: `.10x/evidence/2026-07-12-curated-photo-selector-implementation.md`.
- 2026-07-12: Adversarial implementation review passed at `.10x/reviews/2026-07-12-curated-photo-selector-review.md`. Every acceptance criterion maps to deterministic tests or static inspection.
- 2026-07-12: Retrospective: resolving exact Wikidata identity in a separate bounded query prevents a P18 candidate cap from hiding duplicate exact-name entities; this invariant is encoded in source/tests and needs no separate skill. No follow-up remains in this ticket.

## Blockers

None.
