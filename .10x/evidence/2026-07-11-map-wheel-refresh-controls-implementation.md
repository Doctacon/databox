Status: recorded
Created: 2026-07-11
Updated: 2026-07-11
Relates-To: .10x/tickets/done/2026-07-11-add-field-map-encounter-photo-preview.md, .10x/tickets/done/2026-07-11-build-arizona-bird-wheel-catalog.md, .10x/tickets/done/2026-07-11-build-local-refresh-runtime-api.md, .10x/tickets/done/2026-07-11-add-header-source-refresh-control.md

# Map, wheel, and refresh controls implementation

## Observed implementation

- Map snapshot now returns one strict deduplicated catalog photo per encountered species; live read-only result was 1,575 encounters, 152 photo identities, 139 available photos, with warehouse SHA-256 unchanged at `ca7ad49d4edc7c34b96f83944e7f3f5b748b84203b844205a666e309ca87a159`.
- Encounter rows render lazy attributed thumbnails/placeholders. Focus/hover writes an unclustered preview source; focused regression proves no pan or persistent selection and blur clears it.
- Arizona Birds renders all matching names in one scroll-snapped listbox with subtle distance classes, one active media/facts/profile preview, keyboard navigation, no pagination, no inactive image/audio elements, and playback cleanup.
- Header exposes confirmed fixed-scope refresh. Server status/launch routes enforce loopback same origin, exact confirmation, fixed six-source command/environment, one-running status, durable atomic status/PID/log reference, safe stale-process failure, source/SQLMesh phases, persistent failure, explicit retry, and shared 3,000-ms success handling. Tests use fake process only; no live refresh ran.

## Verification

- Full Python suite: 711 passed with three snapshots before the final phase/log hardening; focused source-refresh/map API suite passed 23/23 after implementation.
- Final full frontend suite: 264 passed, including the hover/focus preview regression. TypeScript passed.
- Production Vite build and bundle configuration audit passed.
- Ruff, Ruff format, MyPy, secret scan, production build, bundle audit, and diff checks passed after final phase/log hardening.
- SQLMesh unit suite: 13 passed.

## Limits

No live source provider, Quack refresh, SQLMesh apply, AVONET/media refresh, model call, or email occurred. Independent aggregate reviews remain blocked by the session-wide 40/40 subagent spawn limit.
