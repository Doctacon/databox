# Warehouse Recovery Operator Grant Plan

## Status

Applied once after exact filename-and-SHA-256 approval; that approval is consumed. See [apply evidence](warehouse-recovery-operator-grant-apply.md).

## Objective

Grant the existing `databox-recovery-operator` IAM user the minimum S3 access needed for the isolated Stage-1 warehouse recovery drill. This creates no user, role, profile, access key, bucket, object, or catalog resource.

The authenticated infrastructure profile was exported once and its exact credentials were STS-verified as the expected account-root principal before planning. No identity, account, bucket, credential, or token is recorded here.

## Exact private plan

- File: `infra/recovery/warehouse-recovery-operator-grant-20260915T161119Z.tfplan`
- SHA-256: `5e2b8592271a608b9350a7859457bae979c477c9e1bdc6e37deff2a911c43ff8`
- Private plan log: `infra/recovery/warehouse-recovery-operator-grant-20260915T161119Z.log`
- Plan and log mode: `0600`
- Live-refresh summary: `1 to add, 0 to change, 0 to destroy`

A bounded `tofu show -json` verifier confirmed exactly one actionable resource change: creation of `aws_iam_user_policy.warehouse_recovery_drill` on the existing recovery operator. A fresh exact export of the reauthenticated non-root profile was STS-verified and its caller ARN privately compared to the Terraform state output for that policy recipient; exact equality and IAM-user type both passed without exposing either value.

## Exact grant

| Scope | Allowed actions | Constraints |
|---|---|---|
| Existing warehouse bucket | `s3:GetBucketLocation`, `s3:GetBucketVersioning`, `s3:GetLifecycleConfiguration`, `s3:GetBucketPolicy` | Read-only protection verification |
| Existing warehouse bucket | `s3:ListBucketVersions` | Prefix must match `integration/recovery/????????????????/stage1/warehouse/*`; requested `s3:max-keys` must be at most 1000 |
| Generated Stage-1 object path only | `s3:GetObjectVersion`, `s3:PutObject`, `s3:DeleteObject` | Resource must match the same exact 16-character-run Stage-1 path |

The plan has no `s3:GetObject`, `s3:DeleteObjectVersion`, `s3:*`, bucket mutation, ACL, tagging, multipart, KMS, canonical-prefix, cleanup, or broader object permission. `CopyObject` uses `s3:GetObjectVersion` on an explicit historical source version and `s3:PutObject` on the same generated destination scope.

## Validation

- `tofu fmt -check`: passed.
- `tofu validate`: passed.
- New exact-token policy contract plus neighboring infrastructure tests: 15 passed.
- Exact reauthenticated-profile-to-policy-recipient binding: passed.
- Independent narrow-permission review found no broader grant; its one recipient-binding concern was resolved by the exact comparison above.
- One unrelated infrastructure test remains excluded because its `.10x` source is intentionally deleted.
- Raw plan output remains private and is not copied into ledger evidence.

## Consumed apply gate

The user explicitly approved this exact file and SHA-256. The file hash, saved-plan structure, current state lineage, root identity, and plan freshness were rechecked before its one successful application. Exact read-back, non-root capability checks, private setting generation, and root logout are recorded in [apply evidence](warehouse-recovery-operator-grant-apply.md). No further apply is authorized.
