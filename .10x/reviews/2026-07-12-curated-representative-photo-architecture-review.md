Status: recorded
Created: 2026-07-12
Updated: 2026-07-12
Target: `.10x/tickets/done/2026-07-11-verify-curated-representative-photos.md`, `.10x/specs/superseded/curated-representative-bird-photos.md`, curated representative-photo implementation and migration records
Verdict: fail

# Curated representative-photo architecture review

## Review

- **Correct:** The selector has a coherent shared server-side boundary. `select_curated_photo` stops after an eligible Wikimedia result and distinguishes Wikimedia failure from a safe no-eligible result before entering iNaturalist (`packages/databox/databox/curated_photo.py:125-158`, `:302-361`, `:552-598`). Offline validation binds persisted provider, exact identity, URL grammar, attribution, license, dimensions, attempted-source order, and timestamp (`packages/databox/databox/curated_photo.py:160-239`).
- **Correct:** Catalog/profile/map GET paths reconstruct persisted metadata and apply the offline validator rather than invoking discovery (`packages/databox/databox/api.py:1236-1303`, `:1417-1435`). Trip Planner does the same for curated evidence (`packages/databox/databox/api.py:849-900`). The recorded API tests also compare the DuckDB file before and after GETs. No GET-path network or write owner was found.
- **Correct:** Field Map has no separate media persistence owner. It reads catalog-media rows and passes them through the same `_catalog_photo` conversion (`packages/databox/databox/api.py:1417-1435`). The aggregate read-only schema inspection found no separate map media table.
- **Correct:** Current persisted state was independently reconstructed through `CuratedPhotoResult`: 706/706 valid catalog rows and 8/8 valid singleton saved-plan rows, as recorded in `.10x/evidence/2026-07-12-curated-representative-photo-aggregate-verification.md`. The child evidence also records exact protected-state fingerprints and empty staging.

- **Blocker:** The legacy catalog refresh path still owns representative-photo persistence and can destroy the completed curated state. `enrich_recommendation_media` returns curated photos in its normal production configuration (`packages/databox/databox/agent_tools/recommendation_media.py:78-157`), but `_bounded_catalog_evidence` still requires `source == "gbif"` for every photo and converts any curated result to a GBIF unavailable result (`packages/databox/databox/catalog_media.py:388-413`). `_lookup_taxon` sends that result to `_persist_taxon`, which deletes the species' existing rows before inserting the replacement (`packages/databox/databox/catalog_media.py:415-489`). The still-supported `scripts/catalog_media.py --refresh` path invokes this legacy batch (`scripts/catalog_media.py:19-48`). Therefore an explicit ordinary catalog refresh can overwrite valid curated photos with legacy-typed unavailable rows. This is a persistence-ownership collision and violates the no-GBIF-representative-photo contract. The full-suite pass does not cover this post-migration transition; existing legacy tests use the injected GBIF compatibility seam and mask the production behavior.

- **Significant:** Saved-plan resume checkpoints occur only after the entire target set has been looked up. `run_media_backfill` calls `enrich_recommendation_media` once with all photo targets and receives the complete in-memory batch before entering the per-recommendation transaction loop (`packages/databox/databox/agent_tools/recommendation_media_backfill.py:116-169`). A process interruption during lookup repeats every earlier completed provider lookup on rerun. The test named `test_curated_photo_only_commits_each_completed_recommendation` injects failure during persistence, not during provider lookup (`tests/test_recommendation_media_backfill.py:492-533`), so it does not prove the specification's “interruption ... without repeated completed lookups” requirement. The live eight-row run completed successfully, but the claimed general resume architecture is stronger than the implementation.

- **Significant:** Saved-plan idempotence classifies a photo as complete from cardinality and provider name alone. `_inspect` replaces a singleton only when its source is outside `wikimedia_commons`, `inaturalist`, or `curated_photo`; it does not reconstruct and validate identity, payload, URL, license, dimensions, status, or exact recommendation scientific name (`packages/databox/databox/agent_tools/recommendation_media_backfill.py:240-314`). A malformed, stale, or partially corrupted curated row is skipped forever and produces a false no-op. This differs from catalog resume, which derives completion through `_valid_result_rows` and `curated_photo_result_is_safe` (`packages/databox/databox/catalog_media.py:277-308`, `:750-789`).

- **Significant:** Planner browser validation is weaker than the shared server validator for Wikimedia. `curatedPhotoMatches` accepts any Wikimedia source record matching `Q…|File:.+`, any upload path merely containing `/wikipedia/commons/thumb/`, and any Commons source path merely starting `/wiki/File:`; it does not bind the three file titles, MD5 buckets, thumbnail width, or exact source identity (`app/src/tripPlanValidation.ts:276-294`). The rendering guard repeats the same coarse checks (`app/src/App.tsx:118-141`). Thus a response with source record `File:A.jpg`, thumbnail `File:B.jpg`, and source page `File:C.jpg` passes the browser boundary even though the server validator rejects it. This violates the explicit browser source/identity-validation requirement and illustrates validation drift from duplicating only part of the shared grammar.

- **Significant:** Aggregate observability does not satisfy the active specification. `birding_catalog_media.photo_runs` stores only aggregate target/processed/lookup counters and one terminal failure string (`packages/databox/databox/catalog_media.py:150-166`); it has no safe counts by attempted provider/status or per-provider failure class. Available iNaturalist results retain only attempted-source order, not why Wikimedia produced no eligible result. The final migration yielded 621 iNaturalist, 85 unavailable, and zero Wikimedia results, while the governing decision cites P18 presence for 616/624 species. Zero Wikimedia selections are not by themselves proof of incorrect selection, but the required traces do not exist to reconcile this outcome. Consequently the aggregate evidence's claim that all non-review specification criteria pass is overstated.

