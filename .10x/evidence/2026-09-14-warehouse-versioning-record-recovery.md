Status: recorded
Created: 2026-09-14
Updated: 2026-09-14
Owner: .10x/tickets/2026-09-11-separate-warehouse-versioning-record-branch.md

# Recover the warehouse-versioning record branch

## Identity, authority and custody

User reports catalog feature merged into main and requests a new warehouse/file-recovery branch. The parent created `feature/warehouse-file-recovery` from clean merged main `8321475dda7b3a041e8dd8efe668c923cf723fb5`. This user-directed base replaces the ticket's older local sanitized-candidate base; main and other branches/worktrees are not edited. This pass recovers records only, not any feature child. Closure awaits independent review.

Verified private bundle: `~/Private/databox/recovery-evidence/2026-09-11T235551Z-05aef1141954/`. All three published metadata anchors in `.10x/evidence/2026-09-11-private-recovery-originals.md` match. All 64 payload digests/byte counts and 42 committed source path/blob identities match; the 22 working variants are intentionally compared to the snapshot, not today's merged checkout. Canonical ancestor ownership/no-symlink/non-writable-by-others checks, owner-only directory/file permissions, single-link regular files, private ACL absence, host FileVault, and destination-device APFS/FileVault/global-permissions/matching-device checks pass. No private file was written, moved, or removed.

The ten modified bases and old active decision match the current cleaned base exactly after removing its publication banner and applying the four established exact identifier substitutions. Therefore no three-way semantic conflict exists. Each working variant is recovered with those same substitutions and a working-artifact provenance label. Existing publication banners remain; the moved decision's committed-original pointer explicitly names its old source path. Historical hashes continue to identify originals, never the redacted counterpart.

## Exact pending-path accounting

All 11 original tracked dispositions (10 modifications, 1 deletion) and all 12 untracked new/moved originals are accounted for. Original-artifact hashes below identify private uncommitted payloads, not current public files. Publication/custody-only files and unrelated work are excluded from the feature delta.

