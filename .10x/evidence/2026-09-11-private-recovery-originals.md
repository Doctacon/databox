Status: recorded
Created: 2026-09-11
Updated: 2026-09-12
Relates-To: .10x/tickets/done/2026-09-11-preserve-private-recovery-originals.md, .10x/reviews/2026-09-12-private-recovery-originals-review.md
Owner: .10x/tickets/done/2026-09-11-preserve-private-recovery-originals.md

# Private recovery originals: custody execution

> Candidate reference scope: the following paths denote preserved pending/future third-ticket material in the original dirty checkout and private custody snapshot, NOT files in this catalog-only candidate. No versioning follow-up branch/revision exists yet; final branch-qualified reconciliation belongs to ticket 3.
> `.10x/decisions/superseded/catalog-backup-with-rebuildable-iceberg-warehouse.md`
> `.10x/decisions/version-iceberg-warehouse-objects-for-30-days.md`
> `.10x/research/2026-09-10-s3-warehouse-versioning-semantics.md`
> `.10x/specs/iceberg-object-version-restore.md`
> `.10x/specs/iceberg-warehouse-version-retention.md`
> `.10x/specs/iceberg-writer-version-delete-denial.md`
> `.10x/tickets/2026-09-10-apply-iceberg-warehouse-version-protection.md`
> `.10x/tickets/2026-09-10-build-iceberg-object-version-restore.md`
> `.10x/tickets/2026-09-10-declare-iceberg-warehouse-version-protection.md`
> `.10x/tickets/2026-09-10-inspect-iceberg-warehouse-protection-prerequisites.md`
> `.10x/tickets/2026-09-10-protect-iceberg-warehouse-object-versions.md`
> `.10x/tickets/2026-09-10-prove-iceberg-object-version-recovery.md`

## State and boundary

Custody copies verified; parent accepted completion on 2026-09-12 following independent review, with the later raw-index discrepancy expressly qualified below. The procedure/results sections retain the worker's execution-time observations. This is only the first child of `.10x/tickets/2026-09-10-ratify-catalog-recovery-publication-boundary.md`. No public redaction, separation, staging, commit, ref/worktree/branch/stash change, AWS/network call, credential change, or later-ticket execution occurred. Parent/dependency records remain unchanged.

Source HEAD: `027af8b4271d60ffc193967d092b5d2497af13ad`, branch `feat/backup-plan-iceberg`. Index initially empty of staged changes; its raw digest matched through the worker's final check. A later independent review found raw-index drift while logical staged entries still exactly matched HEAD; see the parent acceptance section. The pending inventory was rechecked, not assumed: **11 tracked record paths (10 modifications, one deletion), 12 untracked versioning records, eight separate untracked publication/custody records, and unrelated modified `uv.lock`**.

## Refindable private owner and integrity anchors

Operator-owned bundle, outside Git:

`~/Private/databox/recovery-evidence/2026-09-11T235551Z-05aef1141954/`

Never overwrite or automatically delete this bundle or the originals. This run created the three previously missing approved parent directories and a new timestamp/random run directory; it did not reuse a prior bundle.

- `manifest.json`: exact source paths, HEAD revision/Git blob IDs and Git modes, explicitly separate working provenance/modes, copy paths, original-byte SHA-256 and byte counts, affected-path inventory, 23 pending dispositions, moved-and-edited decision mapping, exclusions, and reconstruction instructions.
- `source-state.json`: metadata/fingerprints of all 997 preexisting tracked/nonignored-untracked paths, including missing-path state and four unrelated symlinks hashed as link text without following them; index/ref/worktree/status digests. No unrelated file contents are exported.
- `verification.json`: completed first-process byte, source-state, permission, exclusion, FileVault, and Git checks.
- `separate-check.json`: separate-process verification artifact; not a claim of review by another person/agent.

SHA-256 anchors (these are **private metadata artifact digests**, not hashes of a redacted plan or an old binary plan):

| Artifact | SHA-256 |
| --- | --- |
| `manifest.json` | `585e73cdf2f52cc939a1c3b3153248c55e2000fde9e5eba519254eefd2d82257` |
| `source-state.json` | `337a67ba2394462f2d4c8d02a7b4ef5c5f5c798d38b3af60edf8fb3737f1365a` |
| `separate-check.json` | `67610860cf18282b6affcf97bf8ef3addb504c412a23a880dbb893609e8e2a5e` |

## Protection and permission gates

