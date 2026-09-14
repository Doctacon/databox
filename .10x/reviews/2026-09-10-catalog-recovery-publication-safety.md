Status: recorded
Created: 2026-09-10
Updated: 2026-09-10
Target: feat/backup-plan-iceberg at 027af8b4271d60ffc193967d092b5d2497af13ad
Verdict: concerns

# Catalog recovery: public-merge safety assessment

> Candidate reference scope: the following paths denote preserved pending/future third-ticket material in the original dirty checkout and private custody snapshot, NOT files in this catalog-only candidate. No versioning follow-up branch/revision exists yet; final branch-qualified reconciliation belongs to ticket 3.
> `.10x/tickets/2026-09-10-protect-iceberg-warehouse-object-versions.md`

## Scope and provenance

The user asked whether the catalog recovery branch is safe to merge into public `main`, and whether the newest versioning records should be separate work. This was an Outer Loop read-only assessment, not authorization to move files, branch, stage, commit, push, open a PR, alter history, rotate credentials, or modify AWS.

- Assessed HEAD: `027af8b4271d60ffc193967d092b5d2497af13ad`.
- Local and anonymously observed GitHub main: `50d787f8f012cf4df595b230ed1a0b52978c7759`, also the merge base.
- Branch delta: 125 commits; 150 final changed paths.
- Source system: GitHub, repository `Doctacon/databox`, https://github.com/Doctacon/databox/tree/feat/backup-plan-iceberg .
- Anonymous GETs to `https://api.github.com/repos/Doctacon/databox`, `/branches/feat%2Fbackup-plan-iceberg`, and `/branches/main` on 2026-09-10 confirmed public visibility and the exact SHAs above. This is current remote observation, not merely an inference from a local tracking ref.
- The newest S3-versioning work was uncommitted: 11 changed tracked `.10x` paths and 12 untracked `.10x` paths, with no staged changes. It includes the moved prior decision and cross-reference edits, not just the six new tickets. Its parent is `.10x/tickets/2026-09-10-protect-iceberg-warehouse-object-versions.md`.

## Methods and observed results

1. Inspected `.gitignore`, `.pre-commit-config.yaml`, `scripts/platform/check_secrets.py`, its tests, Git trees/history/path inventories, changed-file metadata patterns, and all four committed workflow files. No formatter, build, test suite, dependency installation, or mutating workflow ran.
2. Ran the inspected read-only scanner with `python3 -B scripts/platform/check_secrets.py .`: 936 eligible tracked working-tree files passed. Separately scanned all 12 untracked record files: no findings. The working-tree result alone is not evidence about removed files or old commits.
3. Read committed Git objects in memory using `git ls-tree`, `git rev-list --objects <base>..HEAD`, and `git cat-file --batch`: scanned all 977 HEAD blobs and all 514 distinct branch-only historical blobs (4,595,917 historical bytes), plus branch commit messages. All blobs were UTF-8 text; none were skipped as binary. Applied the repository scanner's provider/literal rules and additional JWT, AWS STS token, signed-S3-URL, and cipher/session assignment checks. No confirmed credential finding remained after candidate inspection.
4. Extra checks initially flagged synthetic fixture values/redaction assertions in `tests/platform/test_catalog_recovery.py`, an empty `.env.example` field incorrectly spanning a newline in the exploratory regex, and the Jinja environment lookup in `scripts/sources/templates/source/rest/source.py.j2:47`. These were inspected; the template is identical on main. Tightening only the in-memory audit regex and classifying exact inspected fixture values left no unresolved supplemental candidate. No repository scanner/test was modified.
5. Compared 13 nonempty configured project-local secret-like values of at least eight characters against HEAD and branch-only blobs entirely in memory: zero matches; no values, hashes, or credential files were exported. Two shorter local Polaris settings yielded ordinary-word matches, largely already present on main, but no credential-context match under the bounded inspection. This is not a strength/rotation assessment or exhaustive semantic proof that arbitrary text cannot coincide with a credential.
6. `.env`, `infra/recovery/recovery.auto.tfvars`, local state and state backup, and the inspected binary `.tfplan` were ignored and untracked. HEAD and branch-history path enumeration found no actual `.env`, `.tfvars`, `.tfstate`, private-key file, calendar `.ics`, or warehouse database/data file introduced by the branch. `.env.example` is intentionally tracked.
7. Anonymous GitHub API queries for open PRs on this branch, check runs at HEAD, and combined commit statuses returned no open PR, zero check runs, and zero statuses. The API's aggregate `pending` state with zero statuses does not mean a running or failed check. There is no hosted CI evidence for this exact commit.

