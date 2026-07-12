Status: recorded
Created: 2026-07-11
Updated: 2026-07-11
Relates-To: .10x/tickets/done/2026-07-11-auto-dismiss-rufous-success-messages.md, .10x/specs/transient-success-feedback.md

# Transient success feedback verification

## Success surface inventory

Static `import.meta.glob` inventory found exactly three production success-banner render sites and requires one `useTransientSuccess()` owner per site:

| Owner | Banner sites | Successful actions |
| --- | ---: | --- |
| `MyBirdsPage` | 1 | observation create/edit/delete; Watch create/edit/pause/resume/delete; alert reconciliation/retry |
| `ProfileCollectionControls` | 1 | profile observation create; Watch create/pause/resume/delete |
| `TripCalendarControls` | 1 | accepted calendar send/update/retry/reconciliation result |

Planner and Target Bird creation transition directly to persisted result views and have no transient success banner. Loading, errors, media failures, empty states, persisted collection/calendar/target/plan states, warnings, pending, and delivery-unknown surfaces do not use the success class.

## Shared behavior

`app/src/useTransientSuccess.ts` is the sole timer owner. It uses one constant `SUCCESS_DISMISS_MS = 3000`, restarts its timer even when the same message is set again, clears immediately when set to null at action start, and clears the pending timer on replacement or unmount.

Both My Birds owners replaced only their prior success state with the hook. Existing live-region markup, error focus, mutation locking, collection invalidation, and action behavior are unchanged.

Calendar accepted results use the transient hook. Pending, failed, superseded, retry-wait, and delivery-unknown action results use the existing persistent announcement surface and are not timed. The persisted calendar status remains independently visible in `source-status`. Starting another calendar action clears either prior announcement, while busy status remains visible.

## Fake-timer verification

`app/src/useTransientSuccess.test.tsx` proves:

- visible through 2,999ms and absent at exactly 3,000ms;
- errors remain after timer advancement;
- replacing the same text at 2,000ms restarts the full interval;
- action reset clears immediately;
- unmount reduces the pending timer count to zero;
- every production success banner has a one-to-one shared-hook owner.

`app/src/TripCalendarControls.test.tsx` additionally proves accepted result focus and 3,000ms removal, while delivery-unknown action results remain after 30,000ms. Existing My Birds tests exercise every listed success-producing action and both page/profile owners through the shared hook.

Focused timer/surface verification passed 13/13; focused My Birds passed 19/19.

## Full gates

```text
cd app && npm test -- --run
16 files passed; 259 tests passed

cd app && npm run typecheck
passed

cd app && npm run build
passed; 52 modules transformed

.venv/bin/python scripts/audit_app_bundle.py app/dist
bundle configuration audit passed: 12 names and 10 configured values absent
```

The existing Vite lazy Field Map chunk-size advisory remains unrelated.

## What this supports

- All and only transient success banners dismiss at exactly three seconds.
- Replacement, same-message repetition, explicit action reset, and unmount are deterministic.
- Errors, warnings, busy/pending, delivery-unknown, and persisted state remain untimed.
- Existing focus, live regions, and concurrency semantics remain intact.
- Static inventory prevents a production success banner without a shared hook owner.
- No files were staged or committed.

## Limits

Fake timers verify React/jsdom behavior rather than physical assistive-technology speech duration. Independent review remains required before closure.
