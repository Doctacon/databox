Status: recorded
Created: 2026-07-13
Updated: 2026-07-13
Target: `.10x/tickets/done/2026-07-11-verify-curated-representative-photos.md`, operational hardening, migration reconciliation, durable artifacts, and current working-tree state
Verdict: pass

# Final iNaturalist-only closure privacy/security/source rereview

## Review

- **Correct — request accounting and sanitized diagnostics:** `CuratedPhotoResult` carries bounded `request_count`, `failure_class`, and `retryable` fields, and persisted-result validation restricts request count to 0/1/2 and failure-class syntax (`packages/databox/databox/curated_photo.py:48-68, 222-242`). `_lookup_inaturalist` increments only after each budget reservation succeeds and immediately before each v2/v1 transport attempt, producing zero requests for non-queryable identities, one for a v2-stage failure, and two after both stages (`curated_photo.py:196-219, 342-416`). Catalog and planner run records separately persist lookup and actual request counts, bounded outcome-class JSON, duration, and safe failure text (`packages/databox/databox/catalog_media.py:169-195, 926-1097`; `packages/databox/databox/agent_tools/recommendation_media_backfill.py:96-110, 170-376`). Provider exceptions and payloads are reduced to fixed caveats/outcome keys or bounded exception class names; no raw provider response, arbitrary URL, credential, coordinate, or personal row value enters run diagnostics.

- **Correct — restart-safe locked local budget:** `InaturalistRateLimiter` uses a stable sidecar lock with `fcntl.LOCK_EX`, loads only the bounded three-field state, resets by UTC day, reserves before transport, and atomically replaces the JSON state (`curated_photo.py:108-190`). The default is 1.0 seconds between requests and 9,999 requests/day, satisfying the <=60/minute and <10,000/day local contract. Tests cover a reconstructed limiter after restart and two separate processes sharing a temporary state path (`tests/test_curated_photo.py:285-319`). The remaining boundary is explicitly local-filesystem coordination, not multi-host distributed enforcement.

- **Correct — tightly scoped retry behavior:** Budget, transport, and schema failures become strict unavailable results marked retryable; identity and exhausted-shortlist outcomes remain terminal (`curated_photo.py:292-316, 342-416`). Catalog completion derives from strict, campaign-owned, non-retryable rows (`packages/databox/databox/catalog_media.py:314-354, 948-1038`), while the saved-plan inspector targets only missing, invalid, or retryable photo singletons (`recommendation_media_backfill.py:381-467`). Curated-photo-only planner runs force `call_targets=[]` and request only `recommendation_photo` evidence (`recommendation_media_backfill.py:197-212, 276-305`). Catalog and planner retry/no-op tests establish that completed rows are not requeried, retryable rows are replaced without duplicates, actual attempts accumulate durably, and success makes the next run network/write-free (`tests/test_catalog_media.py:866-1041`; `tests/test_recommendation_media_backfill.py:709-796`).

- **Correct — endpoint, redirect, identity, and candidate URL safety:** Only the fixed v2 taxa endpoint and exact positive-integer v1 taxon path are accepted (`curated_photo.py:580-585`). Transport uses HTTPS, a descriptive user agent, ten-second timeout, one-MiB cap, disabled redirects, and post-response scheme/host/path/credential/port/fragment checks (`curated_photo.py:27-34, 71-84, 588-642`). V2 must yield exactly one exact-name active species-rank positive ID; v1 must repeat the same ID/name/rank/active identity before its bounded ordered shortlist is considered (`curated_photo.py:419-462`). Display/source URLs are independently restricted to allowlisted hosts, exact photo IDs, `large` display variant, supported extensions, and no credentials, explicit ports, query, or fragment (`curated_photo.py:319-339, 465-532, 645-663`). Adversarial URL, redirect, cap, and no-automatic-transport-retry coverage is present at `tests/test_curated_photo.py:208-282`.

