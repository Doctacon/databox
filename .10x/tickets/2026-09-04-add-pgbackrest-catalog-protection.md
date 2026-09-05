Status: open
Created: 2026-09-04
Updated: 2026-09-04
Parent: .10x/tickets/2026-09-04-build-polaris-iceberg-disaster-recovery.md
Depends-On: None

# Add pgBackRest catalog backup and WAL protection

## Scope

Integrate a pinned pgBackRest runtime with the existing PostgreSQL 17.6 Compose service. Keep one `compose.iceberg.yml` and require a successful backup-readiness gate before Polaris becomes available. Configure encrypted S3 repository access through host-injected short-lived backup session credentials, continuous WAL archive with a maximum five-minute archive opportunity, startup-driven weekly full/daily differential cadence, retention for 30-day PITR, configuration/repository checks, and operator commands.

Keep graph construction and ordinary credential-free CI hermetic. Backup commands may require configured infrastructure, but importing settings, building Compose configuration, and running unit/static tests must not contact AWS or mutate local warehouse state.

## Acceptance criteria

- One `compose.iceberg.yml` owns normal protected operation; no separate normal/backup Compose files or unprotected mode exist.
- PostgreSQL may start internally, but Polaris and writers remain unavailable until complete host-injected short-lived backup session credentials, repository access, stanza state, WAL archival, and required initial backup are verified.
- Missing, partial, expired, or invalid backup configuration and any failed backup prerequisite keep Polaris unavailable with a clear diagnostic; no bypass is accepted.
- PostgreSQL and pgBackRest versions are explicit and compatible; local/remote pgBackRest command paths cannot silently diverge.
- WAL archive uses pgBackRest and a PostgreSQL archive timeout no greater than 300 seconds.
- Repository configuration accepts dedicated bucket/region inputs, uses the intentionally fixed `repo1-path=/polaris`, and accepts host-injected temporary backup access key, secret key, and session token; no long-lived access key is required.
- The PostgreSQL image contains no AWS CLI and mounts no host AWS profile, SSO cache, credential-process executable, or whole `~/.aws` directory.
- Client-side encryption requires an external secret and fails closed when absent at a real backup boundary.
- The startup gate uses repository timestamps to run a full backup when no successful full exists or the newest full is at least seven days old, a differential when the newest successful backup is at least 24 hours old, and no unnecessary backup otherwise; it verifies any requested backup in fresh repository metadata.
- Commands exist for stanza initialization/check, manual full backup, manual differential backup, and repository verification/info.
- Retention configuration preserves physical backup dependencies and WAL for the complete 30-day PITR window.
- Backup failure and stale archive state are legible to the operator.
- Tests cover absent/partial temporary backup credentials, missing session token, missing encryption secret, archive configuration, retention, no-I/O construction, and secret redaction.
- Focused tests, Compose rendering, Ruff, format, MyPy, secret scan, and diff checks pass without AWS calls or live backup writes.

## Explicit exclusions

- Live backup upload or AWS apply.
- Restore/cutover implementation owned by the recovery-drill child.
- Long-lived static access keys.
- High availability.
- Provider refresh or SQLMesh behavior changes.

## References

- `.10x/decisions/startup-only-catalog-backup-gate.md`
- `.10x/specs/polaris-catalog-continuity.md`
- `.10x/research/2026-09-04-polaris-iceberg-disaster-recovery.md`
- `compose.iceberg.yml`

## Evidence expectations

Record exact rendered PostgreSQL/pgBackRest configuration, temporary-session injection and redaction tests, backup command dry/static validation, changed files, all commands/results, and explicit no-live-AWS/no-provider limits.

## Progress and notes

