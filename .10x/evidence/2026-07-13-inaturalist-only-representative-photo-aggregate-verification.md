Status: recorded
Created: 2026-07-13
Updated: 2026-07-13
Relates-To: `.10x/tickets/done/2026-07-11-verify-curated-representative-photos.md`, `.10x/specs/curated-inaturalist-representative-bird-photos.md`

# iNaturalist-only representative-photo aggregate verification

## What was observed

The active iNaturalist-only implementation and exactly-once serialized migration satisfy every non-review aggregate criterion. Fresh bounded read-only reconstruction found 706/706 strict catalog photo singletons (622 available iNaturalist, 84 typed placeholders) and eight/eight strict saved-plan photo singletons (all available iNaturalist), with zero Wikimedia or GBIF representative rows. Mixed placeholder API, profile, Field Map, saved-plan, and browser GETs returned 200 while provider discovery was replaced by a forbidden function; the DuckDB SHA-256 remained unchanged.

No implementation, provider request, DuckDB write, or live migration was performed during this aggregate phase.

## Active-spec scenario mapping

1. **First eligible curated shortlist photo:** `tests/test_curated_photo.py::test_first_eligible_curated_photo_wins_without_other_provider_requests` proves ordered v2/v1 selection and first-eligible behavior. Implementation evidence records 172 focused Python tests and the live migration records only iNaturalist v2 exact identity plus v1 exact-ID shortlist requests.
2. **Ambiguous/inactive/subspecies/cross-version/hybrid/non-binomial:** `tests/test_curated_photo.py::test_exact_active_species_identity_is_required`, `::test_cross_version_identity_mismatch_fails_closed`, and `::test_non_binomial_makes_no_request`; catalog persistence coverage is `tests/test_catalog_media.py::test_non_binomial_identity_is_unavailable_without_parent_lookup`.
3. **Dimension floor:** `tests/test_curated_photo.py::test_dimension_floor` covers 900x900, 1200x700, and 1000x750 orientation-independent boundaries.
4. **License/attribution/URL/source safety:** `tests/test_curated_photo.py::test_unsafe_or_ineligible_candidate_yields_typed_unavailable`, `::test_display_url_validator_rejects_adversarial_urls`, `::test_source_url_validator_is_exact`, and `::test_default_transport_rejects_redirect_and_oversized_body`; `app/src/curatedPhotoValidation.test.ts` and `app/src/tripPlanValidation.test.ts` reject provider, ID, host/path, port, query, fragment, credentials, license, dimension, identity, and extra-field mismatches.
5. **Typed unavailable placeholder without whole-response failure:** `tests/test_bird_catalog_api.py::test_list_returns_all_706_stable_bounded_rows_without_network_or_writes`, `::test_catalog_get_returns_validated_persisted_media_and_fails_stale_identity_closed`, `app/src/BirdPages.test.tsx` “accepts mixed typed-unavailable and curated iNaturalist catalog photos,” plus the fresh current-state GET proof below. This directly closes the user-observed `invalid unavailable photo` failure.
6. **Image-load failure retains metadata and announcement:** `app/src/BirdPages.test.tsx` “preserves attribution and shows safe image and call load errors,” `app/src/FieldMap.test.tsx` “preserves photo source, license, and attribution after thumbnail load failure,” and `app/src/App.test.tsx` “retains photo attribution and safe links after an image load failure.”
7. **Catalog interruption/resume/no repeat:** `tests/test_catalog_media.py::test_interruption_resumes_without_repeating_checkpoint_and_hybrid_has_no_lookup`, `::test_706_taxon_apply_campaign_resumes_partial_batches_until_complete`, `::test_photo_only_refresh_resumes_and_preserves_calls`, and `::test_completed_photo_refresh_rerun_is_database_and_network_no_op`.
8. **Saved-plan photo-only preservation/resume:** `tests/test_recommendation_media_backfill.py::test_curated_photo_only_replaces_legacy_photos_preserves_calls_and_is_idempotent`, `::test_curated_lookup_interruption_resumes_without_repeating_checkpoint`, `::test_mid_persistence_failure_preserves_completed_photo_checkpoint`, and migration fingerprints proving all non-photo evidence/state unchanged.
9. **GET zero discovery/write and strict rejection:** `tests/test_catalog_media.py::test_inspect_is_read_only_network_free_and_does_not_create_tables`, `::test_curated_photo_dry_run_is_network_free_and_read_only`, `tests/test_bird_catalog_api.py::test_list_returns_all_706_stable_bounded_rows_without_network_or_writes`, strict backend/frontend response tests, and the fresh forbidden-discovery/hash proof below.
10. **Field Map exact catalog reuse:** `app/src/FieldMap.test.tsx` covers photo source/license/attribution and list/point/cluster/selected-card equivalence; `tests/test_map_snapshot_api.py` and prior implementation evidence prove map photos derive from catalog rows with no separate map media store.

