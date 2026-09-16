# Stage 2C joint catalog and warehouse recovery plan

Status: first authorized execution stopped before point A and is contained; fresh execution requires new authorization

## Decision and endpoint

Stage 2C proves one coordinated recovery point across an isolated Polaris catalog and real versioned warehouse objects. It is complete only when exactly two run-owned Iceberg v2 tables are restored to the same point-A catalog pointers and exact point-A object graphs, schemas, and rows after both catalog and object state diverge at point B.

The campaign permits one recovery cycle and stops on the first success, uncertainty, or failure. Execution is capped at 20 minutes, excluding mandatory compensation/containment after damage. It never touches active or canonical catalog/table resources; never uses the deployed catalog-backup repository or its credentials; and never cuts over, broadens IAM, purges versions or markers, calls `DeleteObjectVersion`, or automatically cleans retained resources.

## Scope

- Generated 16-character run ID.
- Existing protected bucket only, under the already authorized IAM sandbox `integration/recovery/<run-id>/stage1/warehouse/`.
- Exactly one generated catalog and namespace and two generated tables.
- Exactly three deterministic point-A rows and one distinct point-B append per table.
- One generated Docker network and separate source, restored, and local POSIX pgBackRest repository volumes.
- Transient generated PostgreSQL, Polaris bootstrap, and Polaris containers only.
- Existing recovery-operator credentials and existing recovery storage role only; no root or catalog-backup credentials.
- Ignored private evidence under `/.recovery/catalog-warehouse-stage2c/<run-id>/`, directories mode `0700`, files mode `0600`.

## Limits

- At most 64 distinct S3 keys across both accepted point-A graphs and the capability canary.
- At most 32 MiB across accepted graph versions.
- At most 16 versions per key.
- One local full backup, one named restore target, one destructive cycle.
- No second attempt inside the same run after a causal failure.

## Sequence

1. Pin source/runtime/image/configuration and generated resource scope in a private no-replace plan before live effects.
2. Export and STS-verify one non-root recovery-operator credential set; verify bucket owner, region, versioning, 30-day noncurrent retention, and root-only protection controls; require an empty generated prefix and absent generated Docker resources.
3. Prove ordinary delete and exact-version promotion with one bounded run-owned canary.
4. Bootstrap isolated PostgreSQL and the real Polaris schema, create the generated catalog/namespace/tables, and commit/validate point A.
5. Capture each table's pointer, UUID, snapshot, schema, row digest, complete graph, and exact S3 VersionIds/ETags/sizes/content digests. Require disjoint table graphs and aggregate limits.
6. Create the local pgBackRest stanza, enable synchronous archival, take one full backup after point A, create a named target, and archive its containing WAL.
7. Append point B to both tables. Require changed pointers/snapshots/graphs/row digests, shared A/B dependencies, then commit and archive a relational B marker.
8. Freeze an exact private recovery plan. Persist delete intent before every ordinary delete and promotion intent before every exact-version copy.
9. Delete only exact point-A manifest/data dependencies that remain live in point B, leaves before parents. Prove both point-B tables fail solely on their own approved missing objects and every historical point-A source remains readable.
10. Contain source services, restore PostgreSQL into the separate volume at the named target, and prove A present, B absent, and promotion complete.
11. Promote exact point-A S3 versions, start real Polaris against the restored database, and validate both tables through fresh clients.
12. Require exact per-table point-A pointer/UUID/snapshot/logical graph/schema/row equality; preserve original historical sources; prove point-B-only objects remain unreferenced; contain all credential-bearing containers; publish a bounded private result and stop.

## Failure and interruption

Before deletion, stop and retain evidence. After delete intent exists, compensation is restoration-only: restore every journal-attributable point-A object, contain containers, preserve the primary and containment outcomes separately, and stop. A resumed run may complete restoration only and can never continue damage or claim a fresh success.

## Proof boundary

This would prove composition of local synthetic Polaris PITR with real exact-version S3 recovery for two tables. It does not prove canonical historical object reconstruction, deployed catalog-backup restoration (already covered separately by Stage 2B), arbitrary scale, unattended RPO, cutover, destructive cleanup, account/region loss, or recovery after retained versions expire.

## First authorized execution

The implementation passed focused unit and static review, then the first exact campaign stopped before point A. Docker represented an ephemeral loopback publish with an empty configured host port and the assigned numeric port only in runtime network state; the initial ownership validator incorrectly required the configured field itself to be numeric. No recovery plan or damage journal existed, no table/catalog fixture was created, and warehouse scope contained only the successful capability-canary history.

The failure receipt correctly retained `failed-uncertain` because its original containment pass rejected the same valid Docker representation. The validator now separately checks configured loopback intent, runtime numeric loopback binding, and exposed-but-unpublished runtime ports. Focused regressions pass. A separately recorded private containment correction confirms every generated container is absent, the generated network/volumes and evidence remain retained, and the S3 inventory is exactly one canary key with two versions and one delete marker. The failed plan is consumed and will not be replayed. A fresh campaign is outside the consumed authorization.
