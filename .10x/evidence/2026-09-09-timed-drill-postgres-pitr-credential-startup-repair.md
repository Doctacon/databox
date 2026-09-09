Status: recorded
Created: 2026-09-09
Updated: 2026-09-09

# Timed drill PostgreSQL PITR credential startup repair

## Live failure

Consolidated operator run `w7x5rxrmlo7lvi4r` authenticated, reconciled the prior marker, archived marker WAL synchronously, and completed the pgBackRest file restore. Isolated PostgreSQL then exited before readiness because recovery startup needed `archive-get` and the secret-free container had no repository cipher passphrase or temporary S3 credentials. Logs reported `archive-get command requires option: repo1-cipher-pass` and inability to locate the required checkpoint.

The active marker `databox_recovery_drill_w7x5rxrmlo7lvi4r` and prior marker `databox_recovery_drill_y0puu4ucgfgbx81p` are absent. Marker cleanup WAL reported complete. Active services were not restarted or cut over.

Preserved artifacts:

- volume `databox_polaris_recovery_drill_w7x5rxrmlo7lvi4r`, with a cryptographic ownership label;
- network `databox_polaris_recovery_drill_w7x5rxrmlo7lvi4r`;
- exited container `databox-polaris-recovery-drill-postgres-w7x5rxrmlo7lvi4r`, with no ports, no restart policy, and no secret environment names;
- no recovery Polaris container.

## Repair

Recovery PostgreSQL now follows two phases inside one preserved secret-free sleeper container:

1. A detached `postgres` exec runs as OS user `postgres` with name-only backup environment injection. PITR may fetch required WAL with the fresh MFA session.
2. After promotion and marker-boundary validation, the container is stopped to erase the credential-bearing process, restarted as the secret-free sleeper, and PostgreSQL is launched again without backup environment names under `archive_mode=off`. Marker-boundary validation runs again before Polaris starts.

If startup, promotion validation, stop/start, scrubbed launch, or post-scrub validation fails, the state machine stops the PostgreSQL container, preserves its container/volume/network, separately reports quiescence state, and continues active-marker cleanup. No credential value enters argv or preserved container configuration; no file mount or credential handoff file is used.

## Validation

Focused recovery and validator tests passed, including exact phase ordering, backup names only on the first PostgreSQL exec, no names on the second exec, promotion validation before restart, post-scrub validation before Polaris, and PostgreSQL quiescence on every pre-scrub failure. Disposable no-network pinned-image probing used dummy values only and no mounts; no AWS, active SQL mutation, marker cleanup, retry, artifact deletion, or cutover occurred during the repair.
