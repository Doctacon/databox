Status: recorded
Created: 2026-07-11
Updated: 2026-07-11
Relates-To: .10x/tickets/done/2026-07-11-harden-trip-planner-browser-boundary.md

# Trip Planner browser boundary hardening

## What was observed

The Trip Planner browser client now validates successful API responses before rendering and maps backend failures to fixed client-owned messages.

- Location results, plan lists, and plan details require exact bounded shapes.
- Plan lists remain bounded to 100 rows.
- ISO timestamps reject impossible calendar dates, invalid times, and invalid offsets while accepting valid leap days, microseconds, and offsets.
- GET detail responses must contain the requested trip-plan ID.
- Recommendation, evidence, weather, media, and trace identities/cardinalities are validated together; contradictory nested media is rejected before any plan card renders.
- Unknown, malformed, or unallowlisted error envelopes use one generic message. Allowlisted status/code pairs never display backend-provided message text.
- Alert reconciliation exposes `aria-busy`, a live status message, and disabled actions for the mutation lifetime.

The initially failing frontend cases were stale fixtures that represented response combinations the FastAPI serializer cannot produce, such as an available nested call with a different typed recording ID, common-name-only media ownership, authority-bearing scientific-name mismatch, or partially populated available media. Those cases now assert fail-closed whole-response rejection. Valid fixtures keep weather as a separate JSON value and carry the modeled recommendation enrichment fields from which the backend derives nested media.

## Procedure and results

### Focused browser boundary

```text
cd app && npm test -- --run src/App.test.tsx src/tripPlanValidation.test.ts src/tripPlannerApi.test.ts
3 test files passed
88 tests passed
```

Coverage includes exact list cardinality at 100/101, impossible timestamps, requested-ID equality, weather identity/equality, media/evidence linkage, orphan and duplicate relationships, raw-model payload keys, non-finite values, malformed/extra fields, safe errors, and no partial plan render.

### Complete browser gate

```text
task app:check
10 test files passed
159 tests passed
TypeScript typecheck passed
Vite production build passed
bundle configuration audit passed: 12 names and 10 configured values absent
```

### Backend response contract

```text
uv run --no-sync pytest --no-cov -q tests/test_api.py
16 passed

uv run --no-sync ruff check packages/databox/databox/api.py tests/test_api.py
passed

uv run --no-sync mypy packages/
Success: no issues found in 90 source files
```

The backend API tests confirm the response shapes and derived recommendation photo/call/media behavior used by the browser fixtures.

## What this supports

- Strict success-response validation is active at the browser trust boundary without increasing the plan-list maximum or relaxing timestamp validation.
- Cross-record identity mismatches fail closed and do not partially render recommendations.
- Fixed client-owned error messages prevent backend path, secret, and raw-model text from reaching the UI.
- Alert delivery reconciliation has an announced busy state.
- Existing Planner, catalog, My Birds, target-bird, collection, and alert browser tests remain green.

## Limits

- Final independent adversarial review passed and is recorded at `.10x/reviews/2026-07-11-trip-planner-browser-boundary-review.md`.
- This evidence is scoped to the browser boundary and relevant FastAPI response contract; it does not claim aggregate Pokédex closure.
