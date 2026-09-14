Status: blocked
Created: 2026-09-04
Updated: 2026-09-04
Relates-To: .10x/tickets/done/2026-09-04-apply-and-prove-disaster-recovery.md

# Recovery operator MFA repair apply attempt

> Publication redaction (2026-09-12): deployment account/bucket literals are replaced by labeled placeholders; generic principal labels are retained. This historical record is not a fresh approval or an executable plan. Original conclusions and verification limits still apply.
> Source revision: `027af8b4271d60ffc193967d092b5d2497af13ad`. Original-artifact SHA-256 (NOT this redacted text): `ed49dc742c0e588f3f2e1c243adf7d25baab414d1ebd1219a1197b744b3544d6`.
> Exact private original: `~/Private/databox/recovery-evidence/2026-09-11T235551Z-05aef1141954/`; `manifest.json` entry with `source_kind=committed-head` and `source_path` equal to this public path. Any preexisting plan/export hashes below identify original artifacts, not this changed counterpart.


## Authorized plan

The user explicitly approved applying only `/tmp/databox-recovery-operator-mfa-repair.tfplan`, SHA-256 `a65f87e7a160e26ffd9932e48e71431c7c7158ca8b3c0aab49d27187eaf7fcc4`.

Immediately before execution, the worktree was clean; the binary hash matched; `infra/recovery/terraform.tfstate` existed with mode `0600`; and profile `databox-debug` authenticated exactly as `arn:aws:iam::<REDACTED_ACCOUNT_ID>:root` in account `<REDACTED_ACCOUNT_ID>`.

## Result

From `infra/recovery/`, the exact authorized command

`tofu apply -input=false /tmp/databox-recovery-operator-mfa-repair.tfplan`

failed before mutation. OpenTofu rejected the saved plan because its dependency selections did not match the current lock/configuration and its prior state lineage did not match the actual local state. No replan or alternate apply was attempted.

Post-failure verification observed:

- state SHA-256 remained `0794afe7339895a6b59b87c029c800775ea041cebb436fc63839304b0dbd5ab7`;
- state remained mode `0600` with the same eight managed remote resources plus two local data entries;
- IAM user `databox-recovery-operator` remained absent;
- root STS remained active as the exact expected ARN;
- the Git worktree remained clean before this evidence record.

## Required repair

The approved binary is unusable and MUST NOT be retried. Generate a normal-refresh plan from the actual `infra/recovery` working directory using the current `.terraform.lock.hcl` and actual local `terraform.tfstate`, prove matching state lineage/dependency selections, record a new hash, independently review it, and obtain explicit approval before any further apply.

## Limits

No AWS resource, IAM trust, bucket, state, credential, password, MFA device, object, backup, WAL, service, volume, or restore was created, changed, or destroyed. Root intentionally remains logged in for a future reviewed repair.