- **Correct — zero prohibited or legacy activation:** The active selector has no Wikimedia/Wikidata/WDQS/P225/P18/Commons, GBIF-photo, observation-photo, model, fuzzy, parent, synonym, or proprietary representative-photo branch. Recommendation photos call only `select_curated_photo`; Xeno-canto remains call-only (`packages/databox/databox/agent_tools/recommendation_media.py:71-164`). Remaining GBIF-photo strings in `recommendation_media_backfill.py:37-41, 434-440` are narrow detection of a historical unavailable row so it can be replaced; they cannot select or activate GBIF media. API reconstruction accepts only strict iNaturalist available data or a URL-free placeholder and fails legacy evidence closed (`packages/databox/databox/api.py:801-878, 1168-1233`). Catalog photo persistence replaces only the owned photo singleton plus its photo-run checkpoint transactionally (`catalog_media.py:837-923`); planner photo-only persistence deletes/reinserts only the targeted recommendation-photo singleton (`recommendation_media_backfill.py:224-274`). No image bytes are requested or stored.

- **Correct — durable protected fingerprint reproducibility and sanitization:** The durable procedure `.10x/evidence/.storage/2026-07-13-inaturalist-photo-fingerprint-procedure.py` opens DuckDB read-only, inventories schemas/counts, and emits commutative SHA-256 row digests without row values. Independent comparison found all 86 protected fingerprints equal across original-pre, original-post, reconciliation-pre, post, post-gates, and final artifacts; all 20 non-rate-ledger external hashes also match across reconciliation snapshots. Every entry currently named by `2026-07-13-inaturalist-reconcile-artifact-sha256.txt` matched its file. Re-executing the durable procedure against the current database into `/tmp` reproduced the final 86 protected fingerprints and non-rate-ledger hashes, plus 706/706 strict catalog rows (622 available/84 placeholders) and eight valid planner singletons with no missing/duplicates. The artifacts contain column names (including names of personal/location columns), counts, and digests, but no personal row values, credentials, provider payloads, coordinates, or arbitrary URLs.

- **Correct — current source/data coherence:** Browser validators require exact response keys, exact scientific identity, canonical Creative Commons metadata, safe integer dimensions, fixed provider, and photo-ID-bound URLs (`app/src/curatedPhotoValidation.ts:1-72`; `app/src/birdApi.ts:53-91`). Current fingerprint reconstruction confirms zero invalid catalog/planner singleton state; source grep found legacy names only in rejection/regression fixtures and the bounded migration detector, not an activation implementation.

- **Note — two checksum-manifest logs are not repository-durable:** `.10x/evidence/.storage/2026-07-13-inaturalist-reconcile-apply.log` and `...rate-isolation.log` exist and match the checksum manifest, but `.gitignore:56` ignores `*.log` and neither file is tracked or reported by normal untracked-file status. This does not prevent protected-fingerprint reproduction—the procedure, six JSON snapshots, API validation JSON, and checksum manifest are trackable and independently sufficient for the verified equality—but the evidence record should not describe those two logs as durable repository artifacts unless they are exposed under a non-ignored format or explicitly force-added.

- **Blocker:** None.

## Verdict

**Pass.** The prior request-count, retry, restart/process-local budget, campaign ownership, and fingerprint-reproducibility findings are resolved. Endpoint/redirect/identity/URL controls fail closed; diagnostics are bounded and sanitized; retry writers remain photo-only; no legacy representative source can activate; the current catalog/planner state and protected fingerprints independently reconcile. The ignored-log packaging note does not undermine the protected fingerprint proof but should be corrected before claiming every manifest entry survives a clean checkout.

## Residual risks

- Rate coordination is intentionally limited to processes sharing one local filesystem/state path; it is not distributed across hosts.
- A crash after budget reservation but before transport conservatively consumes a daily slot; this fails safe and resets on the next UTC day.
- Provider-hosted metadata/images may change or disappear because Rufous intentionally persists metadata/URLs rather than binaries.
- Browser image display contacts the allowlisted iNaturalist open-data host; server-side GET routes remain local, network-free, and read-only.
- Physical-browser remote-image availability and provider behavior were not exercised in this deterministic rereview.
- Two supplemental `.log` artifacts are ignored and therefore will not survive ordinary repository staging unless renamed or force-added.

