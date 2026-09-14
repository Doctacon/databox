Status: superseded
Created: 2026-09-04
Updated: 2026-09-04

# Protect Polaris and Iceberg through separate same-account AWS recovery buckets

## Context

Databox makes dlt-managed Iceberg tables on AWS S3 authoritative while a local Apache Polaris service stores catalog state in PostgreSQL. The current named Docker volume is not an off-host backup. S3 Iceberg files alone cannot reconstruct complete Polaris realms, registrations, principals, roles, and grants, while PostgreSQL alone cannot restore missing Iceberg metadata or data objects.

The project avoids always-on infrastructure and prefers open-source components. It already uses AWS S3 as the accepted Iceberg object store. The user requires a five-minute catalog RPO while Polaris runs, a 60-minute catalog RTO, 30 days of catalog PITR, and 45 days of recoverable Iceberg object history.

## Decision

Databox will use open-source pgBackRest for encrypted PostgreSQL physical backups and continuous WAL archiving. pgBackRest will obtain renewable short-lived AWS credentials through a credential process and write to a dedicated backup bucket.

Iceberg warehouse objects will receive a non-destructive recovery copy in a second dedicated bucket with 45 days of recoverable history. The catalog backup bucket and Iceberg recovery bucket will be separate from each other and from the primary warehouse bucket, but will remain in the same AWS account and `us-west-1` region. Normal Iceberg writers must not have backup deletion authority.

OpenTofu will declaratively manage buckets, versioning/retention controls, encryption, public-access blocking, replication, and least-privilege IAM boundaries. The first execution phase will produce tested automation and a reviewable plan only. It MUST NOT run `tofu apply` or mutate AWS. Live provisioning and the first timed recovery drill require separate explicit authorization after plan review.

The recovery design MUST treat PostgreSQL and Iceberg objects as one consistency boundary: a catalog restored to time T must retain access to every object referenced at T. A 60-minute RTO remains an objective, not a proven result, until a timed live drill records evidence.

## Alternatives considered

- **Self-hosted MinIO on a separate machine:** strongest fit with open-source and failure-domain principles, but rejected for this phase because it adds another always-on system and operating burden.
- **Local NAS:** rejected because its credential, geographic, and availability boundaries are less clear than the selected AWS path.
- **Same Docker host or another local volume:** rejected because it does not survive host loss.
- **Logical `pg_dump` only:** rejected because it cannot provide WAL-based PITR; retained only as a secondary recovery artifact.
- **AWS CLI-only provisioning:** rejected because imperative scripts provide weaker review, state tracking, and drift detection than OpenTofu.
- **Separate AWS account or region:** recommended for stronger blast-radius isolation but explicitly declined in favor of same-account, same-region simplicity.
- **Long-lived AWS access keys:** rejected; renewable short-lived credentials are required.

## Consequences

Databox gains reviewable disaster-recovery automation, bounded catalog data loss, retained Iceberg object history, and a reproducible restore procedure without proprietary backup software. OpenTofu and pgBackRest become maintained operational dependencies.

Same-account, same-region backups remain exposed to account-wide compromise and regional failure. Separate IAM and bucket deletion boundaries mitigate only narrower failures. AWS remains a managed dependency; the migration path is to point pgBackRest and object-copy automation at S3-compatible MinIO without changing the backup/recovery contracts.

Backup success will not prove recovery. Regular isolated restore drills, table-pointer validation, and timed evidence are continuing obligations. Any future Iceberg snapshot expiration or orphan cleanup policy must preserve the 45-day recovery contract and the PostgreSQL PITR consistency invariant.
