Status: recorded
Created: 2026-09-12
Updated: 2026-09-12
Relates-To: .10x/tickets/done/2026-09-11-sanitize-catalog-recovery-publication.md, .10x/reviews/2026-09-12-catalog-publication-commit-review.md
Owner: .10x/tickets/done/2026-09-11-sanitize-catalog-recovery-publication.md
Source-HEAD: 027af8b4271d60ffc193967d092b5d2497af13ad

# Catalog publication cleanup: execution history and acceptance

> Current continuation (2026-09-12): local cleanup commit
> `75e2d5bea39d67f9961c68909134db635e3c3ed8` was created through unchanged normal hooks after
> independent precommit approval. See “Reviewed local commit” below. Earlier no-commit/B1 wording
> records prior observation boundaries. Only this evidence and the owning ticket receive subsequent
> unstaged result updates; committed implementation remains byte-identical to the reviewed candidate.
> Subsequent exact-commit review and parent acceptance completed; see the final section and
> `.10x/reviews/2026-09-12-catalog-publication-commit-review.md`. Earlier sections retain their
> historical stage boundaries and old ticket paths in exact inventories/commands; current ownership
> is under `tickets/done/`. Closure consolidation is record-only, not an implementation change.

## Candidate identity and authority

Only ticket 2 was executed. Candidate worktree:
`/Users/crlough/Code/personal/databox.worktrees/catalog-publication-cleanup`

Local branch: `chore/catalog-recovery-publication-cleanup`.
Branch HEAD/base: `027af8b4271d60ffc193967d092b5d2497af13ad`.
**No cleanup commit exists. The branch revision still names the published, unsanitized base;
only this uncommitted working tree contains the prepared cleanup.** Both staged sets remain
empty. Independent review has completed: prepared content checks pass, while the safe
commit route and exact-commit acceptance remain blocked. The canonical review is
`.10x/reviews/2026-09-12-catalog-publication-cleanup-review.md`. This ticket is not closed or moved.

The original checkout remains on `feat/backup-plan-iceberg` at that base. Only its owning
cleanup ticket is edited. The candidate copies the explicit eleven-file publication/custody
decision/spec/audit/evidence/knowledge/cleanup-ticket graph, including the parent and ticket-3
ownership pointers. No pending versioning feature record or working variant is imported.
References to its absent feature files are explicitly marked preserved pending/future
third-ticket material in the original checkout/private snapshot, not local candidate files.
No versioning follow-up branch exists; final branch/revision reconciliation belongs to ticket 3.
The parent and ticket-3 copies are ownership context, not new execution or closure authority.

## Reverified private custody before redaction

Refindable operator-owned bundle, retained without overwrite or regeneration:
`~/Private/databox/recovery-evidence/2026-09-11T235551Z-05aef1141954/`.

Reverified all three public metadata anchors from
`.10x/evidence/2026-09-11-private-recovery-originals.md` before trusting the manifest.
All **42 committed originals/bases + 22 current working variants = 64 payloads / 322,252 bytes**
match recorded sizes/SHA-256, HEAD path/blob/mode provenance or current working bytes/modes.
All **23 pending dispositions** remain recoverable, including the deleted decision and distinct
moved/edited working copy. This already-current snapshot was verified, not replaced.
Exact enumeration remains **68 files and 20 bundle directories**, plus the three approved
private parents. Every private file is operator-owned regular single-link `0600`; directories
are `0700`, with no private ACLs or symlinks. Canonical ancestor ownership/modes/ACLs pass;
the existing home delete-denial ACL is unchanged.

Captured `fdesetup status`, destination-specific `df -P`, and device-specific `diskutil info -plist`
verify APFS, FileVault enabled, global permissions and matching destination/mount device.
No raw private manifest, identifier, credential, old plan or diff is printed. No private
configuration/state is copied. The original anchored metadata and all payload bytes remain
unchanged; the later custody-review raw-index discrepancy is not erased or reattributed.

## Original-byte provenance and redaction semantics

Exact identifiers were re-derived privately from bounded existing recovery configuration and
HEAD operational bucket/ARN fields: **one configured account and three bucket literals**.
The 35 operational HEAD records with substring matches all have anchored private originals.
After source-backed principal-label classification, **30 records actually require redaction**,
including **eight historical text-plan exports**. The other five are unchanged principal-label
records. The only additional documentation substring match is also a retained principal label;
`docs/configuration.md` is byte-unchanged, so no additional original needed preservation.

Every changed operational record retains its public path, original body except for approved
exact substitutions, original conclusions/status and original embedded artifact hashes. Its
new provenance label identifies source HEAD, its own **original-artifact SHA-256 (not the
redacted text)**, the private bundle and manifest lookup by committed-head source path.
All text-plan exports are labeled **redacted historical, non-executable**, never fresh approval.
A private comparison removes only those labels and proves exact equality with the approved
substitution of the anchored HEAD original. Existing plan/binary hashes retain their original
meaning; no changed text is claimed to match an old plan hash.

