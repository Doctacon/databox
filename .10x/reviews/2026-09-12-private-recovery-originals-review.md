Status: recorded
Created: 2026-09-12
Updated: 2026-09-12
Target: .10x/tickets/done/2026-09-11-preserve-private-recovery-originals.md
Source-HEAD: 027af8b4271d60ffc193967d092b5d2497af13ad
Verdict: concerns

# Independent private-originals custody review

This local 10x copy is canonical. Imported from the fresh verifier's configured output `custody-independent-review.md` in workflow `ca4f1c7a-e016-402d-abc9-b21e845b153f`, child `856a55a9-c3f1-48cc-96f5-0397b7185c1b`. The source artifact remains under the originating session's `subagent-artifacts/outputs/ca4f1c7a-e016-402d-abc9-b21e845b153f/`; its observations and concerns verdict are retained below.

## Verdict and finding

**Custody integrity, coverage, recoverability and current protection checks pass. One audit discrepancy prevents an unqualified unchanged-index attestation.** No missing/corrupt copy, lost pending content, staged change, unsafe private destination or credential finding was observed. This review does not close the ticket or authorize downstream execution.

### C1 — Raw index drift; logical contents preserved; attribution unresolved

The current raw Git index differs from the anchored `source-state.json` baseline:

- Baseline SHA-256: `ca2a08049c97541609456580ae8e2178a34033a5fc6a977ca801400ef8917052`.
- Independently observed SHA-256: `8df78a9ca52ac8b40c793c08a81c27a8e7289cc95151ebd40ccbf7b074051d5e`.
- Current index: 137,070 bytes, format version 2; mtime `2026-09-12T00:02:52.422750Z`.

Crucially, **all 977 current stage-0 path/blob-OID/mode entries exactly match the specified HEAD tree**. There are zero staged differences, duplicate/conflicted entries or staged private-bundle additions. HEAD, branch, refs and worktree-list fingerprints match the saved baseline. The saved source state records zero staged paths and an index digest, but contains neither an original index-byte copy nor a separate logical-entry snapshot. Current logical contents match the baseline's stated HEAD/empty-staged condition; the raw-byte difference cannot be localized from that metadata alone.

I inspected the custody worker's execution transcript in memory. Its final checker asserted index-digest equality and returned successfully at `2026-09-12T00:01:09.132Z`; inspected Git constructors in the copy/recheck/final-check commands explicitly use `--no-optional-locks`. The current index mtime is later than that check, the separate-check artifact (`2026-09-11T23:59:42.066472Z`), and the transcript's last event (`2026-09-12T00:02:52.156Z`). This supports a later change, but **does not identify its writer or prove a benign stat-cache refresh**. No attributable refresh event was established from the inspected evidence. My Git commands also used `--no-optional-locks`.

**Acceptance concern:** parent must retain/acknowledge this exact qualification when deciding closure; do not repeat an independently verified raw-index-unchanged claim through review time. No index repair/recreation or replacement custody copy is warranted by these observations. This is not evidence of staged-code loss or a demonstrated custody-worker mutation.

## Scope and method

Read the owning ticket, both active referenced specs, active privacy decision, original publication-safety review and public custody evidence. Independently inspected actual private artifacts rather than relying on their result fields. Read private content/configuration/transcript material into memory and emitted only safe aggregate results. No raw private manifest, original text, deployment identifier or credential value was printed.

Bundle located directly from the public reference:

`~/Private/databox/recovery-evidence/2026-09-11T235551Z-05aef1141954/`

Only this externally mandated review artifact was written. No repository/private-bundle edit, copy, chmod, Git mutation, AWS/network call, test suite, repair or later-ticket execution was performed.

## Independently reproduced results

### Selection, exact originals and reconstruction

- Derived the configured account in memory from bounded existing recovery configuration; corroborated it against account-qualified original plan ARNs. Derived three exact bucket literals from HEAD operational plan bucket fields, with the configured recovery bucket included. Used these exact values—not the manifest's affected-path list—to enumerate affected HEAD and current records.
- Re-derived **35 affected HEAD records**, and **42 committed originals/bases** after union with the approved tracked versioning bases and deduplication.
- Rechecked the public 23-path inventory against actual Git status and private dispositions: **10 tracked modifications, one tracked deletion and 12 untracked new/moved records**. Eight separate publication/custody records and unrelated modified `uv.lock` remain outside the selected content.
- Verified **22 working variants**, separately classified from committed originals. Every committed entry's revision/path resolves to its recorded Git blob OID; source bytes, Git/source modes, copy bytes, sizes and SHA-256 agree for all **64 payloads / 322,252 bytes**.
- Independently re-derived **41 affected current working records** and verified an exact private copy of each.
- The deleted earlier decision has its HEAD original. Its superseded-path working counterpart has a distinct, exact edited copy and explicit move mapping. All 23 dispositions are reconstructible from the saved bases, working files, modes and deletion/move mapping. No restore operation was performed.
- Unique safe relative copy paths and complete bundle enumeration agree exactly: **68 files / 640,242 bytes**, comprising 64 payloads plus four metadata files; no extra payloads. All three public metadata integrity anchors match. All 67 per-file digest/size assertions inside `separate-check.json` were independently reproduced.
- Payloads are **56 Markdown records and eight operational text-plan exports**, all valid UTF-8 without NULs. The eight exports were checked for operational plan semantics, including the export whose filename does not end in `.tfplan.txt`.

