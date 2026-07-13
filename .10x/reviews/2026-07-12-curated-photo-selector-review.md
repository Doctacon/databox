Status: recorded
Created: 2026-07-12
Updated: 2026-07-12
Target: packages/databox/databox/curated_photo.py, tests/test_curated_photo.py, .10x/tickets/done/2026-07-11-implement-curated-photo-selector.md
Verdict: pass

# Curated photo selector implementation review

## Assumptions tested

- Provider order cannot silently change after Wikimedia outage/malformed data.
- Exact identity cannot be inferred from query text, common names, parent taxa, broad search ordering, or one API version alone.
- API return order cannot change Wikimedia selection.
- Provider URLs cannot activate arbitrary hosts, credentials, traversal, query/fragment variants, mismatched IDs/files, oversized variants, or non-photographic formats.
- Missing creator, unsupported license, insufficient/malformed dimensions, and unsafe metadata fail closed.
- The selector cannot request image bytes or affect GBIF occurrence/Xeno-canto behavior.

## Findings

No blocker or significant defect was found after the final diff and test inspection.

- Wikidata ambiguity is checked in a dedicated exact-entity query capped at two before bounded P18 retrieval, avoiding ambiguity hidden by a statement candidate cap.
- Commons candidates are ranked by all specified signals plus stable persisted fields, and tests reverse both statement and page responses.
- Wikimedia failure/no-eligible states are distinct; only a valid no-eligible result reaches iNaturalist.
- The v2/v1 split enforces repeated exact ID/name/rank/active identity and tests every mismatch family.
- Offline result validation rechecks exact source-record identity, provider-specific active URL, attempt order, creator sanitation, dimensions, and canonical Creative Commons metadata.
- The module imports only the existing exact-name/license helpers; existing recommendation GBIF and Xeno-canto selectors remain unchanged and their focused suites pass.

## Verdict

Pass for the selector ticket.

## Residual risk

No post-ratification live provider smoke or visual image review was performed. Provider schema drift will fail typed lookup unavailable rather than silently selecting another source. The rate limiter is deliberately process-local and depends on the governed serialized batch owner in later tickets.
