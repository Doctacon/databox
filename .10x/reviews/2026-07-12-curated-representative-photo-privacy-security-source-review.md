Status: recorded
Created: 2026-07-12
Updated: 2026-07-12
Target: curated representative-photo aggregate change; `.10x/tickets/done/2026-07-11-upgrade-representative-bird-photos.md`, its three completed children, `.10x/tickets/done/2026-07-11-verify-curated-representative-photos.md`, and the corresponding implementation/tests/live-migration evidence
Verdict: fail

# Curated representative-photo privacy, security, and source-integrity review

## Review

- **Correct:** The selector's persisted-result boundary is fail-closed for provider, exact species, source-record identity, dimensions, Creative Commons license, attribution, attempted-source order, and provider-specific HTTPS paths (`packages/databox/databox/curated_photo.py:160-239`). Catalog and planner APIs reconstruct and revalidate persisted metadata before exposure. The current DuckDB read-only check found only `inaturalist` available rows and typed `curated_photo` unavailable rows; no legacy GBIF representative-photo rows remain.
- **Correct:** Provider requests are metadata API requests with fixed endpoint families, a descriptive user agent, ten-second timeout, one-MiB body cap, JSON-object requirement, bounded candidate counts, and bounded retries (`packages/databox/databox/curated_photo.py:753-800`). No implementation path inspected downloads, proxies, caches, transforms, or stores image binaries.
- **Correct:** The reviewed aggregate evidence records passing secret scan and production bundle audit (12 configured names and 10 configured values absent). No credential is added to curated-photo requests. Diagnostics persist only bounded failure classes/caveats, not raw provider bodies or arbitrary URLs.
- **Correct:** The live migration evidence is unusually strong: the catalog run preserved 86 protected table/subset fingerprints and 19 external hashes; the saved-plan migration preserved 86 protected fingerprints, 109 non-photo evidence rows, and 19 external hashes. Recorded results show zero inserted calls during the saved-plan migration. This supports no model, email, routine source refresh, AVONET refresh, call lookup/refresh, personal-state, calendar/outbox, or unrelated warehouse mutation within the stated fingerprint limits.

## Findings

### Blocker — Wikimedia primary selection is nonfunctional with real Commons thumbnail responses

**Code:** `packages/databox/databox/curated_photo.py:242-253`, `packages/databox/databox/curated_photo.py:428-438`

The selector requests `iiurlwidth=1024`, but Commons can return a provider-generated 1280-pixel thumbnail for that request. The validator then rejects every thumbnail wider than 1024. A bounded live metadata probe for `Trogon elegans` observed an exact P225/P18 item, a qualifying 1920×2560 CC BY-SA image, and a Commons `thumburl` ending in `1280px-Elegant_Trogon.jpg`; `safe_wikimedia_thumbnail_url` returned `None`, and selection incorrectly fell through to iNaturalist. `Melanerpes formicivorus` reproduced the same fallback.

The migrated state corroborates a systemic failure rather than an isolated image: all 621 available catalog photos and all eight saved-planner photos are iNaturalist; there are zero Wikimedia results. This conflicts with the research record's 616/624 exact-name P18 coverage and violates the mandatory Wikimedia-first source order. The deterministic fixture tests do not model Commons' real 1280 response behavior, so their pass does not establish production source-order correctness.

**Required resolution:** Request or derive a provider-generated Commons thumbnail that is actually no larger than 1024 while retaining exact host/path/file/hash validation; add a real-shape regression fixture where Commons returns its 1280 response to the current request; prove an eligible Wikimedia candidate is selected and iNaturalist is not called. Because current rows are treated as completed curated results, explicitly re-evaluate all catalog and saved-plan photo rows after the fix rather than relying on the present missing-only/no-op resume path. Re-run preservation fingerprints and final provider counts.

### Significant — Wikidata action-API search cannot prove exact-name uniqueness

**Code:** `packages/databox/databox/curated_photo.py:803-824` (`_wikidata_api_result`)

The apparent exact `SELECT DISTINCT ... LIMIT 2` boundary is translated into relevance-ranked `wbsearchentities` with a 50-result cap, followed by P225 filtering. A bounded search result is not an exhaustive set of entities carrying the exact P225 value: an additional exact-name entity can be outside the relevance window. The implementation can therefore accept one visible exact item while failing to detect another, contrary to the specification's requirement that ambiguous exact-name entities fail closed.

