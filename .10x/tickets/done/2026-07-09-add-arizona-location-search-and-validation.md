Status: done
Created: 2026-07-09
Updated: 2026-07-09
Parent: .10x/tickets/done/2026-07-09-improve-trip-planner-location-and-results.md
Depends-On: None

# Add Arizona location search and validation

## Scope

Implement `.10x/specs/arizona-trip-location-resolution.md` across the local Python API, planner, and React form.

Required work:

- add a bounded local API endpoint backed by Open-Meteo geocoding,
- normalize comma/state suffix searches so `Prescott, Arizona` can find `Prescott`,
- return stable typed suggestion objects with display name, coordinates, timezone, and Arizona region identity,
- add a debounced, cancellable, keyboard-accessible React combobox/listbox,
- preserve manual coordinate input and known local aliases,
- reject outside-Arizona coordinates before weather/evidence/model/persistence,
- detect the positive-longitude Prescott-shaped mistake without silently correcting it,
- ensure coordinate inputs retain `US-AZ` filtering for eBird/GBIF evidence,
- add API/planner/frontend tests for named search, selection, stale requests, keyboard behavior, geocoder failure, correct coordinates, positive-longitude error, and outside-Arizona rejection.

## Explicit exclusions

- No global bird recommendations or global ingestion.
- No map UI.
- No proprietary geocoder.
- No silent coordinate sign change.
- No unrelated result-view changes.

## Acceptance criteria

- `Prescott` and `Prescott, Arizona` produce a selectable Prescott, Arizona suggestion.
- Selecting Prescott persists its normalized name, latitude/longitude, timezone, and `US-AZ` identity.
- `34.54,112.50` fails before source/model calls and suggests checking the missing negative sign.
- `34.54,-112.50` validates as Arizona and retains Arizona evidence filters.
- Outside-Arizona names/coordinates cannot create a plan.
- Autocomplete is keyboard accessible, bounded, debounced, and cancels stale responses.
- Geocoder unavailability is user-safe and valid Arizona coordinates/known aliases remain usable.
- Focused tests, frontend checks, Ruff, MyPy, CI, docs, and secret scans pass.

## Evidence expectations

Record API/frontend tests, upstream response fixtures, validation-before-side-effect assertions, accessibility assertions, exact commands/results, and independent review.

## Progress and notes

- 2026-07-09: Added bounded Open-Meteo Arizona geocoding through `GET /api/locations`, suffix normalization for `Prescott, Arizona`, stable typed suggestions, and safe upstream failure handling.
- 2026-07-09: Added pre-side-effect Arizona validation for selected places, aliases, and coordinates. Positive Prescott-shaped longitude fails with an explicit negative-longitude suggestion; valid coordinates retain `US-AZ` and `America/Phoenix`.
- 2026-07-09: Added debounced/cancellable accessible React combobox behavior and deterministic API/planner/frontend tests.
- 2026-07-09: Initial independent review found rectangular boundary false positives and an unnormalized urllib timeout path.
- 2026-07-09: Replaced the rectangle with an in-repo generalized official US Census TIGERweb Arizona polygon and inclusive deterministic point-in-polygon validation. Tests reject reviewer examples `36.9,-114.8` and `31.3,-114.8` while accepting Prescott, Phoenix, Yuma, and a stored boundary vertex.
- 2026-07-09: Added typed geocoder error normalization for direct/socket timeouts and HTTP/URL failures; the API returns stable JSON and the frontend preserves coordinate fallback.
- 2026-07-09: Focused Python checks passed 37 tests; frontend passed typecheck, nine tests, build, and bundle audit; full CI passed 209 tests at 82.48% coverage; strict docs build passed.
- 2026-07-09: Evidence updated in `.10x/evidence/2026-07-09-arizona-location-search-and-validation.md`.
- 2026-07-09: Independent re-review passed after confirming the Census polygon coordinate-for-coordinate against a fresh official retrieval and directly probing timeout, socket-timeout, HTTP, and URL failures. Review: `.10x/reviews/2026-07-09-arizona-location-search-and-validation-review.md`.
- 2026-07-09: Retrospective: a rectangle is not an Arizona boundary and transport safety must test the concrete exception classes emitted by urllib. The official generalized boundary module and failure-normalization tests preserve both lessons in executable form; no additional knowledge or skill record is needed.

## Blockers

None.
