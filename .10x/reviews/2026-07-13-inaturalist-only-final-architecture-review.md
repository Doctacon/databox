Status: recorded
Created: 2026-07-13
Updated: 2026-07-13
Target: `.10x/tickets/done/2026-07-11-verify-curated-representative-photos.md`, active iNaturalist-only representative-photo implementation, migration, and record graph
Verdict: fail

# iNaturalist-only representative-photo final architecture rereview

## Review

- **Correct:** Wikimedia was eliminated from active representative-photo architecture rather than hidden behind a branch. Bounded searches of `packages/databox/databox`, non-test `app/src`, and `scripts` found no WDQS, Wikidata, P225/P18, Commons host, or `wikimedia_commons` source logic. The only `wikimedia_commons` occurrences are three frontend adversarial tests that prove rejection. Creative Commons strings are license metadata, not provider logic. The selector now exposes only `inaturalist` and typed `curated_photo` unavailable results (`packages/databox/databox/curated_photo.py:24-35,119-142`).

- **Correct:** The runtime discovery boundary is single-source and exact. It normalizes one binomial, resolves exactly one active species-rank v2 taxon, checks the same identity in v1, and inspects only ordered `taxon_photos` (`packages/databox/databox/curated_photo.py:119-142,244-335`). Candidate validation binds photo/taxon/curated-position identity, dimensions, attribution, canonical CC metadata, and exact iNaturalist display/source URL grammars (`packages/databox/databox/curated_photo.py:145-205,338-415`). No production caller of the legacy GBIF `_lookup_photo` helper was found.

- **Correct:** The prior catalog persistence-ownership blocker is resolved. Ordinary catalog apply/refresh obtains representative photos through the shared curated selector (`packages/databox/databox/catalog_media.py:489-516,572-674`), while the photo-only migration uses the same selector and full offline validator (`packages/databox/databox/catalog_media.py:774-853,856-996`). Both reject GBIF representative activation; calls remain separately owned by Xeno-canto. The dedicated photo writer replaces only the photo row atomically (`packages/databox/databox/catalog_media.py:795-853`).

- **Correct:** The prior planner checkpoint and stale-row findings are resolved. Saved-plan photo enrichment is performed one recommendation at a time and commits each lookup result before proceeding (`packages/databox/databox/agent_tools/recommendation_media_backfill.py:124-171`). Completion reconstructs the entire persisted result and validates it against the exact recommendation scientific identity rather than trusting provider/cardinality (`packages/databox/databox/agent_tools/recommendation_media_backfill.py:246-375`).

- **Correct:** Typed unavailable is now a first-class strict state. Server validation permits bounded exact identity and attempted-source metadata but requires all active media fields to be absent (`packages/databox/databox/curated_photo.py:145-175`). Catalog serialization degrades malformed rows to a local placeholder instead of failing the containing response (`packages/databox/databox/api.py:1200-1233`), and planner serialization likewise returns a typed unavailable object (`packages/databox/databox/api.py:801-878`). The shared frontend validator accepts only strict available iNaturalist objects (`app/src/curatedPhotoValidation.ts:1-72`); unavailable planner objects must have all media fields null (`app/src/tripPlanValidation.ts:340-359`).

- **Correct:** GET ownership is local and read-only. Catalog/profile attach persisted rows through `_catalog_photo`, Field Map derives its photo list from the same catalog-media rows, and no separate map store or discovery call is present (`packages/databox/databox/api.py:1200-1233,1288-1298,1348-1365,1405-1427`). Fresh recorded reconstruction additionally forbade discovery, returned HTTP 200 for mixed placeholders, and preserved the DuckDB hash (`.10x/evidence/2026-07-13-inaturalist-only-representative-photo-aggregate-verification.md`).

