Status: done
Created: 2026-07-09
Updated: 2026-07-09

# Ratify and implement cross-source bird species conformance strategy

## Scope

Decide and implement how the `environmental_observations` CDM stitches species/taxon rows across eBird, GBIF, and Xeno-canto.

In scope:

- Record the user-ratified conformance decision.
- Conform eBird, GBIF, and Xeno-canto species in `environmental_observations.dim_species` using normalized scientific name.
- Apply source precedence: eBird first, GBIF fills taxonomy identifiers/gaps, Xeno-canto supplies media context.
- Use union coverage: include species present in any source.
- Update `.schema/environmental_observations` taxonomy, ontology, and CDM artifacts.
- Update SQLMesh models/tests/contracts and generated docs as needed.
- Record evidence and review.

Out of scope:

- Changing current GBIF/Xeno-canto ingestion.
- Downloading or storing Xeno-canto audio.
- Adding a maintained external taxonomy crosswalk beyond the normalized scientific-name rule.

## Acceptance criteria

- A user-ratified decision exists for whether eBird, GBIF, and Xeno-canto species should be conformed: satisfied by `.10x/decisions/cross-source-bird-species-conformance.md`.
- The exact natural key and source precedence/conflict handling are explicit: satisfied.
- `environmental_observations.dim_species` includes union species coverage from eBird, GBIF, and Xeno-canto: satisfied.
- Bird observation, GBIF occurrence, and Xeno-canto recording facts can reference the conformed species dimension where a normalized scientific-name key is available: satisfied.
- `.schema/environmental_observations` artifacts reflect the conformance strategy: satisfied.
- Relevant checks pass and evidence is recorded: satisfied by `.10x/evidence/2026-07-09-cross-source-species-conformance.md`.

## Progress and notes

- 2026-07-09: CDM workflow update for GBIF and Xeno-canto intentionally avoided cross-source species stitching because no natural key or conflict policy was ratified.
- 2026-07-09: User ratified: conform all three sources; use normalized scientific name; eBird-first precedence; union coverage.
- 2026-07-09: Decision recorded in `.10x/decisions/cross-source-bird-species-conformance.md`.
- 2026-07-09: Implemented conformed `environmental_observations.dim_species` using normalized scientific name, source-scoped fallback keys, eBird-first precedence, and union coverage.
- 2026-07-09: Updated eBird/GBIF/Xeno-canto facts to reference conformed `species_sk` without duplicate fallback joins.
- 2026-07-09: Added SQLMesh regression tests for duplicate normalized eBird species, no-name fallback rows, GBIF blank-name fallback, and eBird fact duplicate-join prevention.
- 2026-07-09: Validation passed: source layout, platform-health check, generated docs check, 10 SQLMesh tests, `task verify`, `task ci`, `task docs:build`, and `task eval:agent`.
- 2026-07-09: Final review passed. Residual risk is limited to the intentionally lightweight scientific-name normalization; full taxonomy synonym/crosswalk service remains out of scope.

## Evidence and review

- `.10x/evidence/2026-07-09-cross-source-species-conformance.md`
- `.10x/reviews/2026-07-09-cross-source-species-conformance-review.md`

## Blockers

None.
