Status: recorded
Created: 2026-07-13
Updated: 2026-07-13
Target: `.10x/tickets/done/2026-07-11-verify-curated-representative-photos.md`, completed iNaturalist-only representative-photo implementation/migration, current working-tree diff
Verdict: fail

# Final iNaturalist-only privacy/security/source-integrity rereview

## Review

- **Correct — endpoint, redirect, and SSRF boundary:** `packages/databox/databox/curated_photo.py:24-25, 443-506` permits only the fixed iNaturalist v2 taxa endpoint or an exact positive-integer v1 `/taxa/{id}` endpoint. Requests use HTTPS, a ten-second timeout, a one-MiB cap, and a no-redirect opener; the final response scheme, host, and path must still equal the requested endpoint. Candidate display/source URLs are independently bound to fixed allowlisted hosts, exact photo IDs, allowed variants/extensions, and reject credentials, ports, query, fragment, and non-matching paths (`curated_photo.py:220-242, 392-403`). Deterministic adversarial coverage exists in `tests/test_curated_photo.py:202-236` and browser-side coverage in `app/src/curatedPhotoValidation.test.ts:22-36`.
- **Correct — exact source identity:** v2 must yield exactly one exact-name, active, species-rank positive taxon ID; v1 must repeat that same ID/name/rank/active state before its ordered `taxon_photos` are considered (`curated_photo.py:278-332`). The selected display URL is derived only after the returned photo URL proves the allowlisted host/path/photo-ID relation, and the canonical source URL is synthesized from the same photo ID (`curated_photo.py:334-389`). No common-name, synonym, subspecies, parent, fuzzy, observation, model, or computer-vision selection path was found in the active selector.
- **Correct — metadata-only and bundle/secret posture:** selector transport reads bounded JSON only and never requests a display URL (`curated_photo.py:475-506`). Persistence stores bounded summary/payload/caveat JSON and remote URLs, not media bytes (`catalog_media.py:770-852`; `agent_tools/recommendation_media_backfill.py:388-439`). The inspected implementation needs no iNaturalist credential. Recorded post-migration gates report the secret scan and bundle audit passed, with 12 configured names and 10 configured values absent from the bundle (`.10x/evidence/2026-07-13-inaturalist-only-representative-photo-migration.md`).
- **Correct — prohibited activation paths:** the active recommendation enrichment path calls `select_curated_photo` for `recommendation_photo`; its `gbif_getter` is not used for photos (`agent_tools/recommendation_media.py:78-159`). The direct legacy GBIF helper remains in the shared module for historical/general compatibility, but no representative-photo production caller was found; `tests/test_recommendation_media.py:373-382` explicitly proves an injected GBIF getter cannot activate. Active implementation grep found no Wikimedia/Wikidata/WDQS/P225/P18/Commons representative-photo path. GBIF occurrences remain separately exposed as non-photo context in `api.py`. The photo-only saved-plan command requests only `recommendation_photo`, leaves call targets empty, and directly inserts photo evidence without invoking planner/model/email/refresh code (`recommendation_media_backfill.py:113-199`).
- **Correct — browser/source-integrity boundary:** backend persisted rows are reconstructed and revalidated against the complete provider/identity/license/dimension/URL contract before serialization (`api.py:827-883, 1168-1234`). Frontend validation requires exact keys, exact scientific identity, provider `inaturalist`, exact photo-ID URL binding, canonical Creative Commons metadata, dimensions, and bounded plain text (`app/src/curatedPhotoValidation.ts:1-73`). Typed unavailable catalog rows allow only null active-media fields and an exact containing identity (`app/src/birdApi.ts:78-91`), preventing one placeholder from activating a URL or invalidating the whole catalog.
- **Correct — migration scope in source:** catalog migration atomically replaces only the photo row and advances its owned photo-run checkpoint in the same transaction (`catalog_media.py:770-852`). Saved-plan migration deletes/reinserts only the targeted `recommendation_photo` evidence row per transaction and sets `call_targets=[]` in curated-photo-only mode (`recommendation_media_backfill.py:113-199`). Recorded current-state reconstruction reconciles 706 catalog singletons (622 available/84 unavailable), eight planner photo singletons, zero legacy representative rows, and zero inserted calls.

