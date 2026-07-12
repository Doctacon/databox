Status: recorded
Created: 2026-07-11
Updated: 2026-07-11
Relates-To: .10x/tickets/done/2026-07-11-repair-trip-calendar-naive-arizona-window.md

# Trip calendar Arizona-local window repair

## What was observed

The user's persisted plan `trip_eaacd4a497e94cea883338744dace56f` had naive browser-local windows `2026-07-18T16:00:00` and `2026-07-18T18:00:00`. Read-only `_canonical_source` initially raised `ValueError: timestamp must include an offset`; the confirmed endpoint returned `409 invalid_plan` before queue or SMTP.

## Procedure and results

- Before and after repair, `birding_calendar.trip_event_intents`, `trip_outbox`, `trip_outbox_attempts`, and `trip_accepted_snapshots` each contained zero rows. No delivery command ran.
- The Arizona calendar boundary now interprets persisted naive values as fixed `UTC-07:00`, retains rejection of explicitly non-Arizona offsets, and emits normalized offset-aware canonical windows.
- Read-only canonicalization of the saved plan succeeded with:
  - start `2026-07-18T16:00:00-07:00`
  - end `2026-07-18T18:00:00-07:00`
  - source hash `9a29e070a11fb18e595df9bc7a771c54f1f19f347aa87c7ebfb3c6b25b8cbcb5`
- `pytest -q tests/test_trip_plan_calendar.py --no-cov`: 230 passed.
- `pytest -q --no-cov`: 709 passed with three snapshots.
- Ruff check/format and focused MyPy passed.

## What this supports

The saved plan is now valid for canonical invitation construction without altering planner timestamp storage, weakening non-Arizona offset rejection, creating an outbox row, or contacting Proton Bridge.

## Limits

No live invitation was sent. The running non-reload Uvicorn process must be restarted before it loads this Python change.
