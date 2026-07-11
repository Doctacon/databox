Status: recorded
Created: 2026-07-11
Updated: 2026-07-11
Relates-To: .10x/tickets/done/2026-07-11-harden-remaining-browser-timestamps-and-load-states.md

# Remaining browser timestamp and load-state hardening

## What was observed

A shared browser ISO utility now governs target-plan, bird catalog/profile, and alert-delivery date/time fields.

- `isIsoDate` accepts exact `YYYY-MM-DD` calendar dates only.
- `isIsoTimestamp` accepts exact backend ISO date-times with required seconds, optional one-to-six fractional digits, and optional `Z`/offset where the API permits it.
- Alert delivery requires an explicit `Z` or numeric offset, matching the timezone-aware backend contract.
- Calendar validation handles leap years and exact month lengths and rejects year zero, impossible dates, hour/minute/second overflow, offsets beyond `+/-14:00`, numeric/non-string values, non-ISO separators, date-only values in timestamp fields, and timestamps in date-only fields.
- Target window duration comparison uses parsed microseconds rather than `Date.parse`.

Every target timestamp family is covered: plan window, evidence freshness, creation, candidate observation/evidence freshness, and weather retrieval. Bird coverage includes catalog/activity/location observation timestamps, AVONET load time, GBIF/Xeno date-only fields, and every source freshness timestamp. Alert coverage includes next attempt, updated, terminal, and nested attempt timestamps.

My Birds now records collection and alert-history load success independently. Initial collection failure renders one safe error without any life-list, observation, wishlist, or watch empty claim. Initial alert-history failure renders the safe error without claiming the history is empty. Successful empty responses still render their established empty states. Existing revision/mutation tests remain green; a later failed refresh can retain previously loaded state rather than replacing it with a false empty state.

## Procedure and results

### Focused adversarial browser tests

```text
cd app && npm test -- --run \
  src/isoDateTime.test.ts src/targetApi.test.ts src/BirdPages.test.tsx \
  src/alertDeliveryApi.test.ts src/MyBirds.test.tsx

5 files passed
85 tests passed
```

The strict timestamp matrix includes invalid non-leap February 29, April 31, 24:00, minute/second overflow, `+24:00`, `+14:01`, year zero, numeric `0`, slash/space/non-padded forms, and date/timestamp type confusion. Accepted forms include valid leap day, naive backend timestamp, UTC `Z`, fractional microseconds, and positive/negative offsets.

The My Birds tests distinguish initial failed loading from valid empty responses across all collection tabs and alert delivery and assert exactly one safe alert on failure.

### Complete frontend gate

```text
task app:check
11 test files passed
199 tests passed
TypeScript typecheck passed
Vite production build passed
bundle audit passed: 12 server-only names and 10 configured values absent
```

### Relevant backend/API and static gates

```text
uv run --no-sync pytest --no-cov -q \
  tests/test_target_planning.py tests/test_bird_catalog_api.py \
  tests/test_bird_alert_delivery.py tests/test_bird_alert_outbox.py \
  tests/test_personal_collection_api.py
87 passed

uv run --no-sync python scripts/check_secrets.py .
passed

uv run --no-sync mypy packages/
Success: no issues found in 90 source files
```

## What this supports

- Remaining browser APIs no longer use `Date.parse` as date/timestamp validation.
- Impossible or non-ISO date/time values fail the complete response boundary without partial rendering.
- Exact backend date, naive date-time, timezone-aware date-time, and microsecond forms remain accepted where appropriate.
- Failed initial My Birds loads cannot be misrepresented as genuinely empty local state.
- Existing navigation, mutation revision, alert reconciliation, accessibility, type, build, and secret/bundle behavior remains intact.

## Limits

- Final independent adversarial review passed and is recorded at `.10x/reviews/2026-07-11-remaining-browser-timestamps-and-load-states-review.md`.
- This ticket does not change backend schemas or retrofit unrelated API clients outside its explicit target, bird, and alert-delivery scope.
