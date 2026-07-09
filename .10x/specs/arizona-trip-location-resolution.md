Status: active
Created: 2026-07-09
Updated: 2026-07-09

# Arizona Trip Location Resolution

## Purpose and scope

This specification governs location entry, autocomplete, normalization, and geographic safety for the Arizona-only Birding Trip Copilot dataset.

The current evidence warehouse is Arizona-scoped. The product MUST NOT accept an arbitrary global coordinate and then present Arizona bird evidence as if it were local.

## Location search behavior

- The location field MUST support typeahead place search through the local Python API.
- Suggestions MUST identify the place clearly enough to disambiguate duplicate names, including locality, state/administrative area, and country where available.
- `Prescott` and `Prescott, Arizona` MUST resolve to Prescott, Arizona.
- The browser MUST NOT call the geocoder directly; the Python API owns request validation and upstream access.
- The first implementation SHOULD use Open-Meteo's open geocoding API because Open-Meteo is already an approved request-time dependency and requires no browser credential.
- Search MUST be bounded and cancellable. The UI SHOULD wait for a short typing pause, require a minimum useful query length, limit result count, and cancel stale requests.
- Keyboard users MUST be able to move through, select, and dismiss suggestions with an accessible combobox/listbox interaction.

## Arizona-only safety

- Only Arizona suggestions may be selected for plan creation.
- Manual coordinate input MAY remain available, but coordinates MUST fall within an explicit Arizona boundary before planning.
- The boundary MUST use a deterministic compact in-repository polygon derived from the public-domain US Census TIGERweb Arizona state boundary (STATE `04`), not a rectangular bounding box. Points exactly on the stored generalized boundary count as inside.
- The planner MUST NOT silently flip a longitude sign or silently substitute a different location.
- A coordinate shaped like `34.54,112.50` MUST fail before evidence lookup with a clear message that Arizona longitudes are negative and MAY suggest `34.54,-112.50` for explicit user confirmation.
- A selected or entered location MUST persist normalized name, latitude, longitude, timezone, and `US-AZ` region identity needed by evidence queries.
- Evidence queries MUST retain Arizona filtering even when the original input was a coordinate pair.

## Failure behavior

- No plan may be persisted when location resolution or Arizona validation fails.
- Geocoder timeout/unavailability, including direct and socket timeouts plus HTTP/URL transport failures, MUST normalize to the stable JSON geocoder-unavailable response and MUST preserve the ability to enter valid Arizona coordinates or a supported local alias.
- Empty, stale, outside-Arizona, and ambiguous results MUST NOT silently select the first match.

## Acceptance scenarios

### Named place

Given the user types `Prescott, Arizona`, when location search completes, then an Arizona Prescott suggestion is available and selecting it resolves approximately to latitude `34.54`, longitude `-112.47`, timezone `America/Phoenix`, and region `US-AZ`.

### Missing longitude sign

Given the user enters `34.54,112.50`, when the request is validated, then planning stops before weather or bird-evidence lookup and the error explains that Arizona longitude must be negative.

### Correct coordinate

Given the user enters `34.54,-112.50`, when the request is validated, then it is treated as an Arizona location and Open-Meteo elevation is expected to be in the Prescott-area high-elevation range rather than the value for 112.5 degrees east.

### Outside Arizona

Given a geocoded place or coordinate outside Arizona, when the user submits, then the app explains that the current bird dataset supports Arizona only and does not create a plan.

## Explicit exclusions

- No global recommendation support in this version.
- No silent coordinate correction.
- No browser-side DuckDB access.
- No proprietary geocoder dependency.
- No map UI unless separately ratified.
