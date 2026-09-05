Status: recorded
Created: 2026-09-04
Updated: 2026-09-04
Relates-To: .10x/tickets/2026-09-04-apply-and-prove-disaster-recovery.md

# Recovery operator MFA repair plan

A normal-refresh, state-aware OpenTofu plan was generated after requiring MFA on the human operator's `AssumeRole` request.

- Binary: `/tmp/databox-recovery-operator-mfa-repair.tfplan`
- Binary SHA-256: `a65f87e7a160e26ffd9932e48e71431c7c7158ca8b3c0aab49d27187eaf7fcc4`
- Exact text: `.10x/evidence/.storage/2026-09-04-databox-recovery-operator-mfa-repair.tfplan.txt`
- Text SHA-256: `ac69ca32d2e7a589d59b7bb5141de952996e80045f63d7850a78d7991a122365`
- Actions: 2 create, 1 in-place update, 0 destroy; seven existing bucket/role resources are no-op and the trust document is a deferred local read.

The plan creates console-only IAM user `databox-recovery-operator` and its policy allowing only `sts:AssumeRole` on `databox-polaris-catalog-backup`. It updates that role to trust the exact user only when `aws:MultiFactorAuthPresent=true`. It creates no access key, login profile, password, or MFA resource and changes no bucket.

The human supplies MFA during `AssumeRole`; pgBackRest receives only the resulting short-lived role credentials and never receives MFA data.

Validation: OpenTofu format/validate, 25 focused tests, Ruff, and diff checks passed. No apply, user/password/MFA creation, credential issuance, backup, WAL, service, volume, or restore occurred. Plan is not approved pending independent review and explicit user approval; prior repair hash `677f9ce7a6b5ee499f8bebb71b96115d8e443a31b1cbcf6f6f4eb2767fc96bcc` is invalid.
