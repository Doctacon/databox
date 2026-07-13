Status: done
Created: 2026-07-12
Updated: 2026-07-12
Parent: .10x/tickets/done/2026-07-11-upgrade-map-catalog-and-refresh-controls.md
Depends-On: .10x/tickets/done/2026-07-12-close-refresh-recovery-edge-cases.md

# Prove process-group cleanup and terminal CAS

## Scope

Resolve the two remaining closure blockers and one evidence-order gap:

1. Recovery/runner cleanup MUST prove the entire recorded orchestration process group is gone before releasing ownership, not merely the gate leader. A missing leader with surviving group descendants MUST remain fail closed; a verified leader may be terminated, but ownership releases only after group nonexistence is established. The runner's caught-error path follows the same rule.
2. Recovery failure publication MUST be an actual cross-process compare-and-swap: terminal status written after recovery inspection can never be overwritten by stale active state. Apply the same invariant to GET and POST stale recovery.
3. Connected exact-six success/failure tests MUST launch the API first, derive source arguments from its command, and use those arguments to invoke the real orchestration seam before passing output through the durable runner.

## Governing records

- `.10x/specs/local-source-refresh-control.md`
- `.10x/decisions/rufous-wheel-map-preview-and-source-refresh.md`
- `.10x/reviews/2026-07-12-map-wheel-refresh-post-edge-architecture-review.md`
- `.10x/reviews/2026-07-12-map-wheel-refresh-post-edge-correctness-review.md`
- `.10x/reviews/2026-07-12-map-wheel-refresh-post-edge-privacy-security-source-review.md`
- `.10x/reviews/2026-07-12-map-wheel-refresh-post-edge-ux-accessibility-review.md`

## Acceptance criteria

- Process-group existence is checked directly (not inferred from leader identity). Tests cover: gate leader exits while a signal-resistant/slow descendant remains; ownership stays locked or escalates and is released only after the group is proven empty; uncertainty stays fail closed.
- Runner caught-error cleanup also withholds owner release unless its process group is proven empty.
- Status writes and recovery active→failed transition use a bounded cross-process lock/CAS or equivalent atomic conditional update. A deterministic interleaving test writes terminal success after recovery inspection but before conditional publication and proves success remains.
- Connected success/failure tests derive real orchestration input from API launch before invoking `execute_parallel_refresh`; each asserts one Quack server and maintenance/SQLMesh ordering.
- Focused Python, Ruff/format/MyPy, secret and diff checks pass. No frontend change is expected.

## Evidence expectations

Record process-group survivor mechanics, CAS interleaving, connected test ordering, commands/results, and no-live-workflow limits.

## Exclusions

No live provider/refresh/warehouse/SQLMesh/model/email/media workflow, frontend semantic change, multi-worker expansion, or unrelated refactor.

## Progress and notes

- 2026-07-12: Opened after final post-edge reviews; UX/accessibility passed, while architecture/correctness/privacy found these bounded remaining issues.
- 2026-07-12: Added direct whole-process-group existence proof and fail-closed group cleanup in API and runner; missing leaders with surviving descendants no longer unlock.
- 2026-07-12: Added cross-process locked conditional active-to-failed transition and deterministic terminal-write interleaving coverage.
- 2026-07-12: Reordered exact-six success/failure proofs so API-derived source arguments drive the real orchestration seam before runner marker processing.
- 2026-07-12: Evidence recorded at `.10x/evidence/2026-07-12-process-group-terminal-cas-proof.md`: 31 focused tests passed; Ruff/format/MyPy/secret/diff gates passed; parent remained nonempty.
- 2026-07-12: Acceptance mapping re-read and complete. Retrospective invariant: ownership release requires proof that the entire recorded process group is absent, while durable recovery transitions require a cross-process conditional write.

## Blockers

None. Final aggregate review/closure remains owned by `.10x/tickets/done/2026-07-11-verify-map-wheel-and-refresh-controls.md`.
