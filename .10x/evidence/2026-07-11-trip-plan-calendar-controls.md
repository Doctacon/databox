Status: recorded
Created: 2026-07-11
Updated: 2026-07-11
Relates-To: .10x/tickets/done/2026-07-11-add-trip-plan-calendar-controls.md, .10x/specs/trip-plan-calendar-invitations.md

# Trip-plan calendar controls verification

## What was observed

The persisted Trip Planner result now renders only the strictly validated actions for its calendar invitation state: first Send, accepted Update, failed Retry, and both delivery-unknown reconciliation choices. Pending/claimed/retry-wait/superseded states expose no action. Every mutation uses a native confirmation, a synchronous in-browser duplicate guard, disabled native buttons, `aria-busy`, live status, and focused success/error output. Accepted text is explicitly limited to the local mail Bridge and disclaims inbox/calendar confirmation.

Runtime validation rejects unknown statuses, mismatched/duplicate actions, transport fields, missing identity/timestamp relationships, missing acceptance wording, extra response fields, and action-response outbox mismatches. Browser API errors are selected from fixed client-owned text; backend messages are ignored.

Rendering persisted not-created, pending, accepted, failed, and unknown state performs no action. GET/history/reload and plan creation remain read/create-only; calendar POSTs are reachable only from a confirmed control.

## Procedure

From repository root:

1. `cd app && npm test -- --run src/TripCalendarControls.test.tsx src/tripPlannerApi.test.ts src/tripPlanValidation.test.ts`
   - Passed 46/46 focused tests across 3 files.
2. `cd app && npm run typecheck`
   - Passed TypeScript project references with no diagnostics.
3. `cd app && npm test`
   - Passed 220/220 tests across all 12 frontend suites, including planner, Target Bird, My Birds, alert API, accessibility interactions, runtime validation, and privacy errors.
4. `cd app && npm run build`
   - Passed TypeScript build and Vite production bundle; 41 modules transformed, JS bundle 261.76 kB (76.60 kB gzip).
5. `! grep -Eio 'recipient@example|/private/|raw_model_response|raw-model response|payload_json|BEGIN (RSA |EC |OPENSSH )?PRIVATE KEY' app/dist/assets/*.js`
   - Passed with no prohibited transport/private payload markers in the production JavaScript bundle.
6. `git diff --check`
   - Passed with no whitespace errors.
7. `git diff --cached --name-only`
   - Empty; no files are staged.

## What this supports or challenges

This supports the ticket's first/update/concurrent/unknown/failed/reload/malformed/no-implicit-send criteria and full frontend type/test/build/bundle/privacy gates. The build preserved generated `app/dist` artifacts in place and no live SMTP or backend delivery command ran.

## Limits

The verification uses the completed API contract and mocked browser transport. It does not send a live message and does not claim inbox or calendar delivery.
