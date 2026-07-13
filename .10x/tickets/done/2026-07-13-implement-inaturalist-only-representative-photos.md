Status: done
Created: 2026-07-13
Updated: 2026-07-13
Parent: `.10x/tickets/done/2026-07-11-upgrade-representative-bird-photos.md`
Depends-On: `.10x/tickets/done/2026-07-12-repair-curated-catalog-refresh-ownership.md`, `.10x/tickets/done/2026-07-12-harden-trip-planner-curated-photo-resume.md`, `.10x/tickets/done/2026-07-12-repair-curated-photo-frontend-contracts.md`

# Implement iNaturalist-only representative photos

## Scope

Replace the superseded Wikimedia-first selector and contracts with the active curated iNaturalist-only specification across selector, catalog/planner persistence boundaries, API serialization, browser validation, presentation, CLIs, tests, and run observability. Delete Wikimedia/Wikidata representative-photo code rather than retaining a dormant branch. Repair the observed `invalid unavailable photo` whole-catalog failure so typed unavailable rows render Rufous placeholders.

## Acceptance criteria

- Representative-photo discovery performs only iNaturalist v2 exact identity plus v1 curated shortlist requests.
- No WDQS, Wikidata, Commons, Wikimedia host, P225/P18, Wikimedia ranking, thumbnail hash/title, or source-order branch remains in active implementation or browser contracts.
- Available results validate/persist/serialize only provider `inaturalist`; GBIF remains occurrence context only.
- Typed unavailable results are strictly validated as valid data and one unavailable row cannot invalidate catalog/profile/map/planner responses.
- Exact species identity, cross-version consistency, curated-order selection, dimensions, allowed licenses, attribution, bounded URLs, redirect policy, rate limits, checkpoints, metadata-only persistence, and GET purity remain.
- Catalog/profile/Field Map/new planner/saved planner use one coherent strict contract and Rufous placeholder behavior.
- Deterministic tests cover first-eligible shortlist order, no eligible, unavailable mixed into a valid catalog, malformed unavailable payload, non-binomial no-network, identity mismatch, URL/license/dimension attacks, interruption/resume, GET no-network/write, and legacy Wikimedia/GBIF rejection.
- Focused Python/frontend tests, full Python/frontend, TypeScript, build/bundle, Ruff/format/MyPy, secret/diff/hooks, and relevant SQLMesh non-mutating gates pass before migration.

## Explicit exclusions

No live migration, model call, source/AVONET/call refresh, email, binary media storage, new provider, fuzzy taxonomy, or unrelated UI work.

## Evidence expectations

Record deleted source surfaces, exact focused/full gate counts, forbidden-Wikimedia-network tests, typed-unavailable browser/API evidence, GET purity, and honest physical-browser/assistive-technology limits. Create an independent adversarial review before closure.

## References

- `.10x/decisions/curated-inaturalist-only-representative-photos.md`
- `.10x/decisions/inaturalist-curated-photo-api-split.md`
- `.10x/specs/curated-inaturalist-representative-bird-photos.md`
- `.10x/tickets/cancelled/2026-07-12-repair-curated-selector-source-integrity.md`
- Screenshot supplied 2026-07-13 showing `invalid unavailable photo` on Arizona Birds.

## Progress and notes

- 2026-07-13: Opened after explicit user ratification. No implementation has begun.
- 2026-07-13: Replaced the active selector, persistence/API/browser contracts, provider labels, and tests with curated iNaturalist-only behavior. Deleted Wikimedia/Wikidata/Commons source logic rather than retaining a dormant branch. Typed unavailable rows with exact scientific identity now load as placeholders; malformed unavailable rows still fail closed.
- 2026-07-13: Focused gates passed with 172 Python tests and 145 frontend assertions. Full gates passed with 776 Python tests, three snapshots, 86.33% coverage, 295 frontend tests, TypeScript/build/bundle audit, Ruff/format/MyPy, secrets/generated/docs/source-layout, 13 SQLMesh tests, all pre-commit hooks, diff check, and empty staging. Evidence: `.10x/evidence/2026-07-13-inaturalist-only-representative-photo-implementation.md`. Independent self-review: `.10x/reviews/2026-07-13-inaturalist-only-representative-photo-implementation-review.md`.
- 2026-07-13 retrospective: Eliminating the superseded provider removed substantially more validation and operational surface than adding another fallback would have. The observed whole-catalog failure came from treating exact identity retained by a typed unavailable result as active media; unavailable validation must distinguish safe identity metadata from forbidden active URLs/attribution. A shared mutable frontend fixture briefly contaminated later tests, reinforcing that adversarial response fixtures must be cloned before mutation. These lessons are encoded in the active spec and regression tests; no separate follow-up record is required.

## Blockers

None. Acceptance criteria are satisfied; live re-enrichment remains exclusively owned by the dependent migration ticket.
