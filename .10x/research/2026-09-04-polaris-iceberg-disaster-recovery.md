Status: done
Created: 2026-09-04
Updated: 2026-09-04

# Polaris and Iceberg disaster-recovery architecture

## Question

How should Databox back up and recover its local Apache Polaris PostgreSQL catalog and AWS S3-backed Iceberg warehouse without introducing always-on proprietary backup software?

## Sources and methods

Inspected current repository authority:

- `compose.iceberg.yml`
- `docs/adr/0008-polaris-iceberg-raw-authority.md`
- `docs/runbook.md`
- `packages/databox/databox/config/settings.py`
- `.10x/decisions/manual-protected-iceberg-integration-gate.md`

Consulted official documentation on 2026-09-04:

- Apache Polaris relational JDBC metastore: https://polaris.apache.org/releases/1.7.0/metastores/relational-jdbc/
- Apache Polaris production configuration: https://polaris.apache.org/releases/1.7.0/configuration/configuring-polaris-for-production/
- Apache Polaris Helm persistence guidance: https://polaris.apache.org/releases/1.7.0/helm-chart/persistence/
- PostgreSQL 17 continuous archiving and PITR: https://www.postgresql.org/docs/17/continuous-archiving.html
- PostgreSQL 17 `pg_verifybackup`: https://www.postgresql.org/docs/17/app-pgverifybackup.html
- pgBackRest user guide and configuration reference: https://pgbackrest.org/user-guide.html and https://pgbackrest.org/configuration.html
- Apache Iceberg reliability: https://iceberg.apache.org/docs/latest/reliability/
- Apache Iceberg maintenance: https://iceberg.apache.org/docs/latest/maintenance/

The repository turbo-search skill was inspected from `HEAD` because its working-tree exposure file was already deleted before this investigation. Live retrieval was attempted against the Polaris, Iceberg, and PostgreSQL namespaces. The installed wrapper was stale, and the repository fallback reached turbopuffer but returned HTTP 401; no retrieved result was relied upon. Official pages were fetched directly instead.

## Findings

### Two recovery planes

Polaris stores all Polaris metadata in its PostgreSQL metastore. Iceberg separately stores table metadata JSON, manifests, data files, delete files, and snapshot history in object storage. Neither PostgreSQL nor S3 alone is a complete recovery strategy.

The governing consistency invariant is: a PostgreSQL catalog restored to time T must be able to read every Iceberg object referenced by its table pointers at T. Newer unreferenced objects can be reconciled later; missing referenced objects can make tables unreadable.

### PostgreSQL recovery

PostgreSQL base backups plus continuous WAL archiving support point-in-time recovery. Logical dumps do not contain the physical state needed for WAL replay, but remain useful as a secondary migration and inspection escape hatch. PostgreSQL warns that backup verification cannot prove operability; actual test restores remain necessary.

pgBackRest is an open-source implementation supporting online full, differential, and incremental backups, WAL archive checks, repository verification, retention, client-side encryption, S3-compatible repositories, PITR, and process-based renewable temporary credentials. It has no built-in scheduler, so Databox must own scheduling and failure visibility.

A five-minute RPO while Polaris is running requires WAL archiving plus a bounded archive timeout no greater than five minutes. A 60-minute RTO is an objective until a timed restore drill proves it.

### Iceberg recovery

Iceberg writes form atomic snapshots and retain rollback history until snapshots and referenced files are expired. Snapshot rollback repairs bad logical publication; restoring the entire Polaris metastore is not the first response to one bad table write.

Snapshot expiration and orphan-file deletion are destructive maintenance. Iceberg explicitly warns that orphan retention shorter than maximum write duration can corrupt tables. Backup/object recovery retention must be coordinated with any future maintenance policy.

### Current repository gap

The current Compose stack has one named PostgreSQL volume but no physical backup, WAL archive, independent backup repository, inventory, restore command, timed drill, or Iceberg object recovery copy. Loss of the volume can leave warehouse objects intact while losing complete catalog, security, and registration state.

## Ratified conclusions

The user ratified these targets and boundaries on 2026-09-04:

- catalog RPO: at most five minutes while Polaris is running;
- catalog RTO: at most 60 minutes;
- catalog PITR window: 30 days;
- Iceberg object recovery history: 45 days;
- two separate backup buckets in the same AWS account and `us-west-1` region;
- OpenTofu as the open-source declarative infrastructure manager;
- renewable short-lived AWS credentials through a credential process rather than long-lived keys;
- automation and a reviewable OpenTofu plan first; no live `tofu apply` in the first execution slice.

Same-account and same-region storage does not protect against account-wide compromise or regional loss. Separate bucket policies, roles, credentials, and deletion boundaries reduce but do not remove that residual risk.

## Conclusion

Implement pgBackRest physical backup and continuous WAL archive for the Polaris PostgreSQL control plane, a non-destructive separately permissioned recovery copy for Iceberg objects, declarative OpenTofu infrastructure, deterministic catalog inventories, and isolated restore drills. Keep logical dumps as secondary artifacts. Do not claim the RPO or RTO as proven until a live timed drill succeeds after an explicitly reviewed apply.
