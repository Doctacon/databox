Status: recorded
Created: 2026-07-09
Updated: 2026-07-09
Target: .10x/tickets/done/2026-07-09-implement-request-time-recommendation-media.md
Verdict: pass

# Request-time recommendation media review

## Target

Implementation and evidence for `.10x/specs/recommendation-media-enrichment.md`.

## Findings

### Passed — execution and persistence boundary

Enrichment runs after deterministic ranking; model grounding receives only pre-media evidence. Cardinality is validated before atomic plan persistence. Exactly one photo and call available/unavailable row per recommendation is persisted and reconstructed into recommendation-centric API objects. GET performs no discovery.

### Resolved significant — license, URL, geography, and transport safety

Initial review found generic Creative Commons acceptance, host-only GBIF URLs, trusted response geography, and credential-bearing transport causes. Repairs establish an explicit license family/version matrix, audio-only ND allowance, exact GBIF 500x500 cache path/key/MD5 verification, returned US/Arizona validation, exact Xeno Arizona/global scope, and cause/context-free transport errors. Independent probes rejected malformed licenses, paths, traversal, identity mismatches, and geographic inconsistencies.

### Resolved significant — total deterministic selection

Initial and follow-up reviews found API-order ties, including casefold-equivalent persisted spellings. Photo/call ranking now includes semantic preference keys, normalized immutable fields, and every exact persisted output field. Reversing candidates across identifiers, attribution, geography, recording type, quality, URLs, and license produces identical complete evidence objects.

### Passed — Queen Valley and failure behavior

The fixture uses the exact eight researched Queen Valley species and proves eight photos/calls, six Arizona calls, and global labels for Ross's Goose and American White Pelican. Timeouts, malformed/unlicensed/unsafe/missing media persist unavailable states without changing recommendations or model behavior.

## Verdict

Pass. No blocker remains.

## Residual risk

Photo display depends on GBIF's remote derived cache. License versions and safe hosts/paths are intentionally finite and require reviewed updates when upstream contracts change.
