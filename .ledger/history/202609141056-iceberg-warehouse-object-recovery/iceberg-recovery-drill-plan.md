Status: Stage 1 implemented and independently reviewed; no private plan generation or live drill authorized
Created: 2026-09-14
Updated: 2026-09-14

# Stage-1 Iceberg warehouse object-recovery drill

## Decision and proof boundary

Implement one manual, live-ready Stage-1 proof for a uniquely named synthetic Iceberg v2 table. The proof uses an isolated run-owned PostgreSQL/Polaris stack and the existing protected warehouse bucket under:

```text
integration/recovery/<run-id>/stage1/warehouse/
```

It proves that exact retained S3 versions can reconstruct the complete accepted point-A graph while the isolated Polaris catalog pointer remains intact. It does not prove catalog PITR, negative policy enforcement, arbitrary-table recovery, recovery after lifecycle expiration, bucket/account recovery, or cleanup.

Stage 2A/2B catalog-PITR work is deferred until Stage-1 evidence exists and is accepted. The active Polaris service, canonical catalogs/tables, `warehouse/`, catalog-backup repository, and authoritative data are outside Stage 1.

## Authorization model

The CLI deliberately has only two commands:

```text
iceberg_recovery_drill.py prepare
iceberg_recovery_drill.py execute --manifest <private-plan> --sha256 <approved-hash>
```

There are still two distinct approvals:

1. `prepare` emits `.recovery/iceberg/<run-id>/seed-a.plan.json` without AWS, S3, Polaris, Docker create/start/remove/build/pull, catalog, or table mutation.
2. `execute` consumes only that exact Seed-A filename and SHA-256. It seeds the isolated stack/table and, only after secret-bearing containers are removed, emits `.recovery/iceberg/<run-id>/manifest.json` as Recovery-A.
3. A second `execute` consumes only the separately reviewed exact Recovery-A filename and SHA-256.

Plans expire after six hours. An expired Recovery-A cannot begin damage. If an exact mode-`0600` journal proves damage already began under that Recovery-A hash, expiry does not strand restoration: re-entry is restore-only and can never continue deleting.

No command logs in, replans, retries, falls back to root, or infers approval. The private plan and supplied SHA-256 are re-read and compared before dispatch. First publication of every plan and initial damage marker is atomic no-replace, so a concurrent receipt can never be overwritten. Settings, source/runtime bindings, parent-plan relationship, and generated names are revalidated.

## Generated scope and hard limits

One program-generated 16-hex-character run ID derives every accepted name:

- one Docker bridge network;
- one PostgreSQL volume;
- transient PostgreSQL, Polaris-bootstrap, and Polaris containers;
- one Polaris catalog, namespace, and table;
- one S3 warehouse prefix;
- one private evidence directory.

Reject operator-supplied keys, path traversal, symlinks, canonical names, sibling prefixes, external URIs, or a bucket mismatch. The live evidence root is fixed at ignored `/.recovery/iceberg`; run directories are mode `0700`, files mode `0600`, atomically replaced/fsynced, and no private JSON may exceed 1 MiB.

The accepted point-A fixture is exactly three deterministic rows, Iceberg format v2, one snapshot, `main` only, no live delete files, at most 64 graph objects, and at most 32 MiB total version-specific content. Each key has bounded version history and sufficient headroom. Limits are checked before object-body reads and again while hashing.

## Mutation-free Seed-A planning

`prepare` reads configuration and performs local read-only inspection only. Seed-A pins:

- generated scope and all resource names;
- expected region, non-secret bucket/storage configuration digests, and one caller-identity digest;
- exact installed Docker image IDs, entrypoint, command, default environment, user, and working directory;
- Docker client/server runtime fingerprint;
- Git revision, script SHA-256, Python, PyIceberg, and PyArrow versions;
- deterministic data contract, maximum counts/sizes, allowed operations, prohibited operations, and containment/preservation behavior;
- an HMAC binding derived from a private run secret without storing generated credentials.

Image inspection never pulls or builds. Preparation writes only the private plan and returns its path/hash plus non-sensitive generated identifiers.

## Seed-A execution

