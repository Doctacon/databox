Status: superseded
Created: 2026-09-04
Updated: 2026-09-04

# Inject session-scoped catalog backup credentials from the host

## Context

Databox requires pgBackRest backup health before Polaris becomes available. The first implementation attempted to execute `aws configure export-credentials` inside the PostgreSQL container. That requires installing AWS CLI and mounting host AWS profile/configuration into the database container, expanding credential exposure and coupling the container to host authentication internals.

The existing Iceberg writer already accepts temporary AWS session credentials from the host. The user rejected mounting host authentication machinery into PostgreSQL as unnecessarily indirect and approved matching the existing temporary-session pattern for backup access.

## Decision

The host MUST obtain short-lived credentials for the dedicated catalog-backup role before starting the protected stack. Compose MUST inject the backup access key, secret key, and session token into the PostgreSQL container through environment variables. These values MUST remain runtime-only and MUST NOT be committed, written to OpenTofu state, logged, or copied into recovery inventories.

The PostgreSQL image MUST NOT install AWS CLI or mount host AWS profiles, SSO caches, credential-process executables, or the whole `~/.aws` directory. pgBackRest MUST receive only its dedicated temporary backup credentials. Missing or partial values MUST fail the backup-readiness gate clearly.

This change addresses credential delivery only. The separate recorded finding that ongoing backup failure must revoke protected operation remains unresolved and owned by `.10x/tickets/2026-09-04-add-pgbackrest-catalog-protection.md`.

All other active recovery choices remain unchanged: one Compose file; fail-closed Polaris startup; pgBackRest; OpenTofu; separate same-account, same-region buckets; five-minute RPO while running; 60-minute RTO; 30-day catalog PITR; 45-day Iceberg recovery; and no live AWS apply before explicit plan approval.

## Alternatives considered

- **Install AWS CLI and mount a dedicated host profile/cache:** rejected as unnecessary host-authentication exposure inside the database container.
- **Mount all of `~/.aws`:** rejected because it exposes unrelated profiles and credentials.
- **Credential broker or metadata sidecar:** rejected as more machinery than the local-first runtime requires.
- **Long-lived IAM access keys:** rejected because they increase compromise lifetime and rotation burden.
- **Run Polaris on AWS compute with workload identity:** operationally clean for an always-on service but outside the ratified local-first architecture.

## Consequences

The container contract becomes explicit and matches the existing temporary Iceberg writer pattern. Operators must refresh the dedicated backup session and restart/reload the protected runtime when credentials expire. Automatic in-container renewal is intentionally not provided.

The eventual ongoing-health repair must detect expired/rejected credentials and enforce the separately ratified fail-closed behavior; this decision does not treat startup success as indefinite backup health.

This decision supersedes `.10x/decisions/superseded/fail-closed-polaris-backup-gate.md` only for credential delivery. Its fail-closed startup and one-Compose decisions remain active as restated here.
