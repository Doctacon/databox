Status: done
Created: 2026-07-12
Updated: 2026-07-12
Parent: .10x/tickets/done/2026-07-11-upgrade-map-catalog-and-refresh-controls.md
Depends-On: .10x/tickets/done/2026-07-12-prove-process-group-and-terminal-cas.md

# Require empty process group on normal exit

## Scope

Close the final process-lifecycle proof gap:

- after every gate exit—success, ordinary nonzero, or caught error—the runner MUST prove the entire recorded process group absent before releasing ownership; surviving descendants MUST be terminated/escalated and ownership retained on uncertainty;
- add a bounded real POSIX process-group test where the leader exits while a descendant ignores SIGTERM, proving recovery remains locked until the group is explicitly proven absent;
- add runner coverage for ordinary gate exit with a surviving/uncertain group;
- repair moved-ticket graph references; final aggregate verification will rerun full gates separately.

## Governing records

- `.10x/specs/local-source-refresh-control.md`
- `.10x/reviews/2026-07-12-map-wheel-refresh-definitive-architecture-review.md`
- `.10x/reviews/2026-07-12-map-wheel-refresh-definitive-correctness-review.md`
- `.10x/reviews/2026-07-12-map-wheel-refresh-definitive-privacy-security-source-review.md`
- `.10x/reviews/2026-07-12-map-wheel-refresh-definitive-ux-accessibility-review.md`

## Acceptance criteria

- Normal success/nonzero paths call whole-group absence proof before ownership release; if descendants remain, group TERM/KILL cleanup runs and release occurs only after absence; uncertainty keeps the owner.
- A real temporary leader exits while a descendant ignores SIGTERM in the same PGID; status recovery does not unlink ownership or permit retry while that group survives. Cleanup leaves no process.
- Focused refresh tests, Ruff/format/MyPy, secret/diff checks pass.
- Parent and verification references point to completed proof tickets and this active child until it closes.

## Exclusions

No live provider/refresh/warehouse/SQLMesh/frontend/model/email/media workflow.

## Progress and notes

- 2026-07-12: Opened from definitive reviews. Terminal CAS, source ownership, connected test ordering, and UX already pass.
- 2026-07-12: Runner now proves whole-PGID absence after normal zero/nonzero exit and retains ownership on cleanup uncertainty.
- 2026-07-12: Added a real leader-gone/SIGTERM-ignoring-descendant regression with guaranteed group cleanup, plus parameterized normal-exit runner coverage.
- 2026-07-12: Focused 34-test suite, Ruff/format/MyPy, secret, diff, no-staged, and stale-process checks passed. Evidence: `.10x/evidence/2026-07-12-normal-exit-process-group-proof.md`.
- 2026-07-12: Acceptance mapping was initially considered complete. Retrospective invariant: every exit path, including success, requires whole-process-group absence before durable ownership release.
- 2026-07-12: Reopened after final privacy review reproduced an unexpected post-launch `ValueError` escaping the narrow handler while `safe_to_release` remained true, deleting ownership without PGID cleanup. Every post-launch exception path must default to retained ownership until cleanup/absence proof succeeds.
- 2026-07-12: Repaired release safety to default fail closed after launch and added an outer `BaseException` cleanup guard. Unexpected exceptions and interrupts now clean/prove the PGID before release and retain normal propagation.
- 2026-07-12: Regression evidence injects `ValueError` after `SOURCE_START` and proves cleanup called plus owner retained on uncertainty; `KeyboardInterrupt`/`SystemExit` cleanup and propagation are also covered. Focused final suite passed 37/37; Ruff/format/MyPy/secret/diff/no-staged gates passed. Evidence updated at `.10x/evidence/2026-07-12-normal-exit-process-group-proof.md`.
- 2026-07-12: Acceptance mapping re-read and complete. No new broader lesson beyond the already-recorded invariant that post-launch ownership release requires positive whole-PGID cleanup proof.

## Blockers

None. Final aggregate verification and reviews remain owned by the verification ticket.