### Contextual principal-name exception, not a bucket-substring allowlist

The supervisor inspected and approved retaining the complete IAM username used by the
existing local credential exception. It overlaps a bucket literal but is explicitly a principal
label, not a bucket reference or fictional identity. Twelve occurrences remain, each checked
against its unchanged original line and full-token context, across:

- `.10x/decisions/allow-long-lived-local-primary-warehouse-key.md` — 3.
- `.10x/evidence/2026-09-08-restored-polaris-primary-credential-proof.md` — 2.
- `.10x/reviews/2026-09-08-primary-warehouse-credential-compatibility-review.md` — 1.
- `.10x/reviews/2026-09-08-restored-polaris-primary-credential-proof-review.md` — 1.
- `.10x/tickets/2026-09-05-establish-primary-warehouse-session-credentials.md` — 4.
- `docs/configuration.md:60–66` — 1.

These are not S3 URIs, standalone bucket literals, bucket fields or ARN account components.
Generic user/role/profile labels remain public. Raw substring matching therefore has explained
matches; this evidence does not claim zero raw substring matches or broaden the privacy policy.

## Policy and future raw-artifact handling

`infra/recovery/main.tf` differs in exactly the sign-in ARN account component, now
`${var.aws_account_id}`. Privately substituting the existing configured account into that
one new interpolation reproduces the **entire original main.tf byte-for-byte**. This proves
configured effective-policy equivalence locally without printing the input or calling AWS.
No action, region, resource suffix, trust condition, role, grant, input or permission is changed.
The sign-in test asserts the parameterized exact ARN; an AST comparison confirms every
other existing assertion/function is unchanged.

Only two scoped ignore patterns are added for future raw recovery text exports in
`.10x/evidence/.storage`: `*.tfplan.txt` and `*-databox-*-plan.txt`. Existing tracked redacted
counterparts stay tracked. The active public-content spec warns that `.storage` is not private,
forbids force-adding raw exports, and directs exact future originals to approved private custody
with its protection gates. Positive/negative ignore checks cover both raw patterns and unrelated
Markdown/JSON/source-apply evidence. A focused regression test protects this boundary.
There is no blanket ignore of `.10x`, evidence or unrelated source-reconciliation artifacts.

## Preservation baseline and limits

Before candidate creation, captured a fresh **1,000-path** original tracked/nonignored-untracked
fingerprint inventory (missing-state/type/mode/size/SHA-256; four unrelated symlinks use link-text
bytes without following targets), full **977-entry logical index inventory**, current raw index
hash/mtime/size, and refs/worktree inventory. All logical entries equal HEAD, no staged changes.
This is a new observation boundary, not equality with custody's old raw-index anchor.

Final checks compare **999 protected original path states**, excluding only the authorized owning
ticket edit; the original inventory gains no file during worker execution. At the worker's final
check, raw and logical index matched this fresh baseline. Later independent review found a new
raw-index difference while all 977 logical entries still matched; its cause remains unknown.
The canonical review records C1 and the parent's separate acknowledgment, without index repair.
Parent review/progress-record additions occur after these original preservation observations. All preexisting refs/worktrees, including the unrelated audit branch/worktree, remain
unchanged; only the specifically authorized candidate branch/worktree is added. All 23 pending
versioning dispositions and private bundle file fingerprints remain unchanged.

Original `uv.lock`: **718,042 bytes**, SHA-256
`49d7c920d95c8c1fe981b0bb43573412d0e29e7c8c0281e979b952f4da70166f`.
The candidate retains published HEAD's lock bytes instead of importing the unrelated dirty lock.
No calendar changes or private config/state copies enter the candidate. Ignored private files/data
were not swept into baseline snapshots, so this is not a historical fingerprint attestation for
all ignored contents. No configured secrets, cloud credentials or warehouse data are exported.

## Validation and commit gate

Tools/hooks/tests were inspected before invocation. Existing local Python/pytest/ruff are used
directly: no uv/npm sync/install, AWS/network/runtime/warehouse/resource operation, new config,
credential rotation, push/PR/merge/history rewrite or published-ref movement.

- Focused infrastructure and secret-scanner tests: **21 passed**, using existing Python with
  `PYTHONDONTWRITEBYTECODE=1`, `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1`, `-B -m pytest`,
  `-o addopts='' -p no:cacheprovider --noconftest`. This is hermetic focused validation, not the
  full coverage/CI suite. Secret-scanner tests stage only their temporary synthetic fixture repos.
- Existing ruff `check --no-cache` passed. Initial read-only `format --check --no-cache` reported
  one new string-wrapping mismatch; fixed manually in the candidate test, never by a mutating hook.
