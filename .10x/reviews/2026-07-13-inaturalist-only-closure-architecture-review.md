Status: recorded
Created: 2026-07-13
Updated: 2026-07-13
Target: `.10x/tickets/done/2026-07-11-verify-curated-representative-photos.md`, operational-hardening and migration-reconciliation repairs, current implementation/tests/durable artifacts
Verdict: pass

# iNaturalist-only closure architecture rereview

## Review

- **Correct — actual request accounting:** `CuratedPhotoResult` carries a bounded `request_count`, and the selector increments it immediately before each actual injected/default transport call, yielding zero for non-queryable or pre-transport budget failure, one for a failed v2 attempt, and two after v2 and v1 are attempted (`packages/databox/databox/curated_photo.py:48-68,196-219,342-416`). Catalog and planner persist request attempts before photo persistence, so interruption after transport does not erase operational truth (`packages/databox/databox/catalog_media.py:1018-1036`; `packages/databox/databox/agent_tools/recommendation_media_backfill.py:206-267`). Focused tests assert 0/1/2 selector behavior, interruption accounting, retry accumulation, and no repeated completed requests (`tests/test_curated_photo.py:92-113,156-166,229-245`; `tests/test_catalog_media.py:752-863,980-1041`; `tests/test_recommendation_media_backfill.py:709-796`).

- **Correct — durable run observability:** Catalog `birding_catalog_media.photo_runs` and planner `birding_agent.recommendation_photo_runs` now persist run identity, running/failed/complete status, start/completion and duration, target/processed/checkpoint counts, lookup and actual request counts, bounded outcome/failure-class JSON, and safe failure (`packages/databox/databox/catalog_media.py:168-195,883-920,948-1080`; `packages/databox/databox/agent_tools/recommendation_media_backfill.py:96-110,170-196,218-266,321-333,358-375`). This resolves the prior final architecture review’s missing request-count and planner-run findings.

- **Correct — retryable versus terminal recovery/no-op semantics:** Persisted budget/transport/schema failures remain strict typed-unavailable presentation data but are recognized as retryable; non-binomial/exact-identity-invalid and exhausted-shortlist results remain terminal (`packages/databox/databox/curated_photo.py:222-316,342-416`). Catalog campaign completion excludes retryable rows and the explicit photo-only refresh retries only unfinished rows (`packages/databox/databox/catalog_media.py:338-354,965-1038`). Planner inspection similarly replaces only invalid or retryable singleton photos and preserves terminal/completed singletons (`packages/databox/databox/agent_tools/recommendation_media_backfill.py:427-467,470-514`). Both paths become provider no-ops after success, with durable run rows unchanged in the catalog test and durable planner totals retained (`tests/test_catalog_media.py:866-917,980-1041`; `tests/test_recommendation_media_backfill.py:780-796`). No model, call, email, source, or AVONET operation was added to either photo-only path.

- **Correct — local cross-process/restart rate budget:** `InaturalistRateLimiter` uses a stable sidecar `fcntl` lock, validates bounded JSON state, reserves the request before transport, atomically replaces state, applies one-second spacing (the <=60/minute target), and caps the UTC-day count at 9,999 (`packages/databox/databox/curated_photo.py:108-193`). Tests use temporary paths and prove shared-instance restart persistence, separate-process serialization, and daily-cap refusal (`tests/test_curated_photo.py:285-319`). The mechanism is intentionally local-filesystem coordination, matching the local-only architecture.

- **Correct — authoritative campaign ownership and count 706:** Catalog completion is derived from strict terminal rows filtered by the authoritative run ID rather than global row validity (`packages/databox/databox/catalog_media.py:314-354,785-820,963-1008`). The reconciliation used the supported photo-refresh path to adopt exactly 82 prior-campaign terminal non-queryable placeholders with zero provider requests, while retaining the 624 already owned queried identities. The terminal run owns all 706 rows and reconciles `target=706`, `processed=706`, `lookup=624`, `request=1248`, with outcomes `identity.unavailable=82`, `inaturalist.available=622`, and `inaturalist.no_eligible=2` (`.10x/evidence/2026-07-13-inaturalist-photo-migration-reconciliation.md`). The mixed-owner regression directly proves this behavior (`tests/test_catalog_media.py:919-977`). The durable artifact checksum manifest validates successfully for the procedure, pre/post/final snapshots, API validation, apply log, and rate-isolation log.

- **Correct — current persisted and GET architecture:** Reconciliation evidence records 706 strict catalog singletons (622 available plus 84 typed unavailable), eight strict planner singletons, zero legacy representative providers, HTTP 200 for catalog/placeholder profile/map/saved plan/browser with discovery forbidden, and unchanged database hash. Eighty-six protected database fingerprints and 20 non-rate-ledger external hashes match. This is coherent with the active spec’s local, network-free, read-only GET boundary and Field Map catalog ownership.

- **Correct — dormant GBIF representative-photo elimination:** The prior `_lookup_photo`, candidate/cache URL helpers, `gbif_getter` injection seam, and positive GBIF representative-photo tests are deleted from `packages/databox/databox/agent_tools/recommendation_media.py`. Current representative enrichment accepts only curated iNaturalist photos plus separately owned Xeno-canto calls (`packages/databox/databox/agent_tools/recommendation_media.py:24-39,47-81,95-164`). Remaining GBIF strings in `recommendation_media_backfill.py:37-41,434-440` are narrowly bounded legacy-row recognition for migration compatibility, not a discovery helper or activation path. Separately typed GBIF occurrence context remains intentionally intact.

