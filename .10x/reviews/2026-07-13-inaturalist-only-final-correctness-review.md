Status: recorded
Created: 2026-07-13
Updated: 2026-07-13
Target: iNaturalist-only representative-photo implementation, migration, and aggregate verification
Verdict: fail

# Independent final correctness rereview

## Review

- **Correct:** The selector implements the governed two-version boundary: exact normalized binomial resolution through v2, followed by exact-ID v1 shortlist retrieval, cross-version ID/name/rank/active checks, and provider-order first-eligible selection (`packages/databox/databox/curated_photo.py:119-142`, `244-389`). Available-result validation binds positive taxon/photo/position IDs, exact species, dimensions, creator, license, display/source URLs, and attempted source (`packages/databox/databox/curated_photo.py:145-205`). URL handling restricts the large image to the open-data host and exact photo path, and the source link to the exact iNaturalist photo (`packages/databox/databox/curated_photo.py:221-241`, `392-410`).
- **Correct:** Server and browser contracts fail legacy providers closed while treating a strict unavailable row as valid containing data. Catalog reconstruction validates persisted payload shape and the full curated result (`packages/databox/databox/catalog_media.py:177-218`); API serialization converts invalid or legacy media to a placeholder instead of invalidating the catalog (`packages/databox/databox/api.py:1168-1234`); frontend catalog validation permits only null active fields plus null/exact containing scientific identity for unavailable rows (`app/src/birdApi.ts:81-96`) and applies the strict available validator (`app/src/curatedPhotoValidation.ts:1-73`). Field Map obtains photos from catalog media by exact species code/identity rather than a separate store (`packages/databox/databox/api.py:1338-1365`).
- **Correct:** Fresh independent focused gates passed: 140 Python tests and 87 frontend tests. Current read-only reconstruction found 706/706 valid catalog photos (622 `inaturalist:available`, 84 `curated_photo:unavailable`), zero Wikimedia/GBIF catalog representative rows, and eight planner photo rows for eight distinct recommendations, all available from iNaturalist with zero legacy providers. Planner curated-photo dry-run reported zero targets, zero lookups, zero duplicates, and zero missing rows. These results substantiate exact identity/ordering, dimensions, license/attribution/URL rejection, mixed unavailable behavior, planner singleton behavior, legacy rejection, and current no-op state.
- **Blocker (significant): The recorded “706 processed” migration did not re-evaluate or persist all 706 identities in the new migration campaign.** The active specification requires the explicit migration to re-evaluate all 706 identities and checkpoint each species (`.10x/specs/curated-inaturalist-representative-bird-photos.md:51-55`). Current DuckDB state shows only 624 photo rows owned by the claimed iNaturalist-only run `catalog_photo_617cb94de24c470b89c8b7ff1e8ca447` (622 available and two unavailable); the other 82 unavailable rows still carry the earlier run ID `catalog_photo_2b8741d643ec4f97a8f566ee1a79b943`. The implementation computes `finished` from every valid current row without restricting it to the resumable/current campaign (`packages/databox/databox/catalog_media.py:878-885`), seeds a new run’s `processed_taxa_count` with that cross-run total (`:912-921`), excludes those rows from targets (`:933`), then reports completion from global valid-row cardinality (`:952-965`). Consequently the latest terminal record says `processed_taxa_count=706`, while its outcome counts total only 624 and only 624 rows carry its run ID. Migration evidence acknowledges the 82 old rows at `.10x/evidence/2026-07-13-inaturalist-only-representative-photo-migration.md:18-20` but then presents the aggregate count as an exactly-once 706-row run at `:22-42`. The spec’s resume skip permits completed checkpoints, but these 82 have no checkpoint in this campaign; they are inherited from a prior provider-era run. This weakens both the explicit re-evaluation claim and run observability. Before aggregate closure, either (a) migrate/checkpoint those 82 under the active campaign and reconcile terminal counts/outcomes, or (b) explicitly supersede the contract to ratify cross-campaign full-contract validation as “re-evaluation” and change run fields/evidence so `processed` is not represented as work performed by the latest run.
- **Note:** Except for the migration campaign-ownership/count issue, scenario-to-evidence strength is good. The aggregate evidence maps all ten scenarios to named tests and current-state checks (`.10x/evidence/2026-07-13-inaturalist-only-representative-photo-aggregate-verification.md`). Scenarios 1–6 and 9–10 are backed by focused selector/API/frontend tests; planner preservation/singleton/no-op has both tests and current DB evidence. Scenario 7’s interruption tests cover resume mechanics, but the live evidence overstates current-run ownership as described above.
- **Note:** `/Users/crlough/Code/personal/databox/plan.md` and `progress.md` were requested inputs but do not exist. The active spec, decisions, parent/verification tickets, child evidence, aggregate evidence, code, tests, diff/status, and current DuckDB state were available and reviewed.
- **Note:** No files are staged. The working tree is broad and contains unrelated map/refresh lifecycle work as well as this change; this review evaluated the representative-photo surfaces and governing records rather than asserting the entire working tree is a single focused diff.

## Verdict

**Fail pending migration evidence/count repair.** The runtime selector, strict contracts, mixed-placeholder behavior, singleton planner state, current catalog cardinality, legacy-provider rejection, and focused tests are correct. Closure is blocked because the latest migration’s `processed=706` claim conflates 624 rows handled by that campaign with 82 valid rows inherited from an earlier run, contrary to the active explicit re-evaluation wording and the evidence’s exactly-once characterization.

