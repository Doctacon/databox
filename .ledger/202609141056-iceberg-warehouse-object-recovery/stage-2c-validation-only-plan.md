# Stage 2C Retained-State Validation-Only Plan

Status: consumed; final coherence checks passed, then the command failed-contained on an invalid copied-ETag postcondition

## Purpose

Complete the one missing final coherence check against the already restored and contained third Stage-2C attempt. This is not a fourth recovery attempt, does not replay a consumed campaign plan, and cannot claim an uninterrupted recovery or the original 20-minute objective.

## Authorization boundary

The operator selected the bounded validation-only continuation. It may:

1. hash-bind the retained campaign plan, recovery plan, damage journal, terminal failure receipt, and restoration-correction receipt;
2. verify the retained journal still records deletes complete, break proof passed, exact catalog/object restoration complete, final validation pending, containment passed, and every damage node promoted;
3. bind the exact detached network/volume inspection projections and every bounded-prefix S3 version timeline before startup;
4. start only the isolated restored PostgreSQL volume with archival disabled;
5. prove the synthetic catalog marker contains A and excludes B and that PostgreSQL is promoted;
6. start only the isolated restored Polaris service;
7. read and compare both restored tables' exact pointer, UUID, snapshot, graph, schema, and deterministic rows against point A;
8. prove point-B-only objects remain unreferenced and the exact prefix version timelines are unchanged; and
9. remove every generated credential-bearing container while retaining the exact prefix, network, volumes, and private evidence.

It must not create a prefix, start source/bootstrap resources, run pgBackRest backup or restore, write/delete/copy/promote S3 objects, mutate the damage journal, touch canonical resources or active topology, alter IAM or bucket controls, cut over, clean retained resources, or claim RTO/uninterrupted recovery.

## Execution contract

- Preparation publishes one mode-`0600` validation plan under the existing private run directory and binds every retained artifact, detached Docker resource projection, and S3 version timeline by SHA-256.
- Execution is one-shot with a ten-minute objective plus existing per-command timeouts. An independent watchdog removes credential-bearing containers when that objective expires; this is not a hard whole-process or RTO claim.
- A start receipt is written before the first container effect. If execution is interrupted after that receipt, re-entry may contain only; it cannot repeat validation. That containment path uses the immutable plan's exact Docker ownership binding and does not depend on plan freshness, current source/images, AWS credentials, or bucket reads.
- Success is recorded separately as `validation-result.json`. The original failure receipt, correction receipt, damage journal, and absent original result remain unchanged.
- Any failure attempts containment, rechecks exact retained-resource and prefix fingerprints, writes only a sanitized validation failure receipt, and stops. A containment or fingerprint failure remains uncertain and cannot be retried.
- Private identifiers, object keys, version IDs, image IDs, account/bucket details, and credentials remain outside tracked evidence.

## Permitted claim after success

A successful run may establish eventual coherent point-A recovery for the retained failed attempt. It may not establish that the original automation completed successfully, that recovery was uninterrupted, or that the 20-minute recovery objective was met.

## Outcome

The one authorized invocation is consumed and was not replayed. Promoted-version checks and the exact two-table restored-Polaris validation passed. The command then stopped `failed-contained` at prefix inventory because it incorrectly compared four promoted objects' new S3-copy ETags with their historical source ETags. Read-only diagnosis proved the exact key set and timelines were unchanged and found no size, byte, version-cardinality, delete-marker, or historical-source mismatch. The maintained postcondition now uses exact bytes and recorded source/promoted VersionIds instead of cross-version ETag equality. An append-only adjudication preserves the qualified result: eventual coherent recovery is proven, but the command/workflow did not pass and no RTO or uninterrupted-recovery claim is made.
