# Warehouse Recovery Operator Grant Apply

## Status

Applied once and verified. The exact apply approval is consumed. This did not authorize or run the Iceberg drill `prepare`, Seed-A, Recovery-A, cleanup, or any S3 object mutation.

## Applied artifact

- Plan: `infra/recovery/warehouse-recovery-operator-grant-20260915T161119Z.tfplan`
- Plan SHA-256: `5e2b8592271a608b9350a7859457bae979c477c9e1bdc6e37deff2a911c43ff8`
- Result: `1 added, 0 changed, 0 destroyed`
- Added resource: `aws_iam_user_policy.warehouse_recovery_drill`

Before apply, the plan hash, mode, freshness, one-create structure, state serial/hash, resource absence, and exact account-root identity were rechecked. The saved binary was applied directly without replanning.

## Verification

- Terraform state advanced from serial 7 to serial 8.
- Current state SHA-256: `8379b578af43473648c302b8e9387a9a8903f03afdf8df12280285b8d33f5606`.
- Current state mode: `0600`.
- Previous-state backup SHA-256: `c38d8da966f2ee234d3e60718381263327eb12feb303d88b0aef5ceb5d1e71e4`.
- Previous-state backup mode: `0600`.
- Apply log SHA-256: `ec7995472abe4c9179384f1b8c1422629e8a80d68e30d6bbd3f2a07f5136eecf`.
- Apply log mode: `0600`.
- Root IAM read-back matched the exact reviewed three-statement policy.
- A fresh exact export of the non-root profile was STS-verified and still matched the exact IAM-user policy recipient.
- The same pinned non-root credentials successfully verified bucket location, versioning, lifecycle, exact two-Deny bucket policy, and bounded version listing under an exact generated Stage-1-shaped prefix.
- Object mutation capability remains intentionally untested until an exact Seed-A approval permits the canary.

No account, bucket, object key, ARN, VersionId, credential, token, or raw IAM document is recorded here.

## Private settings and session closure

Only after all post-apply checks passed, these existing `.env` settings were atomically populated without printing their values:

- `DATABOX_RECOVERY_PROFILE`
- `DATABOX_RECOVERY_IDENTITY_SHA256`
- `DATABOX_RECOVERY_RUN_SECRET`

`.env` remains a mode-`0600` regular file. The root-backed CLI login was then ended; a subsequent credential export was unavailable. The non-root operator login remains available for later separately authorized work.

## Next gate

A fresh user authorization is required before running mutation-free `prepare`. If authorized and successful, report only the exact private Seed-A plan filename and SHA-256, then stop. Seed-A execution requires its own later exact approval.