- **Significant:** Request-level run observability still does not satisfy the active specification. One eligible selector lookup makes two provider requests—v2 and v1 (`packages/databox/databox/curated_photo.py:251-266`)—but catalog `lookup_count` increments only once per queryable taxon (`packages/databox/databox/catalog_media.py:933-948`) and planner enrichment also increments once per recommendation (`packages/databox/databox/agent_tools/recommendation_media.py:125-135`). The catalog run schema has no separate request counter (`packages/databox/databox/catalog_media.py:155-166`), while planner backfill has no durable run record containing status, checkpoint, duration, request count, or failure-class counts (`packages/databox/databox/agent_tools/recommendation_media_backfill.py:70-237`). Consequently the recorded values `624` and `8` are selector lookups, not the specification's actual provider request counts. This directly misses the active spec requirement that run records expose safe status/failure-class counts, checkpoint, duration, and request count.

- **Significant:** Transient provider failures are checkpointed as terminally complete, so the promised operator-driven rerun path cannot retry them. The selector catches every v2/v1 exception and returns a fully valid typed unavailable row (`packages/databox/databox/curated_photo.py:244-273`); offline validation treats that row as complete (`packages/databox/databox/curated_photo.py:159-175`). Catalog resume then includes it in `finished` and returns a no-op once all rows are safe (`packages/databox/databox/catalog_media.py:878-907`), and planner inspection similarly skips it after `_persisted_curated_photo_is_safe` succeeds (`packages/databox/databox/agent_tools/recommendation_media_backfill.py:299-317,334-375`). `curated_photo_outcome_keys` can label the row `inaturalist.failed.metadata` (`packages/databox/databox/curated_photo.py:208-218`), but that failure class does not affect completion. A temporary timeout, throttle, schema incident, or daily-budget exhaustion can therefore become a permanent placeholder; `--refresh-photos` and `--curated-photos` will not retry it. The catalog's broader `--refresh` also refreshes calls and requires Xeno-canto, so it is not the governed photo-only recovery path; the planner has no equivalent force option. This conflicts with the active spec's operator-driven rerun architecture.

- **Note:** A dormant GBIF representative-photo selector and its direct tests remain in `packages/databox/databox/agent_tools/recommendation_media.py:203-360` and `tests/test_recommendation_media.py`, and `enrich_recommendation_media` still accepts an unused `gbif_getter` (`packages/databox/databox/agent_tools/recommendation_media.py:78-89`). Search found no production call path, so this is not an active second source and is not a contract blocker, but it weakens the legibility of the single-source boundary and leaves a misleading extension seam.

- **Note:** The active parent ticket contains July 13 progress while its `Updated` header remains `2026-07-11` (`.10x/tickets/done/2026-07-11-upgrade-representative-bird-photos.md:1-3`). Dependencies otherwise reconcile: both replacement implementation/migration tickets are done, the superseded Wikimedia decision/spec are historical, the canceled WDQS repair is not an active dependency, and aggregate verification remains open pending four rereviews.

- **Note:** The requested root `plan.md` and `progress.md` do not exist. This rereview used the active decision/spec, parent and aggregate tickets, implementation/migration tickets and evidence/reviews, superseded Wikimedia records, prior architecture review, current source/tests, working-tree diff, and status instead.

## Prior architecture finding resolution

1. **Catalog persistence collision:** resolved by shared curated selection and strict persistence validation.
2. **Planner lookup checkpointing:** resolved by per-recommendation lookup/transaction sequencing.
3. **Planner provider-only completion:** resolved by full persisted-result reconstruction against exact identity.
4. **Incomplete Wikimedia browser grammar:** superseded by source elimination; the shared browser validator now accepts only strict iNaturalist available objects.
5. **Provider-outcome observability:** partially resolved by `provider_outcomes_json`, but actual HTTP request counts and durable planner run observability remain missing, as above.

## Verdict

**Fail.** The representative-photo source, persistence owners, GET paths, typed unavailable behavior, and prior correctness findings are architecturally coherent, and the completed migration state is well supported. Closure is still unsupported because two active operational MUSTs remain unsatisfied: run records do not count actual provider requests (and planner runs lack the required durable observability), and transient provider failures are persisted as completed rows with no governed photo-only operator retry path.

## Required resolution

