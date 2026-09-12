Status: recorded
Created: 2026-09-12
Updated: 2026-09-12
Target: .10x/tickets/done/2026-09-11-sanitize-catalog-recovery-publication.md
Reviewed-State: historical uncommitted, pre-hook-approval candidate
Later-Review: .10x/reviews/2026-09-12-catalog-publication-commit-review.md
Verdict: concerns
Execution-Gate: blocked
Source-Verifier-Verdict: blocked
Repair-Within-Scope: false

# Independent catalog-publication cleanup review

## Verdict and candidate identity

**The prepared working-tree content passes the bounded publication checks below. Ticket completion remains blocked: no sanitized commit exists and the commit route needs separate approval. A new raw-index discrepancy also requires an explicit preservation qualification.** No source repair, ticket closure, publication or ticket-3 execution is recommended or performed by this review.

- Actual inspected candidate: `/Users/crlough/Code/personal/databox.worktrees/catalog-publication-cleanup`.
- Local branch: `chore/catalog-recovery-publication-cleanup`.
- HEAD/base: `027af8b4271d60ffc193967d092b5d2497af13ad`.
- That revision still identifies the **unsanitized published base**, not a sanitized Git commit. Findings about identifier absence apply to the prospective current working tree, including its untracked records, not HEAD/history.
- Independently matched all **45 changed-path fingerprints** against the handoff. Canonical sorted compact JSON SHA-256: `10f5fb9262560804c68293b40681f176906926a075e0f877a977347ecf3b5f7a`.
- Both actual repository indices have **zero staged paths**. This review writes only the externally mandated artifact; it adds no candidate review file or repository change.

## Findings

### B1 — Approved stop remains a completion blocker

Candidate `.10x/evidence/2026-09-12-catalog-publication-cleanup.md`, “Validation and commit gate,” and owning ticket “Blockers”: the inspected installed hook invokes the full pre-commit configuration, including mutating fixers, `ruff --fix`/format and possible environment setup. Those conflict with the execution constraints. The supervisor-approved uncommitted stop is correctly disclosed. No commit was attempted by this reviewer; no hook override, installation or security-check bypass was used.

The ticket's local scoped-commit outcome is not complete. Parent must obtain a separately approved safe commit route and review the resulting exact revision before closure. This is not permission to repair hooks or commit now. `repairWithinScope=false`: resolving this blocker needs authority beyond mechanical content repair.

### C1 — New raw-index drift relative to ticket 2's fresh baseline

The original checkout's raw index no longer matches `/tmp/databox-publication-cleanup-baseline.json`:

| Observation | Fresh execution baseline | Independent current observation |
| --- | --- | --- |
| SHA-256 | `8df78a9ca52ac8b40c793c08a81c27a8e7289cc95151ebd40ccbf7b074051d5e` | `bc23d73c02f8324d760df19bd4f3300ea6c408401387e6724b58ac98ba559df8` |
| Bytes | 137,070 | 137,157 |
| UTC mtime | 2026-09-12T00:02:52.422750Z | 2026-09-12T01:14:13.997920Z |

This is a **new observation relative to the second ticket's baseline**, not a demand that custody's older raw bytes match. All **977 logical stage-0 path/mode/blob entries exactly equal the fresh logical snapshot and HEAD**; both original and candidate indices equal their HEAD trees. There are no staged changes, lost protected files, changed private originals or moved preexisting refs.

The writer/cause of this raw-byte change is not established. Do not call it a proven benign refresh or extend the worker's final unchanged-raw-index statement through this review. The earlier custody C1 disposition does not automatically dispose of this new observation. Parent should retain/acknowledge this qualification in its acceptance record without recreating the index or overwriting custody metadata. This is an attribution limitation, not a demonstrated content-repair requirement. The supervisor was notified during review.

## Independently reproduced checks

### Authority, custody and source preservation

Read the full owning ticket, both active specs, privacy decision, publication audit, completed custody ticket/evidence/review, parent plan, fingerprint knowledge and candidate execution evidence. Read candidate records themselves, not only the original checkout. Compared all eleven imported graph records to their original counterparts in memory: complete original bodies remain after removal of only explicit candidate status/reference-scope blocks and the scoped raw-artifact handling section.

Located the private bundle from the public reference, `~/Private/databox/recovery-evidence/2026-09-11T235551Z-05aef1141954/`. Independently verified:

