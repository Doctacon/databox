Status: recorded
Created: 2026-09-04
Updated: 2026-09-04
Relates-To: .10x/tickets/2026-09-04-add-pgbackrest-catalog-protection.md

# Catalog PostgreSQL image packaging proof

## Result

The first local build proved that Debian's current PostgreSQL apt repository supplies pgBackRest 2.59.1, not the configured 2.55.1, so the Dockerfile's exact-version assertion correctly failed. The pinned image/configuration was narrowly updated to the available 2.59.1 and rebuilt successfully as `databox-polaris-postgres:17.6-pgbackrest-2.59.1`, local image ID `sha256:719f95efb02fbeb825faca9cbc02d22b4607c93368e4e7fd1dcc9c0e6b7b9a96` (`linux/arm64`).

A disposable `docker run --rm --network none --user postgres` inspection observed:

- `uid=999(postgres) gid=999(postgres)`;
- `pgBackRest 2.59.1`;
- `postgres (PostgreSQL) 17.6 (Debian 17.6-2.pgdg12+1)`;
- readable `/etc/pgbackrest/pgbackrest.conf` with fixed `repo1-path=/polaris`;
- executable and shell-valid `/usr/local/bin/run-pgbackrest`;
- executable readiness script whose missing-setting path ran as `postgres`;
- no `aws` executable.

## Procedure and limits

Build used `docker-compose -f compose.iceberg.yml build postgres` with inert placeholder interpolation values. Inspection used no network, volume, port, AWS/provider credential, stanza, WAL, backup, restore, or application service. Docker pulled public base/package artifacts and mutated only the local image/cache. This proves packaging, not repository access or recovery behavior.