Before copying, `fdesetup status` reported FileVault on. The actual destination filesystem was resolved with `df -P` on the nearest existing parent, then `diskutil info -plist` on that device: APFS, `FileVault=true`, `GlobalPermissionsEnabled=true`, and equal `st_dev` for its mount and destination ancestor. Checks repeated for the newly created custody root and populated run. A host-wide FileVault result alone was not accepted as destination proof.

Every existing path component was canonical/non-symlink, directory-typed, appropriately root/operator-owned, and not group/other writable. The home ACL was only `everyone deny delete`; root and `/Users` had no ACL entries. These existing ancestors' ownership, modes and ACLs remained unchanged; no chmod was used on them. All three new approved parents and all 20 bundle directories were operator-owned `0700`, with no ACL entries. Copied files and private metadata were created `0600`, no ACL entries, regular, single-link, and operator-owned. No unsafe destination links were followed. `umask(077)`, exclusive new-file creation (`O_EXCL|O_NOFOLLOW`), write/flush/fsync, readback and recursive permission checks were used.

One exploratory `diskutil info -plist` invocation on the home directory returned exit 1 because the operand was not a device/mount. Device resolution via `df` supplied the actual filesystem for successful verification before any write; no fallback destination or encryption-state change was made.

## Exact selection and copy results

Exact account/bucket identifiers were discovered only in memory from bounded existing recovery configuration and committed operational text exports. One configured account matched the account-qualified ARNs in those exports; three exact bucket fields covered the deployed and historical recovery-plan targets. No identifier values or configuration contents were printed or copied into metadata. Selection used exact strings, not broad numeric/name replacement, and did not perform any redaction.

- **35 affected HEAD operational records/text plans** selected by exact identifier matches.
- **42 HEAD copies** total: those 35 plus the necessary versioning bases, with overlap deduplicated.
- **22 distinct working copies**: ten modified tracked variants and twelve untracked new/moved records.
- **64 payload files, 322,252 original bytes**, copied byte-for-byte. All SHA-256, byte-count and source comparisons passed. The deleted decision is preserved from HEAD; the moved-and-edited working decision is a distinct artifact, not assumed identical.
- Four private metadata files accompany the payload: **68 files / 640,242 bytes total**, in 20 bundle directories (plus the three approved parent directories). No binaries/configuration/state/data were included.
- Separate-process checking passed all 42 Git blob/OID comparisons and 22 working comparisons, all 23 pending dispositions, and exact private-copy coverage for **41 affected current working records**. The different HEAD/working affected counts reflect the pending moved/new record set.

The repository credential scanner's inspected provider/literal rules ran on all selected bytes in memory before copying, plus supplemental JWT, signed-S3-query and AWS-session-token-prefix checks: **zero findings**. All payloads were UTF-8 text without NULs and satisfied the explicit `.10x` Markdown/operational-text allowlist. Manifest inventory and directory enumeration verify exclusion of credentials, `.env`, host AWS configuration/caches, private `.tfvars`, state, binary plans, datasets, volumes, personal files, publication-only contents and `uv.lock`. Existing private configuration stayed in place; no `.env` or host AWS file was read by this execution.

## Approved pending versioning inventory

Tracked bases and exact working dispositions:

- Deleted: `.10x/decisions/catalog-backup-with-rebuildable-iceberg-warehouse.md`
- Modified: `.10x/decisions/filevault-only-local-opentofu-state.md`
- Modified: `.10x/decisions/startup-only-catalog-backup-gate.md`
- Modified: `.10x/specs/polaris-catalog-continuity.md`
- Modified: `.10x/tickets/2026-09-04-build-polaris-iceberg-disaster-recovery.md`
- Modified: `.10x/tickets/2026-09-04-simplify-recovery-infrastructure-to-catalog-only.md`
- Modified: `.10x/tickets/2026-09-05-establish-primary-warehouse-session-credentials.md`
- Modified: `.10x/tickets/cancelled/2026-09-09-repair-continuous-catalog-wal-credentials.md`
- Modified: `.10x/tickets/done/2026-09-04-apply-and-prove-disaster-recovery.md`
- Modified: `.10x/tickets/done/2026-09-04-build-isolated-catalog-recovery-drill.md`
- Modified: `.10x/tickets/done/2026-09-04-verify-disaster-recovery-automation.md`

Untracked working originals:

