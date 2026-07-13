Status: done
Created: 2026-07-11
Updated: 2026-07-12
Parent: None
Depends-On: None

# Upgrade Field Map, catalog browsing, and refresh controls

## Outcome

Deliver three independent Rufous improvements: photo-backed encounter previews, a subtle accessible bird wheel, and a confirmed background routine source refresh.

## Governing records

- `.10x/decisions/rufous-wheel-map-preview-and-source-refresh.md`
- `.10x/specs/field-map-encounter-photo-preview.md`
- `.10x/specs/arizona-bird-wheel-catalog.md`
- `.10x/specs/local-source-refresh-control.md`

## Child plan

1. `.10x/tickets/done/2026-07-11-add-field-map-encounter-photo-preview.md`
2. `.10x/tickets/done/2026-07-11-build-arizona-bird-wheel-catalog.md`
3. `.10x/tickets/done/2026-07-11-build-local-refresh-runtime-api.md`
4. `.10x/tickets/done/2026-07-11-add-header-source-refresh-control.md` (depends on 3)
5. `.10x/tickets/done/2026-07-12-repair-map-wheel-refresh-review-findings.md` (review repair)
6. `.10x/tickets/done/2026-07-12-harden-refresh-lifecycle-and-recovery.md` (lifecycle hardening)
7. `.10x/tickets/done/2026-07-12-isolate-refresh-status-announcement.md` (frontend aggregate repair)
8. `.10x/tickets/done/2026-07-12-close-refresh-recovery-edge-cases.md` (edge-case repair)
9. `.10x/tickets/done/2026-07-12-prove-process-group-and-terminal-cas.md` (process/CAS proof)
10. `.10x/tickets/done/2026-07-12-require-empty-group-on-normal-exit.md` (normal-exit group proof)
11. `.10x/tickets/done/2026-07-11-verify-map-wheel-and-refresh-controls.md` (depends on 1–10)

Aggregate verification follows all implementation and review-repair children.

## Aggregate acceptance

- Encounter rows show validated thumbnails and hover/focus-only unclustered map highlights.
- Arizona Birds uses one accessible subtle centered wheel and one identity-matched preview without pagination or autoplay.
- Header launches exactly the routine six-source Quack/SQLMesh refresh after confirmation, one at a time, with durable safe status and temporary-busy disclosure.
- Privacy, identity, licensing, source ownership, personal/runtime-state preservation, accessibility, and full backend/frontend/data/static gates pass with independent reviews.

## Exclusions

No AVONET/media refresh, external map resources, strong 3D wheel, autoplay, staged warehouse swap, automatic retry, or live source refresh during ordinary tests.

## Progress and notes

- 2026-07-11: User ratified highlight-only map preview, subtle wheel, routine six-source refresh, confirmed background execution, temporary warehouse-busy behavior, and validated GBIF thumbnail requests with map resources remaining local.
- 2026-07-11: All four implementation children completed and aggregate verification began.
- 2026-07-12: Three bounded repair children resolved findings from review and aggregate cycles; evidence is indexed by the verification ticket.
- 2026-07-12: A later worker accidentally emptied this parent file; the orchestrator restored it from the previously inspected record before continuing.
- 2026-07-12: Closure-grade reviews found remaining hard-runner-crash, durable-status validation/CAS, wheel recentering, browser source-contract, and connected-evidence findings. Child 8 owned them.
- 2026-07-12: Child 8 closed with hard-kill-safe pre-mutation gating, strict durable status, terminal recheck, dynamic browser source contract, connected success/failure evidence, and wheel recentering. Evidence: `.10x/evidence/2026-07-12-refresh-recovery-edge-case-closure.md`.
- 2026-07-12: Post-edge reviews passed UX but found whole-process-group cleanup, terminal CAS, and connected-test ordering gaps. Child 9 resolved that slice.
- 2026-07-12: Definitive reviews required normal-exit whole-group proof plus a real leader-gone/SIGTERM-ignoring-descendant regression. Child 10 initially closed with focused 34-test evidence, then reopened after an unexpected post-launch `ValueError` exposed a fail-open release path.
- 2026-07-12: Child 10 reclosed with fail-closed default ownership, outer `BaseException` cleanup, `ValueError` uncertainty retention, and propagated `KeyboardInterrupt`/`SystemExit` regressions. Final focused suite passed 37/37; evidence updated at `.10x/evidence/2026-07-12-normal-exit-process-group-proof.md`.
- 2026-07-12: Definitive post-cleanup aggregate gates and state checks passed. Architecture, correctness, privacy/security/source, and UX/accessibility reviews found no implementation blocker; architecture requested final record reconciliation, which was completed and documented.
- 2026-07-12: Aggregate verification closed at `.10x/tickets/done/2026-07-11-verify-map-wheel-and-refresh-controls.md`. Independent parent closure review passed at `.10x/reviews/2026-07-12-map-catalog-refresh-parent-closure-review.md`.
- 2026-07-12: Retrospective complete. Durable lifecycle invariants are preserved in the active spec, implementation, focused process tests, and evidence; no follow-up or new skill is required.

## Blockers

None.