### Protection and exclusion boundary

- Destination is canonical, outside the repository, with no symlink components. Existing components have appropriate operator/root ownership and are not group/other writable. Existing home ACL is limited to its delete-denial entry; no unexpected ancestor ACL was found.
- Three private parent directories and **20 bundle directories** are operator-owned `0700`; all **68 regular, single-link files** are operator-owned `0600`. No private ACL entries or destination links were found.
- Independently checked host FileVault status and resolved the destination device using `df`, then `diskutil` plist data: **APFS, FileVault enabled, global permissions enabled, matching mount/destination `st_dev`**. This is destination-volume verification, not merely a host-wide assertion.
- Exact selection/content and full enumeration exclude credentials/configuration, `.env`, host AWS files, private `.tfvars`, state/binary plans, datasets/volumes, personal files, publication-only payloads and unrelated lockfile content. Existing private configuration was only read in memory for bounded identifier classification, not exported.
- Re-ran the inspected repository provider/literal scanner logic and supplemental JWT, signed-query and session-token-prefix patterns over all 64 payloads, four private metadata artifacts and two public custody records: **zero findings**. Exact-identifier checks on public custody evidence/ticket also found zero matches. This is bounded scanning, not a universal secret-absence proof.

### Protected work and Git state

- Independently matched **996 protected preexisting path states**: 991 regular files, four unrelated symlinks fingerprinted by link-text bytes without following targets, and the expected missing decision. Only the owning progress ticket was exempted.
- Current tracked/nonignored-untracked inventory differs from the saved 997-path inventory only by the authorized new evidence record. Removing that evidence status entry reproduces the saved initial status digest exactly.
- `uv.lock` remains **718,042 bytes**, SHA-256 `49d7c920d95c8c1fe981b0bb43573412d0e29e7c8c0281e979b952f4da70166f`. Protected parent, dependency and unrelated records match their saved bytes/modes.
- HEAD and branch remain the stated revision and `feat/backup-plan-iceberg`; refs/worktree-list digests match. Logical index verification passes as described in C1; raw index-byte verification does not.
- Scoped `git diff --check` and public-record trailing-whitespace checks pass.

## Failure handling and specification scenarios

- **Preserve before redaction:** satisfied for the selected originals. Protected operational counterparts remain unchanged; custody is not redaction.
- **Committed/uncommitted reconstruction:** satisfied by independent byte/provenance/disposition checks, including deletion and moved-and-edited decision.
- **Cold-operator lookup:** demonstrated by finding the actual bundle from the public reference and verifying its anchored metadata and original digests. No redacted counterpart exists yet, so the later redacted-label/hash/pointer scenario is not claimed complete.
- **Failure gates:** worker transcript records the initial helper error, subsequent supervisor authorization and successful corrected execution. Stopping rather than bypassing the unrelated-symlink fingerprint error was appropriate; link-text fingerprinting preserves the no-follow selection boundary. The exploratory directory operand failure for `diskutil` was corrected by actual-device resolution, not a fallback destination. Current protected-state checks reveal no unrelated source mutation. Historical absence of transient writes and original pre-copy ancestor permissions cannot be reconstructed solely from current artifacts; no deliberate negative-gate test or repair was attempted.
- **Public-content/branch spec:** parameterized policy equivalence, identifier-free candidate trees, redacted counterpart labeling, separated branch tips, infrastructure tests and publication/merge readiness are later-ticket scenarios, not passed by this custody review. Published history remains unchanged and public.

## Limits and disposition

The baseline fingerprints/public anchors and execution transcript are contemporaneous worker evidence, not a pre-execution observation by this reviewer. Current bytes/protection and comparisons were independently reproduced; ignored private files lack saved baseline fingerprints, so historical byte-preservation of every ignored file cannot be independently certified. No local artifact proves absence of every possible transient write or external action.

FileVault is not off-host backup, immutability, protection against an authorized process on an unlocked host, or disk-loss survival. Originals and bundle remain retained; no cleanup occurred. At review delivery, keep the ticket active for the parent's acceptance decision, with C1 explicitly recorded. No downstream execution or general merge approval follows from this review.

## Parent disposition — 2026-09-12

C1 is accepted as a nonblocking audit limitation for custody completion, not resolved or reclassified as a proven benign refresh. The reviewer observed matching 977 logical index entries and 996 protected path states; the parent independently reproduced all 64 source/copy comparisons, three metadata anchors, owner-only permissions/no ACLs, actual-volume FileVault, unchanged refs/worktrees, exact logical index equality to HEAD, zero staged paths, and unchanged `uv.lock`. The parent also reproduced the raw-index mismatch.

The worker's contemporaneous final successful check precedes the later index mtime; no actor or cause for the later change was established. Custody completeness, source preservation and present staged contents are supported; a byte-unchanged index through review time is not. No repair, replacement copy, historical rewrite or separate investigation is prescribed because these observations identify no missing/corrupt payload, staged loss or unsafe destination. This rationale owns the unresolved attribution limit and does not authorize index mutation in future work. The concerns verdict is intentionally retained. Parent acceptance and closure evidence are appended to `.10x/evidence/2026-09-11-private-recovery-originals.md`.
