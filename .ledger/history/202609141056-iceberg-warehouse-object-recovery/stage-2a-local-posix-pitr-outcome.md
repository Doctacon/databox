# Stage 2A local POSIX catalog PITR outcome

Status: bounded proof passed

## Scope

The authorized campaign remained fully local and run-owned. It used pinned local PostgreSQL/pgBackRest and Polaris images, a POSIX pgBackRest repository in a generated Docker volume, synthetic catalog state, generated Docker resources, and ignored private evidence. It did not contact AWS, use the deployed catalog-backup repository or role, inspect or mutate active services, read canonical catalogs/tables, access warehouse objects, change IAM, cut over, or clean up retained evidence.

## Proof

The maintained workflow and its final fresh run:

1. Bootstrapped the actual Polaris relational schema in isolated PostgreSQL.
2. Wrote deterministic synthetic point-A state.
3. Created a local pgBackRest stanza and full backup with synchronous WAL archival.
4. Created a named recovery target, then committed distinct point-B state and archived later WAL.
5. Restored into a separate generated PostgreSQL volume and promoted at the named target.
6. Proved point A was present, point B was absent, and PostgreSQL was no longer in recovery.
7. Started the real Polaris service against the restored database and passed its internal readiness check.
8. Removed credential-bearing containers while retaining the generated network, source volume, restored volume, POSIX repository volume, and private evidence.

Private mode-`0600` evidence records `pass`, `local-posix`, `A-not-B`, PostgreSQL promotion, Polaris readiness, container absence, and retained-resource categories.

## Contained corrections

An initial disposable run selected a timestamp too close to the recorded backup stop and failed before restore; it is preserved with a sanitized contained-failure receipt. A later run restored correctly, then exposed a generated local client secret in operator output; its private evidence is explicitly retired and non-authoritative, its containers are absent, and its resources remain preserved. The maintained workflow now suppresses child output, mounts the retained POSIX repository/config during recovery startup, checks Polaris readiness on its management port, creates the stanza before enabling archival, and distinguishes confirmed container absence from an unverifiable Docker API. A final fresh run passed with sanitized stdout and zero stderr bytes. No cloud or authoritative state was involved.

## Boundary

This proves local POSIX pgBackRest PITR correctness for synthetic Polaris state. The maintained command is `task catalog:recovery-stage2a`; behavioral tests cover fail-closed containment, and independent review reports no critical, high, or medium findings. It does not prove the deployed S3 catalog-backup repository, authenticated WAL catch-up, canonical catalog validation, production RPO/RTO, cutover, or cleanup; those remain Stage 2B or later work. Both the original bounded proof and this productization pass completed within their respective ten-minute limits.
