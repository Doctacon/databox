Status: complete
Created: 2026-09-14
Updated: 2026-09-15

# Retrospective

## What Mattered

The initial handoff preserved agreed protection semantics separately from unresolved restore choices and live-operation approvals. `.10x` remains intentionally deleted; only the active plan was carried forward. The rollout succeeded because its root-only retention-control guarantee, three-prefix/cost impact, exact plan/hash and full propagation pause were approved as separate gates.

## Learnings

Historical records can contain stale branch/status claims. Verify current Git state and cite an immutable source revision instead of restoring the whole archive or treating old tickets as current execution authority.

A saved plan does not pin apply credentials, so exact root identity still required an independent apply-time check. AWS login exposes short-lived credentials backed by an automatically refreshable login session; credential expiry alone is not the session lifetime. S3 returns Terraform's empty lifecycle filter as the equivalent bucket-wide `Filter: {Prefix: ""}`. OpenTofu also created a state backup with broader permissions than required, so both live and backup state modes need explicit verification.

For live recovery tooling, a plan generated after mutation is not an approval gate. Splitting Stage 1 into mutation-free Seed-A planning and exact-hash Seed-A execution was necessary before Recovery-A could be a meaningful second approval. Isolating PostgreSQL/Polaris also removed accidental dependence on the active catalog.

Crash containment requires more than labels. Exact retained network/volume fingerprints, full sleeper-container launch checks, network-attachment inventory, and all-container volume-consumer inventory are needed before reusing or removing a run-owned remnant. Recovery-plan expiry must block new damage without stranding already journal-bound restoration. The tagged Polaris 1.7 management API returns a catalog directly rather than in a `catalog` wrapper; pin protocol parsers with response-shape tests.

Global durable milestones and append-only sanitized receipts turned ambiguous safe refusals into bounded results. Earlier cycles proved exact object restoration and containment without proving table break or final query validation; successful S3 reconstruction could not be promoted into an Iceberg recovery claim. Campaign 2 then durably passed every milestone and supplied the missing end-to-end proof.

The bounded budgets worked as intended. They forced local fault testing and independent review rather than repeated live experimentation. The decisive reproduction used the installed PyIceberg and PyArrow versions against a disposable local table: PyIceberg requested the exact manifest-list URI through the prefix fence, while PyArrow's backend `FileNotFoundError` omitted that fully qualified URI. Normalizing only `FileNotFoundError` at the already-validated `InputFile.open` boundary preserved strict causality, kept unrelated failures closed, and allowed the first fresh campaign-2 cycle to pass.

Catalog recovery needed two distinct proofs. Stage 2A established the mechanics against a local POSIX repository and synthetic Polaris state. Stage 2B then exercised the deployed S3 repository and active WAL boundary without cutover: the isolated restore promoted at the exact before/after bracket, scrubbed temporary credentials, started real Polaris, validated all canonical registry tables, cleaned the active marker, and met the one-hour objective. An explicit pre-authenticated-session path was necessary because the operator had already completed remote login and MFA; skipping a redundant login is safe only when short-lived role export and the minimum remaining lifetime check still run.

## Improvements

Keep future inspection evidence and decisions with this task, using sanitized observations and explicit unknowns. Make verifiers accept documented provider/API-normalized forms while checking semantics strictly, check every `terraform.tfstate*` mode before and after apply, and never make a read-back validator failure trigger automatic reapply or rollback. Keep future live plans narrow and privately review exact filenames/hashes. Record only sanitized counts, hashes, statuses and timings in tracked evidence.

Before any future recovery change, reproduce actual client/library missing-object behavior without authoritative data, preserve a sanitized error taxonomy rich enough for causal diagnosis, and require that harness to pass the same break-proof predicate. Stages 2A and 2B are complete; cleanup and negative enforcement remain separate decisions. The earlier failed campaign is recorded in [bounded-recovery-campaign-outcome.md](bounded-recovery-campaign-outcome.md), the successful object proof in [bounded-recovery-campaign-2.md](bounded-recovery-campaign-2.md), and the deployed catalog proof in [stage-2b-deployed-s3-pitr-outcome.md](stage-2b-deployed-s3-pitr-outcome.md).
