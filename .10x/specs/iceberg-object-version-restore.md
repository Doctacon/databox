Status: draft
Created: 2026-09-10
Updated: 2026-09-10

# Draft: controlled Iceberg object-version restore

> Record recovery (2026-09-14): restored from the verified private snapshot on `feature/warehouse-file-recovery`, based on merged main `8321475dda7b3a041e8dd8efe668c923cf723fb5`. This preserves the captured contract, not new implementation or AWS authority.
> Original working-artifact SHA-256 (NOT this recovered/redacted text): `61c826c9e0b257d3b64e69793d53580845fcca70c6bb99fba118aa2c2a66cdfb`; source revision `027af8b4271d60ffc193967d092b5d2497af13ad` plus the captured uncommitted variant.
> Exact private original: `~/Private/databox/recovery-evidence/2026-09-11T235551Z-05aef1141954/`; `manifest.json` entry `source_kind=uncommitted-working-tree`, `source_path=.10x/specs/iceberg-object-version-restore.md`. Deployment identifiers use the approved publication placeholders; generic principal labels are retained.

## Purpose and status

Define the recovery workflow needed to turn retained S3 versions into a demonstrated Iceberg-table recovery capability. The user requested tickets for recovery tooling and a safe proof after selecting versioning/30-day retention. They have not ratified the selection, destination, permission, or failure/cleanup contract of a restore command. This draft MUST NOT govern implementation, tests asserting those choices, or live mutation until the blockers below are answered and the spec is activated.

## Established boundaries

- `.10x/specs/iceberg-warehouse-version-retention.md` and `.10x/specs/iceberg-writer-version-delete-denial.md` own storage and deletion-control behavior; this draft does not expand their permissions.
- Catalog PITR and the existing read-only validator are governed by `.10x/specs/polaris-catalog-continuity.md`. Its existing command cannot be assumed to restore S3 objects.
- The initial proof is intended to use disposable test data rather than damage an authoritative table. No production cutover, source refresh, automatic cleanup, or new credential grant is authorized.
- The complete selected Iceberg snapshot must eventually have a coherent catalog/metadata pointer and readable manifest lists, manifests, data files, and applicable delete files. Recovering one object alone is not table-level proof.

## Unresolved contract and recommendations

These are candidates, not active acceptance criteria:

1. **Recovery selection:** explicit reviewed object keys/version IDs, one operator-selected table snapshot, or a selected catalog-PITR target? Recommend starting with one selected table/snapshot and explicit evidence of every required object/version rather than guessing from the newest filename or S3 listing.
2. **Restore destination and current state:** restore missing/overwritten objects to their original keys as new versions, or copy to an isolated prefix with Iceberg path rewriting and separate registration? Recommend a wholly disposable table for initial proof; production in-place versus relocated recovery remains a separate choice. Copying metadata alone does not rewrite its absolute object references.
3. **Operator authority:** which existing authenticated identity may list/read retained versions and write the target, and which catalog permissions are needed? Recommend separately reviewed short-lived operator authority, never a new long-lived backup key or a broad grant to `databox-lake-user`. No particular role or grant is approved yet.
4. **Conflicts and partial failure:** what is a valid precondition, how are concurrent writers fenced, how are ambiguous/missing versions handled, and can an interrupted operation resume? Recommend read-only preview and explicit authorization of exact writes, fail closed on ambiguity, no destructive overwrite/purge, and preserved bounded diagnostics. Exact CLI, idempotency, retry, and evidence interfaces are not yet ratified.
5. **Drill lifecycle:** exact isolated catalog/table/prefix, fixtures, allowed overwrite/delete operations, expected row/snapshot assertions, write coordination, and retention/cleanup of run-owned artifacts need approval. Recommend synthetic data with exact expected rows and no automatic cleanup; cleanup is not implied by a successful drill.
6. **Operational ownership:** identify the human responsible for invocation, reviewing the plan, validating results, failure handling, and any cutover/cleanup. No scheduler, notification recipient/cadence, escalation service, or automatic recovery policy is selected.

## Record ownership

- Workflow shaping/implementation: `.10x/tickets/2026-09-10-build-iceberg-object-version-restore.md` (blocked).
- Live table proof: `.10x/tickets/2026-09-10-prove-iceberg-object-version-recovery.md` (blocked).
- Aggregate plan: `.10x/tickets/2026-09-10-protect-iceberg-warehouse-object-versions.md`.

Before either blocked ticket becomes executable, ratify the missing contract, split additional independently governed surfaces if the design requires them, activate the focused specification(s), and derive concrete acceptance scenarios. Do not inherit the rejected 45-day replica design or claim a 30-day complete-table RPO/RTO from S3 lifecycle settings alone.
