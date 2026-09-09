Status: recorded
Created: 2026-09-09
Updated: 2026-09-09
Relates-To: .10x/tickets/2026-09-04-run-timed-catalog-recovery-drill.md, .10x/specs/polaris-catalog-continuity.md

# Timed drill exposed a retained WAL archive gap

## What was observed

Operator drill `ms8wemjnzcnvnkh9` passed authentication and preflight, created a microsecond marker bracket, synchronously archived the current marker WAL, restored pgBackRest files, and launched isolated PostgreSQL with fresh recovery credentials. PostgreSQL did not reach promotion, so marker-boundary validation timed out. The command cleaned the active marker and archived cleanup WAL, stopped isolated PostgreSQL, and preserved its labeled volume, network, and secret-free container. Polaris never started.

The preserved cluster still has `recovery.signal` and target `2026-09-09 22:36:48.577702+00`, proving recovery did not reach the target. The active cluster has six retained `.ready` WAL segments `000000010000000000000015` through `00000001000000000000001A`; every corresponding WAL file remains locally present. Current WAL is `00000001000000000000001B`. Earlier evidence proved the remote archive only through segment `000000010000000000000014` before the active container's startup-injected temporary backup credentials expired.

## Procedure

Inspected the preserved container state/log boundary, copied only recovery configuration and signal presence from the stopped preserved container, queried active marker absence, enumerated active `pg_wal/archive_status/*.ready`, proved each retained segment file exists, and read the current WAL filename. No AWS call, active SQL mutation, Docker start, marker cleanup, retry, artifact deletion, or cutover occurred.

## What this supports

The failure is no longer attributable to marker precision or missing PITR child credentials. The available evidence supports a contiguous remote-archive gap after segment 14: explicit drill archival uploaded current segments but did not backfill older retained `.ready` segments. PostgreSQL therefore could not replay continuously to the selected target.

This is a disaster-recovery architecture failure, not merely another drill-command defect. Backfilling from the still-healthy primary could make a subsequent restore work, but would not prove the five-minute RPO that would have applied if the primary had been lost before backfill.

## Limits

Remote repository contents after segment 14 were not listed because no fresh MFA role session was available to this process. The exact first missing remote segment should be confirmed during the repair proof. The retained local WAL means recovery can likely be repaired without data loss while the primary remains healthy; that is not evidence that the pre-repair RPO objective was met.
