Status: recorded
Created: 2026-09-09
Updated: 2026-09-09
Relates-To: .10x/tickets/2026-09-04-run-timed-catalog-recovery-drill.md

# Interactive drill active-port preflight repair

The user's authorized `task catalog:recovery-drill` completed AWS remote login and MFA, then failed closed during preflight before marker, backup-bucket, or Docker mutation. Active Polaris intentionally publishes exact loopback bindings `127.0.0.1:8181 -> 8181/tcp` and `127.0.0.1:8182 -> 8182/tcp`; PostgreSQL publishes none. Preflight had incorrectly required no bindings for both services. No credential value was recorded.

The repair defines exact service-specific active bindings while retaining exact Compose labels/network checks. It rejects wildcard/non-loopback, extra, missing, or changed bindings. Recovery-container no-port requirements are unchanged.

Validation: 64 focused tests passed. Ruff, format, MyPy, focused secret scan, Task dry-run, and diff checks passed. Tests accept only the exact active loopback shape and reject wildcard, extra, missing, and network drift. No live Docker, AWS, marker, or drill rerun occurred.
