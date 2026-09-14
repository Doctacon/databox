Status: open
Created: 2026-09-11
Updated: 2026-09-14
Parent: .10x/tickets/2026-09-10-ratify-catalog-recovery-publication-boundary.md
Depends-On: .10x/tickets/done/2026-09-11-sanitize-catalog-recovery-publication.md

# Separate versioning records onto a clean local follow-up branch

> Follow-up reference scope (2026-09-14): the following feature paths are recovered on local `feature/warehouse-file-recovery` at `7d402878addf2dc1585e499b1809c4e1cbddbd49`, based on merged main `8321475dda7b3a041e8dd8efe668c923cf723fb5`. They are present in this follow-up tree, not in that catalog-only base. Historical observations below retain their execution-time meaning; recovery does not authorize feature implementation or AWS changes.
> `.10x/tickets/2026-09-10-protect-iceberg-warehouse-object-versions.md`

## Scope

Carry the previously uncommitted warehouse-versioning record work onto its own local follow-up branch based on the sanitized catalog candidate. Preserve the original approved semantics and pending changes, applying only the approved publication redactions to prevent identifiers being reintroduced. This is record/Git separation, not implementation of S3 versioning.

## Current execution boundary — 2026-09-14

The user reported the catalog branch merged into main and requested a new warehouse/file-recovery branch. Use the parent-created `feature/warehouse-file-recovery` from clean merged main `8321475dda7b3a041e8dd8efe668c923cf723fb5` instead of the older standalone sanitized candidate. Recover from the verified custody snapshot; do not remove pending work in any other checkout. Main, the old cleanup branch and published history remain unchanged. Cross-branch pointer repairs live only on this follow-up; their dated historical counterparts on the catalog-only base remain frozen. This is the approved base/scope adjustment, not authority to execute the recovered children.

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

- 2026-09-12: Dependencies completed in the cleanup candidate. Implementation commit `75e2d5bea39d67f9961c68909134db635e3c3ed8` and its record-only closure handoff are the clean foundation; read `.10x/reviews/2026-09-12-catalog-publication-commit-review.md` and current parent progress. The original checkout and its pending 23-path versioning set remain untouched. This ticket has not started; no follow-up branch exists. Recheck current candidate HEAD and the preserved source snapshot rather than relying on obsolete raw-index equality.

- 2026-09-14: Revalidated the custody anchors, all 64 payloads/42 source blobs, canonical ownership/modes/ACLs and actual-volume FileVault. Recovered all 23 original dispositions (10 modified, one deleted, 12 new/moved paths) with approved exact redactions and original-working hashes. Existing publication banners and cleanup body semantics survive; moved original provenance explicitly names the former path. Full path-by-path accounting: `.10x/evidence/2026-09-14-warehouse-versioning-record-recovery.md`.
- 2026-09-14: Local feature-only commit `7d402878addf2dc1585e499b1809c4e1cbddbd49` has sole parent `8321475dda7b3a041e8dd8efe668c923cf723fb5`. Normal installed hooks passed without installation, bypass or byte changes. All 22 recovered bodies match the sanitized private working variants exactly after removing provenance labels; six-ticket dependencies are acyclic and feature record links resolve. Merged-main/follow-up identifier and credential scans pass (992/1,004 blobs, 952/964 credential-eligible files at that observation); exact generic principal contexts remain classified, not blanket bucket exceptions. Whitespace/diff checks pass. No runtime tests or AWS calls ran.
- 2026-09-14: Journal/pointer-only follow-up preserves the feature commit and qualifies inherited publication references with its branch/revision. No main/cleanup-branch edits, other-checkout cleanup, private-bundle writes, pushes or PRs. Existing unrelated tracked/nonignored bytes/type/mode were checked at recovery; the current lockfile baseline and ignored-file limitations are recorded in evidence. Independent review and parent closure are pending; no feature ticket executed.

## Retrospective

Recover the bounded manifest delta, not an indiscriminate record glob or the changed original checkout. Compare cleaned committed bases before carrying pending variants; this prevents publication-banner loss. Align exact plan bucket fields with their already-redacted counterparts: substring mapping can confuse the primary bucket with a longer historical name. Preserve working and committed provenance separately when moving a decision. After a user merge, explicitly qualify old branch observations and establish a new unrelated-file baseline instead of claiming old dirty/index fingerprints still apply.

## Blockers

Implementation of this record-separation ticket is complete; independent exact-commit review and parent acceptance remain before closure. The next feature step is `.10x/tickets/2026-09-10-inspect-iceberg-warehouse-protection-prerequisites.md` under separate execution direction. No target/ownership/IAM inspection, infrastructure adoption, live plan approval or restore contract is supplied by record recovery. Restore and deployment blockers remain exactly as captured. No original pending work will be removed in this pass.
