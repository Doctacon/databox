Status: read-only audit complete; root-only retention-control boundary selected
Created: 2026-09-14

# Root-backed writer permission and warehouse control audit

## Authority and handling

After cancelling the unapplied stage-2 operator grant, the user explicitly chose the root-backed profile for completing warehouse recovery work and deferred deployer-role/IAM cleanup. The user performed a fresh remote login. This audit verified the exact expected account-root identity and made read-only IAM, S3, CloudFormation and CloudTrail calls. It performed no IAM, S3, state, object or service mutation. Raw account/bucket identifiers, policy names/ARNs/documents, role names/trust documents and event principals were kept private.

At audit time, the root CLI login cache remained active for the user-approved recovery session to avoid another immediate login; no mutation used it before exact policy/risk review and saved-plan approval. After the later one-time rollout and final read-back, `aws logout` succeeded for the root-backed CLI profile.

## Writer effective-policy findings

Fresh IAM listings explicitly completed without truncation:

- No permissions boundary.
- No inline policies.
- No groups.
- Exactly two attached AWS-managed policies; both current default documents were read.

Sanitized policy shape:

1. One unconditional Allow statement grants `s3:*` and `s3-object-lambda:*` on `*`.
2. A broad power-user-style Allow uses NotAction exclusions for IAM, Organizations and Account actions on `*`; a second statement grants a small set of account/organization reads and service-linked-role operations.
3. Neither managed policy contains a Deny.

The routine writer therefore directly has wildcard-resource permission to:

- permanently delete object versions;
- enable/suspend versioning;
- create/replace/delete lifecycle configuration;
- create/replace/delete the bucket policy;
- list/read versions and restore objects;
- call `sts:AssumeRole` on wildcard resources.

It does not obtain general `iam:*` or `iam:PassRole` from these documents. Organization, session, endpoint and resource-policy restrictions were not inferred absent exact evidence.

## Role bypass

The same-account role listing completed without truncation: eight roles total. Exactly one role directly trusts the writer user without a condition. Its attached and inline policy listings also completed; that role allows all five relevant S3 bypass/control actions checked: DeleteObjectVersion, PutBucketVersioning, PutLifecycleConfiguration, PutBucketPolicy and DeleteBucketPolicy.

The writer's wildcard AssumeRole identity permission also leaves cross-account trusting roles unenumerable from this account. Therefore a bucket-policy Deny matching only the writer-user ARN is not an effective recovery boundary: the known same-account assumed role already bypasses it, and unknown cross-account roles may do the same.

## Refreshed warehouse findings

The warehouse bucket remains:

- in the expected region and unversioned, with MFA Delete unset;
- without lifecycle, bucket policy, Object Lock, replication or tags;
- with all four public-access-block flags enabled;
- AES256 encrypted and BucketOwnerEnforced;
- owner-only by ACL, without server access logging or event notifications;
- three top-level prefixes and no root-level objects in the completed bounded listing.

No matching CloudFormation-managed resource was found. The exact bucket identifier occurs in four tracked repository files. Recent available bucket-management history contains only same-account actors (account root plus one other same-account principal) for bucket creation/encryption events. These are useful ownership signals but not proof that every prefix has one operational owner.

## Selected protection boundary

The previously agreed exact-writer `s3:DeleteObjectVersion` Deny is bypassable and cannot support a strong protection claim. The user selected the root-only **retention-control** boundary:

- Deny every non-root principal `s3:DeleteObjectVersion` on warehouse object versions.
- Deny every non-root principal mutation/removal of bucket versioning, lifecycle configuration and bucket policy.
- Preserve ordinary object writes/deletes and add no Allow.
- Defer non-root deployment/recovery-role design until after the recovery goal.

This closes the direct writer, known assumed role, future same-account role and unknown cross-account role-session paths for those five actions. It does not make recovery itself root-only: a non-root principal retaining version-read plus object-write access can promote an old version as a new current version. S3 Lifecycle and account root remain intentional permanent-deletion paths. Bucket deletion, Object Lock, unrelated bucket settings, current-object corruption, version storms, storage cost and root/account compromise are outside the narrow guarantee.

The user explicitly accepted the bucket-wide three-prefix controls, including the unclassified prefix's 30-day version-retention cost and root-only control administration. The exact reviewed plan was applied once; [apply evidence](warehouse-object-protection-apply.md) records Enabled versioning, exact policy/lifecycle read-back, preserved unrelated settings and the completed propagation hold. Negative enforcement tests and coherent Iceberg recovery proof remain separate gates.