| Original path | Disposition on follow-up | Original working SHA-256 |
| --- | --- | --- |
| `.10x/decisions/catalog-backup-with-rebuildable-iceberg-warehouse.md` | Deleted here; HEAD original remains in private custody; moved-and-edited counterpart below | Not applicable: captured deletion |
| `.10x/decisions/filevault-only-local-opentofu-state.md` | Modified tracked variant; recovered | `afa3d97cbc97f10c59fa8a31b63b7384e0b6529d9120df53f320bf72e237aa93` |
| `.10x/decisions/startup-only-catalog-backup-gate.md` | Modified tracked variant; recovered | `ae474b426ea4c596b34f3265660706336bd9b5a76922e0626eed1e38f109b4d3` |
| `.10x/decisions/superseded/catalog-backup-with-rebuildable-iceberg-warehouse.md` | Moved and edited from deleted active decision; recovered | `8bd07e22954e858127852b21fefc1668d5ffcc2b97f6278c503f49cb9dda1e20` |
| `.10x/decisions/version-iceberg-warehouse-objects-for-30-days.md` | New record; recovered | `4e64de0ae1ac6f833b2cbc9fe968ac92003dc80fba9211d6c03886c1e12e6d13` |
| `.10x/research/2026-09-10-s3-warehouse-versioning-semantics.md` | New record; recovered | `034eca0322185a55d2fdbabd665e4f8d9d5be7f344d380dd69407b91ea96745c` |
| `.10x/specs/iceberg-object-version-restore.md` | New record; recovered | `61c826c9e0b257d3b64e69793d53580845fcca70c6bb99fba118aa2c2a66cdfb` |
| `.10x/specs/iceberg-warehouse-version-retention.md` | New record; recovered | `70394a7c25c4df5787442360e5593fb9e888c7f2fbfc78a4dc41f96720221954` |
| `.10x/specs/iceberg-writer-version-delete-denial.md` | New record; recovered | `d5f681610e42d78b267c51f3909e180428c183a917642826694b118ae1c839ac` |
| `.10x/specs/polaris-catalog-continuity.md` | Modified tracked variant; recovered | `f5ffba05f81049de83fc317dbbedceac5a6c5da73adfc445c36b42eba835107d` |
| `.10x/tickets/2026-09-04-build-polaris-iceberg-disaster-recovery.md` | Modified tracked variant; recovered | `d3e27da0fd16c7afe2c7f52260b56bc199450fbf65502351712f8c933d0f2575` |
| `.10x/tickets/2026-09-04-simplify-recovery-infrastructure-to-catalog-only.md` | Modified tracked variant; recovered | `f7eba2efe290520eacea6855f2c351fa02857c09b833ac599c10a28a53080504` |
| `.10x/tickets/2026-09-05-establish-primary-warehouse-session-credentials.md` | Modified tracked variant; recovered | `37e46be65122472b6134712ce37b142d5f42aa7f8588d227b952bef04ac0cd7e` |
| `.10x/tickets/2026-09-10-apply-iceberg-warehouse-version-protection.md` | New record; recovered | `57bb7125dee37a8177a310ec5acaf84bd5df8ce7df0a3fcd703fc7d5bad8ee22` |
| `.10x/tickets/2026-09-10-build-iceberg-object-version-restore.md` | New record; recovered | `1ff6924d83c2824c5b2a4f79b7df3446cbfd88f9b07ccd4764378e14162cda32` |
| `.10x/tickets/2026-09-10-declare-iceberg-warehouse-version-protection.md` | New record; recovered | `44ddee597fd5386c78da05049d626841bc5ea13af0bc5703bcb9e92e67c12091` |
| `.10x/tickets/2026-09-10-inspect-iceberg-warehouse-protection-prerequisites.md` | New record; recovered | `4f427cab26e57b4205cdf674cc2680ea7cfc7742e9e93a09ce93ec3385677f8f` |
| `.10x/tickets/2026-09-10-protect-iceberg-warehouse-object-versions.md` | New record; recovered | `5f4d17e283d84f1eeb5bba43b972504e302e33402553f7487d1b2f71e090bd2f` |
| `.10x/tickets/2026-09-10-prove-iceberg-object-version-recovery.md` | New record; recovered | `f8e71ec2fbdb7ae23bcc7f6e1f1faa40196bcea1274d862cf43b5aaeb19dbc04` |
| `.10x/tickets/cancelled/2026-09-09-repair-continuous-catalog-wal-credentials.md` | Modified tracked variant; recovered | `d8a1c94a787ef504e26d6b6bae929420c58d8db9b2f98c9e8895d0047160652f` |
| `.10x/tickets/done/2026-09-04-apply-and-prove-disaster-recovery.md` | Modified tracked variant; recovered | `af697e1032ee76f0c24b0eeb2a8fffc2e10911a8937e68ce31cd35d3fb02eb23` |
| `.10x/tickets/done/2026-09-04-build-isolated-catalog-recovery-drill.md` | Modified tracked variant; recovered | `2b5c83718b472ae99eb068fb9848a40608a88fc0427e32b81e86644c080b1457` |
| `.10x/tickets/done/2026-09-04-verify-disaster-recovery-automation.md` | Modified tracked variant; recovered | `8db4581db6eb3d3cf7b09ce0ab34d5b506efcc53cc85479c438d3eda5499f740` |

## Preservation and verification boundary

