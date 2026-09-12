Status: active
Created: 2026-09-11
Updated: 2026-09-12
Parent: .10x/tickets/2026-09-10-ratify-catalog-recovery-publication-boundary.md
Depends-On: .10x/tickets/done/2026-09-11-preserve-private-recovery-originals.md

# Produce a sanitized local catalog recovery candidate

## Scope

Create a local catalog-cleanup candidate from the published catalog revision, isolated from the pending versioning feature and unrelated work. Replace the account literal with the existing input, sanitize approved deployment identifiers in current public files, preserve provenance, verify locally, and commit only the bounded cleanup. Use a fresh local branch/worktree if needed to keep the original dirty worktree safe; no published history is rewritten.

## References

- `.10x/specs/public-catalog-recovery-content.md`
- `.10x/specs/private-recovery-evidence-custody.md`
- `.10x/decisions/keep-recovery-deployment-identifiers-private.md`
- `.10x/reviews/2026-09-10-catalog-recovery-publication-safety.md`
- `infra/recovery/main.tf`, `infra/recovery/variables.tf`, `tests/platform/test_recovery_infrastructure.py`, `scripts/platform/check_secrets.py`.

## Acceptance criteria and evidence

- Private-custody evidence/review proves originals are safely preserved before any operational record changes. Unexpected identity/classification, missing originals or concurrent source changes block the affected change.
- Sign-in ARN uses `${var.aws_account_id}` in place of its literal account component; its test verifies the parameterized contract. Locally prove equivalent effective policy for the existing input without printing that input or calling AWS. Preserve all actions, resource suffixes, trust constraints and unrelated infrastructure assertions.
- Public candidate content contains no real deployment account IDs, bucket literals or account-specific ARN literals. Exact-value checks are private/aggregate-only; synthetic examples and generic profile/role names remain valid. Do not invent a broader privacy policy.
- Public operational records are clearly redacted, retain correct behavioral/evidence meaning and refindable private originals, and distinguish original hashes from redacted text. Preserve links and repair affected references rather than deleting evidence indiscriminately. Limit any raw-artifact ignore/documentation change to the governed boundary.
- Candidate contains the publication audit, approved contract and cleanup graph, but not the pending S3-versioning feature/spec supersession. Existing catalog implementation remains semantically unchanged except for input parameterization.
- Run focused hermetic infrastructure tests and applicable static/secret/diff checks after inspecting their side effects. Do not use mutating formatter hooks that could touch unrelated work or synchronize dependencies into the user's modified lockfile. Independent review verifies public scope, policy equivalence, provenance and Git boundaries.
- Record candidate revision, exact changed files, evidence/check outputs, preservation of original dirty work and any residual limits. Make only local scoped commits; private originals/configuration must never be staged.

## Exclusions

AWS login/plan/apply, runtime or warehouse operations, credential rotation, new parameters/permissions/services, feature implementation, Git push/PR/merge/history rewrite, published-ref modification, unrelated `uv.lock`/calendar changes, and claiming hosted CI or merge readiness from local checks.

## Progress and notes

- 2026-09-11: Created from ratified scope; implementation has not begun. Generic profile/role labels remain public by explicit selection.

- 2026-09-12: Custody dependency completed with verified private originals and independent/parent checks. Evidence: `.10x/evidence/2026-09-11-private-recovery-originals.md`; review: `.10x/reviews/2026-09-12-private-recovery-originals-review.md`. C1's later raw-index drift is qualified and accepted for custody; do not assert original raw-index equality or overwrite its anchored metadata. Establish a current baseline accounting for recorded closure changes before future execution. This ticket has not started; the current user request covered only preservation.

- 2026-09-12: Explicitly authorized execution of this second child only. Reverified all three custody metadata anchors, 42 HEAD originals/bases and 22 current working variants (64 payloads / 322,252 bytes), all 23 pending versioning dispositions, owner-only modes/ACLs and FileVault on the actual destination. Established a fresh 1,000-path source baseline and retained current raw/logical index fingerprints; no assertion of equality to the earlier custody raw-index anchor.
- 2026-09-12: Created local branch `chore/catalog-recovery-publication-cleanup` and isolated worktree `/Users/crlough/Code/personal/databox.worktrees/catalog-publication-cleanup` from published HEAD `027af8b4271d60ffc193967d092b5d2497af13ad`. Prepared the account-input substitution, scoped test/ignore protection, 30 labeled/redacted operational counterparts and the explicit 11-file publication/custody graph only. Pending versioning remains in the original dirty checkout and verified private snapshot; ticket 3 and final branch-qualified reconciliation are not executed. The candidate is uncommitted; branch HEAD still equals the published base, not the sanitized working tree.
- 2026-09-12: Supervisor classified 12 complete IAM username occurrences across six paths as principal-label uses, not bucket references. They remain unchanged; no blanket substring exception or fictional-identity claim. `docs/configuration.md` is byte-unchanged and needed no new custody copy. Policy equivalence is checked privately with the existing account input, without AWS or configuration export.
- 2026-09-12: Safe execution evidence is candidate-local at `.10x/evidence/2026-09-12-catalog-publication-cleanup.md` on the above worktree/branch (not a file in this original checkout). Original edits are limited to this ticket; parent/dependency records are unchanged. Independent review and parent acceptance/closure remain pending.

