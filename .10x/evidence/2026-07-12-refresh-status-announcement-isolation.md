Status: recorded
Created: 2026-07-12
Updated: 2026-07-12
Relates-To: .10x/tickets/done/2026-07-12-isolate-refresh-status-announcement.md, .10x/tickets/done/2026-07-11-verify-map-wheel-and-refresh-controls.md

# Refresh status announcement isolation

## What was observed

The final aggregate frontend baseline had 271 passing tests and one failure at `app/src/MyBirds.test.tsx:192`: the alert-delivery operation's intentionally unnamed `role=status` query became ambiguous when the header's initial refresh-status retry disclosure also used an unnamed `role=status`.

The header's initial refresh-status recovery announcement now has the specific accessible name `Source refresh status`. The dedicated component regression queries that named status. No unrelated page test or production behavior was weakened.

## Procedure and results

- `cd app && npm test -- --run src/SourceRefreshControl.test.tsx src/MyBirds.test.tsx` — 2 files and 23 tests passed.
- `cd app && npm run typecheck && npm test && npm run build && ../.venv/bin/python ../scripts/audit_app_bundle.py` — TypeScript passed; all 18 files and 272 tests passed; production Vite build passed; bundle audit passed with 12 configured names and 10 configured values absent. Vite emitted only the existing large MapLibre chunk advisory.
- `git diff --check` — passed.
- `git diff --cached --name-only` — empty.

## What this supports

This supports every acceptance criterion in `.10x/tickets/done/2026-07-12-isolate-refresh-status-announcement.md`: the initial recovery status is specifically named, its component test asserts the name, and focused plus full frontend/type/build/bundle gates pass.

## Side-effect limits

No backend file changed. No live refresh, provider request, model call, email, AVONET/media refresh, database/SQLMesh mutation, or image/binary request occurred. The build wrote only normal frontend build output.

## Limits

No physical screen-reader or assistive-technology session was performed. Automated DOM semantics prove the accessible name and query isolation, not announcement quality in every assistive technology.