1. Record actual v2/v1 request attempts separately from taxon/recommendation lookup counts for catalog and planner runs, with durable status, checkpoint, duration, and bounded failure-class totals.
2. Distinguish retryable provider/transport/schema/budget unavailability from terminal identity/no-eligible unavailability in completion checks, or add an explicit serialized photo-only force/retry-failed mode for both catalog and saved plans. Prove it retries only failed targets, preserves completed terminal results, remains idempotent after success, and does not widen into calls/model/source refresh.
3. Re-run the focused interruption/no-op/observability tests and aggregate gates, then update the aggregate evidence and review graph.

## Residual risks

- Provider-hosted URLs/content can later disappear or change because binaries are intentionally not stored.
- Automated/TestClient evidence does not prove physical responsive layout, real image availability, visual subject quality, or NVDA/JAWS/VoiceOver behavior.
- Dormant GBIF photo-selection helpers remain a maintenance hazard despite being unreachable from current production enrichment.

```acceptance-report
{
  "criteriaSatisfied": [
    {
      "id": "criterion-1",
      "status": "satisfied",
      "evidence": "Performed only the requested independent architecture rereview and wrote only the required /tmp review artifact; no repository files were edited."
    },
    {
      "id": "criterion-2",
      "status": "satisfied",
      "evidence": "Inspected active and superseded authority records, aggregate/child tickets and evidence/reviews, prior architecture findings, relevant current source/tests/diff, repository status, and cited concrete file/line evidence for resolved and unresolved findings."
    }
  ],
  "changedFiles": [
    "/tmp/inat-only-final-architecture-review.md"
  ],
  "testsAddedOrUpdated": [],
  "commandsRun": [
    {
      "command": "git status --short && git diff --stat && git diff --cached --stat",
      "result": "passed",
      "summary": "Inspected working-tree scope and confirmed the staged/cached diff was empty."
    },
    {
      "command": "bounded grep for wikimedia|wikidata|wdqs|commons|P225|P18|wikimedia_commons across active backend, frontend, and scripts",
      "result": "passed",
      "summary": "No active backend/script provider logic found; only Creative Commons licensing strings and three adversarial frontend legacy-provider tests remained."
    },
    {
      "command": "numbered source inspection and targeted git diff for curated_photo, catalog_media, recommendation_media/backfill, API, CLI, and frontend validators",
      "result": "passed",
      "summary": "Verified source boundaries, persistence/checkpoint behavior, GET paths, typed unavailable contracts, and the two unresolved operational architecture gaps."
    }
  ],
  "validationOutput": [
    "Recorded post-migration state: 706/706 catalog singletons (622 available iNaturalist, 84 typed unavailable), eight/eight saved-plan singletons, and zero Wikimedia/GBIF representative rows.",
    "Recorded full gates: 776 Python tests, three snapshots, 295 frontend tests, strict TypeScript, production build/bundle audit, Ruff/format/MyPy, security/generated/docs/source-layout checks, 13 SQLMesh tests, all hooks, diff check, and empty staging passed.",
    "Independent inspection confirmed prior persistence, resume, browser-validation, and GET-purity findings are resolved, but actual request-count/planner-run observability and retryable-failure recovery remain unsatisfied."
  ],
  "residualRisks": [
    "Provider-hosted media can later disappear or change.",
    "No physical-browser, real-image, responsive-device, or assistive-technology session was recorded.",
    "Dormant unreachable GBIF representative-photo helpers remain in the shared media module."
  ],
  "noStagedFiles": true,
  "diffSummary": "Review-only task; repository diff was inspected but not modified. The only output is this /tmp architecture review.",
  "reviewFindings": [
    "significant: packages/databox/databox/catalog_media.py:155-166,933-948 and packages/databox/databox/agent_tools/recommendation_media_backfill.py:70-237 - run observability records selector lookups rather than actual v2/v1 requests and lacks a durable planner run record",
    "significant: packages/databox/databox/curated_photo.py:244-273 and packages/databox/databox/catalog_media.py:878-907 - transient provider failures become terminally complete placeholders with no governed photo-only retry path",
    "note: packages/databox/databox/agent_tools/recommendation_media.py:203-360 - dormant GBIF representative-photo code remains unreachable but weakens the single-source boundary"
  ],
  "manualNotes": "Verdict: fail. Requested plan.md and progress.md were absent. No repository files were edited and no staged files were present."
}
```
