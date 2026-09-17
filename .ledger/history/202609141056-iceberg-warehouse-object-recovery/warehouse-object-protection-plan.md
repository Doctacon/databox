Status: applied and verified; see [apply evidence](warehouse-object-protection-apply.md)
Created: 2026-09-14

# Warehouse object-version protection: saved-plan evidence

## Scope and authority

The user selected a temporary root-only retention-control boundary, accepted bucket-wide plan generation across all three prefixes (including the operationally unclassified prefix), and retained separate exact-plan/apply and maintenance gates. The user performed root-backed CLI login. This run revalidated the exact target and existing settings, generated a saved live-refresh plan and structurally inspected its resolved values. It did not apply infrastructure, change S3, access object payloads, stop writers, test enforcement or perform recovery.

## Pre-plan gates

- Ignored `recovery.auto.tfvars` is mode `0600`, is the only auto-loaded variable file, selects the expected root-backed profile and contains the existing warehouse bucket copied from local `DATABOX_AWS_S3_BUCKET`. Local account and bucket consistency checks passed without emitting either value; warehouse and catalog-backup bucket inputs differ.
- The profile is AWS-login backed with no configured static-key, role, source-profile, credential-process, web-identity or other alternate credential source. Live STS matched the exact expected account-root identity, and the Terraform caller-identity precondition passed.
- The warehouse remained in the expected account/region, never-versioned/unset, with no lifecycle or bucket policy. Public-access block, AES256 encryption, BucketOwnerEnforced ownership and the accepted three-prefix scope remained unchanged.
- New warehouse settings addresses were absent from local state. State was mode `0600`, serial 5. No real account/bucket identifier appeared as a standalone value in added tracked content.
- Fourteen focused infrastructure tests, Ruff, OpenTofu format/validate, example formatting, diff whitespace and private-input consistency checks passed. The full infrastructure test file has the same separate pre-existing deleted-`.10x` FileNotFoundError after 14 passes.

## Exact saved live-refresh plan

Run from literal `infra/recovery/` with umask `077`, noninteractive input, state-lock timeout, detailed exit code, no color and a private log:

```bash
tofu plan -input=false -lock-timeout=10s -detailed-exitcode -no-color \
  -out=warehouse-object-protection-20260914T224021Z.tfplan
```

- OpenTofu: 1.12.6.
- Timestamp: 2026-09-14T22:40:21Z.
- Saved binary: `infra/recovery/warehouse-object-protection-20260914T224021Z.tfplan`.
- SHA-256: `0deb607f3bd3407d838a610544788f2603ecda27733d226b1e9f99f0034a2a7a`.
- Private log: `infra/recovery/warehouse-object-protection-20260914T224021Z.log`.
- Binary and log are Git-ignored and mode `0600`; raw plan output/JSON remain private.

Bounded in-memory `tofu show -json` inspection verified:

| Property | Result |
| --- | --- |
| Managed mutations | Exactly three creates listed below |
| Existing catalog/IAM resources | 11 no-op |
| Managed updates/replacements/deletes | None |
| Resource drift | None at plan generation |
| Output changes | None |
| Persisted state | Byte-for-byte unchanged; serial remains 5 |
| Terraform/private inputs/lock | Byte-for-byte unchanged during planning |
| Root caller assertion | Passed |

Exact creates:

1. `aws_s3_bucket_policy.warehouse`
2. `aws_s3_bucket_versioning.warehouse`
3. `aws_s3_bucket_lifecycle_configuration.warehouse`

The existing bucket is a data-source target only; there is no managed warehouse-bucket resource, replacement, destroy, `force_destroy`, relocation or object rewrite.

## Resolved protection contract

The planned bucket policy has version `2012-10-17`, no Allow and exactly two Denies. Both use wildcard Principal plus `ArnNotEquals` `aws:PrincipalArn` against only the exact owning-account root ARN.

- `DenyNonRootVersionDeletion`: only `s3:DeleteObjectVersion`, only the warehouse object ARN.
- `DenyNonRootProtectionChanges`: only `s3:PutBucketVersioning`, `s3:PutLifecycleConfiguration`, `s3:PutBucketPolicy`, and `s3:DeleteBucketPolicy`, only the warehouse bucket ARN.

