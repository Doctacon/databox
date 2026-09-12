Status: recorded
Created: 2026-09-04
Updated: 2026-09-04
Relates-To: .10x/tickets/done/2026-09-04-apply-and-prove-disaster-recovery.md

# Recovery operator remote-login repair apply

> Publication redaction (2026-09-12): deployment account/bucket literals are replaced by labeled placeholders; generic principal labels are retained. This historical record is not a fresh approval or an executable plan. Original conclusions and verification limits still apply.
> Source revision: `027af8b4271d60ffc193967d092b5d2497af13ad`. Original-artifact SHA-256 (NOT this redacted text): `4dbdadf8d94cb85806741b9e65593084c319e7cee8160f357da3567c032c4c26`.
> Exact private original: `~/Private/databox/recovery-evidence/2026-09-11T235551Z-05aef1141954/`; `manifest.json` entry with `source_kind=committed-head` and `source_path` equal to this public path. Any preexisting plan/export hashes below identify original artifacts, not this changed counterpart.


The user explicitly approved only `infra/recovery/recovery-operator-login-repair.tfplan`, SHA-256 `276b5ad36a1a6a13577a2b4b9a3e985c0e0ff1d0fe41340ec61221860f945f45`.

Before apply, Git was clean; state mode was `0600`; current and embedded state lineage `4303cf7d-c96f-55db-0ba3-a1ff1f492194` and serial `3` matched; current and embedded lock SHA-256 `02d2b020180bf03e77af58e54b0539ff0da8e5b4f06db21ff347be0cf092cfd3` matched; and `databox-debug` authenticated exactly as root in account `<REDACTED_ACCOUNT_ID>`. No init, plan, refresh, regeneration, or configuration edit ran.

From literal directory `infra/recovery`, `tofu apply -input=false recovery-operator-login-repair.tfplan` succeeded: 0 added, 1 changed, 0 destroyed. The sole mutation was `aws_iam_user_policy.recovery_operator`; the approved plan contained no role or bucket action.

Live IAM verification proves the operator policy contains exactly:

- `sts:AssumeRole` on `arn:aws:iam::<REDACTED_ACCOUNT_ID>:role/databox-polaris-catalog-backup`;
- `signin:AuthorizeOAuth2Access` and `signin:CreateOAuth2Token` on `arn:aws:signin:us-west-1:<REDACTED_ACCOUNT_ID>:oauth2/public-client/remote`.

The backup-role trust remains the exact operator ARN with `aws:MultiFactorAuthPresent=true`. Root remains authenticated. State lineage remains `4303cf7d-c96f-55db-0ba3-a1ff1f492194`, serial advanced to `4`, mode remains `0600`, and state SHA-256 is `2bf4b47d79eb374ebb25963547bb0345323cf229508f85d2ac110fa7a76b6ac4`.

No login, credential issuance, MFA mutation, role assumption, S3 operation, service, backup, WAL, volume, or restore operation ran. Next, the human must retry `aws login --remote --profile databox-recovery-operator --region us-west-1` in the operator-authenticated private browser. Root must remain available until operator login and MFA-protected role assumption are proven.
