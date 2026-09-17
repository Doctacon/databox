# Bounded Recovery Campaign 2

## Authorization

The user authorized a new proof campaign with standing authorization and at most **two fresh isolated Recovery-A damage cycles**. The campaign may perform local/non-authoritative reproduction, causal fixes, tests, independent review, mutation-free Seed-A planning, fresh isolated Seed-A execution, and exact reviewed Recovery-A execution without intermediate approval pauses.

The campaign does not authorize canonical data or catalog access, IAM or bucket-control changes, root as the drill identity, negative enforcement tests, retained-evidence cleanup, Stage 2, or replay of any frozen plan.

## Attempt budget

- New damage cycles authorized: 2
- New damage cycles used: 1
- New damage cycles remaining: 1 (unused; campaign stopped on success)

A cycle counts only when its fresh schema-2 damage marker is durably published. Pre-damage refusal does not consume a cycle. Restore-only continuation after an interrupted authorized cycle does not consume another cycle.

## Confirmed cause and correction

A deterministic disposable integration harness using the installed PyIceberg and PyArrow versions reproduced the prior break-proof category. PyIceberg requested the exact missing manifest-list URI through the prefix validator, but PyArrow re-raised a backend `FileNotFoundError` whose message omitted the fully qualified URI. The prior proof correctly rejected that unbound message.

The correction wraps only the `InputFile` returned after its request location passes the prefix fence. If and only if `InputFile.open` raises `FileNotFoundError`, the wrapper raises a new `FileNotFoundError` naming the already-validated request location and retains the backend error as its cause. Authentication, authorization, network, catalog, and other unbound errors are not normalized and continue to fail closed.

The actual PyIceberg regression now proves the exact requested location, normalized top-level missing-file error, and original missing-file cause. Existing tests continue to require query/direct same-location correlation, exact URI boundaries, all delete markers, every historical source, exact restoration, final validation, and containment.

## Validated baseline

- 85 focused recovery-drill tests pass.
- 225 focused and neighboring recovery/workflow tests pass.
- 16 selected recovery-infrastructure tests pass; the known intentionally deleted-`.10x` assertion remains deselected.
- Ruff, formatting, Python compilation, secret scan, OpenTofu validation, and `git diff --check` pass.
- Independent read-only review found no critical, high, or medium finding and approved fresh planning.

## Success criteria

One fresh cycle must durably record deletes complete, break proof passed, restoration complete, final validation passed, and containment passed. Final validation must prove the catalog pointer, table identity, snapshot, logical graph, schema, and exact three-row result match point A.

## Outcome

The first fresh cycle completed with public status `pass`. Durable schema-2 evidence records:

- deletes complete;
- break proof passed;
- restoration complete;
- final validation passed; and
- containment passed.

All five nodes are promoted and no failure receipt exists. Final validation proved the point-A catalog pointer, table identity, snapshot, logical graph, schema, and exact three-row query result after restoration. Independent read-only diagnosis also verified all five current promoted objects, all five historical source versions, exact prefix inventory, and retained-resource fingerprint.

The campaign stopped on proof. The second authorized cycle is unused and must not be started. Private plans, markers, object-version evidence, isolated network, PostgreSQL volume, and catalog state remain retained; cleanup remains separately gated and unauthorized.

## Hard stops

Stop without further damage on identity, scope, prefix, catalog, source-version, retained-resource, canary, runtime, image, or plan drift. After damage, continue restoration only until contained. Stop on unknown state, missing history, incomplete restoration, containment failure, any need for broader authority, or exhaustion of the two-cycle budget. Never start a third cycle.

The success stop is now active.
