Status: open
Created: 2026-09-04
Updated: 2026-09-04
Parent: .10x/tickets/2026-09-04-build-polaris-iceberg-disaster-recovery.md
Depends-On: None

# Add pgBackRest catalog backup and WAL protection

## Scope

Integrate a pinned pgBackRest runtime with the existing PostgreSQL 17.6 Compose service. Keep one `compose.iceberg.yml` and require a successful backup-readiness gate before Polaris becomes available. Configure encrypted S3 repository access through host-injected short-lived backup session credentials, continuous WAL archive with a maximum five-minute archive opportunity, weekly full/daily differential scheduling interfaces, retention for 30-day PITR, configuration/repository checks, a secondary encrypted logical export, deterministic non-secret catalog inventory, and operator commands.

Keep graph construction and ordinary credential-free CI hermetic. Backup commands may require configured infrastructure, but importing settings, building Compose configuration, and running unit/static tests must not contact AWS or mutate local warehouse state.

## Acceptance criteria

- One `compose.iceberg.yml` owns normal protected operation; no separate normal/backup Compose files or unprotected mode exist.
- PostgreSQL may start internally, but Polaris and writers remain unavailable until complete host-injected short-lived backup session credentials, repository access, stanza state, WAL archival, and required initial backup are verified.
- Missing, partial, expired, or invalid backup configuration and any failed backup prerequisite keep Polaris unavailable with a clear diagnostic; no bypass is accepted.
- PostgreSQL and pgBackRest versions are explicit and compatible; local/remote pgBackRest command paths cannot silently diverge.
- WAL archive uses pgBackRest and a PostgreSQL archive timeout no greater than 300 seconds.
- Repository configuration accepts dedicated bucket/region/path inputs and host-injected temporary backup access key, secret key, and session token; no long-lived access key is required.
- The PostgreSQL image contains no AWS CLI and mounts no host AWS profile, SSO cache, credential-process executable, or whole `~/.aws` directory.
- Client-side encryption requires an external secret and fails closed when absent at a real backup boundary.
- Commands exist for stanza initialization/check, full backup, differential backup, repository verification/info, and encrypted logical export.
- Retention configuration preserves physical backup dependencies and WAL for the complete 30-day PITR window.
- Backup failure and stale archive state are legible to the operator.
- The catalog inventory is deterministic, excludes secrets, and records versions, schema/realm/catalog identity, table locations, metadata locations, and snapshot IDs.
- Tests cover absent/partial temporary backup credentials, missing session token, missing encryption secret, archive configuration, retention, no-I/O construction, and secret redaction.
- Focused tests, Compose rendering, Ruff, format, MyPy, secret scan, and diff checks pass without AWS calls or live backup writes.

## Explicit exclusions

- Live backup upload or AWS apply.
- Restore/cutover implementation owned by the recovery-drill child.
- Long-lived static access keys.
- High availability.
- Provider refresh or SQLMesh behavior changes.

## References

- `.10x/decisions/session-injected-catalog-backup-credentials.md`
- `.10x/specs/polaris-catalog-continuity.md`
- `.10x/research/2026-09-04-polaris-iceberg-disaster-recovery.md`
- `compose.iceberg.yml`

## Evidence expectations

Record exact rendered PostgreSQL/pgBackRest configuration, credential-process and redaction tests, backup command dry/static validation, changed files, all commands/results, and explicit no-live-AWS/no-provider limits.

## Progress and notes

- 2026-09-04: Opened from the ratified disaster-recovery architecture.
- 2026-09-04: Timeboxed implementation added an explicit PostgreSQL 17.6/pgBackRest 2.55.1 image, encrypted 30-day repository template, renewable credential-process validator, 300-second WAL archive configuration, backup/check/info Task interfaces, environment documentation, and focused hermetic tests. The ticket remains open because automatic weekly/daily scheduling, repository verification, encrypted logical export, and catalog inventory are not yet implemented; no live AWS or backup operation ran.
- 2026-09-04: User explicitly rejected optional normal-versus-backup operation and ratified one-Compose fail-closed availability: Polaris may operate only after the repository, renewable credentials, stanza, WAL archive, and initial backup are proven healthy. The remaining implementation must add this gate rather than making backup variables optional.
- 2026-09-04: Two timeboxed implementation launches failed before child startup and made no repository changes. Both the native worker and available Claude Code writer exited in Pi's experimental client before producing a transcript because `@earendil-works/pi-coding-agent/dist/experimental/server.js` attempted to resolve the nonexistent path `@earendil-works/pi-agent-core/dist/index.js/node`. Execution stopped rather than bypassing the child-ticket ownership rule or spending beyond the user's timebox.
- 2026-09-04: The fail-closed readiness slice now makes PostgreSQL health contingent on a one-time in-container gate that validates complete backup settings, renewable credentials/repository/stanza access through pgBackRest, a WAL archive round trip, and an existing or newly created full backup. Polaris bootstrap remains Compose-dependent on PostgreSQL health, so gate failure prevents catalog availability. Focused hermetic tests pass 8/8 without AWS, backup, provider, or volume access. Compose rendering remains environment-blocked because the installed Docker CLI lacks the Compose plugin. The ticket remains open for scheduling, repository verification, encrypted logical export, inventory, and live proof.
- 2026-09-04: Parent review recorded three significant blockers at `.10x/reviews/2026-09-04-fail-closed-backup-gate-review.md`: the documented AWS CLI credential process is absent inside the image, the initial full backup runs before Polaris bootstrap initializes catalog state, and the ready marker prevents ongoing credential/repository/WAL health failures from making Polaris unavailable.
- 2026-09-04: User rejected installing AWS CLI/mounting host authentication inside PostgreSQL and ratified host-injected temporary backup access key, secret, and session token, matching the existing Iceberg writer pattern. This resolves the design choice for the first review finding; implementation remains open.

## Blockers

Repair the three significant gate findings, using `.10x/decisions/session-injected-catalog-backup-credentials.md` for the first finding in `.10x/reviews/2026-09-04-fail-closed-backup-gate-review.md`. Repository automation also still needs scheduling, repository verification, encrypted logical export, and deterministic catalog inventory. Live repository checks require provisioned infrastructure and belong to the live apply/proof ticket. The real image build, Compose render, pgBackRest/WAL round trip, and initial backup remain unproven in this no-live slice.