- **Correct — validation and graph coherence:** Operational hardening records 98 focused and 775 full Python tests plus static/security/SQLMesh/hooks gates; reconciliation records 145 focused and 776 full Python tests, three snapshots, 86.43% coverage, Ruff/format/MyPy, security/generated/docs/SQLMesh/source-layout, all hooks, diff check, and empty staging. Both bounded repair reviews pass. Active spec/decisions, aggregate dependencies, done tickets, evidence, and repair reviews agree on the iNaturalist-only architecture. The requested root `plan.md` and `progress.md` are absent; the active parent/aggregate ticket graph supplied the authoritative plan/progress instead.

- **Note — local limiter boundary:** The default state path is relative (`data/.inaturalist-photo-rate.json`), so coordination assumes Rufous processes share the project working directory/state path. This matches the present local-only deployment; a multi-host or independently rooted deployment would require an explicit shared path or a different limiter. Conservative reservation may consume budget if a process exits before sending the request, which fails safe.

## Prior architecture finding resolution

1. Actual v2/v1 request attempts and durable planner run observability: **resolved**.
2. Retryable provider failure versus terminal placeholder completion: **resolved**.
3. Governed catalog and planner photo-only retry/no-op behavior: **resolved**.
4. Cross-process/restart-safe local minute/day budget: **resolved**.
5. Dormant GBIF representative-photo helper and injection seams: **resolved**.
6. Authoritative ownership of the 82 prior-campaign placeholders and all 706 catalog rows: **resolved**.
7. Durable reproducible protected-state artifacts: **resolved**; checksum manifest passed.

## Verdict

**Pass.** No blocker or significant architecture finding remains. The operational hardening and campaign reconciliation resolve every failure from the prior final architecture review without reopening provider scope or widening the photo-only operators.

## Residual risks

- Provider-hosted image URLs/content and provider schemas remain remote and can later change because Rufous intentionally stores metadata rather than binaries.
- The rate limiter coordinates one shared local filesystem, not multiple hosts; its conservative pre-transport reservation can under-use the daily budget after a crash.
- Automated/TestClient evidence does not establish physical responsive rendering, live remote-image availability, visual subject quality, or NVDA/JAWS/VoiceOver behavior.
- This rereview did not rerun the full suites; it inspected the implementation/tests and validated the durable artifact checksum manifest, while relying on the recorded post-repair full-gate outputs.

```acceptance-report
{
  "criteriaSatisfied": [
    {
      "id": "criterion-1",
      "status": "satisfied",
      "evidence": "Performed only the requested final architecture rereview, made no repository edits, and wrote only the required /tmp review artifact."
    },
    {
      "id": "criterion-2",
      "status": "satisfied",
      "evidence": "Inspected active spec/decisions, aggregate tickets/evidence, done hardening and reconciliation tickets/evidence/reviews, prior final architecture review, current source/tests/diff/status, and verified the durable artifact checksum manifest with cited file/line evidence."
    }
  ],
  "changedFiles": [
    "/tmp/inat-only-closure-architecture-review.md"
  ],
  "testsAddedOrUpdated": [],
  "commandsRun": [
    {
      "command": "git status --short && git branch --show-current && git log -8 --oneline --decorate; git diff --stat/name-only; git diff --cached --name-only",
      "result": "passed",
      "summary": "Inspected the current working tree and confirmed the staged file list is empty."
    },
    {
      "command": "bounded source/test searches and numbered inspection for request_count, retryable semantics, run tables, rate limiter, campaign ownership, and GBIF photo helpers",
      "result": "passed",
      "summary": "Verified the repaired architecture and found no active GBIF representative-photo helper or injection seam."
    },
    {
      "command": "git diff --check; find data -maxdepth 1 -name '.inaturalist-photo-rate*'; sha256sum -c .10x/evidence/.storage/2026-07-13-inaturalist-reconcile-artifact-sha256.txt",
      "result": "passed",
      "summary": "Diff whitespace validation passed, staging remained empty, local durable rate files were present as expected, and every artifact in the reconciliation checksum manifest verified OK."
    }
  ],
  "validationOutput": [
    "Source inspection confirms bounded 0/1/2 request-attempt accounting and durable catalog/planner run observability.",
    "Source and tests confirm retryable provider failures are not terminal checkpoints, while identity/no-eligible placeholders remain terminal and reruns become no-ops after success.",
    "Reconciliation evidence and durable artifacts support authoritative ownership of 706 rows with 624 lookups, 1,248 requests, and outcomes totaling 706.",
    "Recorded final gates: 776 Python tests, three snapshots, 86.43% coverage, Ruff/format/MyPy, security/generated/docs/SQLMesh/source-layout checks, all hooks, diff check, and empty staging passed.",
    "Artifact checksum validation returned OK for all listed durable reconciliation artifacts."
  ],
  "residualRisks": [
    "Remote provider media/schema availability remains outside Rufous control.",
    "The limiter coordinates a shared local filesystem, not multiple hosts.",
    "No physical-browser, live-image, or assistive-technology session was performed in this rereview.",
    "The reviewer did not rerun the full suites and relies on recorded full-gate outputs plus source/test/artifact inspection."
  ],
  "noStagedFiles": true,
  "diffSummary": "Review-only task; no repository files were changed. The only created artifact is /tmp/inat-only-closure-architecture-review.md.",
  "reviewFindings": [
    "no blockers",
    "no significant architecture findings",
    "note: packages/databox/databox/curated_photo.py:120-156 - local rate coordination assumes processes resolve the same state path"
  ],
  "manualNotes": "Verdict: pass. Root plan.md and progress.md were absent; the active .10x parent/aggregate records were used as authoritative planning and progress sources."
}
```
