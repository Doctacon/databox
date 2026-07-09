Status: recorded
Created: 2026-07-09
Updated: 2026-07-09
Target: .10x/tickets/done/2026-07-09-add-arizona-location-search-and-validation.md
Verdict: pass

# Arizona location search and validation review

## Target

Implementation and evidence for `.10x/specs/arizona-trip-location-resolution.md`.

## Assumptions tested

- Arizona validation is geographical rather than a broad bounding rectangle.
- Geocoder transport failures retain the typed user-safe API contract.
- Invalid coordinates fail before database, weather, evidence, model, and persistence work.
- Valid manual coordinates retain Arizona evidence filtering.
- Browser search remains bounded, cancellable, stale-response safe, and accessible.

## Findings

### Resolved significant — rectangular boundary admitted outside points

Initial review proved `36.9,-114.8` and `31.3,-114.8` were accepted by the rectangular check. The implementation was replaced with inclusive point-in-polygon validation over a 195-point generalized official US Census TIGERweb Arizona boundary. Fresh reviewer retrieval matched the stored polygon coordinate-for-coordinate. Tests now reject both former false positives and accept Prescott, Phoenix, Yuma, and a stored boundary vertex.

### Resolved significant — raw timeout escaped as text/plain HTTP 500

Initial review proved an injected `TimeoutError` bypassed the safe geocoder contract. Direct timeout, socket timeout, HTTP, and URL failures now normalize to `OpenMeteoGeocodingError`; the API emits stable sanitized JSON and the frontend preserves editable coordinate fallback. Direct reviewer probes confirmed all four failure classes.

### Passed — prior contract

Independent re-review confirmed query normalization, Arizona result filtering, typed local API ownership, combobox debounce/cancellation/stale-response protection/keyboard semantics, selected location persistence, pre-side-effect rejection, and `US-AZ` evidence filtering. Focused and aggregate checks recorded in `.10x/evidence/2026-07-09-arizona-location-search-and-validation.md` pass.

## Verdict

Pass. No blocker remains.

## Residual risk

The stored public Census boundary is intentionally generalized at `0.005` degrees, so a point extremely close to the legal boundary may follow the generalized line. CI uses deterministic geocoder fixtures rather than a live Open-Meteo call. Both limits are explicit and appropriate for this trip-location guard.