**Required resolution:** Resolve P225 equality through a query or bounded protocol that can prove zero, one, or multiple exact entities independently of search relevance. Add an adversarial test where a second exact-P225 entity is outside the first search page/window and require typed unavailability without Commons or iNaturalist activation.

### Significant — Metadata HTTP redirects are not constrained to the endpoint allowlist

**Code:** `packages/databox/databox/curated_photo.py:753-772`

Initial endpoint strings are allowlisted, but `urllib.request.urlopen` follows redirects automatically. The code does not validate each redirect target or the final response URL. A compromised/misbehaving approved provider could redirect the local migration process to another origin, including a loopback or private-network GET target. The one-MiB response cap limits exfiltration volume but does not prevent the request or its possible side effect.

**Required resolution:** Disable redirects or install a redirect handler that permits only explicitly governed same-origin targets and validates every hop/final URL. Add tests rejecting redirects to loopback, link-local, private-network, credential-bearing, HTTP, and unapproved public origins.

### Significant — Trip Planner's browser-side Wikimedia validator does not bind URL identity to the persisted record

**Code:** `app/src/tripPlanValidation.ts:276-294`, `app/src/App.tsx:122-142`

For Wikimedia, the Trip Planner validators require only a QID-like source record, approved hosts, and broad path prefixes. They do not require the source page and thumbnail filename to equal the `File:` title in `source_record_id`, do not enforce the provider MD5 path buckets or supported extension grammar, and do not enforce the 1024-pixel thumbnail bound. They also omit password/port checks. Thus a mismatched Commons image/source pair can pass plan validation and be activated in the browser. The catalog validator is stronger (`app/src/birdApi.ts:90-114`), but the specification requires strict validation on every catalog/profile/map/planner browser path.

**Required resolution:** Use one shared exact provider validator for catalog and planner presentation. For Wikimedia, bind QID/file title, canonical source page, encoded thumbnail filename, MD5 buckets, supported raster extension, and width ≤1024; reject credentials, explicit ports, queries, and fragments. Add planner tests that independently mutate each identity/path/hash/width component and prove no image or source link is rendered.

## Verdict

**Fail.** Privacy, secret handling, metadata-only behavior, prohibited-side-effect boundaries, and preservation evidence are adequate within their recorded limits. Closure is nevertheless blocked because the production selector does not implement the mandatory Wikimedia-first policy, current live rows were migrated under that defect, exact Wikidata ambiguity is not provably closed, redirects bypass the outbound-origin allowlist, and the Trip Planner browser path accepts mismatched Wikimedia identities.

## Residual risks

- No packet capture was taken; prohibited network-side effects are supported by command-path inspection, deterministic transports, counters, and state fingerprints rather than wire-level observation.
- Provider schemas and hosted URLs can change after validation; metadata-only persistence intentionally cannot guarantee future image availability or unchanged remote content.
- Metadata validation and provider curation do not establish visual subject correctness, composition, or human-reviewed suitability.
- The process-local request budgets assume the documented serialized single-process migration owner; they do not coordinate quotas across processes or hosts.
- The live metadata probes made during this review were read-only and stored no provider payloads, but they demonstrate current provider behavior only as of 2026-07-12.