- All three original metadata anchors before using the manifest; **42 HEAD originals/bases and 22 working variants**, **64 payloads / 322,252 bytes**. Copy digests/lengths match; HEAD revision/path/blob provenance and Git modes match; current working bytes/modes match.
- Exact **68-file** bundle enumeration and **20 bundle directories**, with no extra payload. All 68 file fingerprints also equal the second-ticket baseline.
- Canonical, non-symlink, outside-repository destination and safe ancestors. Operator-owned private directories are `0700`; regular single-link files are `0600`; no private ACLs. Existing home ACL is limited to delete denial; no unsafe ownership/writable ancestor was found.
- Host FileVault plus actual-device `df`/`diskutil` verification: APFS, FileVault and global permissions enabled, matching destination/mount device. This is not merely a host-wide encryption assertion.
- All **23 pending dispositions** remain recoverable, including the deleted decision and distinct moved/edited variant. All twelve feature-only new/moved paths are absent from the candidate.
- **999 protected original path states** match the fresh 1,000-path baseline, excluding only the authorized owning-ticket edit. Unrelated symlinks were fingerprinted as link text, without exporting targets. Original inventory has no added paths.
- Original dirty `uv.lock` remains 718,042 bytes, SHA-256 `49d7c920d95c8c1fe981b0bb43573412d0e29e7c8c0281e979b952f4da70166f`. Candidate lock bytes equal published HEAD rather than importing that dirty lock.

Current custody integrity is independently verified; the pre-redaction timing is supported by worker evidence, not a pre-execution observation by this reviewer. No original/metadata file was overwritten, regenerated, moved, deleted or repaired.

### Current public content, policy and provenance

- Independently derived the configured account from bounded existing configuration and three bucket literals from original plan bucket fields, in memory. Scanned **989 current candidate files/link texts**, not merely scanner-eligible files or changed paths. Zero unclassified exact-identifier matches.
- Exactly **12 unchanged complete IAM-principal token occurrences across six paths** remain under the supplied supervisor-approved classification. They are source-verified principal labels, not bucket fields, S3 URIs or account-qualified ARNs. No global bucket-substring allowance was applied. `docs/configuration.md` and the other principal-only records remain byte-identical to HEAD.
- `infra/recovery/main.tf` equals the original whole file after exactly one account-component replacement with `${var.aws_account_id}`. Substituting the existing input restores the original whole file. Thus every other action, condition, trust restriction, resource/suffix, region, grant and policy statement is unchanged; no AWS operation was needed.
- All eight existing infrastructure test bodies and their helper compare AST-identically after that exact substitution and normalization of the newly factored local string constant. One new narrowly scoped raw-export ignore test is added. No IAM assertion is removed or weakened.
- All **30 changed operational counterparts** have verified private HEAD originals. Removing their provenance insertion and applying one consistent exact account/bucket replacement mapping reproduces every original body, preserving embedded hashes, observations, outcomes and limitations. Labels identify source revision, manifest lookup by source path and **original-artifact SHA-256, explicitly not the redacted-text hash**. All **eight plan exports** are marked historical/non-executable, not fresh approval.
- The unchanged repository credential scanner passed on **945 eligible tracked/untracked files**. Supplemental JWT, signed-query and STS-token patterns across the complete inventory left only one individually inspected, HEAD-identical mock-test token fixture. Twelve nonempty configured secret-like values of at least eight characters were compared privately with zero matches; two short settings are excluded from a literal-absence claim.
- No actual `.env`, private tfvars/state/binary-plan, custody-bundle or calendar path enters the candidate inventory or index. Examples retain their existing blank/synthetic contracts; no runtime/configuration input was added.

### Graph, feature isolation and Git boundaries

All eleven publication/custody graph imports and execution evidence are present. The imported graph contains **15 distinct per-record absent-file references** expressly classified by candidate scope blocks as preserved pending/future third-ticket material in the original checkout/private snapshot. No versioning follow-up revision exists yet. These are **pending cross-slice references**, not missing implementation deliverables for this ticket. Final branch/revision-qualified pointers belong to ticket 3; do not import its absent feature specs merely to satisfy a link check.

No unclassified missing reference was found in the imported graph. The parent copy explicitly labels its retained pre-execution status snapshot and points to current child evidence. There is no feature-decision/spec supersession in this candidate. Changes outside the 45-path allowlist are absent; the catalog implementation foundation otherwise equals HEAD.

