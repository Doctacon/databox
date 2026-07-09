Status: active
Created: 2026-07-09
Updated: 2026-07-09

# Cross-source bird species conformance

## Context

The `environmental_observations` CDM now includes eBird taxonomy/observation data, GBIF occurrence/taxonomy evidence, and Xeno-canto recording metadata. These sources each carry bird species identity differently:

- eBird uses `species_code`, `sci_name`, `com_name`, taxonomic family/order fields, and region-specific species lists.
- GBIF uses occurrence-level taxonomy fields such as `accepted_scientific_name`, `scientific_name`, `accepted_taxon_key`, and `taxon_key`.
- Xeno-canto recording metadata carries `genus`, `species`, and `english_name`, plus recording/media metadata.

The prior CDM update intentionally kept species evidence source-scoped because no cross-source natural key or conflict policy had been ratified.

## Decision

Conform bird species across eBird, GBIF, and Xeno-canto in `environmental_observations.dim_species`.

Use normalized scientific name as the conformance natural key. Normalization lowercases, trims whitespace, and strips trailing parenthetical authorship where present; it does not collapse hybrids or subspecies to a broader species unless the source scientific-name text already matches after that normalization.

- eBird: `sci_name`
- GBIF: `accepted_scientific_name`, falling back to `scientific_name`, then `species`
- Xeno-canto: `genus || ' ' || species`

Conflict/source precedence:

1. eBird wins for common/scientific names, eBird species code, taxonomic order/category, family code/name, report-as, extinct fields, and region when present.
2. GBIF fills missing names/family/genus/rank fields and supplies GBIF taxon identifiers.
3. Xeno-canto supplies media-context presence and recording counts; audio remains external-link-only.

Coverage is a union: include species present in any of eBird, GBIF, or Xeno-canto. If a source row lacks a usable scientific-name key, do not invent a cross-source match; keep it source-scoped through a fallback key.

## Alternatives considered

- **Keep sources separate**: simplest and avoids bad matches, but leaves the CDM less useful for trip-planning joins and cross-source evidence.
- **eBird + GBIF only**: avoids Xeno-canto matching uncertainty, but would not satisfy the ratified goal to conform all three durable bird sources.
- **GBIF accepted taxon key as key**: more taxonomically precise for GBIF rows, but eBird and Xeno-canto do not carry GBIF taxon keys in current sources.
- **Common/English name as key**: easier to read but ambiguous across regions, synonyms, and languages.
- **Matched-only coverage**: highest confidence, but drops useful source-only evidence and conflicts with the ratified union coverage.

## Consequences

- `environmental_observations.dim_species` becomes a conformed dimension, not an eBird-only dimension.
- Bird observation, GBIF occurrence, and Xeno-canto recording facts can reference the same `species_sk` when normalized scientific names match.
- Source-specific identifiers and provenance remain preserved in facts and dimension columns.
- Species rows with no usable scientific-name key remain source-scoped rather than being guessed into a match.
- Future taxonomy refinements may replace normalized scientific-name matching with a maintained crosswalk or GBIF-backed taxon mapping, but that requires new evidence and a superseding decision.
