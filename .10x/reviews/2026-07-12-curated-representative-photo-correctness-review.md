Status: recorded
Created: 2026-07-12
Updated: 2026-07-12
Target: `.10x/tickets/done/2026-07-11-verify-curated-representative-photos.md`, `.10x/specs/superseded/curated-representative-bird-photos.md`, and the current curated-photo implementation diff
Verdict: fail

# Curated representative-photo correctness review

## Review

### Correct

- **Selector identity and stopping behavior are substantially correct.** `packages/databox/databox/curated_photo.py:125-239,302-360,552-724` conservatively requires an exact normalized binomial, resolves exact Wikidata P225 identity before P18 metadata, rejects ambiguous exact entities, stops on Wikimedia transport/malformed-data failure, calls iNaturalist only after a safe no-eligible result, verifies exact active species-rank identity across v2 and v1, and selects the first eligible curated iNaturalist photo. The focused tests cited in the aggregate evidence exercise response reordering, Wikimedia stop semantics, iNaturalist shortlist order, cross-version mismatch, ambiguity, and network-free non-binomial failure.
- **The shared quality, attribution, license, and server-side URL floor is fail-closed.** `packages/databox/databox/curated_photo.py:160-300,481-550,646-724,903-1003` checks integral dimensions against the 1,000×750 floor, sanitizes bounded creator text, canonicalizes only the allowed CC families/versions, rejects unsupported formats and unsafe URL components, binds iNaturalist URLs to photo ID, and binds Commons URLs to file title and thumbnail width. Available persisted results are revalidated offline before activation.
- **Catalog/profile/map coherence is structurally sound.** `packages/databox/databox/api.py:1236-1299,1359-1426` reconstructs and validates the exact current catalog photo, attaches that same catalog-derived response to catalog/profile rows, and derives Field Map photos from the same species-keyed catalog-media rows without a map-specific media store.
- **Placeholder semantics are safe on the inspected server paths.** Invalid, stale, unavailable, or unvalidated catalog metadata is reduced to a null-URL unavailable photo; the selector never falls back to GBIF after curated-source exhaustion. The frontend components preserve attribution after browser image-load failure and otherwise show the unavailable placeholder.
- **Migration cardinality and idempotence have strong recorded support.** The child and aggregate records report 706/706 unique current catalog results (621 iNaturalist, 85 curated unavailable), eight/eight singleton saved-plan photo results, no separate map-media table, a missing-only catalog resume delta of exactly 250 for 250 missing identities, and deterministic interrupted/resume plus completed-rerun no-op tests (`tests/test_catalog_media.py:604+`; curated backfill tests in `tests/test_recommendation_media_backfill.py`). Protected-state fingerprints support the claim that calls and unrelated state were unchanged within the recorded limits.
- **Repository staging was empty at review time.** `git diff --cached --stat` returned no entries.

### Significant finding 1 — legacy GBIF representative photos remain activatable by backend planner paths

**Code:**

- `packages/databox/databox/agent_tools/recommendation_media.py:127-143`
- `packages/databox/databox/api.py:849-946`

`enrich_recommendation_media` still switches to the legacy GBIF representative-photo selector whenever a `gbif_getter` is injected and no curated getter is supplied. This is not merely retained occurrence-context parsing: it can create a new active `recommendation_photo` from GBIF. `_recommendation_photo` also retains a complete legacy GBIF activation branch and can return that photo as available from persisted evidence.

This conflicts with the active specification's source-order/stopping rule, its statement that representative-photo providers are exactly `wikimedia_commons` or `inaturalist`, and child acceptance requiring planner APIs to reject legacy active URLs. Existing tests intentionally exercise the legacy branch, so passing tests do not prove the active contract. Although the recorded live migration currently leaves no GBIF recommendation-photo rows, stale/imported/corrupted legacy rows or callers using the existing injection boundary can still reactivate the superseded provider.

