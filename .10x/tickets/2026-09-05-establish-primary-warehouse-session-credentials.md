Status: blocked
Created: 2026-09-05
Updated: 2026-09-05
Parent: None
Depends-On: None

# Establish renewable primary-warehouse session credentials

## Scope

Shape and implement a renewable, least-privilege source for `DATABOX_AWS_ACCESS_KEY_ID`, `DATABOX_AWS_SECRET_ACCESS_KEY`, and required `DATABOX_AWS_SESSION_TOKEN` so a future full `compose.iceberg.yml` recreation can authenticate Polaris to the primary warehouse without persistent temporary credentials or misuse of the catalog-backup role.

## Acceptance criteria

- The primary-warehouse principal, permissions, MFA or workload-authentication boundary, credential lifetime, renewal procedure, and ownership are explicitly ratified before implementation.
- A full Compose recreation receives a valid session token without committing credentials or storing catalog-backup-role credentials as warehouse credentials.
- Existing primary-warehouse access remains least privilege and independently verifiable.
- Documentation includes expiration and restart handling.

## Explicit exclusions

- Reusing `databox-polaris-catalog-backup` for warehouse access.
- Long-lived access keys introduced without a separately ratified exception.
- Changing bucket ownership, Iceberg semantics, or disaster-recovery scope.

## References

- `compose.iceberg.yml`
- `.10x/reviews/2026-09-05-first-live-catalog-backup-review.md`
- `.10x/decisions/catalog-backup-with-rebuildable-iceberg-warehouse.md`

## Evidence expectations

Record the exact principal, effective policy, temporary-credential path, full Compose recreation, Polaris health, and secret-scan result without exposing credentials.

## Progress and notes

- 2026-09-05: Opened after the first live backup proof could restart but not recreate Polaris because `.env` lacked `DATABOX_AWS_SESSION_TOKEN`. The existing container was safely restarted after the backup gate. This did not invalidate catalog backup/WAL proof.

## Blockers

The correct primary-warehouse identity and renewable credential mechanism are ambiguous and require shaping before implementation.
