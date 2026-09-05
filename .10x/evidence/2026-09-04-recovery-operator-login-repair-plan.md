Status: recorded
Created: 2026-09-04
Updated: 2026-09-04
Relates-To: .10x/tickets/2026-09-04-apply-and-prove-disaster-recovery.md

# Recovery operator remote-login repair plan

The user ratified exactly `signin:AuthorizeOAuth2Access` and `signin:CreateOAuth2Token`, scoped to `arn:aws:signin:us-west-1:734815189723:oauth2/public-client/remote`, after live `aws login --remote` failed because the operator lacked AWS's required OAuth permissions.

- Binary: `infra/recovery/recovery-operator-login-repair.tfplan`
- Binary SHA-256: `276b5ad36a1a6a13577a2b4b9a3e985c0e0ff1d0fe41340ec61221860f945f45`
- Exact text: `.10x/evidence/.storage/2026-09-04-databox-recovery-operator-login-repair.tfplan.txt`
- State lineage: `4303cf7d-c96f-55db-0ba3-a1ff1f492194`
- State serial: `3`
- Lock SHA-256: `02d2b020180bf03e77af58e54b0539ff0da8e5b4f06db21ff347be0cf092cfd3`

Current and embedded state lineage/serial and lockfile bytes match exactly. The plan was generated literally inside `infra/recovery` after tests and validation, with a clean Git tree, exact root identity, and no `tofu init`.

The only action is an in-place update to `aws_iam_user_policy.recovery_operator`: it retains `sts:AssumeRole` scoped to the exact backup role and adds only the two ratified sign-in actions scoped to the exact remote public client. Plan: 0 add, 1 change, 0 destroy. Role trust and all bucket resources are no-op.

Validation: 8 focused tests passed with `--no-cov`; Ruff, OpenTofu format/validate, and diff checks passed. No apply, login, credential, MFA, role assumption, service, backup, WAL, or restore operation occurred. The plan requires independent review and explicit approval before apply.