- **Note:** The child and aggregate records accurately report the commands and current-state fingerprints, but their resume and aggregate-coherence conclusions do not account for the findings above. The aggregate ticket must not close until the blocker is repaired and rerun evidence proves the ordinary refresh transition preserves curated ownership. The two requested root files, `plan.md` and `progress.md`, were absent; this review used the active parent/ticket/spec/decision graph instead.

## Verdict

**Fail.** Current migrated rows are valid and GET paths are pure, but a supported catalog refresh can overwrite curated representative photos, saved-plan lookup resumption does not meet the no-repeat contract, browser Wikimedia validation is incomplete, and the aggregate observability record cannot explain provider outcomes as required.

## Required resolution evidence

1. Add a transition test beginning with valid curated catalog photos, run the ordinary supported catalog refresh path, and prove curated photo ownership/results are preserved or safely refreshed without any GBIF representative row.
2. Checkpoint saved-plan lookups per recommendation (or explicitly supersede the no-repeat lookup requirement), and test interruption during lookup rather than only during insertion.
3. Determine saved-plan completion by reconstructing the persisted curated result against the recommendation's exact scientific identity.
4. Reuse an exact browser-side Wikimedia grammar or make the duplicated checks equivalent to the server validator; add mismatched file-title/hash/width tests.
5. Record provider-attempt outcome/failure counts and reconcile the zero-Wikimedia final result before claiming aggregate spec coherence.

## Residual risk

Even after these findings are resolved, provider-hosted images can disappear or change availability because only metadata and remote bounded URLs are stored. Physical-browser, responsive-device, screen-reader, keyboard, and live-image-load validation remain unperformed, as already bounded by the aggregate evidence.

```acceptance-report
{
  "criteriaSatisfied": [
    {
      "id": "criterion-1",
      "status": "satisfied",
      "evidence": "Performed an independent review only, wrote solely to the required /tmp output, and made no repository edits or scope expansion."
    },
    {
      "id": "criterion-2",
      "status": "satisfied",
      "evidence": "Inspected the active ticket/spec/decisions, parent and all three child tickets, aggregate and child evidence/reviews, relevant implementation/tests/diff, and cited concrete code paths and line ranges for each finding."
    }
  ],
  "changedFiles": [
    "packages/databox/databox/curated_photo.py",
    "packages/databox/databox/catalog_media.py",
    "packages/databox/databox/agent_tools/recommendation_media.py",
    "packages/databox/databox/agent_tools/recommendation_media_backfill.py",
    "packages/databox/databox/api.py",
    "scripts/catalog_media.py",
    "app/src/birdApi.ts",
    "app/src/tripPlanValidation.ts",
    "app/src/App.tsx",
    "app/src/BirdPages.tsx",
    "app/src/FieldMap.tsx"
  ],
  "testsAddedOrUpdated": [
    "tests/test_curated_photo.py",
    "tests/test_catalog_media.py",
    "tests/test_recommendation_media.py",
    "tests/test_recommendation_media_backfill.py",
    "tests/test_bird_catalog_api.py",
    "tests/test_map_snapshot_api.py",
    "app/src/BirdPages.test.tsx",
    "app/src/FieldMap.test.tsx",
    "app/src/tripPlanValidation.test.ts",
    "app/src/App.test.tsx"
  ],
  "commandsRun": [
    {
      "command": "git status --short && git diff --stat && git diff --cached --stat",
      "result": "passed",
      "summary": "Inspected working-tree scope and confirmed the cached/staged diff is empty."
    },
    {
      "command": "git diff -- <curated-photo implementation and test files>",
      "result": "passed",
      "summary": "Inspected the relevant implementation/test diff; output was large but included the catalog, planner, API, browser, migration, and test changes reviewed above."
    }
  ],
  "validationOutput": [
    "Recorded aggregate gates: 769 Python tests and 273 frontend tests passed; strict TypeScript, production build/bundle audit, Ruff, format, MyPy, SQLMesh tests, hooks, secret/generated/docs checks, diff check, and empty staging passed.",
    "Recorded offline state validation: catalog 706/706 valid curated results; saved planner 8/8 valid singleton curated results; no separate map-media table.",
    "Independent architecture inspection found one blocker and four significant gaps despite the current-state and full-suite passes."
  ],
  "residualRisks": [
    "Provider-hosted images may later disappear or change availability.",
    "No physical-browser, responsive-device, screen-reader, keyboard, or live-image-load validation was performed.",
    "The final zero-Wikimedia provider outcome cannot be diagnosed from the persisted run observability."
  ],
  "noStagedFiles": true,
  "diffSummary": "Shared curated selector, catalog/planner persistence and migrations, API/browser validation, UI attribution, and tests were added or updated; independent review found conflicting legacy catalog persistence ownership and incomplete resume/browser/observability contracts.",
  "reviewFindings": [
    "blocker: packages/databox/databox/catalog_media.py:388-489 - supported legacy catalog refresh can convert curated results to GBIF unavailable rows and overwrite the migrated state",
    "significant: packages/databox/databox/agent_tools/recommendation_media_backfill.py:116-169 - lookup work is batched before per-recommendation commits, so lookup interruption repeats completed requests",
    "significant: packages/databox/databox/agent_tools/recommendation_media_backfill.py:240-314 - provider-name-only completion skips malformed or stale curated rows",
    "significant: app/src/tripPlanValidation.ts:276-294 and app/src/App.tsx:118-141 - Wikimedia browser validation does not bind exact file identity/path grammar",
    "significant: packages/databox/databox/catalog_media.py:150-166 - run records omit required provider/status and failure-class observability"
  ],
  "manualNotes": "Verdict is fail. No repository files were edited. Requested plan.md and progress.md were absent."
}
```
