Status: recorded
Created: 2026-07-10
Updated: 2026-07-10
Relates-To: .10x/tickets/done/2026-07-10-fix-avonet-sqlmesh-production-lint.md

# AVONET SQLMesh production lint repair and apply

## What was observed

- The reviewed live AVONET ingest had already published 10,661 authoritative raw rows. The first production plan failed before mutation because SQLMesh could not expand an external raw-schema star.
- `avonet_normalized` now projects the exact governed 38 AVONET fields plus `_dlt_load_id` and `_dlt_id`. The final trait projection is also explicit so no select-list star remains dependent on unavailable external schema expansion.
- A SQLGlot lint regression test asserts the normalized projection exactly equals `species_natural_key` plus those 40 physical fields and rejects any direct select-star projection in the model.
- Before apply, the nonmutating prod diff contained exactly two additions: `environmental_observations.dim_bird_species_traits` and `birding_agent.arizona_species_catalog`.
- `sqlmesh plan prod --auto-apply --no-prompts` passed 13 tests and successfully full-refreshed exactly the two new models. SQLMesh also recreated the existing `birding_agent.gbif_occurrence_evidence` view as automatic view maintenance; it did not restate or full-refresh that model.
- After apply, `sqlmesh diff prod` reports no changes.

## Live read-only verification

- `raw_avonet.species_traits`: 10,661 rows.
- `environmental_observations.dim_bird_species_traits`: 10,073 rows, 10,073 distinct normalized names, and 10,073 distinct Avibase IDs.
- `birding_agent.arizona_species_catalog`: 706 rows and 706 distinct species codes.
- Categories: 624 species and 82 hybrids.
- Trait availability: 600 available species, 24 unavailable species, zero available hybrids, and 82 unavailable hybrids.
- Recomputed public valid/reviewed/non-private observation aggregates have zero mismatches with catalog counts/latest/notable/location fields.
- Top-location arrays have maximum length 10; zero emitted location metadata tuples lack an exact existing qualifying public observation row.
- `raw_avonet_staging` schemas: zero. Persistent `main._dlt*` relations: zero.

## Procedure

1. Replaced raw and final select-star projections with exact explicit fields.
2. Ran 13 SQLMesh tests and three focused adversarial/lint tests.
3. Ran the nonmutating prod diff and mechanically required exactly the two reviewed additions before apply.
4. Applied the exact prod plan without prompts or unrelated restatement/full refresh.
5. Queried the live warehouse read-only for raw/model cardinality, category/availability reconciliation, aggregate privacy equivalence, bounded coherent locations, and transient metadata absence.
6. Ran the post-apply prod diff, focused validation, repository hooks, and no-stage check.

## Limits

- This task did not run a source refresh, generic full refresh, unrelated restatement, API/UI work, or personal-state mutation.
- Independent review passed and is recorded at `.10x/reviews/2026-07-10-avonet-sqlmesh-production-lint-review.md`.
