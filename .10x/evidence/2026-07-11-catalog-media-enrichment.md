Status: recorded
Created: 2026-07-11
Updated: 2026-07-11
Relates-To: .10x/tickets/done/2026-07-11-implement-catalog-media-enrichment.md, .10x/specs/arizona-catalog-media.md

# Catalog media enrichment

## What was implemented

`birding_catalog_media.results` owns one metadata-only photo result and one call result per exact catalog species code. `birding_catalog_media.runs` records explicit apply/refresh lifecycle, bounded targets, processed checkpoints, lookup counts, completion, and sanitized failure class. The implementation reuses the existing GBIF/Xeno-canto selectors and their response-size, timeout, exact identity, Arizona-first call, license, URL, attribution, and derived GBIF cache-hash validation.

Apply skips only fully validated current species-code/scientific-name result pairs. Apply and refresh each use one durable campaign ID across bounded invocations until every original target is checkpointed; partial batches remain `running`, preserve the original target count, and advance cumulative processed/lookup counts. Each taxon's two results replace atomically; an interrupted or failed taxon leaves its prior aggregate intact. Hybrid and non-exact-binomial identities persist two unavailable results without any provider lookup.

Catalog list/detail GETs only read persisted rows. Absent, incomplete, stale-identity, wrong-source, malformed JSON, unsafe, or invalid metadata becomes an exact typed unavailable photo/call object without dropping the taxon. Browser validators enforce exact fields, identity, status cardinality, dates, attribution, licenses, and provider URL grammars. React presentation is explicitly excluded from this ticket.

## Focused validation

```text
uv run --no-sync pytest --no-cov -q \
  tests/test_catalog_media.py tests/test_bird_catalog_api.py tests/test_recommendation_media.py
56 passed

catalog/API tests after final GET hash, malformed-available, and incomplete-aggregate assertions
26 passed

focused browser catalog/collection/target tests
39 passed

Ruff and focused MyPy
passed
```

Adversarial tests cover absent-table inspect and GET, read-only hash preservation, interruption/resume, zero-work second apply, a 706-taxon 250/250/206 apply campaign with durable running/running/complete state, multi-invocation refresh resume, per-taxon rollback preserving the prior aggregate, hybrid/no-binomial zero lookup, exact result cardinality, unsafe identity/license/URL downgrade, stale identity downgrade, malformed source/JSON/payload/selection reprocessing, available API output, unsupported photo format and missing selection-reason API downgrade, network-blocked GET, missing-Xeno-key preflight before writes, and strict browser rejection.

## Full gates

```text
uv run --no-sync pytest -q --record-mode=none --block-network
432 passed; 3 snapshots passed; coverage 86.71%

task app:check
200 tests passed; TypeScript, Vite build, and bundle audit passed

uv run --no-sync mypy packages/
92 source files passed

secret scan, Ruff, format, all pre-commit hooks, generated docs freshness
passed

MkDocs strict build
passed
```

## Live read-only inspection

No live apply or refresh ran. Credential readiness was checked as a boolean only (`xeno_canto_api_key_configured=true`) without printing its value. The explicit inspection opened the warehouse read-only, performed zero lookup, and left the warehouse SHA-256 unchanged:

```text
before=37fe6a2a660e90e767b4b0e4844eb76e9984ac59d7dfdaa38a3caeaaff0df701
after=37fe6a2a660e90e767b4b0e4844eb76e9984ac59d7dfdaa38a3caeaaff0df701
catalog_count=706
complete_taxa_count=0
target_taxa_count=706
lookup_count=0
birding_catalog_media tables=0
```

No media table, metadata row, run row, source call, model call, refresh, or binary artifact was created in the live warehouse. Apply/refresh now fail before opening a writer or creating tables when `XENO_CANTO_API_KEY` is unavailable.

## Independent review and authorized live apply

The initial review findings were repaired and the independent follow-up review passed with no blocker. Review: `.10x/reviews/2026-07-11-catalog-media-enrichment-review.md`.

After the boolean prerequisite succeeded and API, Quack, and SQLMesh writers were stopped, the authorized live apply completed in 29 sequential bounded invocations under one durable run. Only aggregate results were recorded:

```json
{
  "catalog_count": 706,
  "complete_taxa_count": 706,
  "result_rows": 1412,
  "distinct_taxa": 706,
  "photo": {"available": 524, "unavailable": 182},
  "call": {"available": 600, "unavailable": 106},
  "remaining_taxa_count": 0,
  "durable_run": {
    "mode": "apply",
    "status": "complete",
    "target_taxa_count": 706,
    "processed_taxa_count": 706,
    "lookup_count": 1523,
    "sequential_batches": 29
  }
}
```

A second explicit apply created a zero-target completed run with `processed_taxa_count=0` and `lookup_count=0`; it performed no provider lookup. The subsequent read-only inspect exactly matched 706 complete taxa, 524/182 photo coverage, 600/106 call coverage, and zero remaining. The post-apply warehouse SHA-256 observed during read-only reconciliation was:

```text
805d6d929988bc7b01d08e89021f39d245074d9532ae42f27e9ca063bda9551b
```

The live tables contain exactly 1,412 rows: one photo and one call result for each of 706 exact catalog taxa. No source identity, attribution, URL, credential, or unavailable reason was printed or recorded in this aggregate evidence.

## Retrospective

- A bounded invocation is not a complete run. Durable target, processed, remaining, and status fields must describe the whole campaign and be tested with a realistically larger target set.
- Resume eligibility must validate the complete persisted safety contract, not just identity and cardinality; otherwise corrupt rows become permanent false checkpoints.
- External-service prerequisites belong before the writer boundary and should expose readiness as a boolean rather than a secret value.
- Reusing one governed selector and one offline persisted-result validator kept live acquisition and GET-time fail-closure aligned without adding a second media policy.

## Limits

Remote image/audio bytes are never stored, proxied, cached, or tested for durable availability. Provider-hosted media may later disappear; the API remains fail-closed when persisted metadata is unsafe.
