Status: active
Created: 2026-07-09
Updated: 2026-07-10

# AVONET bird-traits source and model

## Purpose and scope

This specification governs ingestion of the pinned AVONET v7 eBird-aligned species-average dataset through dlt/Quack and its SQLMesh trait model for Arizona bird profiles.

## Source contract

The source MUST use the exact dataset identity in `.10x/decisions/avonet-atomic-staged-publication.md` and MUST:

- fetch only the fixed HTTPS Figshare file URL for file ID `34480856`,
- use bounded connect/read timeouts and a response cap above the expected 21,524,673-byte file but no greater than 24 MiB,
- require exact expected byte length and MD5 before parsing,
- reject redirects to non-Figshare HTTPS hosts, embedded credentials, plain HTTP, malformed workbook content, missing/duplicate worksheet names, and schema drift,
- parse only `AVONET2_eBird`,
- treat blank and exact `NA` cells as null,
- preserve exact categorical/code values and parse bounded numeric/boolean values strictly,
- write one row per AVONET eBird scientific name with `Avibase.ID2` as source identifier,
- attach dataset DOI/version/license/file hash/source URL/load timestamp to every raw row,
- log bounded counts/status only, never arbitrary workbook cells or response bodies.

The workbook and temporary extraction artifacts MUST remain outside the repository and be removed after load success or failure.

## Raw interface

Physical schema `raw_avonet` MUST contain one business table `species_traits` plus source-scoped dlt metadata. The business table MUST preserve:

- source identity: AVONET scientific name, family, order, Avibase ID,
- measurement provenance/counts: total/female/male/unknown individuals, complete measures, inference flag, inferred trait list, reference species, mass source/reference,
- morphology: beak culmen/nares length, beak width/depth, tarsus length, wing length, Kipp's distance, secondary length, hand-wing index, tail length, mass,
- ecology: habitat, habitat-density code, migration code, trophic level, trophic niche, primary lifestyle,
- dataset provenance: DOI, version, license, file ID/hash, source URL, loaded timestamp.

Units and codebook meanings MUST be documented in `.schema/environmental_observations/avonet.dbml` and carried into generated data-dictionary output.

## Pipeline behavior

- `avonet` MUST be registered as an independently runnable source and Dagster ingest job.
- dlt MUST use the existing Quack destination and append only into transient internal schema `raw_avonet_staging`; it MUST NOT write directly to authoritative `raw_avonet`.
- Before each run, crash residue in `raw_avonet_staging` MUST be removed before the independent Quack server starts.
- After a successful dlt load and Quack server stop, one direct single-writer DuckDB transaction MUST validate exactly 10,661 rows, 10,661 distinct non-null Avibase IDs, 10,661 distinct non-null source scientific names, the exact normalized business-table columns, and required source-scoped dlt metadata. Only then may it atomically create or replace `raw_avonet.species_traits` and its metadata from staging.
- Successful publication MUST remove `raw_avonet_staging`. Download, parse, extraction, dlt load, validation, or publication failure MUST leave authoritative `raw_avonet` unchanged and remove staging best-effort; any crash residue MUST be safely cleared before the next run.
- This post-Quack transaction is the only direct DuckDB write allowed for AVONET and MUST occur only after Quack releases ownership. Generic raw deduplication MUST NOT substitute for complete-snapshot publication.
- The static pinned source MUST NOT add a redundant daily schedule. It MAY run explicitly and as a required bootstrap/precondition for catalog modeling.
- Existing six-source parallel refresh overlap/schedules MUST remain unchanged unless a later active decision adds AVONET to that lifecycle.
- Failed download/hash/schema/parsing/load/validation/publication MUST fail the source job and preserve the last successful physical table and metadata; partial staging data MUST NOT become authoritative.

## SQLMesh model

Create `environmental_observations.dim_bird_species_traits` at one row per matched conformed species.

- Normalize AVONET scientific name exactly as governed by `.10x/decisions/cross-source-bird-species-conformance.md`.
- Join only to `environmental_observations.dim_species.species_natural_key`.
- Duplicate normalized AVONET keys or multiple trait rows per species MUST fail tests rather than choose silently.
- Preserve AVONET source scientific name and every provenance/measurement-inference field.
- Expose human-readable codebook labels for habitat density and migration while preserving raw codes.
- Do not convert global range variables into Arizona-specific claims.

Create or update a catalog-facing modeled interface that exposes every eBird `US-AZ` catalog taxon, including hybrids, with `traits_status` equal to `available` only for an exact modeled trait match and `unavailable` otherwise. Missing traits MUST NOT remove a catalog row.

## Acceptance scenarios

### Exact species match

Given a current Arizona species whose normalized scientific name exactly exists in AVONET, when SQLMesh runs, then exactly one trait row joins and retains morphology, ecology, measurement provenance, DOI/version/license, and source name.

### Taxonomy drift

Given one of the currently measured 24 species whose current scientific name is absent from AVONET v7, when SQLMesh runs, then the catalog row remains present with `traits_status=unavailable`; no common-name or historical-name guess is made.

### Hybrid

Given any of the 82 Arizona hybrid taxa, when the catalog model runs, then the hybrid remains explicitly categorized and has unavailable traits unless AVONET itself supplies an exact hybrid row.

### Tampered source

Given a response with the wrong size/hash, unapproved redirect, missing worksheet, duplicate source key, changed column contract, incomplete staging load, or failed publication, when ingestion runs, then the job fails before authoritative replacement, preserves any prior final snapshot, removes staging best-effort, and logs no workbook content.

## Explicit exclusions

- No Wikipedia, turbo-search bird corpus, EOL, AVONICHE, AvianHWI, EltonTraits, Birds of the World, All About Birds, or inferred visual field marks.
- No raw individual specimen table.
- No automatic taxonomy crosswalk beyond exact governed normalization.
- No new daily schedule, concurrent/direct ingestion bypass, direct DuckDB write while Quack owns the file, or browser/request-time download. The bounded post-Quack atomic publication transaction specified above is required.