## Findings

### F1 — Public already, independently of merging

The committed branch is anonymously readable now. Keeping it out of main is not a privacy barrier. A second branch in the same public repository is also public once pushed. The uncommitted versioning work is not included in the published branch or a GitHub merge of its current HEAD.

### F2 — Significant publication concern, not a proven credential leak

Real deployment identifiers are committed in code, tests, decisions, and rendered plan/apply evidence. Examples, with identifier values deliberately omitted here:

- `infra/recovery/main.tf:109`: literal live account component in the sign-in Resource ARN despite an existing `aws_account_id` input.
- `tests/platform/test_recovery_infrastructure.py:79`: asserts that same literal account-specific ARN.
- `.10x/evidence/.storage/2026-09-04-databox-recovery-operator-login-repair.tfplan.txt:20,28`: exact IAM/sign-in resource ARNs.
- `.10x/evidence/2026-09-04-catalog-backup-infrastructure-apply.md:12,20,28`: account/root identity, deployed bucket, and role information.
- Other tracked `.tfplan.txt` exports contain the same class of account, bucket, role, user, trust/policy, and operational details. The `.tfplan` ignore rule does not exclude tracked `.tfplan.txt` text exports; a `.storage` directory is not private by virtue of its name.

Account numbers, resource names and ARNs do not authenticate a caller or grant access by themselves. Publishing them is not equivalent to leaking an AWS secret key. However, they disclose the deployment and security operating model, which may exceed the user's intended public boundary. No blanket permission to publish that information is inferred from a clean credential scan or earlier operational evidence reviews.

### F3 — Merge readiness unproven beyond this privacy assessment

No hosted checks exist for this exact HEAD, and this assessment did not run functional CI or perform a complete code/security review. Prior successful catalog recovery proves that observed drill, not every merge criterion. No workflow was found that automatically invokes OpenTofu apply or the recovery drill on merge; the real Polaris/S3 workflow is manual. Ordinary CI/docs/release workflows can still run on main.

### F4 — Record-only follow-up boundary

Separate the newest versioning record set, including its associated supersession/cross-reference edits, from any eventual catalog-only publication cleanup. `uv.lock` was already modified and remains unrelated. This audit and its shaping owner are publication-assessment records, not part of that versioning implementation plan. No separation has been performed.

## Verdict

Concerns: no confirmed credential leak found within the stated scans, but do not give an unconditional public-merge approval. Ratify/redact the deployment-information boundary, keep new versioning work separate, and obtain the normal exact-commit merge checks. Recommendations and unresolved publication choices are owned by `.10x/tickets/2026-09-10-ratify-catalog-recovery-publication-boundary.md`.

## Limits and no-action rationale

No AWS IAM/S3 call, secret validity test, live runtime inspection, old-main full-history scan, inaccessible/dangling remote-object scan, Actions-log/artifact audit, issue/PR-comment scan, or external cache/fork inspection occurred. Pattern scanning and current-secret comparison cannot prove absence of every secret, including formerly configured credentials or encoded material. Commit author identity was already present in main history; no new author-email identity was introduced in the 125 branch commits.

No credential rotation is prescribed solely for public account/ARN metadata because no authenticating secret exposure was established. The existing live IAM audit remains owned by `.10x/tickets/2026-09-05-establish-primary-warehouse-session-credentials.md`. Removing text in a later commit does not remove old public history or third-party copies; history rewriting, visibility changes, deletion of public artifacts, and any rotation require separate scope/authorization. New audit records deliberately omit the actual identifiers and secret values.
