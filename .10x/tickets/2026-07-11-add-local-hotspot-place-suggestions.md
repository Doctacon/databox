Status: open
Created: 2026-07-11
Updated: 2026-07-11
Parent: .10x/tickets/2026-07-11-upgrade-place-search-feedback-and-map.md
Depends-On: .10x/tickets/done/2026-07-11-build-field-map-data-api.md

# Add local hotspot place suggestions

## Scope

Implement `.10x/specs/arizona-place-suggestions.md`: strict local eBird hotspot token search/ranking, source-labeled suggestion contract, bounded Open-Meteo fallback merge/dedup, component display, and reuse across trip/target/Watch workflows.

## Acceptance criteria

- `lake watson` returns exact Watson Lake hotspot first from local DuckDB with zero upstream call.
- Deterministic token/rank/limit/dedup/source/type contracts and invalid-row fail-closed tests pass.
- Open-Meteo fills remaining capacity; outage preserves local results and safe zero-local failure behavior.
- Browser strict validation and accessible combobox keyboard/cancellation/direct-coordinate behavior remain correct.
- GET performs no writes/model/weather/provider call beyond explicit fallback; full gates pass.

## Exclusions

No Overture/OSM/GeoNames, observation persistence/UI, map repair, or background geocoding.

## Evidence expectations

Record 2,912 live hotspot coverage, Watson query/no-upstream proof, ranking/attacks/fallback and full gates/review.

## Blockers

None.