```acceptance-report
{
  "criteriaSatisfied": [
    {
      "id": "criterion-1",
      "status": "unsatisfied",
      "evidence": "The change remained focused on curated representative-photo metadata and migrations, but packages/databox/databox/curated_photo.py:428-438 requests a Commons width that produced 1280px URLs rejected at lines 242-253; final state contains 0 Wikimedia available photos despite mandatory Wikimedia-first selection."
    },
    {
      "id": "criterion-2",
      "status": "satisfied",
      "evidence": "Independent source inspection, targeted live metadata probes, read-only DuckDB provider/status counts, diff/status inspection, child preservation evidence, and aggregate gate results provide reproducible acceptance evidence and specific required resolutions."
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
    "tests/test_api.py",
    "tests/test_map_snapshot_api.py",
    "app/src/BirdPages.test.tsx",
    "app/src/FieldMap.test.tsx",
    "app/src/App.test.tsx",
    "app/src/tripPlanValidation.test.ts"
  ],
  "commandsRun": [
    {
      "command": "git status --short && git diff --stat && git diff --cached --stat",
      "result": "passed",
      "summary": "Inspected the worktree and confirmed the cached/staged diff was empty."
    },
    {
      "command": ".venv/bin/python read-only DuckDB provider/status query",
      "result": "passed",
      "summary": "Observed catalog counts curated_photo/unavailable=85 and inaturalist/available=621; saved planner inaturalist/available=8; no Wikimedia available rows."
    },
    {
      "command": "PYTHONDONTWRITEBYTECODE=1 .venv/bin/python targeted select_curated_photo probes for Melanerpes formicivorus and Trogon elegans",
      "result": "failed",
      "summary": "Both exact taxa selected iNaturalist despite eligible Wikidata/Commons candidates, failing the required Wikimedia-first validation."
    },
    {
      "command": "PYTHONDONTWRITEBYTECODE=1 .venv/bin/python targeted Commons-stage probe",
      "result": "failed",
      "summary": "Observed a qualifying Trogon Commons image returned as a 1280px thumb for iiurlwidth=1024; the production URL validator rejected it and candidate count was zero."
    },
    {
      "command": "Reviewed recorded aggregate: PYTHONDONTWRITEBYTECODE=1 .venv/bin/pytest",
      "result": "passed",
      "summary": "Aggregate evidence records 769 tests passed, three snapshots passed, and 86.37% coverage."
    },
    {
      "command": "Reviewed recorded aggregate: npm run typecheck && npm test && npm run build && scripts/audit_app_bundle.py",
      "result": "passed",
      "summary": "Strict TypeScript, 273 frontend tests, production build, and configured-name/value bundle audit passed."
    },
    {
      "command": "Reviewed recorded aggregate: ruff, format, mypy, secret scan, SQLMesh tests, pre-commit, git diff --check",
      "result": "passed",
      "summary": "Recorded static, secret, non-mutating SQLMesh, hook, and diff gates passed."
    }
  ],
  "validationOutput": [
    "Current catalog: 706 photo rows = 621 available iNaturalist + 85 typed curated placeholders + 0 Wikimedia.",
    "Current saved planner: 8 available iNaturalist photo rows + 0 Wikimedia; singleton photo cardinality was recorded as valid.",
    "Trogon elegans live metadata: exact Q632823/P18, 1920x2560, CC BY-SA 2.0, provider thumburl 1280px; safe_wikimedia_thumbnail_url returned None.",
    "Recorded migration preservation: catalog 86 protected fingerprints and 19 external hashes unchanged; planner 86 protected fingerprints, 109 non-photo evidence rows, and 19 external hashes unchanged.",
    "Recorded secret and bundle gates passed; no curated-photo request carries credentials and no image binary persistence path was found."
  ],
  "residualRisks": [
    "No packet capture; absence of prohibited network effects is inferred from code paths, counters, and protected-state fingerprints.",
    "Automatic redirects remain an SSRF/source-boundary risk until constrained.",
    "Remote image availability/content and provider schemas can change after metadata validation.",
    "No visual subject-quality guarantee follows from provider curation and metadata checks.",
    "Request budgets are process-local and assume serialized operation."
  ],
  "noStagedFiles": true,
  "diffSummary": "Adds a shared curated Wikimedia/iNaturalist metadata selector, strict persistence/API/frontend contracts, explicit resumable catalog and saved-plan photo migrations, and focused tests; review found the real Commons thumbnail response disables the Wikimedia primary plus three security/source-integrity gaps.",
  "reviewFindings": [
    "blocker: packages/databox/databox/curated_photo.py:242-253,428-438 - Commons returns 1280px for iiurlwidth=1024, so eligible Wikimedia candidates are rejected and all live available rows fell back to iNaturalist.",
    "significant: packages/databox/databox/curated_photo.py:803-824 - relevance-limited wbsearchentities cannot prove exact-P225 uniqueness.",
    "significant: packages/databox/databox/curated_photo.py:753-772 - automatic HTTP redirects are not constrained to approved origins.",
    "significant: app/src/tripPlanValidation.ts:276-294 and app/src/App.tsx:122-142 - planner browser validation does not bind Wikimedia URLs to source_record_id/file identity or enforce the thumbnail bound."
  ],
  "manualNotes": "Verdict is fail. Repair selector/source boundaries and browser validation, then explicitly re-evaluate all current catalog and saved-plan photo rows because existing curated rows are otherwise treated as complete/no-op."
}
```
