Status: recorded
Created: 2026-09-04
Updated: 2026-09-04
Relates-To: .10x/tickets/done/2026-09-04-apply-and-prove-disaster-recovery.md

# Recovery operator live role proof

> Publication redaction (2026-09-12): deployment account/bucket literals are replaced by labeled placeholders; generic principal labels are retained. This historical record is not a fresh approval or an executable plan. Original conclusions and verification limits still apply.
> Source revision: `027af8b4271d60ffc193967d092b5d2497af13ad`. Original-artifact SHA-256 (NOT this redacted text): `f818b002f2dc2f04e49ea3988d3cbd760623334d39304317f1e88fd8a0ff97df`.
> Exact private original: `~/Private/databox/recovery-evidence/2026-09-11T235551Z-05aef1141954/`; `manifest.json` entry with `source_kind=committed-head` and `source_path` equal to this public path. Any preexisting plan/export hashes below identify original artifacts, not this changed counterpart.


## What was observed

The manually provisioned `databox-recovery-operator` successfully authenticated through `aws login --remote`. `aws sts get-caller-identity --profile databox-recovery-operator` returned exact IAM user ARN `arn:aws:iam::<REDACTED_ACCOUNT_ID>:user/databox-recovery-operator`.

The local backup-role profile uses that source profile, role ARN `arn:aws:iam::<REDACTED_ACCOUNT_ID>:role/databox-polaris-catalog-backup`, TOTP serial `arn:aws:iam::<REDACTED_ACCOUNT_ID>:mfa/proton-pass-auth-app`, and region `us-west-1`. The human supplied a TOTP code interactively; no MFA code or credential was recorded. The resulting identity was `arn:aws:sts::<REDACTED_ACCOUNT_ID>:assumed-role/databox-polaris-catalog-backup/<session>`.

Using that role, read-only checks observed the backup bucket in `us-west-1` and successfully listed its empty object namespace. Account-wide `s3:ListAllMyBuckets` failed with `AccessDenied`, as required by the bucket-scoped policy.

`aws logout --profile databox-debug` removed the cached root login credentials. A subsequent root-profile STS call failed while the operator-assumed backup role remained usable. The human must separately close any root AWS Console browser session.

## What this supports

This proves the non-root operator can complete remote console-derived CLI login, satisfy MFA-protected `AssumeRole`, and access the intended backup bucket without account-wide bucket enumeration. It also proves the root CLI login cache was removed.

## Limits

No credential values or MFA codes were captured. Cached access tokens already loaded by another local process can remain usable for up to 15 minutes. This does not prove the human closed the root browser session, state-file backup, S3 write/delete behavior, pgBackRest repository initialization, WAL archival, physical backup, restore, or PITR.
