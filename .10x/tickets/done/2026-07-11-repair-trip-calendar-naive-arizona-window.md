Status: done
Created: 2026-07-11
Updated: 2026-07-11
Parent: None
Depends-On: None

# Repair trip calendar handling of persisted Arizona-local windows

## Context

A real plan created through `POST /api/trip-plans` persists browser-local `window_start` and `window_end` values without offsets, as required by the existing local datetime input contract. Confirmed calendar send for `trip_eaacd4a497e94cea883338744dace56f` returned `409 invalid_plan` before queueing or SMTP because `databox.trip_plan_calendar._parse_arizona_time` requires an explicit `-07:00` offset. The calendar fixture instead seeds offset-aware windows, so verification did not exercise the production persistence contract.

Governing records: `.10x/specs/trip-plan-calendar-invitations.md`, `.10x/decisions/trip-plan-calendar-invitation-lifecycle.md`, and `.10x/specs/local-birding-trip-copilot-app.md`.

## Scope

- Interpret persisted offset-naive trip windows as Arizona local time (`UTC-07:00`) only at the trip-calendar boundary.
- Continue rejecting explicitly offset-aware timestamps whose offset is not Arizona's year-round `-07:00`.
- Align calendar fixtures with the real planner persistence contract.
- Verify the existing saved plan can produce a canonical calendar payload without sending email.

## Acceptance criteria

- A complete persisted plan with naive `2026-07-18T16:00:00` / `18:00:00` windows canonicalizes to timezone-safe UTC DTSTART/DTEND.
- Existing explicit non-Arizona-offset rejection remains covered and passes.
- Calendar unit/API/privacy suites pass.
- Read-only canonicalization of the user's saved plan succeeds.
- No SMTP send, retry, reconciliation, or new outbox record occurs during verification.

## Exclusions

- No live calendar invitation send or retry.
- No mutation of the saved trip plan.
- No change to general timestamp parsing outside the trip-calendar Arizona boundary.

## Evidence expectations

Focused and full calendar test output, read-only canonical payload proof for the saved plan, and before/after trip outbox ledger counts.

## Blockers

None.

## Progress and notes

- 2026-07-11: Reproduced read-only: `_canonical_source` raises `ValueError: timestamp must include an offset`. The endpoint returned before SMTP; the plan remains saved and its calendar status remains `not_created`.
- 2026-07-11: Subagent execution was attempted as required but the session-wide 40/40 spawn limit was reached; parent execution proceeded within this bounded ticket.
- 2026-07-11: Updated only the trip-calendar Arizona parser to attach UTC-07 to persisted naive timestamps while retaining explicit non-Arizona offset rejection. Calendar fixture now matches planner persistence.
- 2026-07-11: Initial focused verification exposed that parsed timestamps also had to replace raw naive values in the canonical payload; repaired before closure. This preserves offset-aware hashing and ICS rendering.
- 2026-07-11: Calendar suite passed 230/230; full Python suite passed 709/709 with three snapshots; Ruff, formatting, and focused MyPy passed. Read-only saved-plan canonicalization produced `16:00:00-07:00` to `18:00:00-07:00`. All four outbox ledger tables remained at zero rows. Evidence: `.10x/evidence/2026-07-11-trip-calendar-naive-arizona-window-repair.md`.
- 2026-07-11: Focused review passed with no correctness, privacy, lifecycle, or scope blocker. Review: `.10x/reviews/2026-07-11-trip-calendar-naive-arizona-window-review.md`.
- 2026-07-11: Retrospective: calendar fixtures must use the planner's persisted naive local-time shape; parsing alone is insufficient unless canonical facts replace raw values with normalized offset-aware timestamps.