## Fresh bounded read-only validation

Command:

```text
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python /tmp/inat_aggregate_validate.py
```

The script opened `data/databox.duckdb` read-only, reconstructed every catalog row with `curated_photo_result_from_row`, reconstructed every planner singleton with the persisted full-contract validator, ran the planner curated-photo dry-run, replaced provider discovery with a forbidden function, requested `/api/birds`, one placeholder profile, `/api/map-snapshot`, one saved plan, and `/birds`, and compared the complete DuckDB SHA-256 before/after.

Observed:

```json
{"catalog_valid":706,"catalog_counts":{"inaturalist:available":622,"curated_photo:unavailable":84},"planner_valid":8,"planner_counts":{"inaturalist:available":8},"legacy_representative_rows":0,"planner_dry_run_targets":0,"planner_dry_run_lookups":0,"api_catalog_counts":{"available":622,"placeholder":84},"get_statuses":{"catalog":200,"placeholder_profile":200,"map":200,"plan":200,"browser":200},"database_sha256_unchanged":true,"latest_photo_run":["complete",706,706,706,624,"{\"inaturalist.available\":622,\"inaturalist.no_eligible\":2}"]}
```

Every catalog species and planner recommendation had exactly one photo row; no duplicate/missing singleton was found. The placeholder profile `baitea` returned typed unavailable successfully. All eight saved recommendations returned available iNaturalist photos.

## Reused fresh post-migration gates

`.10x/evidence/2026-07-13-inaturalist-only-representative-photo-migration.md` records, after the live migrations:

- 159 focused Python tests and 145 focused frontend assertions;
- 776 full Python tests, three snapshots, 86.33% coverage;
- 295 full frontend tests, strict TypeScript, production build, and bundle audit (12 names and 10 configured values absent);
- Ruff check/format, MyPy across 99 files, secret scan, generated staging/platform-health/docs checks, strict MkDocs, source-layout check, 13 SQLMesh tests, all 11 pre-commit hooks, `git diff --check`, and empty staging.

Tests used deterministic injected transports and forbidden-live-network boundaries. The only authorized live calls were the recorded iNaturalist metadata-only probe and exactly-once serialized migrations; no image binary was requested or stored.

## Protected-state and side-effect limits

Migration evidence records 86 protected database fingerprints and 19 external hashes identical before migration, after migration, and after gates. Protected coverage includes non-photo catalog/planner evidence, calls, facts/order/confidence/rationale/timestamps/location/weather, personal observations/Watches, calendar/outbox, source-refresh state, credentials/configuration, warehouse/SQLMesh state, and unrelated runtime tables/files. The saved-plan result inserted zero calls. Code-path inspection, command boundaries, counters, and fingerprints support zero model, email, routine source/catalog-fact/AVONET/call refresh, recommendation regeneration, or binary media work.

## What this supports

