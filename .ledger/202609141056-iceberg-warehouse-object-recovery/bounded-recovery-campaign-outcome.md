# Bounded Recovery Campaign Outcome

## Disposition

The campaign is **hard-stopped without an end-to-end Recovery-A proof**. Both authorized new damage cycles were consumed. No third cycle, replay, cleanup, IAM expansion, canonical-data access, or Stage 2 work is authorized.

## Validated instrumentation

Before the campaign, the drill gained transactional schema-2 milestones for deletes, break proof, restoration, final validation, and containment; append-only sanitized failure receipts; restoration after dangerous journal failures; restore/audit-only handling for legacy schema-1 evidence; and a read-only diagnosis command. A direct regression proves legacy evidence restores objects and then exits `legacy-evidence / inconclusive` rather than passing.

After the first new cycle failed at break proof, the causal seam was tightened and re-reviewed. Break proof requires:

1. healthy catalog namespace access;
2. an exact approved full-S3-location `FileNotFoundError` from a new scan of the point-A table, directly or through a bounded cause chain;
3. a direct `FileNotFoundError` for that same location through the cached, vended, prefix-fenced FileIO; and
4. every expected delete marker and exact historical source version to verify.

Generic catalog, authentication, network, key-only, URI-continuation, and mismatched-object errors fail closed.

Validation passed with 84 focused recovery-drill tests, 140 neighboring catalog/workflow tests, and 16 selected infrastructure tests. Ruff, formatting, Python compilation, OpenTofu formatting/validation, diff checks, and the credential-shaped diff scan passed. Independent review found no critical, high, or medium findings before the final cycle.

## Cycle outcomes

### First new cycle

- Deletes: complete
- Break proof: failed
- Restoration: complete
- Final validation: pending
- Containment: passed
- Five graph objects: restored as verified promoted versions

The plan is frozen and must not be replayed.

### Second and final new cycle

A fresh current-source-bound Seed-A and Recovery-A pair passed deterministic and independent review. Recovery-A failed closed at break proof with sanitized category `missing-query-unexpected-error`.

Durable evidence records:

- Deletes: complete
- Break proof: failed
- Restoration: complete
- Final validation: pending
- Containment: passed
- Node phases: five promoted, none pending or partially restored

Read-only diagnosis independently verified:

- all five current promoted objects match approved bytes;
- all five exact historical source versions remain intact;
- prefix inventory is exact; and
- retained isolated resources match their fingerprint.

Catalog and query readback were intentionally not checked by diagnosis. They remain unproven and cannot be inferred from object-level restoration.

## What is proven

- Same-bucket version history retained every required historical source version through both bounded damage cycles.
- Exact-version promotion restored every approved graph object in both cycles.
- Compensation and containment completed after both break-proof failures.
- Failure evidence is durable, bounded, append-only, and sanitized.

## What is not proven

- A valid break proof for the synthetic Iceberg table.
- Final catalog pointer, graph, schema, and three-row query validation after restoration.
- A complete Stage-1 end-to-end recovery proof.

## Retained evidence

Private plans, markers, receipts, object-version evidence, isolated networks, PostgreSQL volumes, and catalog state remain retained under the ignored private evidence area. Secret-bearing containers are absent. Cleanup remains separately gated and unauthorized.
