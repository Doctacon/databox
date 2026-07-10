Status: recorded
Created: 2026-07-09
Updated: 2026-07-09
Relates-To: .10x/tickets/done/2026-07-09-backfill-existing-plan-media.md, .10x/specs/recommendation-media-enrichment.md

# Existing plan recommendation media backfill

## What was observed

The explicit local backfill reconciled the current `data/databox.duckdb` baseline of 2 persisted plans and 16 recommendations. Final state has exactly one available photo and one available call result for every recommendation, with no missing or duplicate recommendation-media evidence.

All eight Queen Valley recommendations reload as available/available:

- Ross's Goose
- American White Pelican
- Ring-necked Duck
- Bushtit
- Yellow-headed Blackbird
- Northern Mockingbird
- American Coot
- Mallard

The CLI prints bounded counts only. No credentials or arbitrary upstream URLs were printed, and no media bytes were downloaded or stored.

## Procedure and results

### Deterministic dry-run

```text
task media:backfill -- --dry-run
plan_count=2
recommendation_count=16
target_recommendation_count=16
missing_photo_count=16
missing_call_count=16
duplicate_media_count=0
lookup_count=0
```

Dry-run opened the warehouse read-only, performed no discovery, and inserted nothing.

### Initial apply and diagnosis

The first bounded apply inserted exactly 16 call and 16 photo results. Aggregate output was 16 available and 16 unavailable. Read-only evidence inspection established the split unambiguously:

```text
call: available, caveats=[], count=16
photo: unavailable, caveats=["No eligible exact-species Arizona GBIF photo was found"], count=16
```

A single sanitized GBIF diagnostic inspected field structure without printing arbitrary URLs. Returned exact-species Arizona candidates had supported still-image MIME types, complete creator/rights attribution, HTTPS image identifiers, `countryCode='US'`, `country='United States of America'`, `stateProvince='Arizona'`, and Creative Commons licenses on the exact `http://creativecommons.org/licenses/...` host/path. Two fail-closed compatibility gaps explained the blanket rejection:

1. recognized Creative Commons HTTP URLs were rejected instead of canonicalized to their equivalent HTTPS form;
2. the independently returned country cross-check accepted `US` and `United States` but not GBIF's `United States of America` spelling.

The repair preserves the finite license family/version allowlist and exact host/path validation, canonicalizes only recognized Creative Commons HTTP URLs to HTTPS, and accepts the exact US country spelling while still rejecting conflicting country/state data. The same shared selector remains authoritative for new plans and backfill. Selective enrichment ensures photo-only repair does not call Xeno-canto.

A versioned one-time replacement upgraded the exact defective `media_backfill_v2_` GBIF-unavailable photo rows from the prior selector version. The successful final repair apply reported:

```text
target_recommendation_count=16
replaced_photo_count=16
inserted_photo_count=16
inserted_available_count=16
inserted_unavailable_count=0
inserted_call_count=0
lookup_count=16
remaining_missing_photo_count=0
remaining_missing_call_count=0
```

The immediate second apply was a no-op:

```text
target_recommendation_count=0
replaced_photo_count=0
inserted_photo_count=0
inserted_call_count=0
lookup_count=0
```

### Final warehouse and GET verification

A read-only warehouse assertion joined every recommendation to photo and call evidence and reported:

```text
recommendations=16
photo_available=16
photo_unavailable=0
call_available=16
call_unavailable=0
duplicate_or_missing=0
queen_recommendations=8 (all available/available)
```

The same procedure created the API with injected GBIF/Xeno getters that raise if called, hashed all four application tables, issued the Queen Valley GET, then rehashed:

```text
get_status=200
get_network_calls=0
full_snapshot_unchanged=yes
snapshot_sha256=d537844b8568975574111bd5dd4e546cfd0d7380421d56eafa7f1a7e54392d44
```

This supports that GET is read-only/network-free and that the final no-op/live reload did not mutate plans, recommendations, evidence, or traces.

## Automated validation

```text
uv run --no-sync pytest tests/test_recommendation_media_backfill.py tests/test_recommendation_media.py --no-cov -q
33 passed.

uv run --no-sync pytest tests/test_recommendation_media_backfill.py tests/test_recommendation_media.py tests/test_api.py --no-cov -q
49 passed after the final compatibility repair.

uv run --no-sync ruff check <backfill/media implementation and tests>
Passed.

uv run --no-sync mypy packages/databox/databox/agent_tools/recommendation_media.py packages/databox/databox/agent_tools/recommendation_media_backfill.py
Passed.
```

The tests prove dry-run makes no calls/writes; apply persists available and unavailable partial-failure results; a second run makes no calls/inserts; partial existing evidence is not duplicated; plan/recommendation rows hash identically before and after; the Cloudflare synthesis path is never invoked; photo-only enrichment does not invoke Xeno; and GET makes no discovery call or write.

## Review-blocker repair verification

The one-time replacement predicate now requires all three exact properties: an evidence ID beginning `media_backfill_v2_`, status `unavailable`, and caveats JSON equal to the original generic GBIF no-eligible-photo caveat. Parameterized negative tests prove that generic `media_backfill_legacy`, v1, unknown-version, v3/current, changed-caveat, and available rows are not targets. The current v3 warehouse remains outside the repair predicate.

Fault injection establishes transactional and lock safety:

- a selector exception after the transaction begins leaves zero evidence rows;
- an injected failure on the second persistence operation rolls back the first insert and leaves zero evidence rows;
- duplicate media evidence raises before any discovery or write and preserves the original evidence snapshot;
- a separate process holding the DuckDB file lock causes apply to fail at connection acquisition before mutation.

```text
uv run --no-sync pytest tests/test_recommendation_media_backfill.py --no-cov -q
14 passed.

task media:backfill -- --dry-run
2 plans; 16 recommendations; 0 targets; 0 missing; 0 duplicates; 0 lookups.

task media:backfill -- --apply
2 plans; 16 recommendations; 0 targets; 0 inserts; 0 replacements; 0 lookups.
```

No live discovery occurred during these final current-warehouse checks because both modes had zero targets.

## Limits

- Live upstream metadata is temporal. The recorded final state reflects the bounded calls made on 2026-07-09.
- No image/audio binary was downloaded, proxied, cached, transformed, or stored.
- DuckDB's single-writer transaction protects apply; operators must stop source refresh and the local API writer before running the maintenance command.
- Independent final review passed and is recorded at `.10x/reviews/2026-07-09-existing-plan-media-backfill-review.md`.