- **Significant — persisted diagnostics do not expose request count as required.** Each eligible selector attempt invokes `before_request()` twice—once for v2 identity and once for v1 shortlist (`packages/databox/databox/curated_photo.py:250-270`). Catalog `lookup_count`, however, increments once per exact-binomial taxon (`packages/databox/databox/catalog_media.py:933-951`), and recommendation enrichment likewise increments once per photo result (`packages/databox/databox/agent_tools/recommendation_media.py:125-135`). Consequently the recorded catalog value `lookup_count=624` represents 624 identities but normally 1,248 HTTP requests, while early v2 failures can represent only one request. The run record has no separate request counter, so exact request volume cannot be reconstructed from its status/outcome counts. This violates the active specification requirement that run records expose request count and weakens independent rate-budget/diagnostic review.

- **Significant — the advertised daily/rate budget is process-local, not durable.** `InaturalistRateLimiter` explicitly keeps its last-request time, day, and count only in process memory (`packages/databox/databox/curated_photo.py:85-116`). It serializes and limits a single process correctly, and the recorded one-off migration remained well below both limits even after correcting the request count. It does not enforce `<10,000 requests/day` across process restarts or multiple server processes, and it cannot enforce the 60/minute target across multiple processes. `tests/test_curated_photo.py:258-263` proves only one limiter instance. The current migration is safe; the general operational guarantee in the active spec is not fully implemented.

- **Significant evidence gap — protected fingerprint claims are not independently reproducible from the durable evidence.** `.10x/evidence/2026-07-13-inaturalist-only-representative-photo-migration.md` reports 86 database fingerprints and 19 external hashes matching before/after/post-gates, but it does not include the fingerprint inventory, exact digests, the command/script that computed them, or a durable raw artifact path. The aggregate record similarly cites `/tmp/inat_aggregate_validate.py`, which is not a durable/reproducible project artifact. Current source inspection supports the narrow photo-only write paths, and current counts can be rechecked, but a new reviewer cannot independently validate the historical before/after equality or the full claimed no-model/no-email/no-refresh/no-personal-state side-effect proof. This falls short of the requested independent evidence standard.

- **Blocker:** No critical exploit or privacy leak was found. The three significant findings above prevent a pass against the explicit observability/rate/evidence contract.
- **Note:** Requested `plan.md` and `progress.md` do not exist at the repository root. The review instead used the active `.10x` decision, specification, parent/verification tickets, child tickets, evidence, reviews, relevant source/tests, and working-tree diff. No repository file was edited.

## Verdict

**Fail (significant contract/evidence gaps; no critical security vulnerability found).** The selector and activation boundaries are strong: fixed endpoints, disabled redirects, exact cross-version identity, strict URL/photo binding, metadata-only persistence, legacy-provider rejection, local/read-only GETs, and narrow migration writers are supported by source and tests. Closure should wait until request counts are recorded per actual HTTP attempt, the daily/rate budget is enforced or the active contract is narrowed to its process-local guarantee, and the historical protected-state fingerprint evidence is made independently inspectable (or its evidentiary limitation is explicitly accepted in a durable record).

## Residual risks

- Provider-hosted images and metadata may later change or disappear because binaries are intentionally not stored.
- Browser image display necessarily makes the end user’s browser contact the allowlisted iNaturalist open-data host; server-side GETs remain network-free.
- Remote provider schema changes fail closed to placeholders but can reduce coverage.
- Existing GBIF photo helper code remains in the shared media module, although the inspected production representative-photo call path cannot reach it; future callers require regression review.
- Physical-browser behavior and live remote-image availability were not revalidated in this privacy/security/source review.

