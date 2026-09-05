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

All earlier plans, including TLS-enforced plan hash `4656b197fd1039d4972c614e828ad0be92128fec6c6f83d4a6a6fd88abc98837`, MUST NOT be applied. A repaired catalog-only OpenTofu plan requires fresh generation, hash, independent review, and explicit approval before apply. Provisioning and a real pgBackRest backup/WAL proof MUST succeed before isolated restore automation begins.

OpenTofu state is intentionally local and operator-owned at `infra/recovery/terraform.tfstate`, applied only from `infra/recovery/`, ignored by Git, protected by FileVault and the operator's normal encrypted machine backup, and excluded from project cleanup. State loss requires restoring that backup or reviewed import of every live resource before another plan; no remote backend is introduced.

Root was used only for the explicitly approved bootstrap apply, but live verification proved AWS root cannot call `sts:AssumeRole`; the planned runtime flow is therefore blocked. OpenTofu MUST declare the non-root `databox-recovery-operator` IAM user without an access key, login profile, password, or MFA material; grant it only `sts:AssumeRole` on `databox-polaris-catalog-backup`; and make that role trust the exact user ARN only when `aws:MultiFactorAuthPresent=true`. Console access, password setup, and MFA enrollment are a manual second step and MUST never enter configuration or state. The human supplies MFA during `AssumeRole`; AWS returns ordinary short-lived role credentials for host injection, and pgBackRest never receives MFA data. Runtime pgBackRest credentials MUST come from the least-privilege role and MUST never be root credentials. Role assumption MUST succeed before root is logged out and backup operation begins.

## Alternatives considered

- **Continuous S3 replication:** rejected because source versioning, a second warehouse copy, IAM, lifecycle, and replication cost are disproportionate for this rebuildable local project.
- **Scheduled `rclone` or equivalent copy:** rejected because it adds scheduling, credentials, failure handling, and duplicate storage without enough value.
- **No catalog backup either:** rejected because Polaris contains realm, permissions, and table-registration state that is not safely equivalent to rebuilding warehouse data.

## Consequences

The infrastructure and operating model become substantially smaller. The primary bucket does not need versioning for this recovery architecture, and warehouse storage is not duplicated.

A primary-bucket loss may require complete source re-ingestion and can exceed 60 minutes. Provider unavailability, changed upstream data, rate limits, or unavailable pinned inputs may prevent exact reconstruction; this residual risk is explicitly accepted. Recovery drills must distinguish catalog-only recovery from full warehouse rebuild and must not claim object-level recovery capability.
