Status: recorded
Created: 2026-09-04
Updated: 2026-09-04
Relates-To: .10x/tickets/2026-09-04-apply-and-prove-disaster-recovery.md

# Recovery operator MFA repair apply

## Authorization and preconditions

The user explicitly approved only `infra/recovery/recovery-operator-mfa-repair.tfplan`, SHA-256 `45a78d799032c227b1d525433515e2093b452be0f346ea4c2a6d14d9ae5bbc35`.

Immediately before apply, Git was clean; authenticated identity was exactly account root `arn:aws:iam::734815189723:root`; state was mode `0600`, lineage `4303cf7d-c96f-55db-0ba3-a1ff1f492194`, serial `2`; current and embedded state lineage/serial matched; and current and embedded lockfile SHA-256 matched `02d2b020180bf03e77af58e54b0539ff0da8e5b4f06db21ff347be0cf092cfd3`. No init, plan, refresh, regeneration, or configuration edit occurred.

## Apply result

From `infra/recovery`, exact command `tofu apply -input=false recovery-operator-mfa-repair.tfplan` completed: 2 added, 1 changed, 0 destroyed.

Live verification observed:

- IAM user `databox-recovery-operator` exists;
- the user has zero access keys and no login profile;
- its single inline policy allows only `sts:AssumeRole` on `arn:aws:iam::734815189723:role/databox-polaris-catalog-backup`;
- the backup role trusts exactly that user and requires `aws:MultiFactorAuthPresent=true`;
- catalog bucket versioning, AES256 encryption, all four public-access blocks, HTTPS-deny policy, 30-day noncurrent expiry, and seven-day incomplete-upload cleanup remain unchanged;
- state remains mode `0600`, lineage unchanged, serial advanced to `3`, SHA-256 `4e46ce5086816b7d364105372d95c35892cb3589603b5f0d2da45e093a87ecc1`;
- root remains authenticated for manual console/MFA setup.

## Manual next step

Using the AWS console as root, open IAM user `databox-recovery-operator`, enable console access with a human-managed password, require password reset if desired, and enroll an MFA device for that user. Do not create an access key. Passwords, MFA seeds, and recovery codes must not enter Git, OpenTofu state, logs, or evidence. Root must remain available until operator login and MFA-protected role assumption are proven.

## Limits

No password, login profile, MFA device, access key, role session, S3 object, Compose service, pgBackRest stanza, backup, WAL, volume, or restore operation was created or run in this step.
