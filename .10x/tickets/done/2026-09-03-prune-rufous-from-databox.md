Status: done
Created: 2026-09-03
Updated: 2026-09-03
Parent: .10x/tickets/done/2026-09-03-extract-rufous-repository.md
Depends-On: .10x/tickets/done/2026-09-03-transfer-rufous-records-and-docs.md

# Prune verified Rufous surfaces from Databox

## Scope

Delete product implementation from Databox only after equivalent standalone Rufous capabilities and canonical records are evidenced. Reconcile Databox dependencies, SQLMesh/Soda configuration, Dagster definitions, source registry tests, workflows, tasks, docs generation, package manifests, lockfile, and CI around its remaining ingestion/data-product responsibilities.

Remove the Databox Rufous-target USFWS Dagster job while retaining the public `databox_sources.usfws` provider interface and generic source/status/publication primitives. Remove product-specific iNaturalist implementation from Databox because Rufous owns it.

## Acceptance criteria

- Product-owned app, worker, backend/agent/state/media/public modules, product scripts/tests/migrations/config/infra/workflows, `birding_agent` and `rufous_public` models/contracts/tests, and product documentation are absent from Databox.
- Databox retains every source implementation and the complete twelve-relation artifact exporter contract required by Rufous.
- The Rufous-target USFWS job is absent; reusable USFWS provider API/tests and non-product status primitives remain.
- Product-only Python/npm dependencies and task commands are removed; locks regenerate cleanly.
- Dagster definitions contain only Databox-owned assets/jobs/checks and resolve without duplicate or missing keys.
- Databox SQLMesh tests and generated model/contract inventory reflect only retained ownership.
- Residue scans find no active Rufous runtime, deployment, private application, or product-model ownership outside explicit artifact contracts and historical provenance.
- Databox `task ci`, retained SQLMesh tests, strict docs, pre-commit, secret scan, and diff checks pass.
- Standalone Rufous aggregate remains passing after Databox deletion and remote Git pin installation.

## Explicit exclusions

- Changing retained source/data-product behavior.
- Enabling Rufous production.
- Removing historical provenance records required by the record-transfer manifest.
- Merging either repository branch.

## References

- `.10x/specs/databox-rufous-data-product-boundary.md`
- `.10x/specs/rufous-repository-extraction.md`
- `.10x/research/2026-09-03-rufous-extraction-inventory.md`

## Evidence expectations

Record deletion manifest, retained public interfaces/artifact relations, dependency and asset-graph diffs, residue searches, both repositories' complete gate output, and adversarial review.

## Progress and notes

- 2026-09-03: Opened as the destructive slice following canonical record/document transfer.
- 2026-09-03: Deleted verified product-owned implementation and reconciled dependencies, source registry, Dagster, SQLMesh/Soda, generated docs, CI, tasks, settings, and locks. Full Databox pytest passed 393 tests at 85.51% coverage; retained SQLMesh passed 7/7; Ruff, format, MyPy (90 files), strict docs, pre-commit, secret scan (778 files), and diff checks passed. Evidence: `.10x/evidence/2026-09-03-prune-rufous-from-databox.md`.
- 2026-09-03: Bounded timeout recovery inspected rather than repeated the 382-file prune, repaired the one stale Rufous operations wording that blocked its branding test, and passed that exact test. Focused Databox tests passed 66/66; lock check, definitions import, SQLMesh 7/7, residue scan, and both repositories' diff checks passed.
- 2026-09-03: Final aggregate rerun passed: Databox `task ci` completed with 385 tests and 85.47% coverage plus retained generation/secret gates; Rufous passed 1,073 Python tests, SQLMesh 11/11, app 537/537 with typecheck/build, worker 71/71, both npm audits with zero vulnerabilities, locked remote-pin sync, and diff checks. Adversarial review confirmed the twelve exporter relations and public USFWS API/tests remain, then identified stale active Rufous shared-Quack semantics; those records were reconciled or moved to superseded history in Rufous commits `43fc99e` and `2260126`.

## Blockers

None.