The plan enables bucket-wide versioning and declares one enabled empty-filter lifecycle rule containing only 30-day noncurrent-version expiration. It adds no current-version expiration, transition, delete-marker cleanup, newer-version count, multipart-abort rule, Object Lock, replication, logging, notifications, encryption/public-access/ownership changes, `DeleteBucket`, ordinary `DeleteObject`/`PutObject` restriction, service exception or output.

Dependency order is policy, then versioning, then lifecycle. This closes direct writer and role-session control/version-purge paths before versioning becomes the recovery dependency.

## Exact guarantee and exclusions

If applied and read back, protected historical versions cannot be manually purged and versioning/lifecycle/policy cannot be weakened by non-root principals. Ordinary writes and ordinary deletes remain available; a normal delete after versioning normally creates a delete marker. Non-root principals retaining historical-version read plus object write can promote old content as a new current version, so this is not root-only recovery. Account root and S3 Lifecycle remain intentional permanent-deletion paths.

The plan does not protect against bucket deletion, Object Lock mutation, unrelated bucket-setting changes, logical/current-object corruption, version storms/cost, root/account compromise, account or bucket loss, already-lost history, or detection after lifecycle expiration. It does not prove denial enforcement or coherent Iceberg recovery.

First enablement cannot return the bucket to its never-versioned state; a later suspension is not a reversal. Versioning cannot recreate history lost before enablement. Existing null versions gain protected history only after a future overwrite/delete makes them noncurrent. Versions become lifecycle-eligible after 30 noncurrent days, with UTC rounding and asynchronous processing—not immutable retention or an exact 720-hour guarantee. Additional version storage cost depends on workload churn across all three prefixes and has no approved numerical cap.

## Approval freshness fingerprints

| Input | SHA-256 |
| --- | --- |
| `main.tf` | `db3484a945c33d46732f56bcf268e47bca156ebc6ca408ac2841af41da6c254f` |
| `outputs.tf` | `a937505be234bfbcf543b3ad1f38e476fd70c33a771fcba425049a20ac301f53` |
| `variables.tf` | `1ecdc116e1b4a3796ddc047ee6cf4aaff5f446a59df08aaa413a141dd0543273` |
| `versions.tf` | `7aa040e6c7ed59fa3ea680c2fa7e8945643b29db95daef23412e36f7704842b8` |
| `recovery.auto.tfvars` | `914114aa7e6c9693877eef485b09224fcbc0d893902faf0767cac8e9934e9386` |
| `.terraform.lock.hcl` | `02d2b020180bf03e77af58e54b0539ff0da8e5b4f06db21ff347be0cf092cfd3` |
| `terraform.tfstate` | `99825764b85e0dd94b3c0e07cc37477fe4113299ee6cbabc6d6e43c12c8c387b` |

Before apply, reverify every fingerprint, exact plan hash, exact account-root caller, target/account/region separation, accepted three-prefix scope, and still-absent live policy/lifecycle/unset versioning. Apply only the named binary. Any mismatch invalidates freshness; do not replan, import or apply silently. A saved plan does not pin credentials or prove a drift-free interval for the 11 no-op resources.

## Remaining apply and proof gates

- Independent review of this exact sanitized plan projection must find no blocking issue.
- The user must explicitly approve the exact filename/hash and affirm a named maintenance owner can stop every PUT/DELETE path across all three prefixes.
- Immediately before apply, repeat root identity and all freshness checks. Keep writers paused before apply and for a fresh full 15 minutes after versioning reads back `Enabled`, following current AWS first-enablement guidance.
- Read back exact policy, versioning and lifecycle while preserving public-access block, encryption, ownership and unrelated settings. On partial failure, retain the pause, diagnostics and state; do not suspend/delete/retry blindly.
- Root CLI cache is intentionally retained during this user-approved recovery session to avoid another immediate login. End CLI/browser sessions after the approved apply/read-back or if work pauses.
- Live negative tests for direct writer/known role and the coherent disposable-table recovery drill remain separately reviewed operations. Configuration read-back alone proves neither.

At the time this saved-plan record was prepared, no apply had occurred. The later one-time apply and verification are recorded in [apply evidence](warehouse-object-protection-apply.md).
