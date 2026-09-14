Status: recorded
Created: 2026-09-04
Updated: 2026-09-04
Relates-To: .10x/tickets/2026-09-04-simplify-recovery-infrastructure-to-catalog-only.md

# Catalog-only final OpenTofu plan

> Publication redaction (2026-09-12): deployment account/bucket literals are replaced by labeled placeholders; generic principal labels are retained. This historical record is not a fresh approval or an executable plan. Original conclusions and verification limits still apply.
> Source revision: `027af8b4271d60ffc193967d092b5d2497af13ad`. Original-artifact SHA-256 (NOT this redacted text): `87d15b0d4ea2b4c2cc610679c4a10332e08fcc71d938baee185ba79bb4220f36`.
> Exact private original: `~/Private/databox/recovery-evidence/2026-09-11T235551Z-05aef1141954/`; `manifest.json` entry with `source_kind=committed-head` and `source_path` equal to this public path. Any preexisting plan/export hashes below identify original artifacts, not this changed counterpart.


## Result

After repairing multipart-upload authority, rollout ordering, and local-state ownership, authenticated profile `databox-debug` generated a fresh non-mutating plan in account `<REDACTED_ACCOUNT_ID>`, region `us-west-1`.

- Binary plan: `/tmp/databox-catalog-only-final.tfplan`
- Binary SHA-256: `77cf23e243859dac24974be21adfb7f5bdf94bb6ec8168cf70039ddda3b69212`
- Exact text: `.10x/evidence/.storage/2026-09-04-databox-catalog-only-final.tfplan.txt`
- Text SHA-256: `b953de92e2cb80be7d677856cb3c5f9f38345a61f5fe1c0fbe41e4fe140af9fb`
- Actions: 8 create, 0 change, 0 destroy, plus one deferred local policy-document read.

No `tofu apply` ran and no AWS resource was created, changed, or destroyed.

## Repair content

The catalog-backup role now includes object-scoped `s3:AbortMultipartUpload` with get, put, and delete authority on only the catalog bucket object ARN. It has no `GetObjectVersion` or `DeleteObjectVersion` authority. The plan continues to contain one catalog bucket, its versioning, AES256 encryption, public-access block, TLS-deny bucket policy, 30-day noncurrent lifecycle, backup role, and inline role policy; it contains no primary warehouse, Iceberg, or replication resource.

OpenTofu state is local and operator-owned at `infra/recovery/terraform.tfstate`. Apply/import must run from `infra/recovery`; state is ignored by Git, protected by FileVault and normal encrypted machine backup, and excluded from project cleanup. Loss requires backup restoration or reviewed import before another plan.

## Approval boundary

The plan is not approved for apply. It requires independent review and explicit user approval of binary hash `77cf23e243859dac24974be21adfb7f5bdf94bb6ec8168cf70039ddda3b69212`. Any code, input, account, profile, or plan change invalidates the hash. All earlier plans remain rejected.

No service, volume, S3 write, backup, WAL operation, restore, or destructive action occurred. `-refresh=false` does not prove bucket-name availability or remote drift. Provisioning and first real backup/WAL proof must precede restore automation.