**Required resolution:**

1. Make all new recommendation-photo enrichment use `select_curated_photo`; use a dedicated curated transport injection for tests rather than interpreting `media_gbif_getter` as representative-photo authority.
2. Make `_recommendation_photo` reduce all non-curated representative-photo evidence to unavailable. Preserve GBIF only as separately typed occurrence-context evidence.
3. Replace legacy-positive API tests with adversarial tests proving GBIF `recommendation_photo` evidence cannot activate while GBIF occurrence context remains available.

### Significant finding 2 — planner browser validation does not enforce the active license/URL/identity contract

**Code:**

- `app/src/tripPlanValidation.ts:277-291`
- `app/src/App.tsx:121-142`
- Compare the stronger catalog validator at `app/src/birdApi.ts:76-152`.

`curatedPhotoMatches` in the saved/new-plan validator checks only that license fields are non-null and that `license_code === license_text`; it does not enforce the allowed CC family/version or require the canonical license URL. Its Wikimedia branch does not bind the source-record file title to either URL, does not enforce the provider thumbnail path grammar/hash or the 1,024-pixel bound, and does not reject explicit ports. `safeCuratedPhotoUrls` in `App.tsx` repeats the weak Wikimedia checks (`includes('/wikipedia/commons/thumb/')` and `startsWith('/wiki/File:')`) rather than applying the catalog validator's tighter title/path checks.

Consequently, a payload such as `Q…|File:A.jpg` paired with a different Commons file/source path, an oversized thumbnail, or an invented non-CC license can pass plan-detail validation; parts of it may also become active in presentation. This violates the spec's requirement that browser code accept only source-specific validated identity, URL, dimensions, attribution, and license metadata.

**Required resolution:**

1. Extract/reuse one strict curated-photo validator for catalog and planner payloads.
2. Enforce canonical CC0/CC BY/CC BY-SA/CC BY-NC/CC BY-NC-SA codes and HTTPS URLs, exact source-record-to-file/photo identity, exact provider path grammar, no port/query/fragment/credentials/traversal, allowed image extensions, Commons hash/title repetition, and thumbnail width ≤1,024.
3. Add planner validation/render tests for mismatched Commons title, mismatched source URL, arbitrary thumb path, oversized thumbnail, explicit port, unsupported/ND/invented license, and noncanonical license URL.

### Blocker — aggregate evidence overstates active-spec scenario 9

**Record:** `.10x/evidence/2026-07-12-curated-representative-photo-aggregate-verification.md`, “Active-spec scenario mapping,” item 9.

The evidence says planner backend/frontend tests reject provider/URL/identity/license/dimension mismatches. The two significant findings above show that the backend still activates legacy GBIF photos and the planner frontend accepts multiple source-identity, URL, and license violations. Therefore scenario 9 is not proved, the aggregate correctness review cannot pass, and the aggregate verification ticket/parent cannot close on the current evidence.

**Required resolution:** resolve both significant findings, rerun focused backend and frontend adversarial tests plus full gates, repeat read-only current-state validation, and amend the scenario-9 mapping with the exact new tests and results.

## Verdict

**Fail.** Exact selector behavior, current migration cardinality, placeholder behavior, catalog/map reuse, and recorded idempotence are well supported. However, the implementation does not yet enforce curated-only planner activation at the backend boundary and does not enforce the active source/license/URL identity contract in planner browser validation. These are material active-spec violations, not residual polish.

## Residual risks

- The recorded 706 catalog and eight planner database results were not independently re-queried during this review; this review assessed the child/aggregate evidence and implementation statically.
- No tests were independently rerun in this review. The aggregate record reports 769 Python tests, 273 frontend tests, strict TypeScript/build/static gates, SQLMesh tests, pre-commit, diff checks, and offline database validation as passing.
- No physical-browser, responsive-device, screen-reader, keyboard, or live provider-image-load session was performed. Provider-hosted image URLs can later disappear because binaries are intentionally not stored.
- The requested repository-root `plan.md` and `progress.md` were absent when inspected; governing `.10x` tickets/spec/evidence were available and were used instead.

