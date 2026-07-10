Status: recorded
Created: 2026-07-10
Updated: 2026-07-10
Relates-To: .10x/tickets/done/2026-07-10-build-my-birds-and-profile-controls.md, .10x/specs/personal-bird-collection.md

# My Birds and species-profile collection controls

## What was observed

The React app now exposes a private local `/my-birds` route with Life List, Observations, Wishlist, and Watches surfaces while preserving Trip Planner and Arizona Birds routes.

- Native history navigation, direct static fallback, `My Birds · Databox` title, focused page heading, pressed-state section controls, responsive layout, and explicit loading/empty/error/success states are implemented.
- Observation forms use current 706-taxon catalog selection and required date with bounded optional personal location/notes. Edit preserves identity through the API. Permanent delete uses a modal native-dialog semantic, initial cancel focus, Escape cancellation, explicit irreversible wording, and `confirm=true` only after confirmation.
- Life List renders only API-derived count/first/latest facts; the browser does not store an observed flag independently.
- Wishlist add/remove and watch create/edit/pause/resume/delete are explicit independent mutations. Watch creation requires existing Arizona autocomplete selection and 1–300 miles, states that the center is per-watch, and performs no downstream action.
- Stale identities remain visible; stale paused watches cannot resume but can edit or delete. Hybrids are present in the exact current catalog selector without parent inference.
- Species profiles expose explicit observation, wishlist, watch create/pause/resume/delete controls. They fetch only combined state for that species—not all other watch centers. Existing watches link to My Birds for center/radius editing.
- `collectionApi.ts` rejects extra/malformed response fields, bounds every value/list, and maps only known server error codes to fixed safe browser messages. Arbitrary server detail is not rendered.
- Browser code calls only the existing local FastAPI collection/catalog/location routes. No matching, weather, model, calendar, SMTP, database, or credential access was added.

## Validation

```text
task app:check
- TypeScript passed
- 79 Vitest tests passed (7 new My Birds tests; 72 existing planner/catalog/weather tests)
- Vite production build passed
- bundle audit passed: 3 configured names and 3 configured values absent

uv run --no-sync pytest --no-cov -q \
  tests/test_personal_collection_api.py tests/test_bird_catalog_api.py tests/test_api.py
44 passed

uv run --no-sync pytest -q --record-mode=none --block-network
324 passed; 3 snapshots passed; coverage 86.30%

uv run --no-sync python scripts/check_secrets.py .
passed

pre-commit on all ticket files
git diff --check
passed
```

New browser tests cover direct/history/title/focus/empty states; observation create/edit/confirmed hard delete, focus trapping/Escape, and life-list refresh; wishlist/watch independence; stale watch pause/edit/resume guard; selected Arizona watch creation/radius and confirmed delete; explicit profile controls with zero implicit mutation/downstream calls; strict unexpected error suppression; and malformed/private-detail suppression.

The backend layout/static-fallback regression now includes `/my-birds`, responsive My Birds layouts, and mobile action wrapping.

## Post-review repair validation

Review findings were repaired at the browser trust and mutation boundaries:

- exact Gregorian calendar validation includes leap-year rules and rejects impossible dates;
- timestamps require bounded ISO date-time values with explicit UTC (`Z` or `+00:00`), valid fields, and chronological relationships;
- counts require nonnegative safe integers; life-list dates and observed/count and watched/active relationships must agree; stale identities cannot carry current-catalog metadata;
- failed/busy observation saves preserve date, location, notes, and edit identity and focus a bounded safe error;
- one synchronous mutation guard blocks same-tick overlap, while all visible mutating row/profile controls are disabled for the active mutation.

```text
cd app && npm test -- --run collectionApi.test.ts MyBirds.test.tsx
25 passed

 task app:check
97 browser tests passed
TypeScript passed
Vite production build passed
bundle configuration audit passed

uv run --no-sync pytest --no-cov -q tests/test_personal_collection_api.py tests/test_bird_catalog_api.py tests/test_api.py
44 passed

uv run --no-sync python scripts/check_secrets.py .
focused pre-commit
git diff --check
all passed
```

Sixteen direct response-boundary tests exercise leap days, impossible dates, missing/non-UTC/malformed timestamps, chronological inversions, unsafe counts, life-list ordering, inconsistent observed/watch state, independent wishlist state, stale metadata, and watch time ordering. Two UI tests prove failed create/edit preservation and error focus plus mutation serialization/disablement. The catalog navigation test now supplies the profile collection-state dependency explicitly.

## Final review repair validation

- Observation and watch editors are keyed by immutable item/species identity, and profile controls are keyed by profile species. Directly switching between two rows resets species, date, location, notes, center, radius, and mutation target.
- One module-level external-store coordinator atomically claims the browser collection-mutation slot before any await, notifies every mounted collection surface, and retains the claim across route/component unmount. Failed requests still preserve form input.
- Combined collection state must return the exact requested species code.

```text
cd app && npm test -- --run src/collectionApi.test.ts src/MyBirds.test.tsx
29 passed

task app:check
101 browser tests passed
TypeScript passed
Vite production build passed
bundle configuration audit passed

uv run --no-sync pytest --no-cov -q tests/test_personal_collection_api.py tests/test_bird_catalog_api.py tests/test_api.py
44 passed
```

The added adversarial tests cover mismatched collection-state species identity, two-row observation switching, two-row watch switching, and a pending profile mutation followed by navigation to My Birds. The cross-surface test proves the second surface is notified/disabled and only one mutation request occurs.

Post-repair complete validation also passed: the network-disabled Python suite passed 324/324 with three snapshots and 86.30% coverage; focused backend tests passed 44/44; MyPy passed all 82 source files; secret scan, focused pre-commit hooks, and `git diff --check` passed.

## Cross-route coherence repair

The shared mutation external store now exposes a monotonic successful-mutation revision independently from busy state. It increments exactly once after the mutation action resolves and never on failure. My Birds and species-profile controls subscribe to that revision and reload their bounded reads. Per-surface request generations plus effect cleanup prevent stale initial or prior-route responses from overwriting the newest state.

Adversarial tests prove a wishlist mutation started on a profile can complete after navigation to My Birds, trigger exactly one destination invalidation read, and render the added bird; a failed mutation performs no collection-state refetch; and rapid My Birds/profile/My Birds navigation ignores the old deferred response.

```text
cd app && npm test -- --run src/MyBirds.test.tsx src/collectionApi.test.ts
31 passed

task app:check
103 browser tests passed
TypeScript passed
Vite production build passed
bundle configuration audit passed

focused pre-commit
git diff --check
passed
```

## What this supports

The ticket's routes, typed client boundary, collection mutation flows, explicit state independence, current catalog selection, stale/hybrid states, per-watch center/radius, accessibility semantics, privacy, responsive layout, bundle safety, and complete regression criteria have executable evidence.

## Limits

- Automated DOM and CSS-contract tests cover focus, keyboard confirmation, native semantics, and responsive declarations; no separate screenshot-based visual audit was run.
- Final independent adversarial review passed and is recorded at `.10x/reviews/2026-07-10-my-birds-and-profile-controls-review.md`.