- Private aggregate-only checks cover exact identifiers across all current candidate files,
  unchanged repository credential patterns on every eligible tracked and untracked candidate
  file, supplemental JWT/signed-S3-query/STS-token patterns, original-byte redaction equivalence,
  AST policy-test preservation, explicit graph references, feature isolation and scoped ignores.
- Observational Git uses `--no-optional-locks` / `GIT_OPTIONAL_LOCKS=0`. Scoped diff/whitespace
  checks and final re-verification are recorded below.

**Concrete commit blocker:** installed `core.hooksPath` pre-commit wrapper invokes the complete
`.pre-commit-config.yaml` pipeline: whitespace/EOF/mixed-line-ending fixers, ruff `--fix` and
formatter, plus possible hook-environment setup. These conflict with the authorized constraints.
Supervisor directed preparation/checks only, leaving a blocked, uncommitted, unstaged candidate.
No commit is attempted; hooks are not disabled, overridden, replaced or reconfigured; no
security check is skipped. A safe commit route requires separate approval before execution.

FileVault is not immutable/off-host backup or disk-loss protection. Pattern scans are bounded,
not proof of absence of every encoded/historical credential. Local cleanup does not erase
already-public history or external copies, establish hosted CI, or certify publication/merge
readiness. Parent owns independent review, commit-gate resolution and ticket closure.

## Final local check results — 2026-09-12

- Focused pytest rerun after the manual wrapping correction: **21 passed in 2.10s**.
- Ruff nonmutating checks: **all checks passed; 1 file already formatted**.
- Exact-identifier content inventory: **989 current candidate files**, zero unclassified
  matches; the 12 full IAM username occurrences are individually source-context classified.
- Unchanged repository credential scanner: **945 eligible tracked/untracked files**, zero
  findings. Supplemental formats have only the existing source-verified synthetic STS-token
  fixture in `tests/platform/test_catalog_recovery.py:408`; no blanket fixture exclusion.
- All 30 redacted operational bodies and original embedded hashes match approved transformations
  of anchored originals. The eight plan exports are explicitly non-executable.
- Graph references, absent pending feature files, unchanged published catalog foundation,
  whole-main configured-policy equivalence and existing test-assertion AST checks pass.
- Positive/negative raw-plan ignore checks, candidate `git diff --check` and new-record
  whitespace/newline checks pass. Checks inspect content, not just ignored filenames.
- Custody/protection and original preservation rerun passes: all 64 copies, all anchors,
  23 pending dispositions, 999 protected source states, current raw/logical index and old
  refs/worktrees. Both original and candidate have **zero staged files**.

Preflight/helper failures were fail-closed and corrected before their dependent operations:
stored custody status values needed whitespace-normalized comparison; the whole-tree scan
revealed the supervisor-resolved IAM-label overlap; a verification-only provenance-label
removal offset was corrected; the missing new evidence link was satisfied by this record;
and the known synthetic supplemental fixture was individually classified. No failure was
bypassed by changing original artifacts, ignoring unclassified identifiers or disabling
security checks. The original custody bundle was never regenerated or modified.

## Exact candidate changed files relative to published base

- `.10x/decisions/catalog-backup-with-rebuildable-iceberg-warehouse.md`
- `.10x/decisions/keep-recovery-deployment-identifiers-private.md`
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
- `.10x/evidence/2026-09-11-private-recovery-originals.md`
- `.10x/evidence/2026-09-12-catalog-publication-cleanup.md`
- `.10x/knowledge/git-index-and-worktree-fingerprints.md`
- `.10x/reviews/2026-09-04-catalog-only-tls-plan-review.md`
- `.10x/reviews/2026-09-04-recovery-operator-login-plan-review.md`
- `.10x/reviews/2026-09-10-catalog-recovery-publication-safety.md`
- `.10x/reviews/2026-09-12-catalog-publication-cleanup-review.md`
- `.10x/reviews/2026-09-12-private-recovery-originals-review.md`
- `.10x/specs/private-recovery-evidence-custody.md`
- `.10x/specs/public-catalog-recovery-content.md`
- `.10x/tickets/2026-09-04-simplify-recovery-infrastructure-to-catalog-only.md`
- `.10x/tickets/2026-09-10-ratify-catalog-recovery-publication-boundary.md`
- `.10x/tickets/2026-09-11-sanitize-catalog-recovery-publication.md`
- `.10x/tickets/2026-09-11-separate-warehouse-versioning-record-branch.md`
- `.10x/tickets/done/2026-09-04-apply-and-prove-disaster-recovery.md`
- `.10x/tickets/done/2026-09-11-preserve-private-recovery-originals.md`
- `.gitignore`
- `infra/recovery/main.tf`
- `tests/platform/test_recovery_infrastructure.py`


## Candidate-only cached-hook preparation — 2026-09-12

### Authority and fresh preservation boundary

