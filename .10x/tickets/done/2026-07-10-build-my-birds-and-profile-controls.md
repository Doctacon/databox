Status: done
Created: 2026-07-10
Updated: 2026-07-10
Parent: .10x/tickets/2026-07-09-build-local-birding-pokedex.md
Depends-On: .10x/tickets/done/2026-07-10-implement-personal-bird-collection-storage-and-api.md

# Build My Birds and profile collection controls

## Scope

Implement the React “My Birds” navigation and Life List, Observations, Wishlist, and Watches surfaces plus explicit species-profile controls governed by `.10x/specs/personal-bird-collection.md`.

Use strict runtime API validation, local catalog species selection, native forms/confirmation/dialog semantics, route title/focus/history behavior, responsive states, and clear independence among observed/wishlist/watch state.

## Acceptance criteria

- Navigation/direct/back-forward routes preserve Trip Planner and Arizona Birds behavior.
- Observation create/edit/hard-delete flows require species/date, support optional location/notes, confirm deletion, and refresh derived life-list state.
- Wishlist and watch add/remove/pause/resume/edit controls are explicit, idempotent, and never mutate another state.
- Watch forms use validated Arizona center selection and 1–300-mile radius; no global origin is implied.
- Hybrid/stale/empty/loading/error/busy states, keyboard/focus behavior, responsive layout, and non-color status cues pass.
- Browser bundle, logs, rendered errors, and tests contain no personal fixture values or server credentials; existing planner/catalog/media tests remain green.

## Explicit exclusions

No match evaluation, target planning, weather/model call, calendar/outbox/SMTP side effect, map, remote account, or eBird import.

## Evidence expectations

Record exact UI/API mapping, route/accessibility behavior, state independence, confirmations, sparse/error cases, bundle/secret scan, and complete frontend regression.

## Progress and notes

- 2026-07-10: Ticket depends on the collection API contract and owns only browser presentation/mutations.
- 2026-07-10: Implemented native `/my-birds` navigation and Life List/Observations/Wishlist/Watches surfaces, strict bounded collection client validation, current-catalog selectors, observation create/edit/confirmed hard delete, independent wishlist/watch mutations, per-watch Arizona center/radius create/edit/pause/resume/confirmed delete, stale/hybrid/empty/error states, and explicit species-profile controls without downstream calls.
- 2026-07-10: `task app:check` passed TypeScript, 79 browser tests, build, and bundle audit; 44 focused backend regressions passed; complete network-disabled Python suite passed 324/324 with three snapshots and 86.30% coverage; secret scan, focused hooks, and diff checks passed. Evidence: `.10x/evidence/2026-07-10-my-birds-and-profile-controls.md`.
- 2026-07-10: Review repair hardened calendar-date/leap-year and UTC timestamp parsing, safe-integer counts, chronological and collection-state relationships, and stale identity response invariants. Failed observation creates/edits now preserve all form values and edit identity while focusing the safe error. A synchronous mutation guard plus disabled row/profile controls prevents overlapping mutations. Sixteen direct boundary tests and two UI failure/concurrency tests were added; `task app:check` passes all 97 browser tests, typecheck, build, and bundle audit, and 44 focused backend regressions remain green.
- 2026-07-10: Final review repair keys observation/watch/profile forms by immutable species/item identity, strictly checks combined-state species identity, and replaces component-local guards with one module-level observable mutation coordinator that survives route unmount/navigation. Two-row switch tests prove every field and mutation target reset; a profile-to-My-Birds pending-request test proves one global mutation and cross-surface disablement. Focused boundary/UI tests pass 29/29 and `task app:check` passes 101 browser tests, typecheck, build, and bundle audit.
- 2026-07-10: Cross-route coherence repair adds a monotonic success-only mutation revision and revision-driven bounded reloads with request-generation race guards. A pending profile wishlist mutation now refreshes the mounted My Birds destination exactly once after success; failures do not invalidate; rapid route changes ignore stale loads. Focused tests pass 31/31 and `task app:check` passes 103 browser tests, typecheck, build, and bundle audit.
- 2026-07-10: Final independent review passed with no blocker. Review: `.10x/reviews/2026-07-10-my-birds-and-profile-controls-review.md`.
- 2026-07-10: Retrospective preserved strict client relationship validation, shared cross-route mutation serialization/invalidation, keyed editor identity, and stale-load guards directly in tests; no additional skill record is needed.

## Blockers

None.