- 2026-09-04: Opened from the ratified disaster-recovery architecture.
- 2026-09-04: Timeboxed implementation added an explicit PostgreSQL 17.6/pgBackRest 2.55.1 image, encrypted 30-day repository template, renewable credential-process validator, 300-second WAL archive configuration, backup/check/info Task interfaces, environment documentation, and focused hermetic tests. The ticket remains open because automatic weekly/daily scheduling, repository verification, encrypted logical export, and catalog inventory are not yet implemented; no live AWS or backup operation ran.
- 2026-09-04: User explicitly rejected optional normal-versus-backup operation and ratified one-Compose fail-closed availability: Polaris may operate only after the repository, renewable credentials, stanza, WAL archive, and initial backup are proven healthy. The remaining implementation must add this gate rather than making backup variables optional.
- 2026-09-04: Two timeboxed implementation launches failed before child startup and made no repository changes. Both the native worker and available Claude Code writer exited in Pi's experimental client before producing a transcript because `@earendil-works/pi-coding-agent/dist/experimental/server.js` attempted to resolve the nonexistent path `@earendil-works/pi-agent-core/dist/index.js/node`. Execution stopped rather than bypassing the child-ticket ownership rule or spending beyond the user's timebox.
- 2026-09-04: The fail-closed readiness slice now makes PostgreSQL health contingent on a one-time in-container gate that validates complete backup settings, renewable credentials/repository/stanza access through pgBackRest, a WAL archive round trip, and an existing or newly created full backup. Polaris bootstrap remains Compose-dependent on PostgreSQL health, so gate failure prevents catalog availability. Focused hermetic tests pass 8/8 without AWS, backup, provider, or volume access. Compose rendering remains environment-blocked because the installed Docker CLI lacks the Compose plugin. The ticket remains open for scheduling, repository verification, encrypted logical export, inventory, and live proof.
- 2026-09-04: Parent review recorded three significant blockers at `.10x/reviews/2026-09-04-fail-closed-backup-gate-review.md`: the documented AWS CLI credential process is absent inside the image, the initial full backup runs before Polaris bootstrap initializes catalog state, and the ready marker prevents ongoing credential/repository/WAL health failures from making Polaris unavailable.
- 2026-09-04: User rejected installing AWS CLI/mounting host authentication inside PostgreSQL and ratified host-injected temporary backup access key, secret, and session token, matching the existing Iceberg writer pattern. This resolves the design choice for the first review finding; implementation remains open.
- 2026-09-04: Implemented the first review repair only. Compose now maps dedicated host-provided backup access key, secret, and session token directly to pgBackRest runtime variables; readiness and the wrapper fail on any missing value without printing values. Removed the in-container credential-process helper and its OpenTofu output/config surface; the image installs no AWS CLI and mounts no host authentication. Fourteen focused catalog/infrastructure tests, Ruff, format, shell syntax, and diff checks pass hermetically. No AWS/provider/backup/restore/apply operation ran. The ticket remains open.
- 2026-09-04: Repaired initial-backup ordering without sleeps or extra Compose files. PostgreSQL health is basic `pg_isready`; Polaris bootstrap runs next; the one-shot `catalog-backup-readiness` service shares only the PostgreSQL data/socket volumes, verifies WAL/repository state, and creates/verifies any required full backup after bootstrap; Polaris depends on successful gate completion. Recovery preparation now explicitly disables authoritative backup archiving. Fourteen focused tests, Ruff/format, `git diff --check`, and standalone Compose rendering passed. No image build, AWS/provider request, backup, restore, volume mutation, or apply ran. The ticket remains open.
- 2026-09-04: User explicitly rejected ongoing monitor/per-write enforcement as overkill. Startup-only backup verification is now authoritative; post-start archive failures surface through ordinary pgBackRest archive/check/backup operations, and the five-minute RPO is an objective while archiving is healthy. The former third review finding is superseded by `.10x/decisions/startup-only-catalog-backup-gate.md`, not left as an implementation blocker.
- 2026-09-04: User ratified startup-driven cadence because the local stack is expected to restart reasonably often: full when absent or at least seven days old, differential when the newest backup is at least 24 hours old, otherwise no backup. No cron or host scheduler is required; manual tasks cover unusually long-running sessions. Repository checks and fresh metadata prove command/repository state, while only a restore drill proves recoverability.
- 2026-09-04: Implemented the startup cadence in the existing one-shot gate. It validates pgBackRest stanza/backup JSON, tolerates the expected no-valid-backups status for initialization, uses successful backup stop timestamps at exact daily/weekly boundaries, and requires a new successful backup label of the requested type in fresh post-command metadata. Focused hermetic tests cover full/differential selection, boundaries, skip, malformed metadata, and rejection of stale post-backup metadata. No Docker, AWS/provider, backup/restore, volume, scheduler, or apply operation ran. The ticket remains open for encrypted logical export and live proof.
- 2026-09-04: User rejected a separately maintained pre-disaster catalog inventory in favor of conventional restore validation. Inventory implementation is removed from this ticket; the isolated restore ticket owns enumeration, source-registry comparison, table loading, S3 metadata/snapshot readability, representative queries, and temporal drill evidence.
- 2026-09-04: User removed the secondary encrypted logical export as redundant. Physical pgBackRest backup plus WAL/PITR is the sole catalog backup mechanism; version-pinned isolated restore drills prove it. No `pg_dump` scheduling, encryption, retention, or restore path will be added.
- 2026-09-04: Final independent static review `.10x/reviews/2026-09-04-catalog-protection-final-static-review.md` raised four closure findings: one stale logical-export MUST, manual Task commands likely running pgBackRest as root, repository-path configurability conflicting with the fixed `/polaris` configuration, and absent focused coverage for a missing encryption secret.
- 2026-09-04: Repaired all four static-review findings: removed the stale logical-export MUST; made all manual pgBackRest Tasks select the `postgres` user; ratified fixed `repo1-path=/polaris`; and added focused missing-cipher/redaction plus Task-user/path coverage. Focused hermetic tests and static checks pass without Docker, AWS, backup, restore, provider, or volume activity.

## Blockers

None for static implementation scope; ready for focused independent re-review and closure. Live repository checks, the real image build, and the pgBackRest/WAL/initial-backup round trip require provisioned infrastructure and belong to the live apply/proof ticket.
