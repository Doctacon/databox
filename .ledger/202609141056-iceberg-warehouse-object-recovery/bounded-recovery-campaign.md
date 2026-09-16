# Bounded Recovery Campaign

## Authorization

The user authorized one bounded diagnostic and recovery campaign after the first Recovery-A attempt returned a safe refusal. This campaign permits local causal fixes, tests and independent review; read-only retained-state diagnosis; temporary diagnostic Docker resources and their removal; internally generated and reviewed private plans; restore-only continuation; and at most **two new isolated damage cycles**.

The campaign does not authorize canonical catalog or warehouse access, IAM changes, negative enforcement tests, existing retained-evidence cleanup, or Stage 2 work.

## Attempt budget

- New damage cycles authorized: 2
- New damage cycles used: 2
- New damage cycles remaining: 0
- The legacy schema-1 attempt predates this campaign and is frozen as inconclusive. It must never be replayed or upgraded to success.

A cycle counts when a new schema-2 `damage-started.json` is durably published. Pre-damage refusals do not consume a cycle. Restore-only continuation after an interrupted authorized cycle does not consume another cycle.

## Legacy attempt disposition

Sanitized read-only diagnosis established:

- all five approved current graph objects exactly match their recorded promoted versions and approved bytes;
- all five original historical source versions remain intact;
- current prefix inventory is exact;
- the detached network and PostgreSQL volume match their retained-resource fingerprint;
- no secret-bearing container exists.

This proves object-level restoration only. The legacy marker did not durably record break-proof or final catalog/query validation, so both remain unknown and the attempt is not a successful recovery proof.

## Diagnostic correction

The implementation now uses transactional global milestones for deletes, break proof, restoration, final validation, and containment. Every dangerous post-delete journal failure enters compensation. Legacy schema-1 evidence is restoration/audit-only and can never pass. Recovery-A failures produce bounded append-only sanitized receipts that retain primary and containment outcomes independently.

Fault injection covers per-node post-delete persistence, `deletes=complete`, `breakProof=failed`, and `breakProof=passed` persistence failures. It also covers failed break proof followed by compensation, primary plus containment failures, and direct schema-1 never-pass behavior.

## First new cycle

The first new schema-2 cycle failed at break proof and was safely compensated. Durable evidence records deletes complete, break proof failed, restoration complete, final validation pending, and containment passed. All five objects were restored as verified promoted versions; no secret-bearing container remains; the exact detached network and PostgreSQL volume are retained. This failed plan is frozen and must not be replayed.

The causal correction retains the prefix-fenced table and vended FileIO validated at point A. Break proof now requires catalog namespace health; an exact approved S3-location `FileNotFoundError` from a new scan, directly or through a bounded cause chain; a direct `FileNotFoundError` for that same location; and complete delete-marker and historical-source verification. Unrelated catalog, authentication, network, key-only, URI-continuation, and mismatched-object errors fail closed.

## Second and final new cycle

A fresh current-source-bound Seed-A and Recovery-A pair passed deterministic and independent review. The second schema-2 cycle nevertheless failed closed at break proof with sanitized category `missing-query-unexpected-error`. Durable evidence records deletes complete, break proof failed, restoration complete, final validation pending, and containment passed. All five nodes are promoted; read-only diagnosis verified all five current promoted objects, all five exact historical source versions, exact prefix inventory, and the retained-resource fingerprint. Catalog and query readback were not checked and cannot be inferred from object restoration.

The two-cycle budget is exhausted. The campaign is hard-stopped: do not replay either failed plan, generate or execute another damage plan, remove retained evidence, broaden permissions, touch canonical data, or claim an end-to-end recovery proof. See [campaign outcome](bounded-recovery-campaign-outcome.md).

## Validated baseline

- 84 focused recovery-drill tests pass.
- 224 focused and neighboring recovery/workflow tests pass.
- 16 selected recovery-infrastructure tests pass; the known intentionally deleted-`.10x` assertion remains deselected.
- Ruff, formatting, Python compilation, secret scan, OpenTofu validation, and `git diff --check` pass.
- Independent read-only review found no critical, high, or medium issue and approved proceeding.

## Hard stops

Stop the campaign without further damage if any identity, scope, prefix, catalog, source-version, retained-resource, canary, runtime, or image binding differs. After damage, continue restoration only until contained. Stop and report on unknown state, incomplete restoration, scope change, or a second failed new damage cycle. Never start a third new damage cycle.

The second new cycle failed after complete restoration and successful containment. This hard stop is now active.
