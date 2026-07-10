Status: done
Created: 2026-07-10
Updated: 2026-07-10
Parent: .10x/tickets/2026-07-09-build-local-birding-pokedex.md
Depends-On: .10x/tickets/done/2026-07-09-add-avonet-bird-traits-source.md, .10x/tickets/done/2026-07-09-model-avonet-traits-and-arizona-catalog.md

# Fix AVONET SQLMesh production lint and apply

## Scope

Repair the production-only parse/lint blocker exposed after the reviewed live AVONET bootstrap:

```text
invalidselectstarexpansion: SELECT * cannot be expanded due to missing schema for raw_avonet.species_traits
```

Replace the raw AVONET `SELECT *` projection in `environmental_observations.dim_bird_species_traits` with the exact explicit governed raw column list while preserving normalization, duplicate guards, output schema, conformance, and tests. Then run the real production lint/diff and apply exactly the reviewed AVONET trait/catalog model additions.

## Acceptance criteria

- Production lint no longer requires star expansion for the new external raw schema.
- SQLMesh unit/adversarial tests and generated schema/contracts remain unchanged or are intentionally reconciled.
- Nonmutating prod diff contains only `dim_bird_species_traits` and `arizona_species_catalog` before apply.
- Production apply succeeds and the live warehouse reconciles 10,661 raw AVONET rows, 706 catalog taxa, 624 species, 82 hybrids, 600 available traits, 24 unmatched species, and zero matched hybrids.
- No unrelated model restatement, full refresh, source call, or browser/API change occurs.

## Evidence expectations

Record the failed command, exact repair, pre-apply diff, apply result, live cardinality/privacy/staging/main-metadata checks, and independent review.

## Progress and notes

- 2026-07-10: Live `avonet_ingest` Dagster run `b15ce6e6-5fbe-4e97-b1a9-85c5d0ce14c6` succeeded with 10,661 validated rows. The subsequent SQLMesh production plan failed before mutation on raw AVONET star expansion. No model was applied.
- 2026-07-10: Replaced `avonet_normalized` star expansion with the exact 38 governed fields plus `_dlt_load_id`/`_dlt_id`. The first retry safely exposed the remaining final `m.*` expansion before mutation, so that projection was also made explicit. Added a SQLGlot regression test for the exact raw projection and absence of direct select-star projections.
- 2026-07-10: The guarded nonmutating prod diff contained exactly the two reviewed additions. `sqlmesh plan prod --auto-apply --no-prompts` passed 13 tests and applied both full models; SQLMesh automatically recreated the existing GBIF evidence view without restating/full-refreshing it. Post-apply prod diff is empty.
- 2026-07-10: Live read-only verification found raw AVONET 10,661; trait dimension 10,073 unique names/Avibase IDs; catalog 706/706 unique codes, 624 species, 82 hybrids, 600 available species, 24 unavailable species, zero available hybrids. Privacy aggregate mismatches, incoherent/nonpublic emitted location tuples, staging schemas, and persistent `main._dlt*` relations are all zero; max top locations is ten. Evidence: `.10x/evidence/2026-07-10-avonet-sqlmesh-production-lint-and-apply.md`.
- 2026-07-10: Independent review passed explicit projections, regression coverage, exact plan/apply boundary, post-apply diff, live cardinality/privacy/location, and cleanup checks. Review: `.10x/reviews/2026-07-10-avonet-sqlmesh-production-lint-review.md`.
- 2026-07-10: Retrospective: fixture rendering can hide production lint dependence on external raw-schema star expansion. Explicit raw projections and a parse-tree regression preserve the production contract; no separate knowledge/skill record is needed.

## Blockers

None. User authorized continued parent execution.
