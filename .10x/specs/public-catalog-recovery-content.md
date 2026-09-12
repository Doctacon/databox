Status: active
Created: 2026-09-11
Updated: 2026-09-11

# Public-safe catalog recovery content and branch separation

## Scope and authority

`.10x/decisions/keep-recovery-deployment-identifiers-private.md` ratifies current-file cleanup and local-only branch/commit operations. The starting published catalog revision is `027af8b4271d60ffc193967d092b5d2497af13ad`. Preserve the original worktree and unrelated changes until the selected record changes have a verified durable owner; do not use broad resets, stashes, staging, cleanup or forced branch replacement.

## Public-content contract

1. Candidate trees MUST exclude the deployment's real AWS account IDs, actual bucket-name literals and account-qualified deployment ARN literals. Identify exact values from the audited records and bounded existing local configuration, without printing them or guessing from broad numeric/name patterns. Synthetic account IDs/bucket examples and generic role/profile names MUST remain distinguishable and usable. Ambiguous ownership/classification MUST block the affected substitution rather than redact unrelated data.
2. Code MUST derive the sign-in ARN account component from the already validated `var.aws_account_id`. Keep the action, service, region, resource suffix, trust conditions, grants and all other effective AWS permissions unchanged. Its test MUST verify the parameterized contract rather than the real account number. No new runtime variable, permission grant, credential change or AWS plan/apply is required.
3. Existing private configuration remains private and unchanged. `.env.example` and infrastructure examples MUST contain only blank/synthetic values. Do not move IAM policy logic into `.env` or persist temporary backup credentials there.
4. Before redacting operational records, satisfy `.10x/specs/private-recovery-evidence-custody.md`. Prefer preserving public record paths with labeled redactions/summaries and repaired pointers over deleting the record graph. Preserve observations, decisions, acceptance criteria and limitations; public sanitization MUST NOT fabricate new verification, close old tickets, invalidate their provenance silently, or revive rejected plans.
5. Exact operational text exports that remain as public counterparts MUST be explicitly labeled redacted and traceable to privately preserved originals. Future raw copies must not be accidentally added; any ignore/documentation adjustment MUST be limited to the approved private/raw artifact boundary, not a blanket exclusion of unrelated 10x records or evidence.

## Raw recovery artifact handling

`.10x/evidence/.storage` is not a private directory. Never force-add raw recovery plan exports:
keep future exact originals under the approved private custody root after its protection gates,
and publish only labeled, reviewed redacted counterparts/summaries with original-byte provenance.
The scoped `.tfplan.txt` and Databox `*-plan.txt` ignore rules prevent accidental new raw exports
in that evidence directory; they do not untrack historical redacted counterparts or ignore other
10x records, source-reconciliation artifacts, or evidence categories.

## Local branch contract

- Keep the catalog publication cleanup and the newer versioning record change set on separate local branch tips. Creating isolated local worktrees/branches and commits is authorized; branch names are mechanical choices, and collisions MUST stop rather than overwrite existing refs.
- The versioning set includes its new decision/specs/research/six-ticket plan, the moved earlier decision, and all related tracked-file/cross-reference changes identified by the audit (11 tracked changes and 12 untracked paths at that snapshot). Publication audit/cleanup records and unrelated `uv.lock` are not versioning content.
- The follow-up branch MUST retain the ratified versioning semantics and correct links while using the cleaned publication foundation; carrying old pending records MUST NOT reintroduce deployment identifiers. Prefer a fresh follow-up branch based on the clean local catalog candidate, without rewriting published commits or merging branches.
- References to records intentionally owned only by the other local branch MUST be explicitly branch/revision-qualified, rather than presented as files present in the catalog-only tree. The final separation step may commit the corresponding pointer-only repairs on the cleanup branch; it MUST NOT copy the feature contract back into that branch merely to satisfy a link check.
- No force-push, push, PR, merge, main update, public-ref rewrite, credential rotation, AWS operation, or removal of existing recovery resources is permitted. Do not delete original pending work until its exact approved contents are safely accounted for and verified; unexpected concurrent changes stop reconciliation.

## Acceptance scenarios and evidence

- For the configured account, the parameterized and original sign-in policy are equivalent, proved locally without credentialed AWS calls; tests still enforce the original scoped permissions.
- All exact deployment-identifier matches in the candidate tree are removed or individually classified as a verified synthetic/generic value. Credential scans pass. Inspect content, not just filenames or ignore rules.
- Every redacted operational counterpart has a verified private original; record references remain coherent and original/redacted hashes are not confused.
- Catalog and versioning branch tips contain their intended work only. Their diff/revisions and the disposition of every original pending path are recorded, with unrelated work byte-preserved and no private bundle staged.
- Focused hermetic infrastructure tests, applicable static/diff/secret checks and independent review support local completion. Hosted CI is a later publication gate, not authorized to be triggered through a push/PR here. No claim that local cleanup erases already-public history or establishes general merge readiness is allowed.
