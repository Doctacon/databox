Status: done
Created: 2026-07-12
Updated: 2026-07-12
Parent: .10x/tickets/done/2026-07-11-upgrade-map-catalog-and-refresh-controls.md
Depends-On: .10x/tickets/done/2026-07-11-add-field-map-encounter-photo-preview.md, .10x/tickets/done/2026-07-11-build-arizona-bird-wheel-catalog.md, .10x/tickets/done/2026-07-11-add-header-source-refresh-control.md

# Repair map, wheel, and refresh review findings

## Scope

Resolve the closure-blocking findings in the four independent reviews of the completed map/wheel/refresh implementation, without running a live refresh or changing ratified behavior:

- derive or pin the exact six-source refresh scope from canonical source authority so reported and executed scope cannot drift;
- make refresh launch/status durable across the pre-PID window and app restart, with bounded sanitized log/status inspection, current phase and per-source progress, source-attributed safe failure, persistent failure disclosure, conflict behavior, and exact fake command/lifecycle coverage;
- keep the selected map marker authoritative, preserve simultaneous hover/focus preview modalities, and retain attribution/license after thumbnail load failure;
- disable wheel animated settling under reduced motion;
- add focused component/API tests for the required refresh, map, and wheel scenarios.

Final aggregate full-suite/evidence gaps remain owned by `.10x/tickets/done/2026-07-11-verify-map-wheel-and-refresh-controls.md`, not this repair ticket.

## Governing records

- `.10x/specs/local-source-refresh-control.md`
- `.10x/specs/field-map-encounter-photo-preview.md`
- `.10x/specs/arizona-bird-wheel-catalog.md`
- `.10x/decisions/rufous-wheel-map-preview-and-source-refresh.md`
- `.10x/reviews/2026-07-12-map-wheel-refresh-architecture-review.md`
- `.10x/reviews/2026-07-12-map-wheel-refresh-correctness-review.md`
- `.10x/reviews/2026-07-12-map-wheel-refresh-privacy-security-source-review.md`
- `.10x/reviews/2026-07-12-map-wheel-refresh-ux-accessibility-review.md`

## Acceptance criteria

- The refresh command executes exactly the six current routine sources and status/browser contracts cannot silently drift from canonical registry authority.
- A GET cannot falsely fail a just-launched pre-PID run; reload/restart can recover a completed child outcome from durable bounded state rather than assuming dead PID means failure.
- Status exposes safe phase and per-source progress plus source-attributed failure; browser UI presents source/SQLMesh progress and reload-preserved safe failure/log reference.
- Log/status reads are bounded and provider/exception output reaching durable refresh logs is sanitized against secrets, credentials, personal data, arbitrary URLs, and raw payload text.
- Tests cover Origin/body/conflict/exact command and environment, pre-PID and restart terminal recovery, source failure/SQLMesh suppression, progress, persistent failure UI, reconfirmed retry, and success dismissal without live providers.
- Field Map preserves attribution after image load failure, hover and focus independently sustain preview, and selection style remains authoritative when selection equals preview.
- Wheel selection uses non-animated scrolling when reduced motion is active.
- Focused Python/frontend tests, Ruff/format/MyPy, TypeScript, secret scan, and diff checks pass.

## Evidence expectations

Create a dedicated evidence record with changed-file scope, focused command results, adversarial cases, and explicit no-live-refresh/no-provider/no-model/no-email/no-media limits.

## Explicit exclusions

No live provider or routine refresh, Quack/SQLMesh apply, AVONET/media refresh, model call, email, binary download, unrelated refactor, or weakening/superseding the active specs.

## Progress and notes

- 2026-07-12: Opened from four independent fail reviews. Aggregate verification remains open and will run final full gates after this repair closes.
- 2026-07-12: Implemented a canonical-scope durable refresh runner with bounded sanitized marker logs, atomic per-source/phase status, pre-PID grace, restart-independent completion, exact command/environment pinning, and source-attributed failure.
- 2026-07-12: Repaired persistent refresh UI progress/failure disclosure, independent Field Map hover/focus state, selected marker authority, thumbnail attribution after load failure, and reduced-motion wheel centering.
- 2026-07-12: Focused final evidence recorded at `.10x/evidence/2026-07-12-map-wheel-refresh-review-repairs.md`: 37 Python and 40 frontend tests passed; Ruff/format/MyPy/TypeScript/secret/diff gates passed. No forbidden live workflow ran.
- 2026-07-12: Acceptance mapping re-read: canonical exact scope and drift prevention are covered by API/runner tests; launch/restart/log/progress/failure contracts by fake lifecycle and component tests; map/wheel contracts by focused regressions; static criteria by recorded commands.
- 2026-07-12: Retrospective found no new reusable project convention or operational procedure beyond the implementation and tests. The aborted accidental BirdPages test deletion was recovered from HEAD and final numstat proves 14 additions and zero deletions in that file.

## Blockers

None. Final aggregate gates and independent review reruns remain explicitly owned by `.10x/tickets/done/2026-07-11-verify-map-wheel-and-refresh-controls.md`.
