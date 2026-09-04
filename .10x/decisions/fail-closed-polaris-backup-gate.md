Status: active
Created: 2026-09-04
Updated: 2026-09-04

# Require healthy catalog backups before Polaris becomes available

## Context

Databox previously selected pgBackRest, separate same-account AWS backup buckets, renewable short-lived credentials, a five-minute catalog RPO while running, a 60-minute RTO, 30-day PITR, and 45-day Iceberg object recovery. During implementation, an optional normal-versus-backup startup design was considered so Polaris could run before backup infrastructure existed.

The user rejected that availability-first behavior. Because Polaris is the sole catalog authority for AWS-hosted Iceberg raw tables, serving it without a working catalog backup path would create an unprotected authoritative control plane.

## Decision

Polaris MUST fail closed until catalog backup health is proven. One `compose.iceberg.yml` remains the operator-visible runtime definition; no separate normal or backup Compose mode will exist.

Startup MUST sequence as follows:

1. PostgreSQL starts internally but is not yet exposed through Polaris.
2. pgBackRest validates renewable credentials, repository access, stanza configuration, and WAL archival.
3. If no valid base backup exists for a newly initialized catalog, the gate creates the required initial backup.
4. Only a successful backup gate permits Polaris bootstrap/service startup and writer access.

Missing, partial, expired, or invalid backup configuration; inaccessible repository; failed WAL archive verification; or absent required backup state MUST keep Polaris unavailable with a clear diagnostic. No bypass or silent unprotected mode is permitted.

Recovery remains an isolated path with writers disabled and MUST NOT archive restored test state into the authoritative backup history.

## Alternatives considered

- **Optional backup configuration with a startup guard:** rejected because it permits the authoritative catalog to operate without proven recovery.
- **Separate normal, backup, and recovery Compose files:** rejected as unnecessary operator and configuration duplication.
- **One Compose file with optional backup enablement:** rejected for the same unprotected-operation risk.
- **Always-on PostgreSQL high availability:** still excluded; tested backup and restore are the current availability tradeoff.

## Consequences

The runtime becomes simpler to understand: operational Polaris always means backup-protected Polaris. AWS backup-bucket or credential-process failure can intentionally block catalog availability and ingestion. This trades availability for recoverability and makes the AWS backup repository a startup dependency.

The automation-first branch cannot run the real Polaris stack until the reviewed OpenTofu infrastructure is applied and backup credentials are configured. Credential-free CI must therefore validate graph/configuration structure without starting the protected runtime.

This decision supersedes `.10x/decisions/superseded/polaris-iceberg-backup-and-recovery.md`. That earlier decision remains authoritative for unchanged choices—pgBackRest, OpenTofu, bucket isolation, same account/region, renewable credentials, retention, and no live apply—only through the restatement above and current specifications.