```acceptance-report
{
  "criteriaSatisfied": [
    {
      "id": "criterion-1",
      "status": "not_satisfied",
      "evidence": "The iNaturalist-only source and migration scope are implemented without an observed provider expansion, but the active request-count and cross-process/day rate-budget requirements remain incomplete."
    },
    {
      "id": "criterion-2",
      "status": "not_satisfied",
      "evidence": "Source/tests and current-state counts are substantial, but historical protected fingerprints are reported without their inventory, digests, reproducible command, or durable raw artifact, so the migration side-effect claim is not independently auditable."
    }
  ],
  "changedFiles": [
    "packages/databox/databox/curated_photo.py",
    "packages/databox/databox/catalog_media.py",
    "packages/databox/databox/agent_tools/recommendation_media.py",
    "packages/databox/databox/agent_tools/recommendation_media_backfill.py",
    "packages/databox/databox/agents/birding_trip_planner.py",
    "packages/databox/databox/api.py",
    "scripts/catalog_media.py",
    "app/src/curatedPhotoValidation.ts",
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
    "tests/test_birding_trip_planner.py",
    "tests/test_api.py",
    "app/src/curatedPhotoValidation.test.ts",
    "app/src/BirdPages.test.tsx",
    "app/src/FieldMap.test.tsx",
    "app/src/tripPlanValidation.test.ts",
    "app/src/App.test.tsx"
  ],
  "commandsRun": [
    {
      "command": "pwd && git status --short && git diff --stat && git diff --cached --stat && git branch --show-current",
      "result": "passed",
      "summary": "Confirmed repository, broad unstaged/untracked working tree, main branch, and empty staged diff."
    },
    {
      "command": "git diff -- packages/databox/databox/catalog_media.py packages/databox/databox/agent_tools/recommendation_media.py packages/databox/databox/agent_tools/recommendation_media_backfill.py packages/databox/databox/agents/birding_trip_planner.py packages/databox/databox/api.py scripts/catalog_media.py app/src/curatedPhotoValidation.ts app/src/tripPlanValidation.ts app/src/BirdPages.tsx app/src/FieldMap.tsx",
      "result": "passed",
      "summary": "Inspected the relevant implementation diff and migration/API/browser call paths."
    },
    {
      "command": "git diff --name-status && git diff --cached --name-status && git ls-files --others --exclude-standard",
      "result": "passed",
      "summary": "Enumerated changed/untracked review scope and reconfirmed no staged files."
    }
  ],
  "validationOutput": [
    "Independent source review found fixed iNaturalist v2/v1 endpoints, disabled redirects, one-MiB/ten-second metadata bounds, strict photo-ID URL binding, and no active Wikimedia representative-photo path.",
    "Recorded post-migration gates inspected: 776 Python tests, 295 frontend tests, TypeScript/build/bundle audit, Ruff/format/MyPy, secret scan, SQLMesh, hooks, diff check, and empty staging passed; these commands were not rerun by this review.",
    "Recorded current state inspected: 706 catalog photo singletons (622 available, 84 placeholders), eight saved-plan photo singletons, zero legacy representative rows, and zero inserted calls.",
    "Diagnostic inspection found lookup_count counts identities rather than actual HTTP requests."
  ],
  "residualRisks": [
    "Process-local limiter cannot enforce daily/minute budgets across restarts or multiple processes.",
    "Protected before/after fingerprints are not independently reproducible from the durable evidence record.",
    "Provider-hosted content may change or disappear because binaries are intentionally not stored.",
    "Legacy GBIF photo helpers remain unreachable in the inspected production representative-photo path but remain a future regression surface."
  ],
  "noStagedFiles": true,
  "diffSummary": "The working tree replaces representative-photo activation with strict curated iNaturalist v2 identity plus v1 shortlist metadata, migrates catalog/planner photo persistence and frontend validation, and adds extensive tests; unrelated map/refresh work is also present in the broad unstaged tree.",
  "reviewFindings": [
    "significant: packages/databox/databox/catalog_media.py:933-951 - lookup_count increments once per taxon although the selector can make two HTTP requests, so required request diagnostics undercount and are not reconstructible on partial failures",
    "significant: packages/databox/databox/curated_photo.py:85-116 - rate/day limits are process-local and reset across restart/process boundaries",
    "significant: .10x/evidence/2026-07-13-inaturalist-only-representative-photo-migration.md - protected fingerprint inventory, digest values, computation command, and raw artifact are absent",
    "no critical endpoint, redirect, SSRF, secret, binary-persistence, or legacy-provider activation blocker found"
  ],
  "manualNotes": "Review-only instruction was honored; only this required /tmp review artifact was written. Root plan.md and progress.md were absent."
}
```
