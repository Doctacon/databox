Status: recorded
Created: 2026-09-04
Updated: 2026-09-04
Target: .10x/evidence/.storage/2026-09-04-databox-recovery-operator-repair.tfplan.txt
Verdict: concerns

# Recovery operator repair plan review

## Finding

### P1 — MFA is documented but not enforced

The planned backup-role trust allows the exact operator user to call `sts:AssumeRole` but has no `aws:MultiFactorAuthPresent` condition. The runbook requires manual MFA enrollment, yet IAM would still accept an operator session without MFA. Existing tests do not require the condition.

Add a `Bool` trust-policy condition requiring `aws:MultiFactorAuthPresent = true`, add focused coverage, generate a new normal-refresh state-aware plan, and independently review its exact hash. Do not apply plan hash `677f9ce7a6b5ee499f8bebb71b96115d8e443a31b1cbcf6f6f4eb2767fc96bcc`.

## Authentication path

AWS documents MFA-protected role assumption through a trust-policy condition plus `SerialNumber` and `TokenCode`. The intended console-only operator path should use `aws login` for the IAM-user source profile and an AWS CLI role profile configured with `role_arn`, `source_profile`, and the operator's `mfa_serial`; the explicit AssumeRole MFA prompt supplies the required context. This must be proven live before root logout.

Sources:

- https://docs.aws.amazon.com/STS/latest/APIReference/API_AssumeRole.html
- https://docs.aws.amazon.com/IAM/latest/UserGuide/id_credentials_mfa_configure-api-require.html
- https://docs.aws.amazon.com/cli/latest/userguide/cli-configure-role.html
- https://docs.aws.amazon.com/cli/latest/userguide/cli-configure-sign-in.html

## Verdict

Do not apply the reviewed plan. Enforce MFA, regenerate, re-review, and obtain explicit approval.

## Residual risk

Console password and MFA enrollment remain intentional manual configuration outside OpenTofu. Root must remain active through apply, manual setup, operator login, MFA-protected role assumption, and verification. A partial trust update may temporarily leave the backup role unusable. Live compatibility between console-login-derived temporary source credentials and MFA-prompted role assumption remains to be proven.
