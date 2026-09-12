Status: done
Created: 2026-09-11
Updated: 2026-09-12
Parent: .10x/tickets/2026-09-10-ratify-catalog-recovery-publication-boundary.md
Depends-On: None

# Preserve original recovery records privately

## Scope

Establish verified private custody before public cleanup. Inventory the exact affected operational records at published HEAD `027af8b4271d60ffc193967d092b5d2497af13ad` and distinguish pending versioning variants; preserve the required originals and a bounded snapshot sufficient for lossless versioning-record separation. This ticket does not redact public files or change Git refs.

## References

- `.10x/specs/private-recovery-evidence-custody.md`
- `.10x/specs/public-catalog-recovery-content.md`
- `.10x/decisions/keep-recovery-deployment-identifiers-private.md`
- `.10x/reviews/2026-09-10-catalog-recovery-publication-safety.md`

## Acceptance criteria and evidence

- Recheck HEAD/index/worktree inventory and distinguish the original 23-path versioning set from publication records and unrelated changes. Record nonsecret provenance and protected-work fingerprints without staging anything.
- Verify FileVault and destination safety/ownership before creating an owner-only new bundle under `~/Private/databox/recovery-evidence/`. Missing/unsafe prerequisites stop before copy or public mutation.
- Copy exactly selected report/record/text-plan originals and required pending record variants byte-for-byte; record private provenance, SHA-256, sizes and copy locations. Verify all copies and directory/file modes (`0700`/`0600`). Never overwrite prior bundles or follow unsafe destination links.
- Exclude all credentials, `.env`, host AWS files, private `.tfvars`, state/binary plans, datasets, volumes and unrelated work. Do not emit deployment identifiers or private manifest contents into public logs/records.
- Record public-safe counts, refindable bundle reference, verification/permission results, limits and independent review. Preserve both originals and pending work on failure. No automatic cleanup.

## Exclusions

Public redaction, branch/commit operations, AWS/network calls, credential changes, policy changes, private-source deletion, full-worktree stashing, or unrelated `uv.lock`/calendar edits.

## Progress and notes

- 2026-09-11: Created after all four questionnaire choices were explicitly confirmed. Authorized destination and custody behavior are active; no copy or filesystem-permission change has run.
- 2026-09-11: Executed only this custody child. Rechecked HEAD, empty staged set, all 23 pending versioning paths, eight separate publication/custody records and unrelated `uv.lock`. Verified FileVault on the actual destination APFS filesystem, canonical ownership/ACL safety, then created a new owner-only bundle at `~/Private/databox/recovery-evidence/2026-09-11T235551Z-05aef1141954/`. Preserved 42 HEAD originals/bases and 22 working variants (64 payload files, 322,252 bytes), exact digests/provenance/deletion-and-move mapping, and protected-work fingerprints. Copy/source/permission checks passed; no Git mutation, redaction, AWS/network call, credential change or later-ticket execution.
- 2026-09-11: The first ephemeral fingerprint helper stopped before writes on four unrelated tracked symlinks. Supervisor approved hashing their link text without following/exporting it; all mandatory gates were rerun successfully without broadening the copy set. No partial bundle existed from that attempt; no source links or ancestor permissions were changed. Details and reproducible checks: `.10x/evidence/2026-09-11-private-recovery-originals.md`.
- 2026-09-11: Separate-process verification passed all 64 original/source comparisons, 23 pending dispositions, 41 affected working-record copies, 996 protected preexisting path states after authorized record writes, all bundle permissions/ACLs and destination FileVault checks, exclusion/credential scans, and unchanged index/refs/worktrees with no staged files. Final bundle: 68 files (four metadata artifacts), 640,242 bytes, 20 directories. Custody remains active pending parent/independent review; self-verification is not independent closure. Originals and bundle retained; parent/dependencies unchanged.

- 2026-09-12: Fresh independent review verified all 64 payloads, source coverage, recoverable pending dispositions, protection/permissions and 996 protected states. Review C1 found later raw Git-index drift, with all 977 logical entries matching HEAD and no staged changes; attribution remains unresolved. Parent independently repeated payload/anchor/protection/logical-index/ref/lockfile checks and reproduced the raw mismatch. Accepted C1 as a nonblocking audit limitation, without claiming the raw index stayed unchanged through review or attributing a benign refresh. Canonical review and disposition: `.10x/reviews/2026-09-12-private-recovery-originals-review.md`.
- 2026-09-12: Parent mapped every acceptance criterion to `.10x/evidence/2026-09-11-private-recovery-originals.md`, confirmed custody-scope spec coherence and retained originals, and completed retrospective extraction into `.10x/knowledge/git-index-and-worktree-fingerprints.md`. Closed only this ticket; no public redaction, Git branch/ref/index operation, commit, AWS change or later-ticket execution was performed by this closure. Subsequent record-only path/status maintenance is distinct from the earlier source-preservation checks.

## Blockers

None for custody completion. C1's unresolved raw-index attribution is explicitly accepted with the bounded no-action rationale in the review; it is not a claim of raw-byte preservation through review time. Later work must recheck its own current state and protection gates. Originals remain retained with no automatic deletion.