All preexisting ref lines and worktree blocks match the fresh baseline, including the unrelated audit branch/worktree. The sole additions are the authorized cleanup branch/worktree at the original base; **no new commit exists**. Local published-tracking refs, main and existing branch tips have not moved. No network query was made, so this is not a fresh hosted-ref observation or proof against hypothetical transient/external actions.

## Bounded commands and results

All private content, configuration, manifests and original diffs were compared in memory, emitting only redacted context or aggregate results. Reviewers' exploratory helper assertions initially needed correction for local-constant AST normalization, helper-function counting, string-encoded manifest modes and the contextual mock fixture; these were checker-assumption corrections, not candidate repairs. The actual raw-index mismatch was retained, not normalized away.

- Read-only `python3 -B` standard-library verification using `git --no-optional-locks` / `GIT_OPTIONAL_LOCKS=0`, captured `fdesetup status`, `df -P`, `diskutil info -plist`, and ACL inspection: results above.
- Existing original `.venv/bin/python -B -m pytest -q -o addopts='' -p no:cacheprovider --noconftest tests/platform/test_recovery_infrastructure.py tests/platform/test_check_secrets.py`, with bytecode disabled and plugin autoload disabled: **21 passed in 2.21s**. Tests were inspected first; scanner tests stage only synthetic temporary fixture repositories, not either actual worktree.
- Existing `.venv/bin/ruff check --no-cache tests/platform/test_recovery_infrastructure.py`: **passed**. No formatter ran in this review.
- Candidate `git --no-optional-locks diff --check`: **passed**.
- `git check-ignore --no-index --stdin -z`: two synthetic raw-export cases ignored; five unrelated/outside-boundary cases not ignored. No probe files created.
- Post-test recheck: 45 candidate fingerprints, 999 protected original states, all 68 private-file fingerprints, fresh logical index and empty actual staged sets still pass.

## Exact reviewed candidate changed paths

Thirty operational redactions:

- `.10x/decisions/catalog-backup-with-rebuildable-iceberg-warehouse.md`
- `.10x/evidence/.storage/2026-09-04-databox-catalog-only-final.tfplan.txt`
- `.10x/evidence/.storage/2026-09-04-databox-catalog-only-recovery.tfplan.txt`
- `.10x/evidence/.storage/2026-09-04-databox-catalog-only-tls.tfplan.txt`
- `.10x/evidence/.storage/2026-09-04-databox-recovery-operator-login-repair.tfplan.txt`
- `.10x/evidence/.storage/2026-09-04-databox-recovery-operator-mfa-local-plan.txt`
- `.10x/evidence/.storage/2026-09-04-databox-recovery-operator-mfa-repair.tfplan.txt`
- `.10x/evidence/.storage/2026-09-04-databox-recovery-operator-repair.tfplan.txt`
- `.10x/evidence/.storage/2026-09-04-databox-recovery.tfplan.txt`
- `.10x/evidence/2026-09-04-catalog-backup-infrastructure-apply.md`
- `.10x/evidence/2026-09-04-catalog-only-final-opentofu-plan.md`
- `.10x/evidence/2026-09-04-catalog-only-recovery-opentofu-plan.md`
- `.10x/evidence/2026-09-04-catalog-only-tls-recovery-opentofu-plan.md`
- `.10x/evidence/2026-09-04-recovery-opentofu-plan.md`
- `.10x/evidence/2026-09-04-recovery-operator-live-role-proof.md`
- `.10x/evidence/2026-09-04-recovery-operator-login-repair-apply.md`
- `.10x/evidence/2026-09-04-recovery-operator-login-repair-plan.md`
- `.10x/evidence/2026-09-04-recovery-operator-mfa-local-plan.md`
- `.10x/evidence/2026-09-04-recovery-operator-mfa-repair-apply-success.md`
- `.10x/evidence/2026-09-04-recovery-operator-mfa-repair-apply.md`
- `.10x/evidence/2026-09-04-recovery-operator-repair-plan.md`
- `.10x/evidence/2026-09-05-first-catalog-backup-attempt.md`
- `.10x/evidence/2026-09-05-pgbackrest-polaris-user-repair-attempt.md`
- `.10x/evidence/2026-09-08-first-isolated-catalog-restore-attempt.md`
- `.10x/evidence/2026-09-08-isolated-catalog-restore-files-success.md`
- `.10x/evidence/2026-09-08-isolated-catalog-restore-retry.md`
- `.10x/reviews/2026-09-04-catalog-only-tls-plan-review.md`
- `.10x/reviews/2026-09-04-recovery-operator-login-plan-review.md`
- `.10x/tickets/2026-09-04-simplify-recovery-infrastructure-to-catalog-only.md`
- `.10x/tickets/done/2026-09-04-apply-and-prove-disaster-recovery.md`

