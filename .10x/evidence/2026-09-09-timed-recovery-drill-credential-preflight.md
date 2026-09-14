Status: blocked
Created: 2026-09-09
Updated: 2026-09-09
Relates-To: .10x/tickets/2026-09-04-run-timed-catalog-recovery-drill.md

# Timed recovery drill credential preflight

## Result

The authorized timed drill stopped at its first credential preflight before the RTO clock or any live mutation began. Dotenv-aware inspection found the configured catalog-backup bucket and repository cipher passphrase, but neither `.env` nor the child process environment contained the three required temporary backup-role values:

- `DATABOX_BACKUP_AWS_ACCESS_KEY_ID`;
- `DATABOX_BACKUP_AWS_SECRET_ACCESS_KEY`;
- `DATABOX_BACKUP_AWS_SESSION_TOKEN`.

Primary warehouse credentials were not treated as substitutes. No role assumption was attempted. The reviewed procedure requires a fresh MFA-assumed `databox-polaris-catalog-backup` session supplied by the operator.

## Safety boundary

No marker table, transaction, WAL switch, backup/repository request, recovery volume, container, network, file restore, Polaris process, validation request, AWS mutation, cutover, cleanup, or deletion occurred. Existing active and recovery services/artifacts were not changed. No credential value was printed or persisted.

## Resume condition

Resume only after the operator obtains and exports all three fresh temporary backup-role credentials through the reviewed MFA path without printing them. The existing timed-drill authorization remains recorded; credential availability does not authorize cleanup or cutover.