- `.10x/decisions/superseded/catalog-backup-with-rebuildable-iceberg-warehouse.md`
- `.10x/decisions/version-iceberg-warehouse-objects-for-30-days.md`
- `.10x/research/2026-09-10-s3-warehouse-versioning-semantics.md`
- `.10x/specs/iceberg-object-version-restore.md`
- `.10x/specs/iceberg-warehouse-version-retention.md`
- `.10x/specs/iceberg-writer-version-delete-denial.md`
- `.10x/tickets/2026-09-10-apply-iceberg-warehouse-version-protection.md`
- `.10x/tickets/2026-09-10-build-iceberg-object-version-restore.md`
- `.10x/tickets/2026-09-10-declare-iceberg-warehouse-version-protection.md`
- `.10x/tickets/2026-09-10-inspect-iceberg-warehouse-protection-prerequisites.md`
- `.10x/tickets/2026-09-10-protect-iceberg-warehouse-object-versions.md`
- `.10x/tickets/2026-09-10-prove-iceberg-object-version-recovery.md`

## Reproducible local checking procedure

Use ephemeral `python3 -B` standard-library commands; capture all subprocess output in memory and print only aggregate results. Never cat a private copy/manifest, configuration or deployment identifier into a transcript.

1. Verify the metadata digests above before trusting manifest paths. Recheck every destination component with `lstat`, canonical resolution, UID, modes and captured `/bin/ls -lde` ACL output. Resolve the actual volume using captured `/bin/df -P <bundle>` then `/usr/sbin/diskutil info -plist <device>`; require matching `st_dev`, APFS, FileVault and global permissions. Recheck `/usr/bin/fdesetup status`. Do not repair failed gates or choose another location.
2. Read `manifest.json` privately. Require 42 committed and 22 working entries, unique safe relative `copy_path` values, only the stated 23 pending paths, and no extra payload files. Require `0700` directories and `0600` regular single-link files, operator UID and no private ACLs.
3. For each entry, read the copy without following links; compare `len(bytes)` and `hashlib.sha256(bytes).hexdigest()` to its manifest values. For HEAD entries, compare bytes to captured `git --no-optional-locks cat-file blob <git_blob_oid>` and independently resolve `<source_revision>:<source_path>` to that OID. For working entries, compare to the current source bytes and mode if the source is still at the captured pending state. Do not substitute current modified bytes for a committed original.
4. Verify each of the 11 tracked dispositions and 12 untracked dispositions. The old decision must be absent in the captured working state, with a HEAD original and a separate new-path working copy. Together the base blobs, 22 working files, source modes and deletion/move map suffice for lossless pending-record reconstruction. Do not actually restore/delete/stage/branch here.
5. Compare preexisting source fingerprints in `source-state.json`; missing paths stay missing, regular files use SHA-256/size/mode, and unrelated symlinks use SHA-256/size of `os.fsencode(os.readlink(path))` without following targets. Only this evidence path and the owning ticket are authorized repository changes. Capture `git --no-optional-locks show-ref --head`, `worktree list --porcelain`, and raw index bytes for comparison with their saved SHA-256; require the same HEAD/branch and no staged paths. Initial status digest is from `status --porcelain=v1 -z --untracked-files=all`; after recording progress only the new evidence path changes status inventory.
6. Re-run the inspected repository scanner on in-memory selected bytes and the bounded supplemental checks; report counts only. Preserve everything on a discrepancy, mark the owner blocked, and obtain independent review. Do not export a raw manifest or its private originals.

## Preserved work and execution correction

All 997 preexisting path states were compared before/after copying, including four unrelated tracked symlinks, 992 regular files and one expected deletion. After authorized progress/evidence writes, the separate process verified all **996 protected preexisting path states**, with only the owning ticket exempted and only this evidence path added. Final public-record checks found zero exact deployment identifiers or credential findings; Markdown whitespace and scoped `git diff --check` passed. Index, refs and worktree-list digests matched; no staged files. Unrelated `uv.lock` remained **718,042 bytes**, SHA-256 `49d7c920d95c8c1fe981b0bb43573412d0e29e7c8c0281e979b952f4da70166f`. Ignored private files/data were not swept into the fingerprint/copy inventory or mutated.

The first custody helper attempt stopped before any write because its overly strict regular-file fingerprint reader encountered four preexisting unrelated tracked symlinks. It created no directory, bundle, or partial copy. The supervisor explicitly approved the mechanical correction: fingerprint link-text bytes and type without following/exporting targets, keep selected-original/destination no-follow gates strict, and rerun every gate. The corrected run did so; no fallback, source-link repair, broadened inventory, or unrelated host change was made.

