Status: recorded
Created: 2026-09-09
Updated: 2026-09-09
Relates-To: .10x/tickets/2026-09-04-run-timed-catalog-recovery-drill.md

# Interactive drill pgBackRest preflight user repair

The second authorized operator-terminal attempt completed AWS login and MFA, then failed closed during preflight because the pgBackRest `info` probe ran as container root. pgBackRest refused with error 031 before marker, backup-bucket, or Docker mutation. No credential value was recorded.

The repair runs the active-container probe as `docker exec --user postgres`, matching Compose and runbook authority, followed by name-only `--env` inheritance. A hermetic command-shape assertion requires the non-root user before environment arguments. No live rerun occurred during repair.
