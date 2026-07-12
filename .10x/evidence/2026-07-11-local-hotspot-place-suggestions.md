Status: recorded
Created: 2026-07-11
Updated: 2026-07-11
Relates-To: .10x/tickets/done/2026-07-11-add-local-hotspot-place-suggestions.md, .10x/specs/arizona-place-suggestions.md, .10x/decisions/rufous-local-hotspot-fallback-policy.md

# Local hotspot place suggestions verification

## What was observed

The local `GET /api/locations` path searches the current Arizona eBird hotspot dimension before considering Open-Meteo. Matching is Unicode/case/punctuation/whitespace normalized, requires every query token regardless of order, ranks deterministically, rejects malformed/duplicate/out-of-Arizona rows, bounds responses to five, and exposes the exact source-labeled contract. Any valid local match suppresses fallback. Zero-local Open-Meteo rows use canonical bounded provider IDs and are deduplicated by exact source identity or equal normalized display label with both coordinates within 0.001°.

The browser validates exact keys, finite Arizona-bounded coordinates, source/type/ID coherence, duplicate source IDs, same-label/0.001° duplicates, and safe visible labels before rendering. The shared combobox displays place type and coordinates and remains used by trip, target, and Watch flows. Suggestion-only metadata is deliberately removed from existing mutation payload shapes so the strict trip/target/Watch write contracts do not widen.

## Procedure and results

### Current warehouse and Watson proof

A read-only DuckDB query returned `2,912` `US-AZ` rows and `2,912` distinct location IDs from `environmental_observations.dim_bird_hotspot`. A FastAPI `TestClient` request against the live warehouse with an injected getter that raises on any call returned:

```text
200
Watson Lake and Riparian Preserve
L270303
Birding hotspot
34.5822319, -112.4259328
upstream_calls=0
```

The warehouse was unchanged across verification:

```text
size=58470400
mtime=1783818811
sha256=87d45ece558cd248aa6efdd295798276775093a4906eeac40f8c41a9eea245bc
```

The focused temporary-database tests also hash the database before and after the GET and prove that a private table value never enters the response.

### Focused backend and browser verification

```text
PYTHONDONTWRITEBYTECODE=1 .venv/bin/pytest -q --no-cov tests/test_place_suggestions.py tests/test_open_meteo_geocoding.py tests/test_api.py
25 passed

cd app && npm run typecheck
passed

cd app && npm test -- --run src/tripPlanValidation.test.ts src/App.test.tsx src/MyBirds.test.tsx src/targetApi.test.ts
4 files passed; 121 tests passed
```

Focused coverage includes reversed tokens, accents/punctuation/whitespace, deterministic ranking, malformed source/ID/control/out-of-Arizona/duplicate hotspot rows, local same-label dedup, local-wins 0.001° dedup, zero-local fallback, canonical Open-Meteo IDs, fallback duplicate suppression, zero upstream calls for local results, private-field exclusion, read-only hashing, strict browser relationship and extra-field rejection, source/type/coordinate display, keyboard selection, aborted stale requests, direct coordinate bypass, and metadata-safe trip/target/Watch payloads.

### Full gates

The final tree passed:

```text
network-proxied-offline PYTHONDONTWRITEBYTECODE=1 .venv/bin/pytest -q
705 passed; 3 snapshots passed; 86.69% coverage

cd app && npm test -- --run
15 files passed; 249 tests passed

cd app && npm run typecheck
passed

cd app && npm run build
passed; 51 modules transformed

.venv/bin/python scripts/audit_app_bundle.py app/dist
bundle configuration audit passed: 12 names and 10 configured values absent

.venv/bin/mypy packages/databox/databox packages/databox-sources/databox_sources
Success: no issues found in 71 source files

.venv/bin/pre-commit run --all-files
all 11 hooks passed

git diff --check
passed

git diff --cached --name-only
no output
```

The build retained the pre-existing Vite advisory that the lazy Field Map chunk exceeds 500 kB; it is unrelated to place suggestions and is not a failure.

## What this supports

- The 2,912-row current hotspot source is sufficient for the named Watson case and is queried read-only.
- `lake watson` is token-order-independent, returns Watson Lake first, and makes no upstream request.
- Local-first ranking, source/type contracts, local-only network behavior, zero-local fallback, deduplication, invalid-row isolation, privacy, and response bounds are mechanically enforced.
- Shared trip/target/Watch combobox behavior, keyboard interaction, cancellation, coordinate bypass, and existing mutation contracts remain intact.
- No file was staged or committed.

## Limits

Open-Meteo fallback behavior is tested through injected deterministic responses and safe failures; no live provider call was made. Arizona polygon membership is authoritative at the backend; browser validation retains the existing bounded Arizona coordinate envelope and accepts only backend-shaped data. Independent review remains the ticket's closure gate.
