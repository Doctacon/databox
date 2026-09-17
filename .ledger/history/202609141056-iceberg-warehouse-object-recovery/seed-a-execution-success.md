# Stage-1 Seed-A Execution Success

## Status

Seed-A completed successfully after a fresh mutation-free plan, deterministic private validation, independent review, and one exact execution under the standing Seed-A authorization. The Seed-A plan is consumed and must not be rerun. Recovery-A damage and restoration have not started and remain separately gated.

## Exact private artifacts

- Consumed Seed-A plan: `.recovery/iceberg/aaf1c1a52043b1fd/seed-a.plan.json`
- Seed-A SHA-256: `82ba4e420b7e4cd209df9f88e5d6765bd867ef5c68fef808ecd5d6d17550a72e`
- Pending Recovery-A plan: `.recovery/iceberg/aaf1c1a52043b1fd/manifest.json`
- Recovery-A SHA-256: `70dcd0a6a6446e32009f1be05998ed88a8c5499618af1ed7d720387c71cae75b`
- Both files: mode `0600`, bounded below 1 MiB, inside the ignored mode-`0700` run directory

Private plan contents, target identifiers, credentials, object keys, object-version identifiers, role identifiers, and Docker image identifiers are not copied into ledger evidence.

## Confirmed cause and correction

Apache Polaris 1.7 bootstrap source confirmed that the generated bootstrap credentials belong to the reserved `root` principal, which receives `service_admin`. Because the drill requests `PRINCIPAL_ROLE:ALL`, assigning the run-owned catalog role through `service_admin` already reaches that principal; no redundant direct principal grant was added.

Polaris source also showed that internal catalogs enforce structured table locations. The prior implementation created the namespace at its catalog-derived location while explicitly creating the table at a sibling path. Polaris reports that location-policy violation as `ForbiddenException`.

A red-first regression test reproduced the call-shape defect. `LiveWarehouseDrillOperations.prepare(...)` now assigns the namespace an explicit run-owned `location` and creates the table beneath that namespace. The exact Stage-1 prefix, catalog allowed location, storage role, and IAM permissions remain unchanged. Independent review approved the correction with no findings.

## Successful result

The exact Seed-A execution produced:

- three deterministic point-A rows;
- five captured Iceberg graph objects;
- an exact logical graph digest and exact historical version bindings in the private Recovery-A plan;
- one retained run-owned network;
- one retained run-owned PostgreSQL volume containing the isolated Polaris catalog state;
- retained run-owned S3 version history, including the capability canary.

Final Stage-1 prefix validation proved that current objects were exactly the retained canary plus the captured graph and remained within the object-count and byte limits. Secret-bearing bootstrap, Polaris, and PostgreSQL containers were removed.

## Validation

Before execution:

- the location regression failed before the correction and passed afterward;
- 71 focused recovery-drill tests passed;
- 140 neighboring catalog/workflow tests passed;
- 16 selected recovery-infrastructure tests passed, with the known intentionally deleted-`.10x` assertion deselected;
- Ruff, formatting, Python compilation, secret scan, OpenTofu validation, and `git diff --check` passed;
- independent code review and independent private Seed-A plan review approved with no findings.

After execution, bounded read-only validation confirmed:

- the Recovery-A plan is schema 4 and exactly bound to its consumed Seed-A parent, current source/runtime/image pins, private settings, and retained-resource fingerprint;
- the Recovery-A plan is mode `0600` and bounded;
- all generated containers are absent;
- the retained network and PostgreSQL volume are detached and unchanged;
- no `seed-a-failure.json` exists;
- no `damage-started.json` exists.

An independent read-only Recovery-A review also approved the hash/mode/size, schema/scope/graph, parent/source/runtime/image/settings bindings, retained resources, pre-damage canary ordering, restore-only resume, prohibitions, secret-free evidence, and current no-damage state. That review establishes approval readiness only; it does not authorize execution.

## Next gate

Do not execute Recovery-A without separate explicit approval of the exact pending Recovery-A filename and SHA-256 above. Cleanup, negative enforcement testing, canonical resources, and Stage 2A/2B remain outside this approval.
