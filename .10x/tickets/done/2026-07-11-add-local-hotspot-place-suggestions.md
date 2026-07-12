Status: done
Created: 2026-07-11
Updated: 2026-07-11
Parent: .10x/tickets/2026-07-11-upgrade-place-search-feedback-and-map.md
Depends-On: .10x/tickets/done/2026-07-11-build-field-map-data-api.md

# Add local hotspot place suggestions

## Scope

Implement `.10x/specs/arizona-place-suggestions.md`: strict local eBird hotspot token search/ranking, source-labeled suggestion contract, bounded zero-local-only Open-Meteo fallback and 0.001° same-label dedup, component display, and reuse across trip/target/Watch workflows.

## Acceptance criteria

- `lake watson` returns exact Watson Lake hotspot first from local DuckDB with zero upstream call.
- Deterministic token/rank/limit/dedup/source/type contracts and invalid-row fail-closed tests pass.
- Open-Meteo is called only for zero-local searches; any local result suppresses fallback, and zero-local outage behavior remains safe.
- Browser strict validation and accessible combobox keyboard/cancellation/direct-coordinate behavior remain correct.
- GET performs no writes/model/weather/provider call beyond explicit fallback; full gates pass.

## Exclusions

No Overture/OSM/GeoNames, observation persistence/UI, map repair, or background geocoding.

## Evidence expectations

Record 2,912 live hotspot coverage, Watson query/no-upstream proof, ranking/attacks/fallback and full gates/review.

## Blockers

None.

## Progress and notes

- 2026-07-11: Ratified the zero-local-only fallback and same-normalized-label/0.001° per-coordinate dedup rule in `.10x/decisions/rufous-local-hotspot-fallback-policy.md`; updated the governing spec and removed the contradictory mixed Prescott scenario.
- 2026-07-11: Implemented strict local hotspot normalization, matching, ranking, validation, local-wins behavior, source-labeled browser contract/display, and metadata-safe reuse for trip, target, and Watch submission flows. Added backend and browser attack, fallback, privacy, keyboard, cancellation, coordinate, and payload tests.
- 2026-07-11: Recorded live 2,912-hotspot/Watson/no-upstream proof and final gates in `.10x/evidence/2026-07-11-local-hotspot-place-suggestions.md`: backend 705/705 with 86.69% coverage, frontend 249/249, typecheck/build/bundle audit, MyPy, all-files pre-commit, unchanged warehouse, and empty staging.
- 2026-07-11: Independent review passed. Review: `.10x/reviews/2026-07-11-local-hotspot-place-suggestions-review.md`.
- 2026-07-11: Retrospective preserved the fallback/dedup clarification as a focused active decision and exhaustive ranking/fallback tests; no additional record is needed.