Before mutation, exact approved Seed-A is revalidated against current settings, source/runtime/image pins, and approval time. One explicit pre-authenticated non-root AWS profile must resolve to the configured storage role's AWS account; it may be an IAM user or assumed role. Its caller digest uses the durable IAM authorization principal rather than a refreshable role-session ARN. The profile is resolved once to temporary credentials, that exact credential environment is STS-verified, and the same set is reused for every direct S3 call and Polaris bootstrap. The storage role remains independently plan-bound for Polaris, and the same pinned operator performs ordinary delete and exact-version recovery. Ambient AWS providers and HTTP proxies are stripped. This proves reconstruction, not separate-principal privilege separation; that stronger proof is out of scope for the selected solo workflow.

Read-only preflight requires:

- exact account/region and expected bucket owner;
- Enabled bucket versioning;
- the single bucket-wide 30-day noncurrent lifecycle rule;
- the exact root-exception/two-Deny retention-control policy;
- an empty generated S3 prefix;
- no generated Docker resource collisions.

Seed-A then creates only its generated Docker network and PostgreSQL volume. The isolated stack publishes Polaris only on an ephemeral loopback port and never reads the active Polaris URL. Generated PostgreSQL/Polaris credentials and temporary AWS credentials stay in memory and enter bounded child processes through stdin, never plans, command arrays, Docker environment configuration, or output.

A separate-key capability canary proves the pinned operator can put/ordinary-delete and exact-version read/promote. Recovery-A repeats it with the newly exported, STS-verified credential set after fresh point-A validation and immediately before no-replace damage-marker publication; restore-only re-entry skips it. The canary never deletes a version or marker. The isolated catalog is provisioned with default and allowed location equal to the exact run warehouse URI, then receives the deterministic table.

Fresh PyIceberg clients traverse the exact catalog-rooted metadata, manifest-list, manifest, and data graph. Each catalog-loaded FileIO must contain nonempty vended access, secret, and session credentials, and every direct FileIO access is prefix-fenced before delegation. Point A records exact opaque source VersionIds, ETags, sizes, content SHA-256 values, table UUID, metadata location, snapshot, schema, row digest, and logical graph digest.

All secret-bearing containers are stopped/removed before Recovery-A is written. Only then is the detached network/volume state fingerprinted. Recovery-A records that fingerprint, the exact Seed-A parent hash, source/runtime binding, catalog-management fingerprint, point-A graph, and exact validation contract. Network, PostgreSQL volume, catalog state, S3 versions, and private evidence remain.

## Docker ownership and interruption containment

Labels alone never authorize reuse or removal. Recovery-A revalidates the full retained network/volume inspection fingerprint and semantic driver/scope settings. Before reuse it inventories all running and stopped containers for:

- each exact generated container name;
- every attachment to the retained network;
- every consumer of the exact PostgreSQL volume.

A recoverable remnant must match the generated name, full container ID across list/container/network evidence, pinned image ID, exact sleeper entrypoint/command, pinned default environment/user/working directory, exact recovery-plan labels, restart/privilege/read-only-root settings, exact network and alias, exact PostgreSQL volume mount, and loopback-only Polaris port binding. A bootstrap remnant is impossible in Recovery-A and is refused. Unknown network attachments, volume-only consumers, changed resources, ambiguous inventory, or any configuration mismatch block removal and reuse.

Only fully validated PostgreSQL/Polaris remnants may be force-removed. Inventory is completed before the first removal, and the volume is rechecked unused afterward. No code removes the network or volume. Exact remnant containment occurs before Recovery-A expiry rejection and before any AWS/profile dependency, so an expired journal-less retry still contains approved credential-bearing remnants and then stops.

## Recovery-A execution

Recovery rechecks the exact Recovery-A hash, parent Seed-A, settings, source/runtime/image pins, retained resources, identities, bucket controls, catalog fingerprint, table pointer, complete current point-A graph, source-version availability, and content before damage.

Immediately before creating `damage-started.json`, it performs a fresh point-A validation. Immediately before each ordinary delete it rechecks that the current key still has the exact approved source VersionId/content. Damage orders leaves before parents and metadata root last.

The per-key journal is atomically replaced/fsynced and records:

- exact run/manifest binding and ordered approved key/source-version list;
- pending phase;
- delete intent/result and returned delete-marker VersionId;
- promotion intent/result and returned promoted VersionId.

