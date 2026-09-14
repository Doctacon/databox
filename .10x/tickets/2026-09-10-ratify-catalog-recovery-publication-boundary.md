Status: open
Created: 2026-09-10
Updated: 2026-09-14
Parent: None
Depends-On: None

# Prepare public-safe catalog recovery and separate versioning work

> Candidate-local authority (2026-09-12): child 2 is complete at implementation commit `75e2d5bea39d67f9961c68909134db635e3c3ed8`, with candidate-local closure records below. The original checkout and its older progress snapshot remain untouched under the user's read-only boundary. Current owner: `.10x/tickets/done/2026-09-11-sanitize-catalog-recovery-publication.md`; exact-commit review: `.10x/reviews/2026-09-12-catalog-publication-commit-review.md`. Child 3 record recovery is now implemented on the follow-up below; independent review/closure remain pending.

> Follow-up reference scope (2026-09-14): the following feature paths are recovered on local `feature/warehouse-file-recovery` at `7d402878addf2dc1585e499b1809c4e1cbddbd49`, based on merged main `8321475dda7b3a041e8dd8efe668c923cf723fb5`. They are present in this follow-up tree, not in that catalog-only base. Historical observations below retain their execution-time meaning; recovery does not authorize feature implementation or AWS changes.
> `.10x/tickets/2026-09-10-protect-iceberg-warehouse-object-versions.md`

## Aggregate scope — parent plan, not executable

Preserve original operational records privately, produce a sanitized local catalog-recovery candidate, and carry the pending warehouse-versioning records onto a separate local follow-up branch. The user approved the exact four questionnaire choices on 2026-09-11; this replaces the former shaping blockers. No push, PR, merge, published-history rewrite, AWS mutation, credential rotation, or unrelated-work change is authorized.

## Governing records

- `.10x/decisions/keep-recovery-deployment-identifiers-private.md`
- `.10x/specs/private-recovery-evidence-custody.md`
- `.10x/specs/public-catalog-recovery-content.md`
- `.10x/reviews/2026-09-10-catalog-recovery-publication-safety.md`

## Ratification reconciliation

| Prior question | User-confirmed answer | State |
| --- | --- | --- |
| Public/private boundary | Remove real AWS account IDs, bucket names and account-specific ARNs; keep reusable code, policy logic, generic role/profile names and redacted evidence. | Answered |
| Private originals | `~/Private/databox/recovery-evidence/`, verified FileVault, owner-only access, no automatic deletion. | Answered |
| Already-public history | Current files only; leave published history unchanged, with no rewrite or force-push. Old material remains accessible. | Answered |
| Git authority | Local branches and commits; separate versioning records. No push, PR, merge, AWS changes, rotation or unrelated `uv.lock` edit. | Answered |

Implementation authorization is present for these concrete boundaries. Do not ask the same four questions again. A failed technical preflight or genuinely new scope conflict must be recorded rather than guessed.

## Ordered child plan

1. `.10x/tickets/done/2026-09-11-preserve-private-recovery-originals.md` — done: verify protection/ownership, inventory originals and pending variants, copy and verify private custody. **Verify:** exact-byte/digest matches, permissions, safe destination and preserved pending work.
2. `.10x/tickets/done/2026-09-11-sanitize-catalog-recovery-publication.md` — done: create a clean local catalog candidate, parameterize the existing account input and sanitize public records after preservation. **Verify:** effective-policy equivalence, scoped hermetic tests, identifier/credential checks, provenance/link coherence and independent review.
3. `.10x/tickets/2026-09-11-separate-warehouse-versioning-record-branch.md` — open, implemented pending independent review: recovered the complete versioning record set on the user-directed merged-main follow-up. **Verify:** exact path accounting, retained semantics, no reintroduced identifiers, coherent branches, local-only commits and unchanged unrelated work.

Keep mutations sequential with one writer per worktree. Assign executable children to subagents with all governing records. The parent reviews evidence, reconciles ownership and records closure only when the criteria below are supported. No implementation occurs in the turn authoring these governing specs/first executable children.

## Integration and acceptance

- Use the existing `aws_account_id` input in `infra/recovery/main.tf` and its corresponding test; do not create `.env` variables, broaden policy or alter runtime configuration.
- The published starting revision is `027af8b4271d60ffc193967d092b5d2497af13ad`. Verify it and the dirty/index state before operations; preserve unexpected/concurrent work. Audit evidence identified 11 tracked changes plus 12 untracked paths belonging to pending versioning, separate from the publication review/owner and later cleanup records.
- All selected originals are privately preserved before public redaction. Public counterparts are labeled and retain truthful source/hash provenance. No private bundle/configuration is staged or committed.
- Candidate branches contain their intended work with approved identifiers removed from current public trees, unchanged effective infrastructure behavior, preserved generic examples/roles and no silently weakened recovery/security contracts.
- The versioning feature remains governed by `.10x/tickets/2026-09-10-protect-iceberg-warehouse-object-versions.md`; its AWS, restore and implementation children are not executed here.
- Local verification/review and original pending-path accounting must be recorded. Unrelated `uv.lock`, calendar files, credentials, local state, active services, warehouse data and preserved recovery resources remain unchanged.
- Final results name the local candidate revisions and preserved private evidence location without exposing redacted values. No claim that local cleanup erases public history or establishes full merge readiness.