Only this evidence record and the owning ticket are written inside the repository. No reusable script/dependency/scaffolding was added; no test suite, generator or formatter ran. A public-safe execution handoff is also written to the separately required agent output path, outside the repository.

## Review and residual limits

Independent review is now recorded at `.10x/reviews/2026-09-12-private-recovery-originals-review.md`; separate-process self-verification was not itself independent review or ticket closure. No claim of cloud backup, immutability, off-host redundancy or survival of local disk loss is made. FileVault protects data at rest, not against an already-authorized/root process on an unlocked host. Bounded credential scanning is not proof against every historical/encoded secret. This custody inventory does not certify future publication safety: later candidate changes still require their own exact-identifier and credential review. Historical rejected plans remain rejected, their original bytes/hashes retain their original meaning, and already-public Git history remains public and unchanged.

## Parent verification and acceptance — 2026-09-12

After reading the full ticket, active contracts, worker evidence and fresh independent review, the parent performed a separate read-only `python3 -B` verification against the actual private bundle. Private content was read in memory without printing it. All subprocess Git calls used `--no-optional-locks` and `GIT_OPTIONAL_LOCKS=0`; no private files were written or repaired.

The parent verified the three metadata anchors; safe unique manifest paths and exact enumeration; all 42 committed revision/path/blob/copy comparisons and 22 current-working/copy comparisons; 64 payloads / 322,252 bytes; 68 total regular files and 20 bundle directories; owner-only modes, single-link/no-symlink files and no private ACL entries. `fdesetup status`, captured `df -P` and device-specific `diskutil info -plist` independently confirmed FileVault/global permissions and matching mount/destination device. All 977 current index path/blob/mode entries exactly matched HEAD, with no staged paths; HEAD, refs/worktree-list anchors and the stated `uv.lock` digest matched.

The parent also independently reproduced **raw_index_matches_original=false**. The independent review found the index's later mtime after the worker's successful final raw-digest check. Its cause/writer is unresolved; neither reviewer nor parent proved a benign refresh. The earlier worker index observations apply only through its check, not through review time.

### Acceptance mapping

| Ticket criterion | Supporting observations |
| --- | --- |
| Distinguish the pending record set and protect unrelated work | Independent reconstruction of all 23 dispositions; 35 affected HEAD records and 41 current affected records; 996 protected preexisting states matched before parent closure maintenance. |
| Verify safe private destination and encryption | Worker pre-copy checks plus reviewer/parent current canonical path, ownership, modes/ACLs and actual-volume FileVault checks. |
| Preserve exact originals, provenance and pending variants | 42 HEAD + 22 working copies; all digest/byte/source comparisons pass; deleted and moved-and-edited decision separately recoverable. |
| Exclude credentials/config/state/unrelated contents | Exact complete bundle enumeration, permitted text payloads, bounded clean scans and reviewer selection/exclusion checks; no raw private content exported. |
| Public-safe evidence and independent review, with originals retained | This record, anchored private artifacts and `.10x/reviews/2026-09-12-private-recovery-originals-review.md`; no overwrite, deletion or automatic cleanup. |

C1 is **accepted as a nonblocking audit limitation**, not dismissed or repaired: no custody corruption, lost pending work, staged content/mode/path change or unsafe destination was found. The review remains `concerns` to preserve the distinction. Its parent-disposition section owns the explicit no-action rationale; no unqualified unchanged-index or universal no-transient-write claim is made.

### Closure and retrospective boundary

The parent accepts this custody ticket only. Public redaction/candidate-tree/branch-separation scenarios belong to later tickets and have not been performed; hosting/merge readiness is not established. Ignored-file historical fingerprints and hypothetical negative-gate behavior were not exhaustively tested, and the original evidence limits remain in force.

Lessons are preserved in `.10x/knowledge/git-index-and-worktree-fingerprints.md`: distinguish raw versus logical index evidence, do not infer attribution, retain bounded logical snapshots for future checks, fingerprint unrelated symlinks without following them, and state ignored-file limits. No source/harness repair or additional private copy is warranted by the current observations.

After these checks, parent closure maintenance updates ticket paths/statuses, parent/dependency progress and public review/evidence/knowledge only. Such explicitly recorded maintenance is later than the 996-path unchanged observation. Future execution must establish its own current baseline while retaining the original custody artifacts and this qualification; never replace anchored private metadata to erase the discrepancy.