The user approved existing candidate-only normal hooks with required formatting limited to the
cleanup whitelist, healthy cached environments first, and no installations/downloads or hook
bypass. This continuation executes preparation only: **neither actual index is staged and no
commit is attempted**. The original checkout, including all progress records and dirty `uv.lock`,
is read-only; there is no synchronization back. The branch and both HEADs remain the base above.
Ticket 3 and parent closure are not executed. Earlier B1 authorization wording is historical;
independent review of this new preparation and a later authorized local commit remain outstanding.

Fresh baseline `/tmp/databox-cached-hooks-preparation-baseline.json` accounts for all authorized
parent record additions: **1,001 original path states, 990 candidate path states, 46 scoped changed
paths**, 68 private-file fingerprints, both raw and logical index inventories, refs/worktrees and
installed hooks/configuration. Baseline-file SHA-256:
`ca574b18f899d338eae415a91d1f30d86e002f4b1cdd0c96c648e0ad404bf262`.
The 46-path whitelist is the exact changed-file list above (the prior 45 plus the canonical cleanup
review). No equality to the obsolete 45-path digest or either older raw-index anchor is claimed.

Current raw-index SHA-256 at this new boundary:
- Original: `bc23d73c02f8324d760df19bd4f3300ea6c408401387e6724b58ac98ba559df8`
  (137,157 bytes; mtime_ns `1789175653997920219`).
- Candidate: `b96f32dd9dde8e78441547bb2cd727754bd5c61b0d7da1aaf0d95f4100738b63`
  (136,522 bytes; mtime_ns `1789175659613415251`).
- Each logical index has 977 stage-0 entries equal to HEAD; the exact `ls-files --stage -z`
  SHA-256 is `edcd3a214c1bc09710f07458d3c9afa6914e770c8604e13322ef736e71e43981`.

Custody was checked before hooks and again after validation: all three anchors, all 42 committed
revision/path/blob/mode/copy comparisons, all 22 working variants, 64 payloads / 322,252 bytes,
23 pending dispositions, exact 68-file/20-directory enumeration, canonical owner-only protection,
no private ACLs/symlinks, and actual destination APFS/FileVault/global permissions passed.
Original metadata/originals were not overwritten or regenerated. Original lock bytes retain the
previously recorded digest. All 1,001 current original states are protected, with **no ticket
exception** in this continuation. Ignored-file historical coverage limits and both earlier C1
attribution qualifications remain unchanged.

### Installed execution inspection and non-installing health checks

`core.hooksPath` is the existing original Git-admin hooks directory. Its only executable non-sample
hook is `pre-commit`; `pre-commit.legacy`, `prepare-commit-msg`, `commit-msg`, `post-commit`,
`post-rewrite`, and corresponding legacy executables are absent. Sample filenames do not execute.
The installed wrapper selects the existing original `.venv/bin/python3` and pre-commit's normal
`hook-impl`. Inspected wrapper, runner `main`, `hook_impl` (including legacy dispatch), `run`,
repository install-state logic, Store/cache lookup, Python health/environment implementation,
system-language adapter, all configured hook manifests and executable Python hook implementations.
Ruff's installed launcher and pinned version were inspected/probed. No hook/configuration changed.

Installed runner: **pre-commit 4.5.1**. Read-only SQLite selection uses the exact configured repo/ref
pairs, not the similarly named Astral cache entry:
- `https://github.com/pre-commit/pre-commit-hooks`, `v4.5.0`:
  `~/.cache/pre-commit/repogtwk55yq/py_env-python3.12`.
- `https://github.com/charliermarsh/ruff-pre-commit`, `v0.12.5`:
  `~/.cache/pre-commit/repokrkx2kg7/py_env-python3.12`; binary reports **ruff 0.12.5**.

Non-installing checks use the installed `load_config`, `load_manifest`, `_hook`, `Hook.create`,
`python.health_check` and `_hook_installed` functions, constructing hooks directly from the
read-only cache query without calling repository setup/clone/install APIs. Every configured
Python hook resolves `python3.12` with no extra dependencies; both v1 dependency-state contents
and v2 state files pass. Health checks verify `pyvenv.cfg`, executing both environment and base
Python version probes. All eleven Python-hook entrypoint `--help` probes pass, proving installed
imports/executables usable. Existing system `python3` resolves Homebrew Python 3.14.7 and executes;
the local credential hook uses only its inspected standard-library scanner. pre-commit 4.5.1
normalizes config language `system` to `unsupported`, whose adapter has no environment installer.

Exact helper invocation (read-only health mode):
```sh
export PYTHONDONTWRITEBYTECODE=1 GIT_OPTIONAL_LOCKS=0
/Users/crlough/Code/personal/databox/.venv/bin/python3 -B /tmp/databox-cached-hooks-preparation.py health
```
These checks were repeated immediately before the normal pipeline. `_hook_installed` returns true
for every required environment, so normal runner setup returns without its installation branch.
No installer, downloader, environment replacement, SKIP flag, hook override or replacement ran.
An initial helper assertion expected unnormalized `system`; inspection confirmed the installed
schema alias and corrected only that checker assumption before pipeline execution. Nothing was
bypassed or changed in the actual configuration/scanner/tests.

