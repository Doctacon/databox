Status: active
Created: 2026-09-08
Updated: 2026-09-08

# Allow the existing long-lived key for the local primary warehouse

## Context

The running local Polaris container accesses the primary Iceberg S3 warehouse as IAM user `databox-lake-user` with an access key and secret stored in Git-ignored `.env`. Long-lived IAM-user credentials do not have a session token, but `compose.iceberg.yml` had begun requiring `DATABOX_AWS_SESSION_TOKEN` as though every primary credential were temporary. That prevented full Compose rendering/recreation despite the existing credential remaining valid.

Temporary credentials are preferable when the workload can renew them. The current host-injection design cannot refresh credentials inside a multi-day Polaris container; requiring an MFA-issued role session would cause warehouse access to fail at session expiry or require controlled container restarts. IAM Roles Anywhere or a credential broker would add disproportionate PKI/service complexity for this personal local stack.

## Decision

The local primary warehouse MAY use the existing long-lived `databox-lake-user` access key and secret without `DATABOX_AWS_SESSION_TOKEN`. Polaris MUST continue to forward the token when temporary OIDC/STS credentials provide one. Primary access key and secret remain mandatory.

This exception applies only to primary-warehouse access on the local FileVault-protected host. `.env` MUST remain Git-ignored and mode `0600`. Catalog-backup credentials remain separate, short-lived, MFA-issued role credentials; `DATABOX_BACKUP_AWS_SESSION_TOKEN` remains mandatory and the backup role MUST NOT be reused for warehouse access.

The effective `databox-lake-user` policy still requires an independent least-privilege audit before this work is complete. If Databox becomes hosted, shared, unattended, or continuously operated, replace this exception with renewable workload credentials before that transition.

## Alternatives considered

- **MFA-assumed primary role with host injection:** stronger credential expiry, but warehouse access fails when the injected session expires and the current container cannot refresh it.
- **IAM Roles Anywhere or a local credential broker:** supports renewable temporary credentials but introduces certificate, helper, or daemon lifecycle complexity.
- **Require a blank/fabricated token:** rejected because it misrepresents the credential type and can break AWS SDK authentication.

## Consequences

Local Compose recreation works with the credential shape already in use, while CI OIDC remains temporary-token authenticated. Compromise of `.env` exposes a non-expiring credential until it is revoked or rotated; that risk is explicitly accepted for the personal local deployment and bounded by FileVault, file permissions, Git exclusion, and the pending least-privilege policy audit.
