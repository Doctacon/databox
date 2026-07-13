Status: recorded
Created: 2026-07-13
Updated: 2026-07-13
Target: iNaturalist-only representative-photo operational hardening, campaign reconciliation, current implementation, and closure evidence
Verdict: pass

# Final iNaturalist-only closure correctness rereview

## Review

- **Correct — authoritative campaign ownership:** Current read-only DuckDB inspection found the latest run `catalog_photo_617cb94de24c470b89c8b7ff1e8ca447` complete with `target=706`, `processed=706`, `lookup=624`, `request=1248`, and all 706 current photo rows owned by that run. Completion and dry-run inspection are campaign-scoped through `_terminal_photo_codes(..., run_id=latest_run_id)` rather than global row validity (`packages/databox/databox/catalog_media.py:785-820`, `948-1016`, `1038-1040`). The deterministic mixed-owner regression forbids provider access and proves adoption of a prior terminal placeholder into the authoritative campaign (`tests/test_catalog_media.py:919-977`). This resolves the prior correctness review's 624-current/82-prior ownership blocker.

- **Correct — 82-placeholders/624-untouched reconciliation:** Durable repair evidence records the one supported resume selecting exactly 82 prior terminal non-queryable placeholders while both selector and default transports were guarded; observed provider requests were zero. The existing 624 campaign-owned rows were excluded by the run-scoped terminal set and were not requeried. Final outcomes reconcile exactly: `82 identity.unavailable + 622 inaturalist.available + 2 inaturalist.no_eligible = 706`; queryable lookups reconcile as `622 + 2 = 624`; historical requests reconcile as `624 × 2 = 1,248`. The pre/post/post-gate/final artifacts record all 86 protected database fingerprints and 20 non-rate-ledger external hashes unchanged (`.10x/evidence/2026-07-13-inaturalist-photo-migration-reconciliation.md` and `.10x/evidence/.storage/2026-07-13-inaturalist-reconcile-*.json`).

- **Correct — request accounting, retry, and outcomes:** The selector counts actual request attempts independently of lookups: non-binomial identities return before transport, v2-stage failures report one request, and v2+v1 attempts report two (`packages/databox/databox/curated_photo.py:196-219`, `348-416`). Budget/transport/schema failures are strict typed-unavailable and retryable, while identity/no-eligible outcomes are terminal (`packages/databox/databox/curated_photo.py:292-316`, `348-416`). Catalog persistence updates request attempts immediately after selection and checkpoints result plus terminal outcome atomically (`packages/databox/databox/catalog_media.py:836-923`, `1018-1037`). Fresh full tests include interruption, retry-only targeting, reconciled campaign ownership, and terminal no-op coverage (`tests/test_catalog_media.py:760-1041`).

- **Correct — planner singleton, observability, and no-op:** Saved-plan photo-only backfill records durable target/processed/lookup/request/outcome state and replaces retryable rows without duplicating singleton evidence (`packages/databox/databox/agent_tools/recommendation_media_backfill.py:114-355`, `449-452`). Its retry test proves request totals `3 → 5`, terminal completion, and a subsequent zero-target/zero-request no-op (`tests/test_recommendation_media_backfill.py:709-798`). Current read-only state contains eight recommendation-photo rows for eight distinct recommendations, all strict available iNaturalist results. The durable API validation reports planner dry-run targets/lookups both zero.

- **Correct — strict current catalog/API state:** Fresh read-only inspection found exactly 706 catalog singleton rows: 622 `inaturalist:available` and 84 `curated_photo:unavailable`, with zero Wikimedia/GBIF representative rows. The 84 placeholders reconcile to 82 identity-unavailable plus two no-eligible outcomes. There are no catalog duplicates or missing species, and no legacy planner provider rows. Strict persisted reconstruction validates bounded result shape before use (`packages/databox/databox/catalog_media.py:198-248`). The durable forbidden-discovery validation reports HTTP 200 for catalog, placeholder profile, map, saved plan, and browser routes, with 622 available/84 placeholder API rows and unchanged database SHA-256 (`.10x/evidence/.storage/2026-07-13-inaturalist-reconcile-api-validation.json`).

- **Correct — current read-only/no-op behavior:** Read-only database inspection left `data/databox.duckdb` SHA-256 unchanged. Campaign dry-run derives completion only from the latest run and performs no network or writes (`packages/databox/databox/catalog_media.py:785-820`). Current durable validation reports catalog campaign remaining=0 and planner dry-run targets/lookups=0. GET validation ran with discovery forbidden and retained an unchanged database digest.

- **Correct — full gates:** A fresh rereview run passed 776 Python tests and three snapshots, 295 frontend tests, strict TypeScript, Ruff check/format, MyPy over 99 source files, 13 SQLMesh tests, `git diff --check`, and empty staging. The post-reconciliation evidence additionally records the secret scan, generated staging/platform-health checks, docs generation, strict MkDocs, source-layout checks, and all 11 pre-commit hooks passing. No live provider call or project DuckDB mutation was performed by this review.

- **Note:** The requested `plan.md` and `progress.md` inputs do not exist at the repository root. Active decisions/specification, parent and verification tickets, child/aggregate evidence, prior correctness review, repair reviews, current code/tests, and read-only database state were available and reviewed. This does not block the correctness verdict.

## Findings