### Exact normal hook command and results

Candidate cwd is the worktree above. Environment: `PYTHONDONTWRITEBYTECODE=1`,
`GIT_OPTIONAL_LOCKS=0`; no hook-skipping or configuration-override environment variables.
The following exact argv runs **all existing configured hooks**, constrained by their normal
file-type filters and these explicit 46 paths. Explicit files avoid the runner's staged-only
stash/index path; this is not an installed-hook replacement or a commit attempt.

```sh
/Users/crlough/Code/personal/databox/.venv/bin/python3 -B -m pre_commit run --hook-stage pre-commit --files \
  .10x/decisions/catalog-backup-with-rebuildable-iceberg-warehouse.md \
  .10x/decisions/keep-recovery-deployment-identifiers-private.md \
  .10x/evidence/.storage/2026-09-04-databox-catalog-only-final.tfplan.txt \
  .10x/evidence/.storage/2026-09-04-databox-catalog-only-recovery.tfplan.txt \
  .10x/evidence/.storage/2026-09-04-databox-catalog-only-tls.tfplan.txt \
  .10x/evidence/.storage/2026-09-04-databox-recovery-operator-login-repair.tfplan.txt \
  .10x/evidence/.storage/2026-09-04-databox-recovery-operator-mfa-local-plan.txt \
  .10x/evidence/.storage/2026-09-04-databox-recovery-operator-mfa-repair.tfplan.txt \
  .10x/evidence/.storage/2026-09-04-databox-recovery-operator-repair.tfplan.txt \
  .10x/evidence/.storage/2026-09-04-databox-recovery.tfplan.txt \
  .10x/evidence/2026-09-04-catalog-backup-infrastructure-apply.md \
  .10x/evidence/2026-09-04-catalog-only-final-opentofu-plan.md \
  .10x/evidence/2026-09-04-catalog-only-recovery-opentofu-plan.md \
  .10x/evidence/2026-09-04-catalog-only-tls-recovery-opentofu-plan.md \
  .10x/evidence/2026-09-04-recovery-opentofu-plan.md \
  .10x/evidence/2026-09-04-recovery-operator-live-role-proof.md \
  .10x/evidence/2026-09-04-recovery-operator-login-repair-apply.md \
  .10x/evidence/2026-09-04-recovery-operator-login-repair-plan.md \
  .10x/evidence/2026-09-04-recovery-operator-mfa-local-plan.md \
  .10x/evidence/2026-09-04-recovery-operator-mfa-repair-apply-success.md \
  .10x/evidence/2026-09-04-recovery-operator-mfa-repair-apply.md \
  .10x/evidence/2026-09-04-recovery-operator-repair-plan.md \
  .10x/evidence/2026-09-05-first-catalog-backup-attempt.md \
  .10x/evidence/2026-09-05-pgbackrest-polaris-user-repair-attempt.md \
  .10x/evidence/2026-09-08-first-isolated-catalog-restore-attempt.md \
  .10x/evidence/2026-09-08-isolated-catalog-restore-files-success.md \
  .10x/evidence/2026-09-08-isolated-catalog-restore-retry.md \
  .10x/evidence/2026-09-11-private-recovery-originals.md \
  .10x/evidence/2026-09-12-catalog-publication-cleanup.md \
  .10x/knowledge/git-index-and-worktree-fingerprints.md \
  .10x/reviews/2026-09-04-catalog-only-tls-plan-review.md \
  .10x/reviews/2026-09-04-recovery-operator-login-plan-review.md \
  .10x/reviews/2026-09-10-catalog-recovery-publication-safety.md \
  .10x/reviews/2026-09-12-catalog-publication-cleanup-review.md \
  .10x/reviews/2026-09-12-private-recovery-originals-review.md \
  .10x/specs/private-recovery-evidence-custody.md \
  .10x/specs/public-catalog-recovery-content.md \
  .10x/tickets/2026-09-04-simplify-recovery-infrastructure-to-catalog-only.md \
  .10x/tickets/2026-09-10-ratify-catalog-recovery-publication-boundary.md \
  .10x/tickets/2026-09-11-sanitize-catalog-recovery-publication.md \
  .10x/tickets/2026-09-11-separate-warehouse-versioning-record-branch.md \
  .10x/tickets/done/2026-09-04-apply-and-prove-disaster-recovery.md \
  .10x/tickets/done/2026-09-11-preserve-private-recovery-originals.md \
  .gitignore \
  infra/recovery/main.tf \
  tests/platform/test_recovery_infrastructure.py
```