## Existing owners and excluded future work

The original catalog aggregate `.10x/tickets/2026-09-04-build-polaris-iceberg-disaster-recovery.md` retains its prior closure obligations. The IAM audit remains with `.10x/tickets/2026-09-05-establish-primary-warehouse-session-credentials.md`. Neither is closed by publication cleanup.

Hosted CI for the final candidate and any PR/push/merge remain a separately authorized publication gate owned here for future continuation, not a blocker to completing the local-only children. No remote workflow is launched merely to get a green result. Public-history removal and credential rotation are excluded under the ratified choice; no action is taken solely for identifier exposure.

## Progress and notes

- 2026-09-10: Opened after read-only local Git/credential-pattern inspection and anonymous GitHub GETs established that the branch is already public and contains deployment identifiers. Wrote only redacted local assessment/owner records; no code, branch, index, remote, AWS, runtime, or credential state changed.
- 2026-09-11: The user selected all four recommended questionnaire answers. Activated the focused publication/custody contracts and decision; replaced shaping-only scope with this parent plan and three bounded sequential children. Rechecked unchanged HEAD and unstaged work; no private copy, branch/ref change, implementation, test suite, commit, or AWS action ran in this planning turn.

- 2026-09-12: Executed and closed child 1 only after the user's explicit first-ticket request. Verified private bundle `~/Private/databox/recovery-evidence/2026-09-11T235551Z-05aef1141954/` contains 42 HEAD originals/bases and 22 working variants, with correct permissions/FileVault and recoverable pending work. Independent review and parent checks are recorded in `.10x/evidence/2026-09-11-private-recovery-originals.md` and `.10x/reviews/2026-09-12-private-recovery-originals-review.md`. Accepted C1 as a nonblocking audit qualification: later raw-index drift is unexplained, while all 977 logical entries match HEAD and no staged content/path/mode loss was found. No index repair or attribution claim. Retrospective recorded in `.10x/knowledge/git-index-and-worktree-fingerprints.md`.
- 2026-09-12: Aggregate progress 1/3 local children complete. Child 2's custody dependency is satisfied; it remains unstarted, and child 3 still depends on it. Parent closure maintenance changes records/references only; no redaction, Git branch/index/ref operation, commit, AWS call or later-ticket execution.

- 2026-09-12: User approved installed normal hooks only on scoped candidate files, after health checks, with no installation/bypass or original-checkout edit. Both scoped preparation hook runs and the local commit passed with no formatter byte changes. Committed reviewed cleanup as `75e2d5bea39d67f9961c68909134db635e3c3ed8`. Fresh precommit and recovered exact-commit reviews, 21 focused tests and parent checks support completion. New post-writer candidate raw-index attribution remains explicitly qualified and accepted as nonblocking; committed/logical content and original/private state verify, no repair performed.
- 2026-09-12: Aggregate progress 2/3 local children complete. Candidate-local record-only handoff closes child 2 and repairs current owner/dependency links; historical execution inventories retain old filenames. Retrospective captured in the local pre-commit and fingerprint knowledge records. Original checkout, its records, dirty lock and pending versioning work remain unchanged. Child 3 is ready but has not been executed; no versioning branch, push, PR, merge or AWS action follows from this closure.

- 2026-09-14: User reported the catalog feature merged and requested a new warehouse/file-recovery branch. Parent created `feature/warehouse-file-recovery` from clean merged main `8321475dda7b3a041e8dd8efe668c923cf723fb5`. Child 3 recovered the verified 23-path snapshot delta in `7d402878addf2dc1585e499b1809c4e1cbddbd49`; publication cleanup survives, exact branch-qualified pointers now live on this follow-up, and original private/other-checkout work is not removed. Evidence: `.10x/evidence/2026-09-14-warehouse-versioning-record-recovery.md`. Closure remains 2/3 accepted, child 3 implemented awaiting independent review/parent acceptance. This does not execute any warehouse feature child or authorize AWS mutation.

## Blockers

Child 3 independent exact-commit review and parent acceptance remain. Main and the old cleanup branch are intentionally unchanged; current follow-up records own the branch/revision reconciliation while those historical trees retain dated snapshots. The feature's read-only inspection is the next separately directed work item; deployment and restore choices remain independently gated. Hosted publication remains outside this pass.