No blocker or significant correctness finding remains. The prior campaign-ownership/count blocker is resolved by run-scoped ownership, the bounded 82-row zero-request reconciliation, coherent durable counters/outcomes, and current all-706 ownership.

## Verdict

**Pass.** The authoritative campaign owns all 706 current catalog rows; the 82 prior terminal placeholders were reconciled with zero provider requests while 624 completed rows were preserved; processed, lookup, request, and outcome totals reconcile; planner state is strict singleton and no-op; current catalog/planner/API state is strict and legacy-provider-free; and the full current deterministic/static gates pass.

The active aggregate verification ticket `.10x/tickets/done/2026-07-11-verify-curated-representative-photos.md` remains the durable owner for completing the full multidisciplinary closure-review set and parent graph reconciliation.

## Residual risks

- Provider-hosted image availability/content can change because Rufous intentionally persists metadata and URLs rather than binaries.
- The rate limiter coordinates processes on one shared local filesystem, not multiple hosts; this matches the active local-only architecture.
- The historical 1,248-request reconstruction is valid only for this exact terminal campaign whose 624 queryable outcomes prove both request stages; it must not be generalized to provider-failure campaigns.
- Automated/TestClient evidence does not prove physical-browser layout, live remote-image rendering, visual subject quality, or assistive-technology behavior; these are already recorded limits, not correctness blockers for this backend reconciliation rereview.

```acceptance-report
{
  "criteriaSatisfied": [
    {
      "id": "criterion-1",
      "status": "satisfied",
      "evidence": "Review-only scope was preserved: no repository implementation or record was edited; only the required /tmp review artifact was written."
    },
    {
      "id": "criterion-2",
      "status": "satisfied",
      "evidence": "Independent current DuckDB queries, source/test inspection, fresh full Python/frontend/static gates, durable reconciliation artifacts, API validation, diff check, and staging check substantiate the pass verdict."
    }
  ],
  "changedFiles": [
    "/tmp/inat-only-closure-correctness-review.md"
  ],
  "testsAddedOrUpdated": [],
  "commandsRun": [
    {
      "command": "read-only DuckDB ownership/cardinality/provider/run reconciliation query with pre/post SHA-256",
      "result": "passed",
      "summary": "Latest campaign owns 706/706; run is complete with processed=706, lookup=624, requests=1248, outcomes 82+622+2; catalog is 622 available/84 placeholders, planner is 8/8 strict singleton, zero legacy providers, and database SHA-256 was unchanged."
    },
    {
      "command": "PYTHONDONTWRITEBYTECODE=1 .venv/bin/pytest --no-cov -q",
      "result": "passed",
      "summary": "776 tests and three snapshots passed."
    },
    {
      "command": "cd app && npm test -- --run",
      "result": "passed",
      "summary": "19 files and 295 frontend tests passed."
    },
    {
      "command": "cd app && npx tsc --noEmit",
      "result": "passed",
      "summary": "Strict TypeScript check passed."
    },
    {
      "command": ".venv/bin/ruff check . && .venv/bin/ruff format --check .",
      "result": "passed",
      "summary": "Ruff checks passed; 163 files were already formatted."
    },
    {
      "command": ".venv/bin/mypy packages/",
      "result": "passed",
      "summary": "No issues in 99 source files."
    },
    {
      "command": "cd transforms/main && ../../.venv/bin/sqlmesh test",
      "result": "passed",
      "summary": "13 SQLMesh tests passed against DuckDB."
    },
    {
      "command": "git diff --check && test -z \"$(git diff --cached --name-only)\"",
      "result": "passed",
      "summary": "Diff whitespace check passed and staging was empty."
    }
  ],
  "validationOutput": [
    "Current run: complete, target=706, processed=706, lookup=624, request=1248, owned rows=706.",
    "Outcomes reconcile: identity.unavailable=82, inaturalist.available=622, inaturalist.no_eligible=2.",
    "Current catalog: 706 unique singletons = 622 available iNaturalist + 84 typed placeholders; zero legacy representative providers.",
    "Current planner: eight rows for eight distinct recommendations, all available iNaturalist; durable dry-run targets=0 and lookups=0.",
    "Forbidden-discovery API validation: catalog/profile/map/plan/browser all HTTP 200 and DuckDB SHA-256 unchanged.",
    "Fresh gates: 776 Python, 295 frontend, TypeScript, Ruff, MyPy, 13 SQLMesh tests, diff check, and empty staging all passed."
  ],
  "residualRisks": [
    "Remote provider content/availability remains mutable because binaries are intentionally not stored.",
    "Rate coordination is local-filesystem scoped rather than distributed across hosts.",
    "Historical request reconstruction is valid only for this exact terminal two-stage outcome set.",
    "Physical-browser, live-image, and assistive-technology behavior remain outside automated evidence."
  ],
  "noStagedFiles": true,
  "diffSummary": "No repository diff was made by this review. The reviewed implementation adds strict iNaturalist-only selection, durable request/run accounting, retry/no-op behavior, and campaign-scoped reconciliation; the current authoritative campaign owns all 706 rows.",
  "reviewFindings": [
    "no blockers",
    "correct: authoritative campaign ownership and 706/624/1248/outcome reconciliation are coherent",
    "correct: planner singleton/no-op, strict current state/API, and full gates pass"
  ],
  "manualNotes": "plan.md and progress.md were absent. No repository files were edited; only the required /tmp review artifact was written."
}
```
