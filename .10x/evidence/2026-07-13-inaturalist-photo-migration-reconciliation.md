Status: recorded
Created: 2026-07-13
Updated: 2026-07-13
Relates-To: `.10x/tickets/done/2026-07-13-reconcile-inaturalist-photo-migration-evidence.md`, `.10x/specs/curated-inaturalist-representative-bird-photos.md`

# iNaturalist photo migration campaign reconciliation evidence

## What was observed

The authoritative iNaturalist-only catalog campaign now owns and checkpoints all 706 catalog photo rows. The supported photo-refresh path resumed exactly 82 prior-campaign terminal non-binomial/hybrid placeholders, issued zero provider requests, and did not requery the 624 current-campaign rows. The final run reconciles 706 outcomes, 624 selector lookups, and 1,248 historical v2/v1 request attempts.

All 706 catalog photo singletons and eight saved-plan photo singletons remain strict and valid. Catalog state remains 622 available iNaturalist photos plus 84 typed placeholders; saved planner remains eight available iNaturalist photos. There are zero Wikimedia or GBIF representative-photo rows. Mixed-placeholder API/browser GETs return 200 without discovery or database writes.

## Procedure and results

### Campaign implementation and deterministic proof

`run_catalog_photo_refresh` and its read-only inspector now define completion by strict terminal photo rows owned by the latest authoritative campaign. A completed but partially owned campaign resumes its missing owned checkpoints rather than treating globally valid prior-campaign rows as work performed by the latest run. Historical request attempts are conservatively reconstructed only when legacy outcomes prove every lookup completed both iNaturalist stages.

`tests/test_catalog_media.py::test_photo_only_refresh_reconciles_prior_campaign_terminal_without_network` creates a mixed-owner campaign, forbids provider requests, and proves the missing terminal identity is adopted with coherent outcomes and 0/2-stage request accounting. All 22 catalog-media tests passed.

### Preflight

- `lsof data/databox.duckdb` found no open DuckDB handle before the repair.
- Read-only `scripts/catalog_media.py --dry-run-photos` reported campaign complete=624 and remaining=82 under run `catalog_photo_617cb94de24c470b89c8b7ff1e8ca447`.
- A fresh sanitized snapshot recorded 86 protected database fingerprints, 21 external hashes, 706/706 strict catalog rows, eight/eight strict planner rows, zero planner invalid/duplicate rows, and provider counts 622 available/84 unavailable.
- No Quack, SQLMesh, Uvicorn, source-refresh, recommendation-media, or catalog-media writer was active.

### Exact supported repair path

The CLI `--refresh-photos` path was invoked exactly once in-process with both selector transport and default provider transport guarded to raise on any request. The guard also required every selected result to report `request_count=0` and asserted exactly 82 selected identities.

Result:

```text
mode=photo_refresh run_id=catalog_photo_617cb94de24c470b89c8b7ff1e8ca447 catalog_count=706 target_taxa_count=706 processed_taxa_count=706 complete_taxa_count=706 remaining_taxa_count=0 lookup_count=624 request_count=1248 available_photo_count=622 unavailable_photo_count=84
guard_target_count=82 guard_provider_request_count=0
```

No planner apply, broad catalog apply, manual SQL edit/delete/reset, provider request, model, email, source/AVONET/call refresh, or binary operation occurred.

### Final run ownership and no-op inspection

Read-only SQL established:

```text
run_id=catalog_photo_617cb94de24c470b89c8b7ff1e8ca447
status=complete target=706 processed=706 lookup=624 request=1248
outcomes={"identity.unavailable":82,"inaturalist.available":622,"inaturalist.no_eligible":2}
safe_failure=NULL
owned_photo_rows=706
```

The prior campaign owns zero current photo rows. Read-only `--dry-run-photos` then reported processed/complete=706, remaining=0, and zero lookup/request activity. It did not write or call a provider.

### Current API and data state

A forbidden-discovery validation run reconstructed every row and reported:

- catalog: 706 valid singletons = 622 `inaturalist:available` + 84 `curated_photo:unavailable`;
- planner: eight valid singleton iNaturalist photos, zero dry-run targets/lookups/duplicates;
- legacy representative rows: zero;
- HTTP 200: catalog, placeholder profile `baitea`, map snapshot, saved plan, and `/birds`;
- database SHA-256 unchanged across GETs.

### Protected fingerprints and durable artifacts

The reproducible sanitized fingerprint procedure and raw artifacts are stored under `.10x/evidence/.storage/`:

- `2026-07-13-inaturalist-photo-fingerprint-procedure.py`;
- `2026-07-13-inaturalist-only-original-pre.json` and `...original-post.json`;
- `2026-07-13-inaturalist-reconcile-pre.json`, `...post.json`, `...post-gates.json`, and `...final.json`;
- `2026-07-13-inaturalist-reconcile-apply.txt`;
- `2026-07-13-inaturalist-reconcile-api-validation.json`;
- `2026-07-13-inaturalist-reconcile-rate-isolation.txt`;
- `2026-07-13-inaturalist-reconcile-artifact-sha256.txt`.

Artifacts contain schemas, row counts, commutative row digests, bounded run metadata, and external file hashes—not personal row values, credentials, raw provider payloads, or arbitrary URLs.

All 86 protected database fingerprints and 20 non-rate-ledger external hashes matched pre-repair, post-repair, post-gates, and final snapshots. The owned locked rate ledger changed only during the first full test run: two catalog API test calls supplied a fake curated getter without the required no-op limiter injection, increasing its sanitized counter. Those tests were repaired to inject `before_inaturalist_request=lambda: None`; the focused culprit test then passed with the ledger digest unchanged. The ledger difference is explicitly bounded:

```text
before=86780368a1a586ff2d227ad5b393c9751af698bf49a05446697050688ecae229
after=586b80538d1d0ca5feb658d9c597e21b6cf1b42e2b25df45077122f3d012f738
current sanitized state={"count":24,"day":"2026-07-13","last_request":1783967322.5989912}
```

The authorized campaign repair itself left the ledger unchanged; pre-repair and immediate post-repair hashes matched. The test isolation fix prevents recurrence.

### Verification gates

- Focused Python: 145 passed.
- Full Python: 776 passed, three snapshots, 86.43% coverage.
- Narrow test-isolation regression: one passed and ledger hash unchanged.
- Ruff check/format, MyPy for 99 source files, secret scan, generated staging/platform-health checks, 13 SQLMesh tests, docs generation, strict MkDocs, source-layout checks, and all 11 pre-commit hooks passed.
- `git diff --check` passed and the staged file list was empty.

## What this supports

This supports every owning-ticket criterion: authoritative campaign ownership; exactly 82 zero-request terminal reconciliations; preservation of 624 completed rows; coherent 706/624/1248/outcome accounting; zero-target read-only completion; strict catalog/planner cardinality; mixed-placeholder GET availability; reproducible durable fingerprint evidence; bounded diagnosis and repair of test-only shared-ledger mutation; and preservation of protected state.

## Limits

The historical request count is reconstructed from a terminal campaign whose 622 available and two no-eligible outcomes prove both v2 and v1 stages completed; it is not inferred for ambiguous/provider-failure outcomes. Provider-hosted images may later change or disappear. Automated/TestClient evidence does not establish physical-browser layout, live image loading, visual subject quality, or assistive-technology behavior.
