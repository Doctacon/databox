Status: active
Created: 2026-07-11
Updated: 2026-07-11

# Arizona place suggestions

## Purpose

Extend the existing local API combobox from city-only geocoding to birding-place-first Arizona suggestions without changing the browser trust boundary.

## Sources and ranking

For normalized queries of at least two characters:

1. Query current `environmental_observations.dim_bird_hotspot` rows with `region_code='US-AZ'`, nonblank unique location ID/name, valid Arizona coordinates, and current bounded snapshot.
2. Normalize Unicode/case/punctuation/whitespace and split query into meaningful tokens. Every query token MUST occur in the normalized candidate name, regardless of order. `lake watson` therefore matches `Watson Lake and Riparian Preserve`.
3. Rank local matches deterministically: exact normalized name, normalized prefix, token position/compactness, all-time checklist count descending, then display name and location ID.
4. Fetch bounded Open-Meteo results only when local search returns zero valid matches. Any valid local hotspot result suppresses fallback. Deduplicate exact source IDs and results with the same normalized display label whose latitude and longitude are each within 0.001°; a local hotspot wins any such collision.

Default/max response limit remains bounded by the existing contract. Upstream failure is possible only after a zero-local search and yields safe geocoder-unavailable behavior. Valid manual Arizona coordinates remain supported.

## Suggestion contract

Each result contains exact keys:

- display name, latitude, longitude, timezone `America/Phoenix`, region `US-AZ`;
- `source`: `ebird_hotspot` or `open_meteo`;
- bounded nonblank `source_id`;
- `place_type`: `Birding hotspot` or `Arizona place`.

Browser displays place type and safe coordinates. Extra/malformed/source-inconsistent/out-of-bounds/duplicate results fail closed. Browser never calls either source directly.

## Reuse

Trip, target, Watch, and observation forms use the same API/component. Workflows may retain different requirements: trip/target/Watch require a selected suggestion; observation location permits selected structured data or unselected free text.

## Acceptance scenarios

- `lake watson` returns Watson Lake hotspot before city fallback.
- `Prescott` returns deterministic local hotspots without an upstream request when any valid local match exists; otherwise it may return the bounded Open-Meteo city result.
- Reversed tokens, case, punctuation, and whitespace normalize deterministically.
- Open-Meteo outage still returns local matches.
- Private personal observations never become suggestion sources.
- Invalid/duplicate hotspot rows fail closed without poisoning valid results.