```acceptance-report
{
  "criteriaSatisfied": [
    {
      "id": "criterion-1",
      "status": "not_satisfied",
      "evidence": "The reviewed change remains out of contract at recommendation_media.py:127-143 and api.py:849-946 because legacy GBIF representative photos can still activate, and planner browser validation is weaker than the active spec."
    },
    {
      "id": "criterion-2",
      "status": "satisfied",
      "evidence": "The review maps concrete selector, API, TypeScript, tests, migration records, aggregate evidence, staging state, required resolutions, and residual limits to specific paths and line ranges."
    }
  ],
  "changedFiles": [
    "packages/databox/databox/curated_photo.py",
    "packages/databox/databox/catalog_media.py",
    "packages/databox/databox/agent_tools/recommendation_media.py",
    "packages/databox/databox/agent_tools/recommendation_media_backfill.py",
    "packages/databox/databox/api.py",
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
    "tests/test_api.py",
    "tests/test_bird_catalog_api.py",
    "tests/test_map_snapshot_api.py",
    "app/src/App.test.tsx",
    "app/src/BirdPages.test.tsx",
    "app/src/FieldMap.test.tsx",
    "app/src/tripPlanValidation.test.ts"
  ],
  "commandsRun": [
    {
      "command": "git status --short --branch && git diff --stat && git diff --cached --stat",
      "result": "passed",
      "summary": "Inspected the broad unstaged diff; cached diff was empty, proving no staged files at review time."
    }
  ],
  "validationOutput": [
    "Aggregate evidence reports 769 Python tests passed with three snapshots and 86.37% coverage.",
    "Aggregate evidence reports 18 frontend files / 273 tests, strict TypeScript, production build, and bundle audit passed.",
    "Aggregate evidence reports Ruff, format, MyPy, secret/generated/docs/source-layout checks, 13 SQLMesh tests, 11 pre-commit hooks, and diff checks passed.",
    "Recorded offline state validation reports 706/706 valid catalog rows, eight/eight singleton planner photo rows, and zero separate map-media tables.",
    "Static adversarial inspection found two significant contract violations, so the passing suite does not prove active-spec scenario 9."
  ],
  "residualRisks": [
    "Current DuckDB cardinality was accepted from recorded evidence rather than independently re-queried in this review.",
    "No test suite was independently rerun during this review.",
    "No physical-browser, assistive-technology, or live provider-image-load verification was performed.",
    "Remote provider images may later disappear because image binaries are intentionally not persisted."
  ],
  "noStagedFiles": true,
  "diffSummary": "The reviewed diff adds the shared curated selector, catalog/map and planner integration, explicit resumable catalog and saved-plan migrations, strict catalog validation, presentation updates, and broad tests; planner backend and frontend boundaries still retain two material legacy/validation gaps.",
  "reviewFindings": [
    "significant: packages/databox/databox/agent_tools/recommendation_media.py:127-143 and packages/databox/databox/api.py:849-946 - legacy GBIF representative photos remain activatable for new or persisted planner results.",
    "significant: app/src/tripPlanValidation.ts:277-291 and app/src/App.tsx:121-142 - planner validation does not strictly bind Wikimedia identity/paths or enforce canonical allowed licenses and all URL bounds.",
    "blocker: .10x/evidence/2026-07-12-curated-representative-photo-aggregate-verification.md scenario 9 - evidence claims stronger rejection coverage than the implementation provides."
  ],
  "manualNotes": "Verdict is fail until the two significant findings are repaired, adversarial tests/full gates are rerun, and aggregate scenario-9 evidence is corrected. Repository-root plan.md and progress.md were absent; the .10x graph was reviewed instead."
}
```
