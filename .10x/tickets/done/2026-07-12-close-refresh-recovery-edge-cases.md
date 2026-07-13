Status: done
Created: 2026-07-12
Updated: 2026-07-12
Parent: .10x/tickets/done/2026-07-11-upgrade-map-catalog-and-refresh-controls.md
Depends-On: .10x/tickets/done/2026-07-12-harden-refresh-lifecycle-and-recovery.md, .10x/tickets/done/2026-07-12-isolate-refresh-status-announcement.md

# Close refresh recovery edge cases

## Scope

Resolve all remaining closure-grade review findings without changing ratified product semantics:

- prevent abrupt runner death from orphaning a warehouse-mutating orchestration that can overlap a retry;
- strictly validate durable backend status: exact canonical ordered source rows with unique names and valid states, bounded safe timestamps/messages/log basename/run identity, and coherent state fields;
- make GET recovery re-read/compare active run state before publishing failure so it cannot overwrite a concurrent terminal success;
- remove frontend source-registry cardinality ownership while retaining bounded unique server-supplied progress validation and exact runtime confirmation derived from current status;
- strengthen the exact-six connected success/failure fake so both begin from API launch and exercise one real orchestration seam with one Quack owner, maintenance ordering, and SQLMesh suppression;
- recenter the wheel's first matching result after filter/sort/search/reset changes, respecting reduced motion;
- preserve the restored parent graph.

## Governing records

- `.10x/specs/local-source-refresh-control.md`
- `.10x/specs/arizona-bird-wheel-catalog.md`
- `.10x/decisions/rufous-wheel-map-preview-and-source-refresh.md`
- `.10x/reviews/2026-07-12-map-wheel-refresh-closure-architecture-review.md`
- `.10x/reviews/2026-07-12-map-wheel-refresh-closure-correctness-review.md`
- `.10x/reviews/2026-07-12-map-wheel-refresh-closure-privacy-security-source-review.md`
- `.10x/reviews/2026-07-12-map-wheel-refresh-closure-ux-accessibility-review.md`

## Acceptance criteria

- Before orchestration can mutate, the parent runner durably publishes enough child/process-group identity for recovery; if the runner dies, stale recovery must verify and terminate/reap or fail closed on any surviving exact-run orchestration before ownership can release. No gap may permit a child to mutate without durable ownership. Tests use a bounded local fake process tree and prove abrupt runner kill cannot overlap retry; no provider/warehouse mutation occurs.
- Backend status validation rejects wrong/empty/reordered/duplicate sources, invalid timestamps, overlong/arbitrary messages, unsafe log names/paths, incoherent run/state/finished fields, and extra values. Runner predicates never trust an unvalidated empty/malformed list.
- GET failure publication uses a current same-run active-state check and cannot overwrite success/failed terminal status written concurrently; an interleaving regression proves this.
- Frontend validates a bounded nonempty unique progress set without freezing canonical cardinality or names; confirmation names the current server-provided routine sources and cannot launch while status is unknown.
- Connected exact-six success and source-failure tests start from API-derived arguments and pass output from the real orchestration seam through the durable runner; both assert exactly one Quack server and cleanup/dedupe/inspection ordering, with success entering SQLMesh only after maintenance and failure never entering SQLMesh.
- Filter, sort, search, and reset recenter the first result with `auto` under reduced motion; focused tests prove active/ARIA/preview/scroll synchronization.
- Parent/child/evidence graph remains nonempty and current.
- Focused Python/frontend, TypeScript, Ruff/format/MyPy, secret and diff gates pass with no live external effects.

## Design constraint

A hard-kill-safe design MUST NOT merely add another runner `finally` path. Use a pre-mutation gate/handshake and durable child process-group identity, or execute orchestration in the durably owned process, so abrupt runner death cannot create an untracked mutator. Stale inspection failure remains fail closed.

## Evidence expectations

Dedicated evidence must record adversarial process-tree test mechanics, status-validation table, CAS interleaving, connected success/failure ordering, frontend dynamic contract/recentering, commands/results, restored parent checksum/nonzero size, and no-live-workflow limits.

## Exclusions

No live refresh/provider/model/email/AVONET/media/SQLMesh apply, multi-worker support, semantic source-set expansion, binary download, or unrelated refactor.

## Progress and notes

- 2026-07-12: Opened from the third closure-grade review round. The parent record was restored before ticket creation.
- 2026-07-12: Added a pre-mutation run-ID gate and durable runner/gate process-group ownership. A bounded local hard-exit process-tree test proves abrupt runner death cannot overlap retry; uncertain inspection remains fail closed.
- 2026-07-12: Hardened canonical backend status validation, same-run terminal recheck, different-run owner preservation, dynamic bounded browser progress, current-source confirmation, API-derived connected success/failure proofs, and reduced-motion wheel recentering for search/sort/filter/reset.
- 2026-07-12: Evidence recorded at `.10x/evidence/2026-07-12-refresh-recovery-edge-case-closure.md`: 27 focused Python, 726 full Python, 36 focused frontend, and 273 full frontend tests passed; build/bundle, Ruff/format, MyPy, TypeScript, secret, and diff gates passed. No live workflow ran.
- 2026-07-12: Acceptance mapping re-read and complete. The restored parent remained nonempty. Retrospective: process ownership must be published before a child receives its mutation handshake; durable PID alone is insufficient when the child can begin first. This invariant is now encoded in the gate and hard-exit regression.

## Blockers

None. Final aggregate review/closure remains owned by `.10x/tickets/done/2026-07-11-verify-map-wheel-and-refresh-controls.md`.
