Status: blocked
Created: 2026-09-04
Updated: 2026-09-04
Relates-To: .10x/tickets/2026-09-04-apply-and-prove-disaster-recovery.md

# Recovery operator MFA repair apply attempt

## Authorized plan

The user explicitly approved applying only `/tmp/databox-recovery-operator-mfa-repair.tfplan`, SHA-256 `a65f87e7a160e26ffd9932e48e71431c7c7158ca8b3c0aab49d27187eaf7fcc4`.

Immediately before execution, the worktree was clean; the binary hash matched; `infra/recovery/terraform.tfstate` existed with mode `0600`; and profile `databox-debug` authenticated exactly as `arn:aws:iam::734815189723:root` in account `734815189723`.

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