**First run exit 0; zero candidate file-byte changes.** All applicable hooks pass. YAML/JSON/TOML
report their normal “no files to check” result because no such file is in the whitelist; no SKIP
flag is set. Ruff lint/fix and format needed no edits. Whitespace/EOF/line-ending hooks likewise
made no byte changes. Consequently every historical redaction body/hash and implementation/test
byte remains exactly as reviewed; there is no formatter normalization exception to provenance.
Normal runner bookkeeping may record candidate config usage in its cache; this is not an
installation or a hook/configuration edit. Ruff may maintain only its candidate-local ignored
cache. Neither original content/index nor shared hooks are changed.

Unstaged preparation limits: `check-added-large-files` normally filters to staged additions, so
its passing unstaged run is not an exact staged-commit check. Separately, every scoped file is
below its default 500 KiB limit. `check-merge-conflict` normally only scans during a merge;
a separate nonmutating explicit conflict-marker check covers the whitelist. A later real normal
commit pipeline and exact-revision review are still necessary; no commit-ready/hosted-CI claim.

### Repeated validation and fingerprints

Exact focused checks from candidate cwd, with bytecode and Git optional writes disabled:
```sh
export PYTEST_DISABLE_PLUGIN_AUTOLOAD=1
/Users/crlough/Code/personal/databox/.venv/bin/python3 -B -m pytest -q -o addopts='' -p no:cacheprovider --noconftest tests/platform/test_recovery_infrastructure.py tests/platform/test_check_secrets.py
/Users/crlough/.cache/pre-commit/repokrkx2kg7/py_env-python3.12/bin/ruff check --no-cache tests/platform/test_recovery_infrastructure.py
/Users/crlough/.cache/pre-commit/repokrkx2kg7/py_env-python3.12/bin/ruff format --check --no-cache tests/platform/test_recovery_infrastructure.py
git --no-optional-locks diff --check
/Users/crlough/Code/personal/databox/.venv/bin/python3 -B /tmp/databox-publication-cleanup-validate.py
/Users/crlough/Code/personal/databox/.venv/bin/python3 -B /tmp/databox-cached-hooks-preparation.py preserve
```

Focused suite: **21 passed in 2.03s**; lint passes and one Python file already formatted.
Tests were inspected; only temporary synthetic fixture indices are staged, not either actual index.
Private aggregate validation passes for all 990 candidate files/link texts, zero unclassified
identifiers, exactly the existing 12 individually source-verified IAM-label occurrences across six
paths (no bucket-substring allowlist), 946 eligible credential-scanned files, and supplemental
formats with only the exact unchanged mock STS fixture. Twelve configured secret-like settings
of at least eight characters are absent by private literal comparison; two shorter settings
are excluded from that absence claim. No configuration, identifier or credential is exported.

All 30 operational body transformations and original embedded hashes, eight non-executable plan
labels, entire configured `main.tf` equivalence, prior assertion ASTs, 80 graph references,
12 absent feature paths, untouched pending tracked variants, and scoped ignore checks pass.
After tests, all original/private fingerprints, raw and logical indices, refs/worktrees and
hook/configuration bytes still match the new baseline. Both staged sets remain empty.

Fingerprint serialization is sorted compact JSON of path to type/mode/bytes/SHA-256 records:
- Fresh 46-path pre-record-update digest (also unchanged by the first hooks/tests):
  `801b33c273c7c523ba870307877c419133c19efc91a8d38615bdf1dff4649186`.
- The 44 scoped files excluding this evolving evidence and owning ticket remain byte-unchanged:
  `e6e88675cc46d8bd0e794dd3fcd5e4f51fc473f4128dc4d34c51c4273d65f2ff`.
- The final complete 46-path fingerprint inventory is recorded after these two progress edits
  at `/tmp/databox-cached-hooks-preparation-final-fingerprints.json` and in the external
  `cached-hooks-preparation.md` handoff. Excluding the two self-reporting records above avoids a
  circular digest, not a source-preservation exception; their final hashes are in that inventory.

Only **this candidate evidence and its owning candidate ticket** are intentionally edited in
this continuation. No formatter changed a file. The same explicit pipeline and checks are
repeated after these records; final results and complete fingerprint are in the handoff.
Ready for independent preparation review, not staging/commit, ticket closure or publication.


## Reviewed local commit — 2026-09-12

### Independent gate and current authority

The actual external `precommit-independent-review.json` in workflow
`77aaa315-28ed-4a64-8b6e-e59156c6a1a1` was read in full: verdict **pass**, `readyForCommit=true`.
Its SHA-256 is `da1322933f64d5b1723e197966becf296a1377f8cd430dfb64b11752cb2e084d`.
It independently approves the exact 46-path unstaged candidate digest
`d8b413083011fb9742a2e7ec9050eb19815c6821e9016c9c99708db3d4fea2bd` for the already
ratified candidate-only normal-hook route after immediate health/preservation checks.
This continuation explicitly authorizes the local commit, superseding the earlier preparation-only
stop. No old finding is deleted or reattributed; exact-commit review and closure remain parent-owned.

