Status: open
Created: 2026-09-09
Updated: 2026-09-09
Parent: .10x/tickets/2026-09-04-run-timed-catalog-recovery-drill.md
Depends-On: None

# Upload pending WAL before local recovery

## Scope

Extend the existing interactive recovery tool so one MFA session enumerates every locally retained pending PostgreSQL WAL file, uploads it oldest-first with synchronous pgBackRest, verifies remote continuity through the newly selected marker, and only then restores. Preserve all existing credential, isolation, redaction, cleanup, and no-cutover boundaries.

## Acceptance criteria

- Pending `.ready` WAL names are enumerated from the active catalog, strictly validated, sorted, bounded, and matched to existing regular WAL files before upload.
- Every pending segment is synchronously archived oldest-first using the fresh MFA-issued backup-role session; failure stops before restore and reports the exact nonsecret segment position.
- The new marker segment is included after backlog catch-up and repository continuity through the selected target is verified before restore.
- No pending file, archive-status file, remote object, backup, or recovery artifact is deleted or manually marked complete.
- Output distinguishes manual off-machine catch-up lag from the marker target-inclusion gap and does not claim continuous five-minute local RPO.
- The preserved failed restore remains untouched; a fresh drill uses new ownership-labeled resources.
- Real pinned-image and stateful integration tests cover multiple ordered pending segments, gaps, malformed names, missing local files, partial upload failure, empty backlog, duplicate-safe upload, and successful restore ordering.

## Exclusions

- Long-lived AWS credentials.
- Unattended credential renewal or scheduling.
- Production cutover.
- Recovery-artifact cleanup.
- Claiming that catch-up proves protection before it ran.

## References

- `.10x/decisions/accept-manual-wal-catchup-for-local-catalog.md`
- `.10x/evidence/2026-09-09-timed-drill-wal-gap-recovery-failure.md`
- `.10x/specs/polaris-catalog-continuity.md`

## Evidence expectations

Record the pre-catch-up oldest/newest pending WAL, count, ordered upload proof, repository continuity, fresh target, restored marker boundary, RPO terminology, RTO, and explicit limits without credentials.

## Progress and notes

- 2026-09-09: Opened after the user explicitly accepted local-only loss between authenticated catch-ups and rejected long-lived backup credentials.

## Blockers

None.
