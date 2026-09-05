Status: recorded
Created: 2026-09-04
Updated: 2026-09-04
Relates-To: .10x/tickets/2026-09-04-simplify-recovery-infrastructure-to-catalog-only.md, .10x/tickets/2026-09-04-apply-and-prove-disaster-recovery.md

# Catalog-only recovery OpenTofu plan

## Result

A fresh non-mutating catalog-only OpenTofu plan was generated with authenticated profile `databox-debug` in `us-west-1` and saved outside the repository at `/tmp/databox-catalog-only-recovery.tfplan`.

- Binary plan SHA-256: `9f01f222d146efa13ef66d13992b8bb9f190198a9caa1a9bca30d1d53fd91292`
- Exact non-secret text plan: `.10x/evidence/.storage/2026-09-04-databox-catalog-only-recovery.tfplan.txt`
- Text plan SHA-256: `f12b1ffca8cd4562099589673427a59537d4bab71f96649fa3d1d4757168e0b9`
- Actions: 7 create, 0 change, 0 destroy, 0 data reads.

No `tofu apply` ran and no AWS resource was created, changed, or destroyed.

## Exact inputs

- Account: `734815189723`
- Region/profile: `us-west-1` / `databox-debug`
- Catalog backup bucket: `databox-lake-catalog-backup`
- Initial bootstrap operator principal: `arn:aws:iam::734815189723:root`

The ignored runtime input file is `infra/recovery/recovery.auto.tfvars`; it contains no credentials and only the four inputs above.

## Exact resource inventory

- `aws_iam_role.catalog_backup`
- `aws_iam_role_policy.catalog_backup`
- `aws_s3_bucket.catalog_backup`
- `aws_s3_bucket_lifecycle_configuration.catalog_backup`
- `aws_s3_bucket_public_access_block.catalog_backup`
- `aws_s3_bucket_server_side_encryption_configuration.catalog_backup`
- `aws_s3_bucket_versioning.catalog_backup`

The plan contains no resource for the existing `databox-lake` primary bucket, no Iceberg recovery bucket, no replication configuration or role, no recovery-reader role, and no warehouse policy. The catalog bucket alone receives versioning, AES256 server-side encryption, public-access blocking, and 30-day noncurrent-version expiration. The backup role policy is limited to listing/location on that bucket and object get/put/delete within it.

## Root bootstrap boundary

The current AWS login identifies as the account root and is accepted only for the initial, separately reviewed bootstrap apply. The plan creates the least-privilege `databox-polaris-catalog-backup` role; pgBackRest runtime credentials must be short-lived credentials for that role, never root credentials. After any separately approved apply and role-access verification, the root CLI session must be logged out. Root trust can be replaced later when a non-root operator identity exists.

## Review and approval boundary

This plan is ready for independent review but is not approved for apply. Any infrastructure edit, input change, authentication-account change, or plan regeneration invalidates these hashes. `tofu apply` requires explicit user approval of this exact replacement plan after review. The rejected 18-create plan remains historical and must never be applied.

## Commands and limits

Observed successfully: authenticated STS identity, secure ignored tfvars rewrite, `tofu init -backend=false -input=false`, `tofu fmt -check`, `tofu validate`, `tofu plan -refresh=false -input=false`, exact text and JSON rendering, hashing, action enumeration, resource-address inspection, and diff checks.

No apply, service startup, volume mutation, S3 write, backup, WAL operation, or restore occurred. `-refresh=false` does not prove global bucket-name availability or detect remote drift. Actual package/runtime compatibility, bucket creation, role assumption, pgBackRest repository access, backup, WAL archival, and recovery remain unproven until separately approved live execution.