Eleven graph imports and one execution record:

- `.10x/decisions/keep-recovery-deployment-identifiers-private.md`
- `.10x/evidence/2026-09-11-private-recovery-originals.md`
- `.10x/evidence/2026-09-12-catalog-publication-cleanup.md`
- `.10x/knowledge/git-index-and-worktree-fingerprints.md`
- `.10x/reviews/2026-09-10-catalog-recovery-publication-safety.md`
- `.10x/reviews/2026-09-12-private-recovery-originals-review.md`
- `.10x/specs/private-recovery-evidence-custody.md`
- `.10x/specs/public-catalog-recovery-content.md`
- `.10x/tickets/2026-09-10-ratify-catalog-recovery-publication-boundary.md`
- `.10x/tickets/2026-09-11-sanitize-catalog-recovery-publication.md`
- `.10x/tickets/2026-09-11-separate-warehouse-versioning-record-branch.md`
- `.10x/tickets/done/2026-09-11-preserve-private-recovery-originals.md`

Three scoped implementation/protection paths:

- `.gitignore`
- `infra/recovery/main.tf`
- `tests/platform/test_recovery_infrastructure.py`

## Limits and acceptance disposition

No installs, network/AWS calls, runtime/warehouse actions, credential changes, staging of actual worktrees, commits, hook changes, ref movement, repairs or ticket closure occurred in this review. No subagents were used. Ticket 3 remains unexecuted.

Bounded scanning is not proof against every historical/encoded credential. Ignored private files lack historical baseline fingerprints; their universal byte-preservation cannot be certified. FileVault is not immutability, off-host backup or disk-loss protection. Local current-file redaction does not erase already-public commits or external copies. No hosted CI, exact-cleanup-commit approval, general merge readiness or publication authorization is established.

Acceptance criterion 1 is not fully satisfied because the required local cleanup commit remains blocked; the prepared content is scoped and verified. Criterion 2 is satisfied by independent actual-candidate/private-custody checks, test results, exact file inventory, fingerprint identity and retained limitations. Parent owns safe commit authorization, C1 disposition, subsequent exact-revision verification and any eventual closure.


## Parent reconciliation — 2026-09-12

This candidate-local 10x copy is canonical; the original checkout holds a thin index at the same relative review path. Source: workflow `a0184bf2-5456-4349-b711-32e3a2f9fd2d`, fresh verifier `9d505f1b-de8d-497c-a317-258eb757b100`, configured output `independent-publication-review.md`. The source's blocked verdict is represented as standard 10x `concerns` plus an explicit blocked execution gate; no finding is removed.

The parent independently matched all 45 reviewed candidate fingerprints and their canonical digest before these record-only additions, inspected the three implementation/protection-file diffs with identifiers redacted, and privately reproduced exact whole-main equivalence with the configured account. Both staged sets remained empty, both HEADs still named the unsanitized base, and the original `uv.lock` digest matched. No cleanup commit or ticket closure is claimed.

B1 remains blocking. The parent independently inspected the installed wrapper and configured hooks. A read-only SQLite query of the existing pre-commit cache found both pinned repositories and Python environments with interpreter/install-state files present. This is availability evidence, not a passed health check or permission to run mutating hooks/install environments. Recommended pending approval: permit existing hooks to format only scoped cleanup files in the isolated candidate, with installed-environment health verified first, no downloads/installations or hook bypass, review of any formatter changes and repeated checks before a local commit. Stop if an environment or broader change is required. No such route has run.

C1 is separately acknowledged as a nonblocking preservation-attribution limitation for the prepared content, not automatically inherited from custody's earlier C1 and not resolved as a benign refresh. Current protected work/logical entries are supported by the fresh verifier; an unchanged original raw index through review is not. No index reconstruction or replacement custody copy is justified by the observed absence of content/staged loss. The cause remains unknown and is retained here.

The source review's final numbered acceptance summary is not a literal mapping to the ticket's bullet numbering: verified private custody supports its first bullet; the outstanding local commit belongs to its final outcome. Content/provenance/test checks support preparation, while commit, exact-commit review and closure remain incomplete. The added canonical review and parent progress qualifications are later record-only changes; the 45-path fingerprint describes the earlier reviewed preparation, not these additional records.