Before any staging, all 46 reviewed file/type/mode/size/SHA-256 records and all 990 candidate path
states matched. No record/provenance addition was made before the commit: the complete reviewed
working tree was committed **without changing any byte**. The complete 46-path committed inventory
is the exact changed-file list above; no private/config/lock/calendar or ticket-3 feature file enters it.

Fresh commit-boundary snapshot `/tmp/databox-reviewed-local-commit-baseline.json` has SHA-256
`0b4e178f432727d6792a76b869d570553c9cfb554e2d09b0fdc3403ea5c212cb`. It separately retains
all 1,001 original states, all 990 candidate states, private-file and raw/logical-index fingerprints,
refs/worktrees and hooks/configuration at this boundary. All current original states and indices
also matched the preceding approved preparation boundary; no obsolete 45-path/old raw-index claim.

### Staging, hook execution and exact result

Used candidate cwd only, with `PYTHONDONTWRITEBYTECODE=1 GIT_OPTIONAL_LOCKS=0`.
Inspected the installed `staged_files_only` runner path before actual commit invocation: staging
all approved changes leaves no unstaged tracked diff or intent-to-add entry requiring its stash/
checkout route. Applicable executable and legacy hooks remain as previously inspected. Read-only
configuration/attribute checks found no signing, fsmonitor, custom clean filter or encoding transform
requiring another executable path. No hook or Git configuration was changed.

Immediately before staging and again immediately before commit, the existing inspected health
helper verified both exact pinned cache mappings, Python/base versions, both install states and
all eleven installed entrypoint probes. Every `_hook_installed` result was true. Private-custody
checks and original protection also passed. No setup/installer/downloader API was called in health
checks, and the normal pipeline did not need its environment installation branch.

Exact staging argv was `git add --` followed by the **46 explicitly enumerated paths above**, in
that sorted order. No `-A`, broad directory, force-add, original-index operation or hook override.
Then `git --no-optional-locks diff --cached --name-only` matched exactly those paths;
`git --no-optional-locks diff --cached --check` passed, with no remaining unstaged/untracked file.
All **990 indexed blobs** were read in memory and verified against reviewed bytes and modes,
including link-text bytes without following symlinks. `git --no-optional-locks write-tree`
produced the expected tree below before committing. These shared object/admin writes are part
of the authorized candidate commit, not changes to the original index or unrelated refs.

Exact normal commit command:
```sh
git commit -m "Sanitize catalog recovery publication records"
```

**One attempt, exit 0.** Installed pre-commit ran through Git's unchanged normal wrapper.
Whitespace/EOF, large-file, merge-conflict, debug, mixed-line-ending, Ruff lint/fix/format and
credential hooks passed. YAML/JSON/TOML had no eligible file under normal filtering; no SKIP
flag was set. No formatter changed any file bytes, no stash/checkout or installation was reported,
and no retry, amend, bypass, replacement or configuration change occurred.

- Local revision: **`75e2d5bea39d67f9961c68909134db635e3c3ed8`**.
- Tree: **`ebb7518e31aa6026018a38321548f6c412daf0ef`** (equals the verified staged tree).
- Sole parent: `027af8b4271d60ffc193967d092b5d2497af13ad`.
- Branch: `chore/catalog-recovery-publication-cleanup`.
- Delta: **46 files, 1,487 insertions, 71 deletions; 13 added records and 33 modified paths**.
- Every committed blob/mode equals the reviewed 990-path candidate inventory. The 46-path
  committed fingerprint remains `d8b413083011fb9742a2e7ec9050eb19815c6821e9016c9c99708db3d4fea2bd`.
- Candidate was completely clean immediately after commit. Both actual staged sets were empty;
  candidate index equaled the new 990-entry HEAD tree, while original index retained all 977 entries.

### Repeated checks and preservation

Before staging, the same inspected focused pytest command recorded above passed **21 tests in
2.20s**, pinned Ruff lint/format checks passed, and private candidate validation reproduced all
990-file identifier checks, 946 eligible credential checks, twelve individually source-verified
principal-label contexts, 30 exact redaction bodies/original hashes, eight non-executable plan
labels, whole configured main.tf equivalence, original assertion ASTs, 80 graph references and
scoped ignore/feature-isolation checks. No bucket-substring allowlist or weakened assertion.

After the commit, verified the sole parent, exact tree, exact 46 changed paths and every committed
blob/mode; all candidate file bytes remained unchanged by normal hooks. Custody recheck passes:
all three anchors, 42 committed plus 22 working copies / 322,252 bytes, 23 pending dispositions,
68-file/20-directory enumeration, safe canonical ownership/modes/ACLs, actual destination
APFS/FileVault/global permissions. Private originals and metadata are retained without regeneration.
Bounded existing private configuration was compared before/after in memory only and remained equal.