- 2026-09-12: Final safe checks passed: 21 focused infrastructure/scanner tests; read-only ruff lint/format checks; 989-file exact-identifier inventory (zero unclassified matches; 12 contextual principal-label occurrences retained); credential scanner on 945 eligible tracked/untracked candidate files; scoped ignore/diff/graph checks; whole-main configured-policy equivalence and original-body/hash provenance. Reverification preserved all 999 protected original path states, 64 private copies, 23 pending dispositions, fresh raw/logical index and preexisting refs/worktrees; both staged sets are empty. No cleanup commit was attempted because of the blocker below.

- 2026-09-12: Fresh independent review completed at `.10x/reviews/2026-09-12-catalog-publication-cleanup-review.md`. It reproduced preparation/custody/policy/provenance checks and 21 passing tests, with no commit. Parent independently matched the 45 reviewed fingerprints and configured whole-main equivalence. New C1 qualifies later raw-index drift against this ticket's fresh baseline; logical entries/protected content remain unchanged, attribution unknown, no repair prescribed. Original unchanged-index claims apply only through the worker check. Parent record reconciliation occurs after those preservation observations.
- 2026-09-12: Parent read-only cache inspection found both pinned hook repositories and existing Python environments/install-state files. Presence is not health verification or execution authority. Proposed narrow next approval: installed hooks may format only scoped cleanup files in the isolated candidate; no installs/downloads or hook bypass, review all resulting changes and rerun checks before a local commit. This proposal is not yet ratified. Ticket stays blocked, both staged sets empty, and ticket 3 remains unexecuted.

- 2026-09-12: User explicitly selected “Allow candidate-only hooks (Recommended)” in the structured checkpoint. Existing hooks may perform required formatting only on scoped cleanup files in this isolated worktree. Verify existing environments first and stop if downloads/installations are needed; review resulting edits and rerun checks before a local commit. No hook bypass, original-worktree edits, push or AWS changes. This resolves B1's authorization question without permitting dependency installation, shared hook/configuration changes or ticket-3 execution. Further progress/closure records are candidate-local; the original checkout remains the preserved pre-continuation snapshot.

- 2026-09-12: Candidate-only cached-hook preparation executed under the user's approval; original checkout is read-only, with no progress synchronization. Established a fresh 1,001-path original / 990-path candidate preservation baseline and explicit 46-path cleanup whitelist, accounting for later parent review/progress additions rather than asserting the obsolete 45-path fingerprint. Reverified all private anchors/copies/protection and both empty logical indices before hooks.
- 2026-09-12: Inspected all applicable executable/legacy Git hooks, installed pre-commit 4.5.1 runner and configured hook implementations. Exact pinned cached Python environments pass installed health/state checks and all eleven entrypoint probes; local system Python is usable. The existing full pipeline on the explicit 46 paths exits 0 with **no formatter byte changes**, no installations/downloads, no hook/configuration bypass or edits. Focused suite rerun: 21 passed; nonmutating lint/format, identifier/credential, policy/provenance, graph/ignore and preservation checks pass. Candidate evidence contains exact commands, environment checks and fresh fingerprints: `.10x/evidence/2026-09-12-catalog-publication-cleanup.md`, “Candidate-only cached-hook preparation.”
- 2026-09-12: Stable 44-path digest excluding only the two evolving candidate progress records: `e6e88675cc46d8bd0e794dd3fcd5e4f51fc473f4128dc4d34c51c4273d65f2ff`; final complete 46-path fingerprints are retained separately after those edits, as linked in evidence. All 1,001 original path states (no ticket exception), private bundle, both fresh raw/logical indices, refs/worktrees and hooks/configuration remain protected. Only candidate evidence and this ticket receive intentional record edits; both actual staged sets stay empty. Preparation is ready for independent review; no staging, commit, ticket closure or ticket-3 execution occurs in this stage.

## Blockers

The previously required cached-environment health and candidate-only hook preparation gates passed without formatting changes or installation. This stage ends unstaged and uncommitted by explicit instruction, not by bypassing normal hooks. Independent review of the new preparation, subsequent authorized local normal-hook commit, exact committed-revision review and parent acceptance remain pending. Recheck environments and preservation before any later commit; stop if installation, broader changes or hook override would be required. Earlier raw-index attribution qualifications remain retained; this ticket is not closed.
