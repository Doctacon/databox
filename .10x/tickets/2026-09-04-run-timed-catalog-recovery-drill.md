Status: blocked
Created: 2026-09-04
Updated: 2026-09-04
Parent: .10x/tickets/2026-09-04-build-polaris-iceberg-disaster-recovery.md
Depends-On: .10x/tickets/done/2026-09-04-verify-disaster-recovery-automation.md, .10x/tickets/done/2026-09-09-add-interactive-catalog-recovery-drill-command.md

# Run timed isolated catalog recovery drill

## Scope

After backup infrastructure, first real backup/WAL proof, isolated restore automation, and final automation verification complete, execute the reviewed PITR drill against an empty isolated target. Validate restored Polaris and readable primary Iceberg tables conventionally, record achieved catalog RPO/RTO, and stop before production cutover.

## Acceptance criteria

- A selected recovery point is restored into a new empty isolated environment without touching the active catalog.
- Polaris identity and permissions validate without bootstrap replacing restored state.
- When the primary warehouse remains readable, registry-owned tables, metadata/snapshot pointers, and representative reads validate.
- Evidence records achieved catalog RPO and end-to-end RTO; results over five minutes or 60 minutes fail their objectives without redefining them.
- Recovery resources are cleaned through reviewed non-destructive procedures while retained backups and OpenTofu state remain preserved.

## Explicit exclusions

- Production cutover.
- Iceberg object recovery or a 60-minute full-warehouse rebuild guarantee.
- Unreviewed destructive action.

## Progress and notes

- 2026-09-09: User explicitly authorized the timed drill. Execution remained blocked until `.10x/tickets/done/2026-09-04-verify-disaster-recovery-automation.md` passed final adversarial review and closed.
- 2026-09-09: All dependencies are now done and live-drill authorization remains active. Execute with a fresh marker-bracketed target and new ownership-labeled recovery resources; stop before cutover or cleanup.
- 2026-09-09: Credential preflight stopped before the RTO clock and before any mutation because the three required temporary backup-role environment values were unavailable. `.10x/evidence/2026-09-09-timed-recovery-drill-credential-preflight.md` records the exact prerequisite and no-mutation boundary. No role assumption was attempted.
- 2026-09-09: A second preflight proved that the operator's MFA role session was not reusable by the separate non-TTY Pi worker. The user rejected both a temporary credential handoff file and another one-off script, then authorized extending the existing recovery entrypoint. No marker, backup-bucket, or Docker mutation occurred.

## Blockers

Blocked only on `.10x/tickets/done/2026-09-09-add-interactive-catalog-recovery-drill-command.md`. Existing drill authorization remains valid. Cleanup remains separately authorized.
