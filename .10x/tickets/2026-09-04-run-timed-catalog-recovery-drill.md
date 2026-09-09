Status: blocked
Created: 2026-09-04
Updated: 2026-09-04
Parent: .10x/tickets/2026-09-04-build-polaris-iceberg-disaster-recovery.md
Depends-On: .10x/tickets/done/2026-09-04-verify-disaster-recovery-automation.md, .10x/tickets/done/2026-09-09-add-interactive-catalog-recovery-drill-command.md, .10x/tickets/2026-09-09-upload-pending-wal-before-local-recovery.md

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
- 2026-09-09: `.10x/tickets/done/2026-09-09-add-interactive-catalog-recovery-drill-command.md` implemented and independently passed review. The operator can now run the already authorized drill from the TTY that owns MFA without a credential file or new script.
- 2026-09-09: The first operator-terminal execution authenticated successfully, then failed closed before mutation because active-port preflight incorrectly rejected Compose's intentional loopback-only Polaris ports. `.10x/evidence/2026-09-09-interactive-drill-active-port-preflight-repair.md` records the scoped repair: exact service-specific active bindings are required, while wildcard, extra, missing, changed, or wrong-network states fail. Sixty-four tests and static/security/Task checks pass; no live rerun occurred.
- 2026-09-09: The second operator-terminal execution completed AWS login and MFA, then failed closed before mutation because the pgBackRest repository probe ran as container root. `.10x/evidence/2026-09-09-interactive-drill-pgbackrest-user-preflight-repair.md` records the repair to require `docker exec --user postgres` while preserving name-only credential inheritance. No live rerun occurred during repair.

- 2026-09-09: Before another live attempt, a proactive command audit found and repaired the same operating-system-user omission on marker and cleanup WAL `archive-push`; integrated coverage now requires every pgBackRest invocation to select `postgres`. Evidence: `.10x/evidence/2026-09-09-interactive-drill-wal-archive-user-repair.md`. No live operation occurred.
- 2026-09-09: The same pre-live audit found psql command tags could be misparsed as marker timestamps. Quiet output and exact single-row timestamp validation were added with regression coverage; evidence: `.10x/evidence/2026-09-09-interactive-drill-marker-parsing-repair.md`. No live mutation occurred.
- 2026-09-09: A live drill committed marker `databox_recovery_drill_y0puu4ucgfgbx81p` but failed before restore because explicit archive-push entered pgBackRest's asynchronous spool and used the active container's expired startup token. No recovery volume, network, or container was created. Evidence: `.10x/evidence/2026-09-09-timed-drill-stale-async-credential-failure.md`. Explicit drill archival is now synchronous with the fresh MFA session; the known marker requires the separately invocable in-tool reconciliation step before rerun.
- 2026-09-09: Hardened that reconciliation path to accept only exact generated marker names and to prove one `public` ordinary table owned by `polaris` before an exact quoted DROP and synchronous WAL archive. Evidence: `.10x/evidence/2026-09-09-failed-drill-marker-reconciliation-hardening.md`. No live cleanup occurred.
- 2026-09-09: After the user stopped the incremental retry cycle, a three-lane end-to-end audit found microsecond target loss, durable preserved-container credentials, non-idempotent partial cleanup, incomplete objective enforcement/timing, ambiguous Docker absence, and duplicated table-count policy. All findings were repaired together; `.10x/evidence/2026-09-09-timed-drill-comprehensive-live-contract-repair.md` records the corrected contract. Final integration review additionally caught the validator sibling-exec environment boundary: it now fails before Docker without host credentials and injects only credential names from the sanitized validator process environment. A disposable no-network Polaris probe proved sibling absence, explicit name-only availability, and zero persisted config names. No live action occurred.
- 2026-09-09: Consolidated run `w7x5rxrmlo7lvi4r` reconciled the old marker, restored files successfully, then failed at isolated PostgreSQL startup because PITR `archive-get` still requires fresh repository credentials during replay. Both active markers and cleanup WAL completed; the labeled recovery volume/network and exited secret-free PostgreSQL container remain preserved, and no Polaris container exists. The repair uses a credential-bearing child process only through promotion, then restarts PostgreSQL without credentials before Polaris. Evidence: `.10x/evidence/2026-09-09-timed-drill-postgres-pitr-credential-startup-repair.md`.
- 2026-09-09: Fresh run `ms8wemjnzcnvnkh9` restored files but could not promote. Read-only inspection found the repository's previously proven sequence ended at segment 14 while locally retained pending segments 15 through 1A had not been uploaded; uploading only the newest marker segment could not bridge the gap. Both active markers and cleanup WAL completed, PostgreSQL was stopped, Polaris never started, and labeled recovery artifacts remain preserved. Evidence: `.10x/evidence/2026-09-09-timed-drill-wal-gap-recovery-failure.md`.
- 2026-09-09: The user explicitly accepted local-machine loss between authenticated catch-ups and rejected long-lived backup credentials. `.10x/decisions/accept-manual-wal-catchup-for-local-catalog.md` replaces the continuous five-minute local RPO claim with explicit oldest-first manual catch-up before backup/recovery reliance.

## Blockers

Blocked on `.10x/tickets/2026-09-09-upload-pending-wal-before-local-recovery.md`. Do not retry until one MFA session uploads every retained pending segment oldest-first and verifies remote continuity before selecting the recovery target. Recovery-resource cleanup remains separately authorized.
