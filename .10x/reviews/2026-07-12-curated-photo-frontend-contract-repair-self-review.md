Status: recorded
Created: 2026-07-12
Updated: 2026-07-12
Target: `.10x/tickets/done/2026-07-12-repair-curated-photo-frontend-contracts.md`, curated-photo frontend repair diff
Verdict: pass

# Curated-photo frontend contract repair self-review

## Assumptions tested

- Catalog and planner do not retain divergent provider/license/identity grammars.
- Wikimedia paths are bound to the persisted file identity and actual MD5 buckets, not merely an approved host/prefix.
- Strict validation rejects malformed data before partial planner rendering.
- Rufous fallback artwork remains decorative while failure/unavailable meaning remains accessible.
- Field Map source/license destinations do not create links nested inside native encounter buttons.
- Persistent attribution is not made a noisy live region.

## Findings

No blocker or significant finding remains within this ticket.

- `birdApi.ts`, `tripPlanValidation.ts`, and `App.tsx` all call `validateAvailableCuratedPhoto`; catalog adds only its separate exact response-key/lookup timestamp checks.
- Wikimedia tests use a known Commons MD5 mapping (`Mexican_Jay.jpg -> e/e4`, `Elegant_Trogon.jpg -> 4/46`) and independently mutate record title, repeated thumbnail title, both hash buckets, width, source title, credentials/port/query/fragment/traversal, extension, license family/version/URL, and attribution text.
- Planner exact-key validation separately rejects extra fields and fails the entire response before recommendation rendering.
- Trip Planner renders the same `PhotoArea` component for create and saved-plan results, so the Rufous fallback and semantic failure state are shared rather than duplicated.
- Field Map links are siblings of the native button. Attribution and links remain after failure; `role=status` appears only after the image error.
- The intermediate test-file truncation was repaired without resetting other dirty work; the final file is repository base plus the already-present map changes and this ticket's assertions, and both focused/full suites pass.

## Verdict

Pass. The repair resolves the frontend findings without provider expansion, visual redesign, MapLibre-control changes, backend contract mutation, or live side effects.

## Residual risk

No physical-browser, narrow-viewport, forced-colors, keyboard/assistive-technology, or live remote-image session was run. jsdom and build evidence cannot establish visual subject quality, actual wrapping, or announcement behavior in every screen reader. The existing large MapLibre chunk advisory is unchanged and unrelated.
