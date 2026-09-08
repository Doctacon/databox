Status: recorded
Created: 2026-09-08
Updated: 2026-09-08
Relates-To: .10x/tickets/2026-09-04-build-isolated-catalog-recovery-drill.md

# Restored Polaris primary-credential compatibility proof

## Authorization and preconditions

The user authorized replacing only isolated PostgreSQL container `databox-polaris-recovery-probe-20260908_214022`, preserving its restored volume, attaching it and one restored Polaris container to a dedicated bridge with no host ports, starting no bootstrap service, and proving Polaris accepts the existing long-lived primary-warehouse credentials with a blank session token.

Before mutation, active PostgreSQL and Polaris were healthy with start times `2026-09-08T21:38:31.476511987Z` and `2026-09-05T16:26:22.471908317Z`; active database size was `8309907`; `.env` was mode `0600`; required PostgreSQL, Polaris-client, primary access/secret, and region values were nonempty under `python-dotenv`; primary session token was blank; and the isolated database reported promoted recovery, archiving off, before marker 1, after marker 0. Successful volume `databox_polaris_recovery_probe_20260908_214022` had the expected nonempty recovery ownership label.

Secret values were passed only through child-process environment by variable name and were not printed or written to evidence. No backup-role credential was used.

## Isolated services

The prior isolated PostgreSQL container was stopped and removed; its volume was never removed. Dedicated bridge `databox_polaris_recovery_validation_20260908_214022` was created. PostgreSQL was recreated under the same container name from pinned image `databox-polaris-postgres:17.6-pgbackrest-2.59.1`, as `postgres`, with only the successful recovery volume mounted read-write, no ports, restart policy `no`, `archive_mode=off`, and TCP enabled only on the dedicated bridge. It remained promoted and preserved exact before=1/after=0 marker state.

Container `databox-polaris-recovery-validation-20260908-214022` started from `apache/polaris:1.7.0` on only that bridge, with relational JDBC to isolated PostgreSQL, restored realm `POLARIS`, no mounts, no host ports, and restart policy `no`. No recovery bootstrap/admin container exists. Its environment contained nonempty primary access/secret values, exact region, and explicitly blank `AWS_SESSION_TOKEN`; it contained zero backup/pgBackRest environment variables. The health endpoint became healthy and sanitized logs contained no missing/blank/invalid AWS credential error.

## Restored API and AWS SDK proof

Container-local OAuth using restored client credentials succeeded without exposing the token. Read-only Iceberg REST calls returned config and 9 namespaces with 29 tables:

- `raw_gbif`, `dlt_polaris_probe`, `raw_noaa`, `raw_xeno_canto`, `raw_usgs`, `raw_usgs_earthquakes`, `raw_ebird`, `raw_usfws`, `raw_avonet`;
- representative table `raw_gbif.occurrences` loaded successfully with `X-Iceberg-Access-Delegation: vended-credentials`.

The load response contained metadata, metadata location, config, and storage-credentials. Only response structure was inspected: both config and storage-credentials contained access-key, secret-access-key, session-token, and expiration fields; no values were printed or persisted. Successful vended temporary credential generation proves restored Polaris's AWS SDK accepted the long-lived `databox-lake-user` base access/secret with explicitly blank session token. No table/catalog/warehouse write or all-table validation ran.

An initial local validation expression had a Python syntax error and made no request. A subsequent structural assertion looked only in the top-level config for a differently spelled secret-key field and exited locally after the already-successful load response; a final value-free shape check verified both credential-bearing sections. These were read-only harness corrections, not service retries or mutations.

## Active-state proof and retained artifacts

After proof, active PostgreSQL and Polaris retained their exact precondition start times and remained healthy; active database size remained `8309907`, and the probe relation remained absent. No active container or volume was mounted, stopped, or restarted. No recovery or S3 object, network, volume, or container was deleted beyond the explicitly authorized replacement of the isolated PostgreSQL container object.

The dedicated bridge and isolated PostgreSQL/Polaris containers remain running for the next validation slice. All prior recovery artifacts remain preserved.

## Limits

This proves restored Polaris startup, restored OAuth/catalog enumeration, representative load-table metadata, and blank-primary-session-token AWS credential vending. It does not prove every registry-derived table, metadata object/snapshot readability, representative data-file reads, production cutover, exact RPO/RTO, or least-privilege policy shape for `databox-lake-user`.
