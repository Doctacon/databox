Status: blocked
Created: 2026-09-04
Updated: 2026-09-04
Parent: .10x/tickets/2026-09-04-build-polaris-iceberg-disaster-recovery.md
Depends-On: .10x/tickets/2026-09-04-verify-disaster-recovery-automation.md

# Apply and prove Polaris/Iceberg disaster recovery

## Scope

After explicit user approval of the exact OpenTofu plan, apply the reviewed infrastructure in the authenticated AWS account, initialize and verify the pgBackRest repository, create the first backups and inventory, confirm Iceberg recovery-copy behavior, and execute a timed isolated point-in-time restore drill.

## Acceptance criteria

- The user reviews and explicitly approves the exact non-secret OpenTofu plan before apply.
- Apply creates only the reviewed same-account, `us-west-1` resources and policies.
- Renewable short-lived credential-process authentication works; no long-lived keys are introduced.
- pgBackRest stanza check, first full backup, WAL archive check, repository verification/info, and logical export complete successfully.
- Iceberg recovery replication/copy and 45-day version protection are observed on bounded non-sensitive test objects without targeting production data for deletion.
- A selected recovery point is restored into an isolated empty environment.
- All Polaris catalog inventory, permissions, registered Iceberg tables, metadata/snapshot pointers, and representative reads validate.
- Evidence records achieved catalog RPO and end-to-end RTO. RPO over five minutes or RTO over 60 minutes fails rather than redefining the targets.
- Recovery environment and bounded test objects are cleaned only through reviewed non-destructive procedures; retained backups are preserved.

## Explicit exclusions

- Unreviewed `tofu apply`.
- Production catalog cutover unless a real incident separately authorizes it.
- Destructive testing against authoritative warehouse objects.
- Cross-account or cross-region changes.

## References

- `.10x/decisions/polaris-iceberg-backup-and-recovery.md`
- `.10x/specs/polaris-catalog-continuity.md`
- `.10x/specs/iceberg-object-recovery.md`
- `.10x/tickets/2026-09-04-verify-disaster-recovery-automation.md`

## Evidence expectations

Record the approved plan hash/summary, apply result, resource identities without secrets, backup/WAL status, bounded replication observation, exact timed drill procedure/results, achieved RPO/RTO, cleanup, and remaining same-account/same-region risk.

## Progress and notes

- 2026-09-04: Opened as the durable owner for live rollout and proof. The user authorized automation first, not live AWS mutation.

## Blockers

Blocked until automation verification completes and the user explicitly approves the exact OpenTofu plan and live AWS apply.
