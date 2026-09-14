Status: recorded
Created: 2026-09-08
Updated: 2026-09-08
Target: .10x/evidence/2026-09-08-marker-backed-isolated-pitr-success.md
Verdict: pass

# Marker-backed isolated PITR review

## Findings

None.

## Verdict

Pass. Evidence coherently supports the authorized active PostgreSQL-only credential refresh, readiness/differential backup, distinct committed markers around target `2026-09-08T21:40:22Z`, forced WAL archive with zero observed failures, new ownership-verified isolated restore/start, target-boundary replay and timeline-2 promotion, `pg_is_in_recovery()=false`, before marker present, after marker absent, active marker cleanup with cleanup WAL, and healthy active PostgreSQL/Polaris.

The isolated container has no active mounts, published ports, restart policy, archive writes, Polaris, or bootstrap. Credentials were not exposed. The parser-only Compose sentinel was not injected into PostgreSQL. The initial duplicate-marker correction remained within the authorized marker/cleanup boundary and created no restore volume.

## Residual risk

Restored Polaris and registry-derived catalog/table validation have not run. This was not a timed RPO/RTO drill and exact active restart downtime was not captured. Temporary role credentials expire. The isolated PostgreSQL container remains running on bridge networking but publishes no ports, listens only on its Unix socket, and has archiving disabled. Same-account/region loss remains outside scope. Recovery artifacts require separate cleanup authorization.
