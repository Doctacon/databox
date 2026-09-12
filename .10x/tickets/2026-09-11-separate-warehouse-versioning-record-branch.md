Status: blocked
Created: 2026-09-11
Updated: 2026-09-11
Parent: .10x/tickets/2026-09-10-ratify-catalog-recovery-publication-boundary.md
Depends-On: .10x/tickets/2026-09-11-sanitize-catalog-recovery-publication.md

# Separate versioning records onto a clean local follow-up branch

> Candidate reference scope: the following paths denote preserved pending/future third-ticket material in the original dirty checkout and private custody snapshot, NOT files in this catalog-only candidate. No versioning follow-up branch/revision exists yet; final branch-qualified reconciliation belongs to ticket 3.
> `.10x/tickets/2026-09-10-protect-iceberg-warehouse-object-versions.md`

## Scope

Carry the previously uncommitted warehouse-versioning record work onto its own local follow-up branch based on the sanitized catalog candidate. Preserve the original approved semantics and pending changes, applying only the approved publication redactions to prevent identifiers being reintroduced. This is record/Git separation, not implementation of S3 versioning.

## References

- `.10x/specs/public-catalog-recovery-content.md`
- `.10x/specs/private-recovery-evidence-custody.md`
- `.10x/reviews/2026-09-10-catalog-recovery-publication-safety.md`
- `.10x/tickets/2026-09-10-protect-iceberg-warehouse-object-versions.md` — governs the feature record set, not authority to execute its AWS/code children here.
- Private custody evidence/snapshot and sanitized-candidate evidence from the dependencies.

## Acceptance criteria and evidence

- Identify every pending versioning path using the verified snapshot, not an indiscriminate `.10x` glob. Account for all 11 originally tracked changes and 12 untracked paths, including the moved original decision and affected historical/current links. Publication records and unrelated work are excluded from the feature delta.
- Create a fresh local follow-up branch from the sanitized catalog candidate; collisions stop. Do not merge, rebase or rewrite published history, push, create a PR, or change main.
- Transfer the complete versioning contract/plan, preserving 30-day retention, the approved version-delete Deny, unresolved restore-tool choices and the no-AWS-change gate. Only approved redactions/provenance repairs may change the captured record contents.
- Verify both candidate trees for deployment identifiers/credentials and their own record-link/status coherence. Where cleanup records refer to the feature-only plan, make an explicit local branch/revision-qualified pointer and, if necessary, a pointer-only local cleanup-branch commit; do not pretend the feature files exist in the cleanup tree or copy them back. The follow-up diff contains versioning record work only; inherited publication cleanup must not be reverted by a moved or restored record.
- Make a scoped local record commit. Before removing any selected pending work from the original worktree, prove it is preserved in the follow-up commit or private original snapshot and that no concurrent edits would be lost. No broad reset/stash, branch replacement or cleanup. Unrelated `uv.lock` and personal files remain byte-unchanged.
- Record branch/revision identities, disposition of every original pending path, record/secret/diff checks, unchanged unrelated-work evidence and independent review. Catalog-only and follow-up ownership must be cold-reader clear.

## Exclusions

Implementing/executing versioning tickets, creating/deleting cloud resources, modifying runtime credentials, removing evidence/private bundles or recovery resources, published-history cleanup, pushes, PRs, merges and unrelated worktree edits.

## Progress and notes

- 2026-09-11: Created after explicit local branch/commit authority. No branch/worktree/ref operation has run.

## Blockers

Sanitized catalog candidate and verified custody snapshot from dependencies. Newly discovered uncaptured/concurrent work must be preserved and reconciled before any removal.