```acceptance-report
{
  "criteriaSatisfied": [
    {
      "id": "criterion-1",
      "status": "satisfied",
      "evidence": "Review-only scope was honored: no repository file was edited; only the required /tmp review artifact was written. Inspection remained limited to the active iNaturalist representative-photo closure surface."
    },
    {
      "id": "criterion-2",
      "status": "satisfied",
      "evidence": "Source/test citations, current diff/state inspection, manifest verification, six-snapshot fingerprint comparisons, and an independent read-only rerun of the durable procedure provide reproducible acceptance evidence."
    }
  ],
  "changedFiles": [],
  "testsAddedOrUpdated": [
    "tests/test_curated_photo.py",
    "tests/test_catalog_media.py",
    "tests/test_recommendation_media.py",
    "tests/test_recommendation_media_backfill.py"
  ],
  "commandsRun": [
    {
      "command": "pwd && git status --short && git status --porcelain=v2 --branch && git diff --stat && git diff --cached --stat",
      "result": "passed",
      "summary": "Inspected the broad unstaged/untracked working tree on main and confirmed the staged diff is empty."
    },
    {
      "command": "git diff -- <curated-photo operational source and tests>",
      "result": "passed",
      "summary": "Inspected selector, catalog/planner persistence and retry paths, API/browser validation, scripts, and focused tests."
    },
    {
      "command": "rg -n -i 'wikimedia|wikidata|wdqs|commons|P225|P18|gbif.*photo|photo.*gbif|gbif_getter|select_gbif|media_cache' packages/databox/databox scripts app/src tests",
      "result": "passed",
      "summary": "Found no active legacy representative-photo selector/activation path; remaining hits are rejection tests, unrelated GBIF occurrence context, or bounded historical-row replacement detection."
    },
    {
      "command": "sha256sum <durable reconciliation artifacts> plus manifest comparison",
      "result": "passed",
      "summary": "All ten currently present files named by the checksum manifest matched their recorded SHA-256 values."
    },
    {
      "command": ".venv/bin/python <snapshot comparison script>",
      "result": "passed",
      "summary": "All 86 protected fingerprints matched across six snapshots; 20 non-rate-ledger external hashes matched across reconciliation pre/post/post-gates/final."
    },
    {
      "command": "PYTHONPATH=packages/databox .venv/bin/python .10x/evidence/.storage/2026-07-13-inaturalist-photo-fingerprint-procedure.py data/databox.duckdb /tmp/inat-fingerprint-review-current.json",
      "result": "passed",
      "summary": "Read-only reproduction matched final protected and non-rate-ledger fingerprints and reported 706 valid catalog rows plus eight valid planner singletons."
    },
    {
      "command": "git check-ignore -v <reconciliation log artifacts> && git ls-files --error-unmatch <reconciliation log artifacts>",
      "result": "passed",
      "summary": "Verified both supplemental logs are ignored by the global *.log rule and are not tracked."
    }
  ],
  "validationOutput": [
    "Independent current reconstruction: catalog_valid_count=706; providers={curated_photo:unavailable:84, inaturalist:available:622}.",
    "Independent current reconstruction: planner_recommendation_count=8, invalid_or_missing=0, duplicates=0, provider={inaturalist:available:8}.",
    "Protected fingerprints: 86/86 equal across original pre/post and reconciliation pre/post/post-gates/final; current rerun equals final.",
    "Non-rate-ledger external hashes: 20/20 equal across reconciliation snapshots and current rerun.",
    "Recorded repair validation inspected: focused 145 and full 776 Python tests passed, plus Ruff/format/MyPy, security/generated/docs/SQLMesh/source-layout, hooks, diff, and empty staging. These suites were not rerun by this review."
  ],
  "residualRisks": [
    "Local filesystem rate coordination is not multi-host distributed coordination.",
    "Provider-hosted content may change or disappear because binaries are intentionally not stored.",
    "Two supplemental checksum-manifest log files are gitignored and not normally repository-durable."
  ],
  "noStagedFiles": true,
  "diffSummary": "Reviewed existing unstaged implementation that adds exact request diagnostics, locked durable local rate state, photo-only retry/run ledgers, campaign reconciliation, strict iNaturalist-only activation, and sanitized reproducible fingerprint artifacts; this reviewer changed no repository files.",
  "reviewFindings": [
    "no blockers",
    "note: .gitignore:56 - two supplemental reconciliation .log artifacts are ignored/untracked despite being described as durable; protected fingerprint reproduction remains independently complete from the procedure and JSON snapshots"
  ],
  "manualNotes": "Requested root plan.md and progress.md were absent; active .10x records were used as authority. Review-only instructions were honored."
}
```
