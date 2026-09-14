Status: active
Created: 2026-09-11
Updated: 2026-09-11

# Keep deployment identifiers out of public recovery files

## Context and authority

The publication audit `.10x/reviews/2026-09-10-catalog-recovery-publication-safety.md` found no confirmed credential leak within its stated checks, but found real account/bucket identifiers and account-specific ARNs in the publicly pushed catalog recovery branch. The newest warehouse-versioning records were still uncommitted.

In the structured questionnaire completed on 2026-09-11, the user selected all four recommended options: deployment-identifier redaction; original reports in `~/Private/databox/recovery-evidence/` with FileVault verification, owner-only permissions and no automatic deletion; current-file cleanup without published-history rewriting; and local branches/commits only.

## Decision

- Remove real AWS account IDs, bucket names and account-specific ARNs from public files. Keep reusable code, IAM policy logic, generic role/profile names, synthetic examples and clearly labeled redacted evidence public.
- Preserve exact original operational records privately before redacting them. `.10x/specs/private-recovery-evidence-custody.md` governs the authorized destination and preservation behavior.
- Use the existing validated OpenTofu `aws_account_id` input instead of the literal account component in code and its test. Preserve effective deployment policy; do not add a new `.env` setting or modify real credentials/configuration.
- Keep temporary MFA-issued backup credentials memory-only. Existing `.env`, host AWS configuration, private `.tfvars`, state and binary plans remain in their existing private locations and are not copied into a new evidence bundle.
- Sanitize current candidate trees only. Published commits, main, remote refs and external copies remain unchanged. This deliberately does not erase historical disclosure or certify a future merge strategy as hiding history.
- Separate the complete new versioning record change set onto a local follow-up branch, including its moved decision and cross-reference edits. Local branches, worktrees and commits may be used for lossless isolation. No push, PR creation, merge, history rewrite, credential rotation, AWS mutation or unrelated `uv.lock`/calendar change is authorized.

Public content and branch boundaries are governed by `.10x/specs/public-catalog-recovery-content.md`; work is owned by `.10x/tickets/2026-09-10-ratify-catalog-recovery-publication-boundary.md`.

## Alternatives and consequences

- Credentials-only cleanup was not selected: deployment identifiers should also leave public candidate files.
- Broader concealment of generic roles and policy logic was not selected; do not invent more privacy categories.
- Published-history removal was not selected; no force-push or deletion is justified by this cleanup.
- Publishing exact reports was not selected. Local private originals remain operator-owned with no automatic deletion; no synchronization service or new backup system is added. FileVault alone is not a second copy, and this task makes no new disk-loss guarantee.

No confirmed credential exposure means rotation is not part of this work. Any newly discovered secret must stop the affected publication path and receive a separately scoped response rather than silently broadening this authorization.
