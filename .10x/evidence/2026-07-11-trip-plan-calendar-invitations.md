Status: recorded
Created: 2026-07-11
Updated: 2026-07-11
Relates-To: .10x/tickets/done/2026-07-11-implement-trip-plan-calendar-invitations.md, .10x/specs/trip-plan-calendar-invitations.md

# Trip-plan calendar invitation implementation evidence

## What was observed

- Trip events use dedicated `birding_calendar.trip_event_intents` and `trip_outbox` tables whose authoritative identity is `trip_plan_id` plus `event_kind='trip_plan'`; no watch ID, species code, or activation generation is present.
- Runtime integrity validation fails closed if the source plan is missing, an intent does not identify its exact current outbox tuple, an outbox is orphaned, an attempt is orphaned, or an accepted snapshot is inconsistent. Runtime and offline migration table shapes were compared by table, ordinal, column, type, and nullability.
- Canonicalization rejects eBird recent-observation evidence with null, blank, missing, duplicate, private, invalid, or unreviewed source identity. Eligible source identities and private authority-table names are not rendered in calendar text. Arizona plan timestamps must carry the year-round `-07:00` offset.
- The first explicit action persists sequence 0 `METHOD:REQUEST`; concurrent explicit actions leave one intent and one outbox. Acceptance followed by another explicit action retains the UID and creates sequence 1.
- Failed and not-delivered reconciliation atomically supersede and enqueue a replacement. Confirmed reconciliation APIs claim/send the replacement immediately through injected fake SMTP and are idempotent. Confirmed `POST /api/trip-calendar-deliveries/deliver-due` explicitly processes pending and scheduled 1/5/15-minute retry rows; it never auto-claims `delivery_unknown`.
- Concurrent claimers produce one claim. Expired pre-send leases are recovered, while expired post-send leases become `delivery_unknown`. A late older acceptance cannot regress the sequence-1 accepted snapshot or current intent.
- Cleanup deletes only aged resolved non-current outbox/attempt rows, retains dedupe identity, and leaves the current intent/action plus unresolved unknown rows coherent.
- API startup and GET/detail/status requests make zero SMTP calls and create zero calendar tables. Unconfirmed POST makes zero calls. Confirmed POST uses injected fake SMTP and returns only safe state with “Accepted by local mail bridge.”
- No live SMTP command, Bridge preflight, or live transport was run. The prior bounded authorization remains exhausted.

## Procedure

```text
uv run ruff check packages/databox/databox/trip_plan_calendar.py packages/databox/databox/trip_plan_calendar_api.py packages/databox/databox/api.py tests/test_trip_plan_calendar.py tests/test_api.py
uv run mypy packages/databox/databox/trip_plan_calendar.py packages/databox/databox/trip_plan_calendar_api.py packages/databox/databox/api.py
uv run pytest --no-cov -q tests/test_trip_plan_calendar.py --count=3
uv run pytest --no-cov -q tests/test_trip_plan_calendar.py tests/test_api.py tests/test_birding_trip_planner.py tests/test_bird_alert_outbox.py tests/test_bird_alert_delivery.py tests/test_trip_plan_privacy_remediation.py
uv run pytest -q
cd app && npm test -- --run && npm run typecheck && npm run build
```

Results: Ruff passed; MyPy passed with no issues in 3 source files; repeated trip suite passed 75/75; focused repair and regression suite passed 100/100; full Python passed 457/457 at 86.51% coverage; browser tests passed 205/205 with typecheck and production build. Fake transports retained constructed messages in memory only for assertions.

## What this supports or challenges

This supports the event-kind schema/state, canonical source privacy eligibility, RFC payload, Arizona offset, stable UID/sequence, concurrent action/claim, lease recovery, atomic retry, explicit worker delivery, reconciliation idempotency, accepted snapshot non-regression, cleanup, migration parity, relationship integrity, API privacy, and no-implicit-send requirements. It challenges any claim of inbox/calendar arrival: fake SMTP proves only local construction and state handling, while SMTP acceptance wording remains explicitly bounded.

## Limits

- No live Bridge or inbox/calendar rendering was tested or authorized.
- DuckDB concurrent behavior was exercised with two independent connections and accepts one writer while the other may observe the committed pending row or receive a transaction conflict; this is not a high-volume multi-process benchmark.
- DuckDB does not provide the required mutable foreign-key lifecycle for these tables, so runtime fail-closed relationship validation is the equivalent integrity mechanism and is invoked before mutations/claims/cleanup.
- Browser controls remain explicitly excluded by this implementation ticket; the API exposes the typed actions required by the separate UI ticket.
