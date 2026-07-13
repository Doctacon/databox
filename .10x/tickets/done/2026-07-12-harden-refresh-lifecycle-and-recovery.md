Status: done
Created: 2026-07-12
Updated: 2026-07-12
Parent: .10x/tickets/done/2026-07-11-upgrade-map-catalog-and-refresh-controls.md
Depends-On: .10x/tickets/done/2026-07-12-repair-map-wheel-refresh-review-findings.md

# Harden refresh lifecycle and recovery

## Scope

Resolve the remaining closure-blocking findings from the final independent map/wheel/refresh review rerun:

- make refresh ownership fail closed and durable across malformed/missing/oversized status, app exit between spawn and PID publication, PID-publication failure, runner crash, and PID reuse/mismatched process identity;
- publish `running_sqlmesh` only from an authoritative marker emitted at the actual SQLMesh boundary after cleanup, dedupe, overlap validation, and inspection;
- add one connected fake proof covering the exact six-source API/runner/orchestration path, one Quack lifecycle, post-source maintenance, and SQLMesh ordering;
- clear recovered frontend status-request errors on every valid response and provide bounded retry/recovery after initial status load failure;
- add focused wheel listbox keyboard/ARIA synchronization regression coverage;
- repair stale parent child-plan/progress/blocker text.

## Governing records

- `.10x/specs/local-source-refresh-control.md`
- `.10x/specs/field-map-encounter-photo-preview.md`
- `.10x/specs/arizona-bird-wheel-catalog.md`
- `.10x/decisions/rufous-wheel-map-preview-and-source-refresh.md`
- `.10x/reviews/2026-07-12-map-wheel-refresh-final-architecture-review.md`
- `.10x/reviews/2026-07-12-map-wheel-refresh-final-correctness-review.md`
- `.10x/reviews/2026-07-12-map-wheel-refresh-final-privacy-security-source-review.md`
- `.10x/reviews/2026-07-12-map-wheel-refresh-final-ux-accessibility-review.md`

## Acceptance criteria

- A durable, atomic ownership mechanism is established before process launch; POST rejects while ownership is active even if status is absent/invalid; launch failure releases ownership safely; the runner publishes/verifies its own identity before warehouse mutation and releases ownership only after terminal status.
- Recovery distinguishes the intended live runner/run from dead, stale, or PID-reused/unrelated processes without trusting PID liveness alone. Tests cover invalid status plus active owner, pre-runner publication, publication failure, dead owner, and mismatched live PID/process identity.
- Actual orchestration emits a bounded authoritative SQLMesh-phase marker after all post-source maintenance/inspection and immediately before SQLMesh. Durable/UI phase changes only on that marker.
- One connected fake test covers exact six canonical sources through API/runner/real orchestration seam, one Quack owner, cleanup/dedupe/inspection, and SQLMesh only after all six succeed; failure suppresses SQLMesh.
- Frontend clears transient request errors after valid running/SQLMesh/success status and retries initial restoration with bounded disclosure; tests cover both recovery paths.
- Wheel tests cover Arrow/Page/Home/End with synchronized `aria-activedescendant` and `aria-selected`.
- Parent record graph/progress is current.
- Focused Python/frontend tests, full static/type/format/secret/diff gates pass without live external effects.

## Evidence expectations

Create a dedicated evidence record with adversarial lifecycle cases, exact connected fake ordering, frontend recovery/keyboard cases, commands/results, and no-live-workflow limits.

## Exclusions

No live refresh/provider/model/email/AVONET/media workflow, DuckDB/SQLMesh apply, binary download, semantic spec change, multi-worker support, or unrelated refactor.

## Progress and notes

- 2026-07-12: Opened after all four final independent reruns returned fail. Prior repairs remain valid; this ticket owns only remaining lifecycle, evidence, UI recovery, keyboard-test, and graph-coherence findings.
- 2026-07-12: Replaced PID-only ownership with atomic pre-launch owner reservation, runner-owned PID/heartbeat publication, bounded owner validation, stale process-command/run-ID verification, fail-closed malformed state, and safe launch/publication failure cleanup.
- 2026-07-12: Moved SQLMesh phase publication to an authoritative orchestration marker after cleanup/dedupe/inspection and added connected exact-six success/failure proofs from API arguments through the real orchestration seam and durable runner.
- 2026-07-12: Added bounded initial status retry, recovered-error clearing, disabled unknown-state launch, and wheel Arrow/Page/Home/End ARIA synchronization tests. Repaired the parent child graph and progress.
- 2026-07-12: Final focused evidence recorded at `.10x/evidence/2026-07-12-refresh-lifecycle-recovery-hardening.md`: 23 Python and 35 frontend tests passed; Ruff, format, MyPy, TypeScript, secret, and diff gates passed. No forbidden live workflow ran.
- 2026-07-12: Final self-review added isolated process-group termination before ownership release when durable status mutation fails mid-run, closing the last malformed-status orphan path; the focused Python suite passed 23/23 afterward.
- 2026-07-12: Acceptance mapping re-read and fully supported. Owner adversarial cases, authoritative phase, connected ordering/failure, frontend recovery, keyboard semantics, and graph coherence each map to focused tests or inspected records.
- 2026-07-12: Retrospective: a targeted edit briefly emptied the new untracked refresh component test; the file was reconstructed immediately, full line count/diff checks were inspected, and final focused/full-file tests prove restoration. No reusable project-wide convention or new operational skill was warranted beyond preserving the regression tests.

## Blockers

None. Final independent review reruns and aggregate closure remain owned by `.10x/tickets/done/2026-07-11-verify-map-wheel-and-refresh-controls.md`.
