Status: recorded
Created: 2026-07-10
Updated: 2026-07-10
Relates-To: .10x/tickets/done/2026-07-10-implement-target-bird-planning.md, .10x/specs/target-bird-planning.md

# Target-bird planning implementation

## What was observed

Databox now creates target-specific local plans from one exact current Arizona catalog taxon, a selected Arizona origin, 1–300-mile Haversine boundary, naive local start, and 1–1440-minute duration.

- Candidate selection reads only `environmental_observations.fact_bird_observation`, requires exact species, `US-AZ`, valid, reviewed, non-private, stable public location/coordinates, and non-null submission identity.
- Candidates cluster by location ID, count distinct submissions across overlapping feeds, take name/coordinates from one coherent newest row, and rank by submission count, newest observation, distance, name, and ID. At most ten persist.
- Open-Meteo runs after ranking for the selected origin/window. Available, partial, and unavailable evidence persist honestly.
- Cloudflare uses only `@cf/zai-org/glm-5.2` through a strict JSON Schema target contract. The model receives exact target/request data; candidate name, coordinates, count, newest observation, distance, and source load time; overall evidence freshness; and a typed normalized weather status, retrieval time, complete nullable summary, exact units, elevation, and caveats. It must echo scalar grounding plus a canonical SHA-256 over all supplied evidence. User-facing guidance is deterministic text keyed by validated actions, and candidate-dependent actions are rejected when evidence is empty.
- Model failure persists no plan, candidate, or trace. Persistence uses one transaction across runtime-owned plan/candidate/sanitized-trace tables; an injected post-DDL failure proves schema and rows roll back.
- Typed POST and GET list/detail APIs serialize creation separately from the Trip Planner. GET replay is read-only and network-free and reproduces persisted facts.
- Browser routes `/birds/{species_code}/find` and `/target-plans/{id}` support profile action, validated Arizona origin, radius/start/duration form, saved results, dual units, candidate evidence, weather, caveats, provenance, focus/history/direct loading, and explicit empty/error states.
- Target plans do not read `birding_personal`, create watches, alter the existing Trip Planner, or expose the configured model selector in the browser bundle.

## Focused verification

```text
uv run --no-sync pytest --no-cov -q tests/test_target_planning.py tests/test_cloudflare_workers_ai.py
34 passed
```

Tests cover privacy/status exclusions, duplicate submission dedupe, coherent newest metadata, true Haversine radius, count/newness/distance/name/ID ties, hybrid empty evidence, weather normalization, exact model grounding/schema, model and persistence rollback, API bounds/location/taxon errors, safe model failure, read-only no-network replay, unchanged DB hash on GET, and absence of private/raw fields.

```text
uv run --no-sync pytest --no-cov -q \
  tests/test_target_planning.py tests/test_cloudflare_workers_ai.py \
  tests/test_api.py tests/test_bird_catalog_api.py tests/test_personal_collection_api.py
76 passed
```

## Browser verification

```text
task app:check
110 tests passed
TypeScript passed
Vite production build passed
bundle audit passed: 3 configured names and 3 configured values absent
```

Seven new target client/component tests validate exact response shape, extra/private-field rejection, selected-origin POST shape, malformed error suppression, direct persisted route, dual units/evidence/weather/provenance, empty evidence, and focused safe errors. Existing Trip Planner, catalog, and My Birds tests passed unchanged.

## Complete repository verification

```text
uv run --no-sync pytest -q --record-mode=none --block-network
338 passed; 3 snapshots passed; coverage 86.45%

uv run --no-sync mypy packages/
Success: no issues found in 84 source files

ruff check / ruff format --check: passed after one final mechanical test-line wrap
check_secrets.py .: passed
pre-commit focused hooks: passed after the same wrap
git diff --check: passed
```

No live responses were recorded and no production warehouse was mutated by tests.

## Post-review repair verification

```text
uv run --no-sync pytest --no-cov -q tests/test_target_planning.py tests/test_cloudflare_workers_ai.py
40 passed

uv run --no-sync pytest --no-cov -q \
  tests/test_target_planning.py tests/test_cloudflare_workers_ai.py \
  tests/test_api.py tests/test_bird_catalog_api.py tests/test_personal_collection_api.py
84 passed

task app:check
121 tests passed; TypeScript/build/bundle audit passed

uv run --no-sync pytest -q --record-mode=none --block-network
344 passed; 3 snapshots passed; coverage 86.42%

uv run --no-sync mypy packages/
Success: no issues found in 84 source files
```

New adversarial cases prove honest empty-evidence actions and pre-persistence rejection, complete model input and tamper-resistant evidence grounding, incomplete/unavailable weather normalization before commit, strict malformed persisted-weather failure, exact client keys/types/finiteness/units/internal relationships, safe structured-error suppression, and available/partial/unavailable weather presentation.

## Final target-route semantics

```text
cd app && npm test -- --run src/TargetBird.test.tsx
6 passed

task app:check
122 browser tests passed; TypeScript/build/bundle audit passed
```

Saved-plan replay now links directly to the encoded `/birds/{species_code}` profile path through native navigation. Direct replay/load failures render and focus `Target plan unavailable` (or `Bird profile unavailable` for profile loads), while form validation and POST failures render and focus the distinct `Could not create that target plan` context with the already bounded safe API detail. Tests exercise the saved-route link/navigation and both error contexts.

## What this supports

The ticket's evidence selection/ranking/privacy, request bounds, weather ordering/degradation, sole strict model, exact grounding, atomic persistence/rollback, typed read/write API, network-free replay, browser route/accessibility/units, bundle safety, and planner/personal-state independence criteria have executable evidence.

## Limits

- Responsive behavior is covered through existing app breakpoints and DOM tests rather than a screenshot audit.
- Final independent adversarial review passed and is recorded at `.10x/reviews/2026-07-10-target-bird-planning-review.md`.
