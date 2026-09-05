Status: active
Created: 2026-09-04
Updated: 2026-09-04

# Back up the Polaris catalog and rebuild the Iceberg warehouse from sources

## Context

The initial recovery architecture protected two independent planes: pgBackRest physical backup and WAL for the Polaris PostgreSQL catalog, plus continuous S3 replication into a second recovery bucket for Iceberg warehouse objects. During review of the first exact OpenTofu plan, the user clarified that they had understood the startup-driven pgBackRest cadence as covering the warehouse too. Continuous S3 replication would instead require versioning on the primary bucket and approximately duplicate warehouse storage.

Databox is a local, source-driven analytics project. Its normal full-refresh path already rebuilds registered Iceberg tables from canonical source definitions. Iceberg snapshots provide logical table rollback while referenced objects remain in the primary bucket, but they are not independent disaster-recovery copies.

## Decision

Databox MUST protect the Polaris PostgreSQL catalog with the ratified pgBackRest physical-backup, WAL, startup-gate, and restore-drill design.

Databox MUST NOT create or manage an Iceberg recovery bucket, S3 replication configuration, replication IAM role/policy, recovery-reader role/policy, or source-bucket versioning solely for disaster recovery. It MUST NOT add a scheduled warehouse-copy process.

Iceberg table snapshots remain the mechanism for logical rollback while their objects exist. Loss or destructive corruption of the primary warehouse is recovered by rebuilding from canonical sources through the existing Databox refresh pipeline, not by restoring object versions from a recovery copy.

The 45-day Iceberg object-recovery objective is removed. The 60-minute RTO applies only to catalog recovery when the primary Iceberg warehouse remains readable; it is not guaranteed for complete warehouse loss or source re-ingestion. The five-minute catalog RPO and 30-day catalog PITR objectives remain unchanged.

The exact plans recorded at `.10x/evidence/2026-09-04-recovery-opentofu-plan.md` and `.10x/evidence/2026-09-04-catalog-only-recovery-opentofu-plan.md` MUST NOT be applied. They are historical evidence invalidated respectively by this decision and the later TLS-enforcement repair. The current TLS-enforced catalog-only plan is recorded at `.10x/evidence/2026-09-04-catalog-only-tls-recovery-opentofu-plan.md`; it still requires independent review and explicit approval before apply.

Because the current AWS login identifies as account root and no non-root operator identity exists, root MAY be used only for the initial reviewed bootstrap apply. Runtime pgBackRest credentials MUST come from the created least-privilege `databox-polaris-catalog-backup` role and MUST never be root credentials. After a separately approved apply and role-access verification, the root CLI session MUST be logged out. Root trust SHOULD be replaced when a non-root operator identity is established.

## Alternatives considered

- **Continuous S3 replication:** rejected because source versioning, a second warehouse copy, IAM, lifecycle, and replication cost are disproportionate for this rebuildable local project.
- **Scheduled `rclone` or equivalent copy:** rejected because it adds scheduling, credentials, failure handling, and duplicate storage without enough value.
- **No catalog backup either:** rejected because Polaris contains realm, permissions, and table-registration state that is not safely equivalent to rebuilding warehouse data.

## Consequences

The infrastructure and operating model become substantially smaller. The primary bucket does not need versioning for this recovery architecture, and warehouse storage is not duplicated.

A primary-bucket loss may require complete source re-ingestion and can exceed 60 minutes. Provider unavailability, changed upstream data, rate limits, or unavailable pinned inputs may prevent exact reconstruction; this residual risk is explicitly accepted. Recovery drills must distinguish catalog-only recovery from full warehouse rebuild and must not claim object-level recovery capability.
