Status: done
Created: 2026-09-10
Updated: 2026-09-10

# S3 warehouse versioning: retention and recovery limits

> Record recovery (2026-09-14): restored from the verified private snapshot on `feature/warehouse-file-recovery`, based on merged main `8321475dda7b3a041e8dd8efe668c923cf723fb5`. This preserves the captured contract, not new implementation or AWS authority.
> Original working-artifact SHA-256 (NOT this recovered/redacted text): `034eca0322185a55d2fdbabd665e4f8d9d5be7f344d380dd69407b91ea96745c`; source revision `027af8b4271d60ffc193967d092b5d2497af13ad` plus the captured uncommitted variant.
> Exact private original: `~/Private/databox/recovery-evidence/2026-09-11T235551Z-05aef1141954/`; `manifest.json` entry `source_kind=uncommitted-working-tree`, `source_path=.10x/research/2026-09-10-s3-warehouse-versioning-semantics.md`. Deployment identifiers use the approved publication placeholders; generic principal labels are retained.

## Question

What precisely does the requested 30-day S3 version history protect, and what must be inspected before configuring Databox's existing warehouse bucket?

## Sources and methods

Read-only repository inspection on 2026-09-10 covered `infra/recovery/{main,variables,versions}.tf`, `tests/platform/test_recovery_infrastructure.py`, `docs/runbook.md`, the warehouse settings/destination, the protected integration workflow, recovery decisions/specifications, and related active, done, and cancelled tickets. No AWS API, authentication, OpenTofu workflow, test, or warehouse operation ran.

Official AWS pages fetched on 2026-09-10:

1. https://docs.aws.amazon.com/AmazonS3/latest/userguide/Versioning.html
2. https://docs.aws.amazon.com/AmazonS3/latest/userguide/lifecycle-expire-general-considerations.html
3. https://docs.aws.amazon.com/AmazonS3/latest/userguide/intro-lifecycle-rules.html
4. https://docs.aws.amazon.com/AmazonS3/latest/userguide/example-bucket-policies.html
5. https://docs.aws.amazon.com/AmazonS3/latest/userguide/manage-versioning-examples.html

Prior investigation: `.10x/research/2026-09-04-polaris-iceberg-disaster-recovery.md`. Its former 45-day replica and continuous five-minute catalog RPO recommendations are historical, not authority for this change.

## Findings

- Versioning is bucket-wide: AWS says its state applies to “all (never some) of the objects in that bucket.” Once enabled, it can be suspended but cannot return to unversioned. Existing objects remain unchanged with version ID `null`; enabling it does not reconstruct earlier lost versions. [1]
- Ordinary DELETE creates a delete marker; PUT over an existing key creates another version. A version-specific DELETE can permanently remove a version. Each stored version is a full object, not a delta, and incurs normal storage charges. [1]
- `NoncurrentVersionExpiration` permanently deletes old versions. Its age is measured from becoming noncurrent, not original object creation, catalog backup time, or enabling the rule. AWS computes eligibility from the successor version timestamp, rounds to the next midnight UTC, and processes expiration asynchronously. [2,3]
- Lifecycle rules affect existing and future eligible objects. Already-noncurrent versions older than 30 days could become immediately eligible upon applying a new rule. Existing rules therefore require inspection, not blind replacement. [2]
- An empty lifecycle filter applies across the bucket. Prefix filters can narrow expiration, but not versioning itself. [3]
- A bucket policy cannot prevent S3 Lifecycle deletions: even a policy denying all actions does not disable configured lifecycle behavior. Denying only `s3:DeleteObjectVersion` is not immutable retention or protection against an actor able to change lifecycle, versioning, or the policy itself. [2,4]
- AWS recommends waiting 15 minutes after first enabling versioning before any object PUT/DELETE; propagation can cause transient `NoSuchKey` responses for newly written objects. Writer coordination is a rollout prerequisite, not authority to stop production automatically. [5]
- Local configuration selects the warehouse with `DATABOX_AWS_S3_BUCKET` and normally `DATABOX_ICEBERG_WAREHOUSE_PREFIX=warehouse`. The protected workflow also uses the configured bucket under `integration/<run>/<attempt>/<source>/warehouse`. Bucket-wide versioning affects these prefixes too; live inventory must establish whether other owners/data exist.
- OpenTofu currently manages only the catalog-backup bucket and catalog operator/role. There is no primary-warehouse configuration resource. Existing tests explicitly forbid all primary/warehouse resource inputs and object-version permissions; a future change must narrow these to preserve catalog-role isolation and the no-replica boundary, not discard protective assertions wholesale.
- `.10x/tickets/2026-09-05-establish-primary-warehouse-session-credentials.md` already owns the unfinished effective-policy audit for `databox-lake-user`. This work must reuse it rather than invent a second full IAM audit.

## Conclusions and limits

The user selected same-bucket versioning, 30-day noncurrent expiration, and an explicit routine-writer version-delete denial. These are intended behavior, not evidence of live configuration. See `.10x/decisions/version-iceberg-warehouse-objects-for-30-days.md` and `.10x/tickets/2026-09-10-protect-iceberg-warehouse-object-versions.md`.

Read-only inspection must establish bucket/account/region identity, lifecycle/policy ownership, current version state, relevant writer privileges, and cost/expiration exposure. Broader control-plane denies, restore selection/destination/credentials, and live mutation are not ratified by these technical findings. Versioning is neither an independent regional/account backup nor proof that a complete Iceberg table can be restored. A table requires its catalog pointer and every referenced metadata, manifest, data, and applicable delete file; restore proof remains separate.
