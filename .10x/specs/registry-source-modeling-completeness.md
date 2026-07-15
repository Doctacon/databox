Status: active
Created: 2026-07-12
Updated: 2026-07-12

# Registry source modeling completeness

## Purpose and scope

Every dlt source registered for ingestion into the Databox DuckDB warehouse MUST pass through the complete governed modeling workflow:

1. annotated source DBML;
2. taxonomy classification;
3. ontology representation;
4. generated CDM representation;
5. SQLMesh transformation.

The contract is registry-derived. Adding a source MUST NOT require adding its name to a second test-owned source list.

## Behavioral contract

For every source in `databox.config.sources.SOURCES`:

- Exactly one annotated source DBML artifact under `.schema/<cdm-name>/` MUST own all of the source's registered `raw_tables`.
- Every registered raw table MUST be classified in `taxonomy.json` as either:
  - mapped to one or more confirmed business concepts; or
  - explicitly excluded with a source pipeline and reason.
- DBML and taxonomy classification MUST agree: the exact `concept:` plus `also_concept:` set equals the taxonomy concept set, while `excluded:` is present if and only if the table appears in taxonomy `_excluded`. Substring lookalikes such as `unconcept:` are not annotations.
- A raw table MUST NOT be both modeled and excluded.
- Every modeled concept contributed by the source MUST appear as an entity in `ontology.ison` and as a `source_entity` in `CDM.dbml`.
- Every non-excluded registered raw table MUST be consumed by at least one CDM-declared SQLMesh MODEL under `transforms/main/models/` through an AST-parsed `exp.From` or `exp.Join` dependency on `raw_<source>.<table>`. INSERT, UPDATE, DELETE, and other table targets MUST NOT count. The MODEL output's CDM `source_entity` MUST intersect the raw table's taxonomy concepts. Operational-only models such as platform-health row counts MUST NOT satisfy business transformation coverage.
- Every source MUST contribute at least one modeled, transformed business table. A source whose registered tables are all excluded MUST fail the contract.
- Explicitly excluded metadata tables do not require ontology, CDM, or SQLMesh transformation coverage.

The guard MUST fail closed when source-to-DBML ownership is missing or ambiguous. It MUST derive current sources and raw-table inventories from `SOURCES`, not a manually maintained source-name matrix.

## Acceptance scenarios

### Complete source

Given a registered source with annotated DBML, complete taxonomy classification, ontology/CDM entities, and SQLMesh dependencies for every modeled table, when the modeling-contract test runs, then the source passes.

### Missing stage

Given a registered source missing annotation, taxonomy classification, ontology entity, CDM entity, or SQLMesh dependency, when the test runs, then it fails and names the source, table or concept, and missing stage.

### Documented exclusion

Given a registered metadata table classified only under `taxonomy.json._excluded` with a reason, when the test runs, then the table does not require ontology, CDM, or transformation coverage.

### Fully excluded source

Given a registered source whose every raw table is excluded, when the test runs, then the source fails because it contributes no modeled warehouse behavior.

### Registry growth

Given a new entry in `SOURCES`, when no modeling artifacts exist, then the same test discovers and rejects it without a source-name edit to the test.

## Constraints and exclusions

- The test is a static repository-coherence guard; it does not replace SQLMesh model execution or data-quality tests.
- The test MUST NOT contact providers, refresh sources, run SQLMesh apply, or access/mutate the shared warehouse.
- The contract does not require transformations for dlt internal tables or explicitly excluded source metadata.
- The contract does not change current taxonomy, ontology, CDM, or SQLMesh semantics.
