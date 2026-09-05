Status: recorded
Created: 2026-09-04
Updated: 2026-09-04
Relates-To: .10x/tickets/2026-09-04-apply-and-prove-disaster-recovery.md

# Recovery operator live role proof

## What was observed

The manually provisioned `databox-recovery-operator` successfully authenticated through `aws login --remote`. `aws sts get-caller-identity --profile databox-recovery-operator` returned exact IAM user ARN `arn:aws:iam::734815189723:user/databox-recovery-operator`.

The local backup-role profile uses that source profile, role ARN `arn:aws:iam::734815189723:role/databox-polaris-catalog-backup`, TOTP serial `arn:aws:iam::734815189723:mfa/proton-pass-auth-app`, and region `us-west-1`. The human supplied a TOTP code interactively; no MFA code or credential was recorded. The resulting identity was `arn:aws:sts::734815189723:assumed-role/databox-polaris-catalog-backup/<session>`.

Using that role, read-only checks observed the backup bucket in `us-west-1` and successfully listed its empty object namespace. Account-wide `s3:ListAllMyBuckets` failed with `AccessDenied`, as required by the bucket-scoped policy.

`aws logout --profile databox-debug` removed the cached root login credentials. A subsequent root-profile STS call failed while the operator-assumed backup role remained usable. The human must separately close any root AWS Console browser session.

## What this supports

This proves the non-root operator can complete remote console-derived CLI login, satisfy MFA-protected `AssumeRole`, and access the intended backup bucket without account-wide bucket enumeration. It also proves the root CLI login cache was removed.

## Limits

No credential values or MFA codes were captured. Cached access tokens already loaded by another local process can remain usable for up to 15 minutes. This does not prove the human closed the root browser session, state-file backup, S3 write/delete behavior, pgBackRest repository initialization, WAL archival, physical backup, restore, or PITR.