Once the journal exists, re-entry is restore-only. If a delete fails after intent, only an exact expected predecessor/delete-marker state can be attributed; unknown versions or markers fail closed. Partial damage never continues to another delete. Approved damaged keys are restored and the drill exits with the distinct interrupted status rather than claiming a pass.

Break proof requires the isolated catalog/namespace to remain healthy, every damaged current key to be an expected marker, every exact historical source to remain independently readable, and a fresh table access to fail only because an exact approved graph key is missing. Generic missing-file, auth, catalog, or network failures are not accepted.

Restoration uses exact `CopyObject` source key and recorded source VersionId with source ETag precondition, expected owner fencing, and no destination rewrite. Each promotion must create a new current version with exact expected bytes while the historical source remains. It never calls `DeleteObjectVersion` or removes a marker.

Final fresh-client validation requires the exact catalog configuration fingerprint, table UUID, metadata pointer, snapshot, schema, logical graph/content, sorted deterministic rows/count/digest, source versions, and journal-attributable promoted current versions.

## Preservation and cleanup boundary

Normal success and caught failure remove transient secret-bearing containers. The run-owned network, PostgreSQL volume, generated catalog state, private plans/journal, S3 versions, delete markers, and restored current objects remain for evidence and a later separately reviewed cleanup design.

Cleanup is intentionally unimplemented and never automatic. A future cleanup may use only ordinary current-object deletes and exact generated resource ownership. It may not purge versions, remove markers, shorten lifecycle, change bucket controls, touch canonical resources, or discard unresolved evidence.

## Validation completed without live access

The implementation is in:

- `scripts/platform/iceberg_recovery_drill.py`
- `tests/platform/test_iceberg_recovery_drill.py`
- `Taskfile.yaml`
- `.env.example`
- `docs/runbook.md`

Local validation covers plan parsing/dispatch, the single-profile/same-account identity contract, durable assumed-role identity binding, one-time exported-credential reuse, fake Seed-A and Recovery-A execution, exact journal resume, expired restore-only behavior, expired/no-journal pre-AWS containment, aggregate limits, prefix/transport/identity fencing, Docker command secrecy, retained-resource fingerprinting, unknown network/volume consumers, exact container ownership, and the Apache Polaris 1.7 direct catalog response shape.

Ruff and 41 focused tests pass. Independent bounded security/intent review is clean after the reported interruption and Docker ownership issues were fixed. One earlier authorized mutation-free `prepare` attempt refused before Docker inspection because its then-required profile settings were absent. A later authorized `prepare` emitted an exact reviewed Seed-A plan; its one approved execution attempt then failed before first resource creation because container inventory used Docker's invalid `{{.Name}}` field rather than `{{.Names}}`. Immediate inspection found no generated Docker/S3/catalog state. The resource-specific format fix has a red-first regression test, 140 neighboring platform tests also pass, and the old plan is preserved but rejected as stale.

## Remaining gates

1. Obtain explicit authorization before invoking even mutation-free `prepare`, because it performs local Docker inspection and writes private evidence.
2. Generate one Seed-A plan, privately inspect its exact filename/content/hash, and stop.
3. Execute Seed-A only after explicit approval of that exact filename/SHA-256.
4. Privately inspect emitted Recovery-A and stop again.
5. Execute damage/restoration only after a separate explicit Recovery-A filename/SHA-256 approval.
6. Record only sanitized counts, hashes, statuses, and timings in tracked ledger evidence.
7. Design negative policy testing, cleanup, and any Stage 2A/2B work as separate authorized plans after Stage-1 evidence is accepted.

Primary protocol references:

- [Apache Iceberg table specification](https://iceberg.apache.org/spec/)
- [Apache Polaris 1.7 management API](https://polaris.apache.org/releases/1.7.0/unreleased/polaris-management-service/)
- [S3 ListObjectVersions](https://docs.aws.amazon.com/AmazonS3/latest/API/API_ListObjectVersions.html)
- [S3 CopyObject](https://docs.aws.amazon.com/AmazonS3/latest/API/API_CopyObject.html)
- [S3 delete markers](https://docs.aws.amazon.com/AmazonS3/latest/userguide/DeleteMarker.html)