All **1,001 original working states** remain unchanged with no record exception; original branch
and HEAD remain at the base. Original raw index digest/size/mtime and all 977 logical entries match
the fresh snapshot; original dirty `uv.lock` retains its previously recorded bytes/digest. Hooks,
configuration and private bundle fingerprints match. Ref/worktree inventories differ **only** in
this authorized candidate branch/worktree HEAD advancement; all other refs, published-tracking
refs, main, original branch and unrelated audit branch/worktree remain unchanged. No network query
or remote operation was made. Earlier C1 attribution limitations remain historical, not repaired.

Safe external result metadata: `/tmp/databox-reviewed-local-commit-result.json`.
The authoritative final handoff is `reviewed-local-commit.md` in workflow
`83f46551-0421-4acd-a497-68a5056df156`; it records post-result-update checks and fingerprints.
Only this evidence and the owning candidate ticket receive **unstaged result additions after the
reviewed commit**. Their current working bytes are not the committed 46-path fingerprint; this
explicit distinction avoids circular commit hashes and does not modify implementation after review.
No second commit or amend is attempted. Both actual indices remain unstaged at handoff.

Ticket stays active for exact-revision independent review and parent acceptance/closure. No
original-checkout progress synchronization, ticket-3 execution, new branch/worktree, installation,
AWS/network/runtime action, credentials change, push/PR/merge or history rewrite occurred. Local
cleanup does not remove already-public history, establish hosted CI/general merge readiness, prove
universal credential absence, or make private custody immutable/off-host; prior ignored-file limits
remain. The unchanged normal non-merge conflict hook retains its documented filtering limitation;
explicit nonmutating marker checks supplement it rather than replacing it.

## Exact-commit acceptance and retrospective — 2026-09-12

The first exact-commit reviewer was interrupted by a transport error after the successful Git commit. A fresh fallback completed the missing review without repeating implementation or committing again. Canonical material findings, provenance and parent disposition: `.10x/reviews/2026-09-12-catalog-publication-commit-review.md`.

The fallback independently matched all 990 committed blobs/modes to the reviewed candidate and the exact 46-path digest, checked committed identifiers/credential patterns, all 30 original-body/provenance transformations, account-only policy equivalence, preserved assertions, graph/feature isolation and protected state. It executed all nine infrastructure tests against committed blobs and read-only Ruff checks; the full focused 21-test runs and normal hook execution are attributed to the independently inspected precommit and worker evidence.

Before closure metadata changes, the parent independently rechecked the commit/tree/parent and 46-path fingerprint, all 1,001 original states and original raw/logical index, private-file/hook/configuration fingerprints, all 64 custody source/copy comparisons and actual-volume FileVault/ownership/ACL checks. Pinned existing hook environments again passed read-only health/state and eleven entrypoint probes.

### Acceptance mapping

| Owning ticket criterion | Evidence |
| --- | --- |
| Private originals verified before operational changes | Anchored 64-copy custody evidence and independent review; repeated actual protection/source comparisons. |
| Parameterized exact account with unchanged effective policy | Whole original main.tf reconstructed by substituting the configured input; exact committed tree and preserved policy/test assertions. |
| No unclassified public deployment identifiers | Independent scan of all 990 committed blobs; 12 exact principal-label contexts retained by source classification, not global allowlisting. |
| Honest public provenance and hashes | Thirty original-body comparisons and eight explicitly historical/non-executable plan exports; original hashes unchanged in meaning. |
| Scoped graph with no pending feature import | Thirteen added publication/custody/cleanup records; explicit preserved-future references and absent versioning files. |
| Hermetic checks and independent review | Twenty-one focused tests before/after commit; committed-blob tests, Ruff, secret/identifier/diff/ignore checks; fresh precommit and recovered exact-commit reviews. |
| Local scoped commit and protected original/private work | Commit 75e2d5be and exact 46-path tree; unchanged original/private/hook state; no push, AWS action or original-checkout synchronization. |

The new post-writer candidate raw-index discrepancy is explicitly accepted as a nonblocking attribution limitation for this immutable committed result. Its actor/cause is unknown; all 990 logical entries still match HEAD, both staged sets were empty at review, and no original/private content loss was found. This is not a benign-refresh claim, not a raw-byte-unchanged assertion through review, and not a reason to recreate an index. Earlier original-index concerns remain separately qualified.

Retrospective learning is recorded in `.10x/knowledge/existing-precommit-environments.md` and `.10x/knowledge/git-index-and-worktree-fingerprints.md`. Healthy cached normal hooks were sufficient; no new hook runner, bypass or installation is warranted. Recover failed reviewer delivery independently from successful Git operations.

Parent closes only this local cleanup ticket. Record-only forward consolidation may include the two result records, canonical final review, ticket move/current references, dependency progress and these lessons through unchanged normal hooks; it must preserve the implementation/redaction body tree. Historical path inventories/commands above intentionally retain their execution-time names. Ticket 3 and hosted publication remain separate, unexecuted gates. The original checkout's records are intentionally not synchronized under the latest read-only boundary.
