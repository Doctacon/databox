Status: done
Created: 2026-09-03
Updated: 2026-09-03
Parent: .10x/tickets/done/2026-09-03-extract-rufous-repository.md
Depends-On: None

# Inventory Rufous extraction boundary

## Scope

Produce a cold-start-capable manifest classifying every Rufous-related implementation, test, model, contract, workflow, configuration, asset, document, and `.10x` record as move, remain, split, regenerate, historical-only, or delete-after-verification. Trace imports and data dependencies across the boundary and identify the exact relations required in the versioned Databox product artifact.

## Acceptance criteria

- Inventory covers `app`, `workers`, packages, scripts, tests, transforms, Soda contracts, workflows, config, docs, migrations, assets, and `.10x` records.
- Every cross-boundary Python import, SQL dependency, filesystem path, command, workflow reference, and generated-doc dependency has an owner and migration action.
- The exact initial DuckDB artifact schemas/tables and compatibility metadata are proposed from observed dependencies, without adding unratified data semantics.
- USFWS public package surface and Rufous-owned orchestration boundary are explicit.
- Proposed child tickets are bounded, sequenced, and independently verifiable.
- No implementation or destination repository mutation occurs.

## Explicit exclusions

- Moving, copying, deleting, or editing implementation files.
- Creating the destination repository.
- Finalizing semantics not established by active records or source.

## References

- `.10x/decisions/split-rufous-into-standalone-repository.md`
- `.10x/specs/databox-rufous-data-product-boundary.md`
- `.10x/specs/rufous-repository-extraction.md`

## Evidence expectations

Record search commands, dependency traces, inventory counts, ambiguous ownership decisions, and reviewed child-slice recommendations.

## Progress and notes

- 2026-09-03: Initial search found product ownership distributed across the React app, Cloudflare worker, `databox` application/media modules, birding/media scripts and tests, `birding_agent`/`rufous_public` models and contracts, workflows, docs, and extensive durable records.
- 2026-09-03: Completed the cold-start inventory at `.10x/research/2026-09-03-rufous-extraction-inventory.md`. It classifies all governed surfaces by path pattern, traces Python/SQL/filesystem/command/workflow/generated-doc edges, proposes 12 exact v1 artifact relations plus compatibility metadata, defines the public USFWS package boundary, and sequences eight bounded implementation slices. No implementation or destination mutation occurred.

## Blockers

None for inventory closure. Six product/contract decisions recorded in the inventory must be ratified before implementation tickets are opened.