- Initial source tree and index were clean on the stated branch/base. All 981 preexisting tracked/nonignored paths outside the selected 11 tracked dispositions retained bytes/type/mode immediately after recovery; unrelated symlinks were fingerprinted as link text without following them.
- Current merged-main `uv.lock`: 718042 bytes, SHA-256 `778a3ec9708e86233f499efbc84784f09b9dd365a1788024245c249723bd778d`; unchanged by this pass. This is a new baseline, not the old dirty-checkout digest.
- Original other checkouts, private configuration/state, credentials, calendars, services, warehouse data and retained recovery resources were not modified or cleaned. Ignored/private runtime files were not swept into fingerprint inventories, so this is not a universal ignored-file historical preservation claim.
- Exact identifiers were derived only in memory from verified committed plan bucket fields/account-qualified ARNs, aligned with already-redacted public plan fields. Three buckets and one account retain their existing labeled placeholders; exact generic `databox-lake-user` principal contexts remain public. No private values were printed or exported.
- Two initial mapping probes failed closed before edits (placeholder regex omitted digits; a bucket-name substring collided with a longer bucket). The successful method uses aligned exact `bucket =` fields, not broad substring classification. No ambiguous substitution was applied.

## Required review and next owner

Independent review must compare each recovered body with its private working original after only approved substitutions/provenance removal, check the moved original's banner, retained catalog/no-replica boundaries, all current links/statuses and final exact commit. The separation ticket remains open until parent acceptance. Neither this record nor successful checks authorize live warehouse changes.

Next executable feature owner, after separate execution direction: `.10x/tickets/2026-09-10-inspect-iceberg-warehouse-protection-prerequisites.md`. Infrastructure declaration awaits that inspection; apply requires reviewed exact plan plus explicit live approval. Restore selection, destination, operator permissions, conflict/failure handling, concurrency, drill/artifact lifecycle and operational ownership remain draft and unratified. The broader IAM audit remains with its existing ticket. No recovered child ran here.

## Local verification and commit observations

- Feature-only recovery commit: `7d402878addf2dc1585e499b1809c4e1cbddbd49`, sole parent `8321475dda7b3a041e8dd8efe668c923cf723fb5`. Git reports 22 rename-aware changed files (23 paths with rename detection disabled), 601 insertions / 18 deletions. Scoped staging was checked against the manifest before committing.
- Recovered-body equality passed for every one of the 22 working originals after stripping only the preserved publication and new recovery banners and applying the four approved exact substitutions. The six-ticket graph is acyclic, local feature `.10x` links resolve, EOF/whitespace and `git diff --check` pass. A first equality probe expected one excess blank line in the new banner; fixing only the in-memory verifier reproduced exact equality without changing the records.
- Exact-value scans cover all 992 merged-main blobs and all 1,004 follow-up working files at the precommit observation. The unchanged repository scanner's provider and assignment rules passed for 952 and 964 eligible text files respectively. Twelve and 21 complete generic principal-label contexts were distinguished from bucket literals. No identifier/configuration values were logged. Bounded scans are not proof against arbitrary encoded or historical secrets.
- Inspected normal Git/pre-commit configuration and existing cached hook installation-state/health. Read-only SQLite lookup avoided clone/install APIs; all 12 hooks were ready and 11 Python entrypoint help probes passed. The feature commit used unmodified normal hooks: all applicable checks passed, non-Markdown checks naturally had no files, and all 22 recovered file byte hashes were unchanged afterward. No application/runtime suite, environment installation, hook bypass, provider call or cloud mutation occurred.
- A separate record-only journal/pointer commit follows the feature-only commit, so the latter is an immutable review target rather than a self-referential hash. Historical cleanup inventories/observations are retained with explicit current branch/revision qualification; no pointer-only edit is made on main or the old cleanup branch under this user-directed boundary. Final metadata revision is in the handoff, not claimed to be part of the feature diff.
- Final pre-journal-commit verification: all 311 tracked non-`.10x` paths match merged-main bytes/type/executable modes; main still names the recorded base. Exact 68-file private enumeration and all 64 payload hashes reverify. The feature-only commit remains unchanged; the final working-tree exact-value scan and 964 eligible-text credential checks pass after pointer edits. No raw-index invariance across deliberate staging/commits is claimed.