All non-review acceptance criteria are satisfied against the active specification. Current catalog/profile/Field Map/new-planner/saved-planner contracts accept only strict iNaturalist available results or typed placeholders; GETs are local/read-only; migration cardinality and preservation reconcile; and the complete post-migration gate set passes.

## Final closure addendum

The earlier current-state run JSON and limits above describe the pre-hardening aggregate checkpoint. Final operational hardening and campaign reconciliation supersede its run-counter interpretation without changing the 706/8 photo state.

Final authoritative catalog campaign:

```text
status=complete target=706 processed=706 lookup=624 request=1248
outcomes={"identity.unavailable":82,"inaturalist.available":622,"inaturalist.no_eligible":2}
owned_photo_rows=706 remaining=0
```

Actual v2/v1 request attempts are now distinct from logical lookups. Catalog and planner runs durably record run status, checkpoint/processed, lookup/request counts, bounded outcome/failure totals, timing, and safe failure text. Provider budget/transport/schema failures persist safe placeholders but remain retryable; identity-invalid and safely exhausted-shortlist results are terminal. Explicit photo-only reruns target only retryable/missing/invalid results and become no-ops after success.

The local iNaturalist budget is coordinated across processes and restarts with atomically locked durable state, one-second spacing, and a 9,999-request UTC-day cap. Deterministic tests use isolated/no-op state. Dormant GBIF representative-photo helpers and injection seams were deleted; GBIF occurrence context remains separately typed.

The supported reconciliation adopted exactly 82 prior-campaign terminal non-queryable placeholders with zero provider requests and did not requery 624 current-campaign rows. Current state remains 622 available iNaturalist photos plus 84 typed catalog placeholders, and eight available saved-plan photos, with zero legacy representative providers.

Durable sanitized evidence is stored under `.10x/evidence/.storage/`: the reproducible fingerprint procedure, original/reconciliation pre/post/post-gate/final JSON, API validation, bounded apply/rate-isolation `.txt` files, and checksum manifest. `sha256sum -c .10x/evidence/.storage/2026-07-13-inaturalist-reconcile-artifact-sha256.txt` passes. The `.txt` rename repairs the final privacy review's ignored-`.log` packaging note. All 86 protected database fingerprints and 20 non-rate-ledger external hashes match within recorded limits.

Final validation includes 776 Python tests, three snapshots, 295 frontend tests, strict TypeScript, production build/bundle audit, Ruff/format/MyPy, secret/generated/docs/source-layout checks, 13 SQLMesh tests, all hooks, diff check, and empty staging.

Final independent verdicts:

- Architecture: pass — `.10x/reviews/2026-07-13-inaturalist-only-closure-architecture-review.md`.
- Correctness: pass — `.10x/reviews/2026-07-13-inaturalist-only-closure-correctness-review.md`.
- Privacy/security/source: pass — `.10x/reviews/2026-07-13-inaturalist-only-closure-privacy-security-source-review.md`.
- UX/accessibility: pass — `.10x/reviews/2026-07-13-inaturalist-only-final-ux-accessibility-review.md`.

All eight aggregate acceptance criteria and all ten active-spec scenarios are supported by the combined implementation, migration, hardening, reconciliation, aggregate, and review evidence.

## Limits and no-action rationale

Provider-hosted image URLs/content and provider schemas may later change because binaries are intentionally not stored. Physical responsive rendering, live remote-image availability, visual subject quality, and NVDA/JAWS/VoiceOver behavior were not established by automated/TestClient evidence. These are accepted design/test limits rather than unfinished implementation: remote mutability follows the metadata-only/no-binary decision, while physical-browser and assistive-technology sampling is not required by the active automated closure contract. No follow-up ticket is opened unless a user-observed rendering/accessibility defect or a new manual-verification requirement appears. The rate limiter coordinates processes sharing one local filesystem/state path, not multiple hosts; that matches the current local-only deployment. `/api/v1/birds` is compatibility/static routing; `/api/birds` is the governed JSON endpoint.
