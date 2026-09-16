# Stage 2C Joint Catalog-and-Warehouse Recovery Outcome

Status: not proven; the authorized three-attempt envelope and its one damage-bearing cycle are exhausted

## Authorization boundary

The fresh campaign allowed up to three new plans and execution attempts, but at most one attempt could cross the durable damage-journal boundary. Pre-damage failures could be corrected and retried only after containment and focused validation. The campaign had to stop after success, any post-damage failure or uncertainty, uncertain containment, prohibited scope drift, or exhaustion of the three attempts. Consumed plans could not be replayed.

All three attempts used distinct generated prefixes, catalogs, Docker resources, exact plan hashes, and private evidence directories. Existing canonical services/tables, the deployed catalog-backup repository and credentials, IAM, bucket controls, and cutover remained prohibited.

## Attempt outcomes

### Attempt 1: contained before the recovery target

The first fresh attempt stopped during point-A handling with a Polaris `ServerError`. It had created both deterministic one-snapshot object graphs but had not created a recovery plan or damage journal. Containment passed and all generated containers were absent. Read-only inventory showed only the capability canary and the two point-A graphs.

The bounded correction added safe retry only for catalog GET operations and exact reconciliation for ambiguous append responses. Ambiguous writes are never repeated. Reconciliation now requires the same table UUID, a changed metadata pointer, the exact predecessor metadata in lineage, the expected snapshot count and parent, and deterministic rows. `CommitStateUnknownException`, server errors, and service-unavailable responses are handled only through this read-side reconciliation. Polaris REST requests also have a mandatory finite timeout.

### Attempt 2: contained before point-B mutation

The second attempt established point A and its local pgBackRest target, then stopped at the start of point B with another `ServerError`. No point-B objects, recovery plan, damage journal, or deletes existed. Containment passed.

The evidence localized the failure to the first post-backup catalog read. Enabling PostgreSQL archival restarts PostgreSQL, invalidating the existing Polaris JDBC pool. The correction now removes and restarts only the exact campaign-owned source Polaris container after backup/restore-point completion, then discards the cached gateway so the next catalog client binds the replacement loopback endpoint. Tests prove this occurs after the backup, restore point, WAL switch, and archive check.

### Attempt 3: damage cycle consumed; proof stopped

The third attempt reached the durable damage boundary. It created both point-A and point-B states, wrote the exact recovery plan and journal, ordinarily deleted four selected dependencies across the two tables, and passed the table-specific break proof. Object restoration later completed by promoting all four exact historical sources.

Catalog restoration stopped before pgBackRest restore because the ownership validator expected Docker `--network none` to produce an empty runtime network map. Docker instead reports the built-in `none` network with no IP address or gateway. The same mismatch prevented the automatic containment pass, so the terminal receipt correctly recorded catalog restoration and containment as uncertain. No further success-path execution or fresh attempt occurred.

The validator now accepts only the exact built-in `none` shape: host network mode `none`, no campaign-network attachment, a single `none` runtime network, no aliases/DNS names, and no IPv4/IPv6 address, gateway, or MAC address. It continues to reject any connected restore helper.

Mandatory post-failure correction then:

1. removed the exact owned restore helper;
2. restored PostgreSQL to the recorded point-A target;
3. proved the synthetic catalog marker contained A and excluded B and that PostgreSQL was promoted;
4. confirmed object restoration was complete;
5. removed every generated container; and
6. retained the generated network, volumes, prefix, and private evidence.

Independent read-only verification found all ten point-A graph objects at their exact expected bytes, all four damage nodes promoted from their recorded historical sources, and journal milestones for catalog restoration, object restoration, and containment complete. This correction restores and contains the failed drill; it does **not** convert the terminal failure into Stage-2C success.

## Result

Stage 2C remains **not proven**. The successful-path final Polaris validation did not run after the post-damage failure, so there is no valid claim that both restored catalog pointers, UUIDs, snapshots, logical graphs, schemas, and deterministic rows jointly agreed at point A. No fourth attempt is authorized or running.

The failure did not mutate canonical resources, active topology, IAM, bucket controls, or the deployed catalog-backup repository. It did not cut over, call `DeleteObjectVersion`, remove delete markers, or automatically clean retained evidence/resources.

Private terminal and correction evidence remains mode `0600` under the ignored recovery root. The current regression suite passes 270 relevant tests plus Ruff, formatting, compilation, secret scanning, and diff checks. Cleanup remains separately gated.
