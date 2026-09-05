Status: recorded
Created: 2026-09-04
Updated: 2026-09-04
Relates-To: .10x/tickets/2026-09-04-apply-and-prove-disaster-recovery.md

# Recovery OpenTofu plan

## Result

A non-mutating OpenTofu plan was generated with profile `databox-debug` in `us-west-1` and saved outside the repository at `/tmp/databox-recovery.tfplan`.

- Binary plan SHA-256: `7698bf7f60cd0d250d7e13c880265ec15663e26ff6e39b4cc6de7b2c79970922`
- Exact non-secret text plan: `.10x/evidence/.storage/2026-09-04-databox-recovery.tfplan.txt`
- Text plan SHA-256: `a003be1c19ba655607712c27cc7c2e428cc9929c09674676ef1d9c5d5aba75c0`
- Actions: 18 create, 0 change, 0 destroy, plus one deferred IAM policy-document read.

No `tofu apply` ran and no AWS resource was created, changed, or destroyed.

## Exact inputs

- Account: `734815189723`
- Region/profile: `us-west-1` / `databox-debug`
- Primary Iceberg bucket/prefix: `databox-lake` / `warehouse`
- Catalog backup bucket: `databox-lake-catalog-backup`
- Iceberg recovery bucket: `databox-lake-iceberg-recovery`
- Operator principal: `arn:aws:iam::734815189723:root`
- Routine writer principal: `arn:aws:iam::734815189723:role/DataboxPolarisS3Role`

The ignored runtime input file is `infra/recovery/recovery.auto.tfvars`; it contains no credentials. Bucket names passed S3-name validation.

## Planned resources

The plan creates two S3 buckets; versioning, AES256 default encryption, public-access blocks, and lifecycle rules for both; an Iceberg recovery bucket policy; three IAM roles and their inline policies; and one replication configuration on the existing `databox-lake` primary bucket.

## Review blockers and risks

### Blocker: primary source bucket versioning is not enabled

Read-only `get-bucket-versioning` returned no status for `databox-lake`. S3 replication requires versioning on the source bucket, but this plan does not enable or manage source-bucket versioning. Applying this exact plan is expected to fail when creating the replication configuration. Infrastructure code must be repaired and a new exact plan generated; this plan must not be approved for apply.

### Primary replication configuration

Read-only `get-bucket-replication` returned `ReplicationConfigurationNotFoundError`, so there is no current replication configuration to overwrite at review time. The plan nevertheless manages `aws_s3_bucket_replication_configuration.iceberg` as the complete replication configuration for the existing primary bucket. If any rule is added outside OpenTofu before apply, this resource would replace the bucket's complete configuration rather than merge it. Recheck immediately before any eventual apply.

### Root operator trust

Both operator-assumable recovery roles trust `arn:aws:iam::734815189723:root`. This is the exact current caller input explicitly selected for plan generation, but it is broader and more privileged than a dedicated operator principal. It must be explicitly accepted or replaced before apply.

### Plan freshness

The plan used `-refresh=false`. It does not prove global bucket-name availability or detect infrastructure changes after generation. Any repair or input change invalidates both hashes and requires a fresh plan and review.

## Commands and limits

Observed successfully: authenticated STS identity, validated derived inputs, `tofu init -backend=false`, formatting, `tofu validate`, `tofu plan -refresh=false`, exact text rendering, hashing, action enumeration, and read-only primary-bucket replication/versioning inspection. The first formatting check stopped on the ignored generated tfvars; the file was formatted and all subsequent checks passed.

No apply, backup, WAL, restore, service startup, volume mutation, or destructive AWS operation occurred.
