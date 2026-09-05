Status: recorded
Created: 2026-09-04
Updated: 2026-09-04
Relates-To: .10x/tickets/2026-09-04-simplify-recovery-infrastructure-to-catalog-only.md, .10x/tickets/2026-09-04-apply-and-prove-disaster-recovery.md

# Catalog-only TLS-enforced recovery OpenTofu plan

## Result

A fresh non-mutating plan was generated after the catalog-backup bucket TLS-policy repair using authenticated profile `databox-debug` in account `734815189723`, region `us-west-1`.

- Binary plan: `/tmp/databox-catalog-only-tls.tfplan`
- Binary SHA-256: `4656b197fd1039d4972c614e828ad0be92128fec6c6f83d4a6a6fd88abc98837`
- Exact non-secret text plan: `.10x/evidence/.storage/2026-09-04-databox-catalog-only-tls.tfplan.txt`
- Text SHA-256: `b953de92e2cb80be7d677856cb3c5f9f38345a61f5fe1c0fbe41e4fe140af9fb`
- Actions: 8 create, 0 change, 0 destroy, plus one deferred local IAM policy-document read.

No `tofu apply` ran and no AWS resource was created, changed, or destroyed.

## Exact inputs

- AWS profile/account/region: `databox-debug` / `734815189723` / `us-west-1`
- Catalog backup bucket: `databox-lake-catalog-backup`
- Bootstrap operator principal: `arn:aws:iam::734815189723:root`

The ignored `infra/recovery/recovery.auto.tfvars` contains only those non-secret inputs.

## Exact managed resource inventory

- `aws_iam_role.catalog_backup`
- `aws_iam_role_policy.catalog_backup`
- `aws_s3_bucket.catalog_backup`
- `aws_s3_bucket_lifecycle_configuration.catalog_backup`
- `aws_s3_bucket_policy.catalog_backup`
- `aws_s3_bucket_public_access_block.catalog_backup`
- `aws_s3_bucket_server_side_encryption_configuration.catalog_backup`
- `aws_s3_bucket_versioning.catalog_backup`

`data.aws_iam_policy_document.operator_assume` resolved locally during planning. `data.aws_iam_policy_document.catalog_backup` is deferred until the new bucket ARN is known during apply and does not contact or create a remote resource.

## Security and scope review

The bucket policy denies all `s3:*` operations on both bucket and object ARNs when `aws:SecureTransport` is `false`. The catalog bucket also receives AES256 server-side encryption, public-access blocking, versioning, 30-day noncurrent-version expiration, and seven-day incomplete-upload cleanup. pgBackRest client-side encryption remains separately required by runtime configuration.

The role policy is limited to bucket location/list and object get/put/delete within this single catalog-backup bucket. The plan contains no existing-primary-bucket action, Iceberg recovery bucket, source versioning, replication, recovery reader, warehouse policy, change, or destroy.

Root is accepted only for the separately approved bootstrap apply. Runtime backups must assume `databox-polaris-catalog-backup` with short-lived credentials; root credentials must never enter Compose or pgBackRest. After role-access verification, the root CLI session must be logged out.

## Approval boundary and limits

This plan is not approved for apply. Any infrastructure edit, input/account/profile change, authentication change, or regeneration invalidates both hashes. Only explicit user approval of this exact plan after independent review may authorize `tofu apply /tmp/databox-catalog-only-tls.tfplan`.

Observed successfully: STS preflight, `tofu init -backend=false -input=false`, `tofu fmt -check`, `tofu validate`, `tofu plan -refresh=false -input=false`, exact text/JSON rendering, hashes, resource/action inspection, and no-primary/no-Iceberg/no-replication checks.

No apply, service, volume, S3 write, backup, WAL operation, or restore occurred. `-refresh=false` does not prove bucket-name availability or remote drift. Runtime role assumption, bucket controls, pgBackRest access, backup, WAL archival, and recovery remain unproven.