## Residual risks

- Provider-hosted image content and availability can change because binaries are intentionally not stored.
- Automated tests do not prove physical-browser responsive layout, real remote-image loading, visual subject quality, or screen-reader behavior.
- v2 identity uniqueness is established within the bounded returned result set; continued provider schema/search semantics remain an external dependency.

```acceptance-report
{
  "criteriaSatisfied": [
    {
      "id": "criterion-1",
      "status": "not_satisfied",
      "evidence": "The implementation is functionally correct, but the explicit migration contract is not fully evidenced: 624 rows carry the claimed current run ID while 82 remain owned by an earlier run, although the latest run reports processed_taxa_count=706."
    },
    {
      "id": "criterion-2",
      "status": "satisfied",
      "evidence": "Independent source inspection, focused test reruns, read-only DuckDB reconstruction, migration run ownership counts, planner no-op inspection, and git staging inspection are recorded above."
    }
  ],
  "changedFiles": [
    ".10x/specs/curated-inaturalist-representative-bird-photos.md",
    ".10x/decisions/curated-inaturalist-only-representative-photos.md",
    ".10x/decisions/inaturalist-curated-photo-api-split.md",
    "packages/databox/databox/curated_photo.py",
    "packages/databox/databox/catalog_media.py",
    "packages/databox/databox/agent_tools/recommendation_media.py",
    "packages/databox/databox/agent_tools/recommendation_media_backfill.py",
    "packages/databox/databox/agents/birding_trip_planner.py",
    "packages/databox/databox/api.py",
    "app/src/curatedPhotoValidation.ts",
    "app/src/birdApi.ts",
    "app/src/tripPlanValidation.ts",
    "app/src/BirdPages.tsx",
    "app/src/FieldMap.tsx",
    "app/src/types.ts"
  ],
  "testsAddedOrUpdated": [
    "tests/test_curated_photo.py",
    "tests/test_catalog_media.py",
    "tests/test_recommendation_media_backfill.py",
    "tests/test_bird_catalog_api.py",
    "tests/test_map_snapshot_api.py",
    "tests/test_birding_trip_planner.py",
    "tests/test_api.py",
    "app/src/curatedPhotoValidation.test.ts",
    "app/src/BirdPages.test.tsx",
    "app/src/FieldMap.test.tsx",
    "app/src/tripPlanValidation.test.ts"
  ],
  "commandsRun": [
    {
      "command": "PYTHONDONTWRITEBYTECODE=1 .venv/bin/pytest --no-cov -q tests/test_curated_photo.py tests/test_catalog_media.py tests/test_recommendation_media_backfill.py tests/test_bird_catalog_api.py tests/test_map_snapshot_api.py tests/test_birding_trip_planner.py tests/test_api.py",
      "result": "passed",
      "summary": "140 passed with five deprecation warnings."
    },
    {
      "command": "cd app && npm test -- --run src/curatedPhotoValidation.test.ts src/BirdPages.test.tsx src/FieldMap.test.tsx src/tripPlanValidation.test.ts",
      "result": "passed",
      "summary": "Four files and 87 tests passed."
    },
    {
      "command": "read-only DuckDB reconstruction plus run_media_backfill(..., apply=False, curated_photos_only=True)",
      "result": "passed_with_finding",
      "summary": "706 strict catalog rows (622 available/84 unavailable), eight strict planner singletons, zero legacy providers, and zero planner dry-run targets/lookups; run ownership split 624 current plus 82 prior."
    },
    {
      "command": "git status --short && git diff --cached --quiet",
      "result": "passed",
      "summary": "Working tree changes are present; cached diff is empty."
    }
  ],
  "validationOutput": [
    "Focused Python: 140 passed.",
    "Focused frontend: 87 passed.",
    "Catalog: 706 valid = 622 inaturalist:available + 84 curated_photo:unavailable; zero Wikimedia/GBIF representative rows.",
    "Planner: eight rows/eight distinct recommendations, all iNaturalist available; dry-run zero targets/lookups/duplicates.",
    "Latest run record: processed=706, lookup=624, outcomes=622 available + 2 no_eligible; persisted ownership is 624 latest-run rows + 82 earlier-run rows."
  ],
  "residualRisks": [
    "Migration campaign ownership/count evidence must be repaired or the contract explicitly revised before closure.",
    "Remote image availability/content and physical-browser/assistive-technology behavior remain outside deterministic evidence."
  ],
  "noStagedFiles": true,
  "diffSummary": "The reviewed change removes active Wikimedia representative-photo behavior, adds strict iNaturalist v2 identity plus v1 curated-shortlist selection, propagates strict available/unavailable contracts through catalog/planner/API/frontend, and adds migration/resume tests and records. The broader working tree also contains unrelated refresh/map lifecycle changes.",
  "reviewFindings": [
    "blocker: packages/databox/databox/catalog_media.py:878-965 - latest migration reports 706 processed by counting 82 valid rows inherited from a prior run; only 624 rows were handled by the claimed iNaturalist-only campaign.",
    "correct: selector, persistence validators, mixed typed-unavailable behavior, planner singleton state, legacy rejection, and focused regression tests passed."
  ],
  "manualNotes": "plan.md and progress.md were absent. No repository files were edited by this review; only the required /tmp review artifact was written."
}
```
