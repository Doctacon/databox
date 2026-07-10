Status: recorded
Created: 2026-07-09
Updated: 2026-07-09
Relates-To: .10x/tickets/done/2026-07-09-implement-request-time-recommendation-media.md, .10x/specs/recommendation-media-enrichment.md

# Request-time recommendation media implementation evidence

## What was observed

The local Python planner now enriches its fixed, ranked recommendation set with exactly one typed photo result and one typed call result per recommendation. Each result is persisted as recommendation-linked `birding_agent.trip_plan_evidence`, including explicit unavailable results. The detail API reconstructs typed `photo` and `call` objects from persisted rows; GET performs no discovery request.

No model prompt/schema was changed. The model receives only the pre-media core evidence and the same fixed recommendation semantics. Media selection occurs after ranking, cannot alter ranks, and is persisted in the existing completed-plan transaction.

## Procedure and fixtures

### Selection/security fixtures

`tests/test_recommendation_media.py` uses injected metadata-only getters and verifies:

- The exact researched Queen Valley recommendations—`Anser rossii`, `Pelecanus erythrorhynchos`, `Aythya collaris`, `Psaltriparus minimus`, `Xanthocephalus xanthocephalus`, `Mimus polyglottos`, `Fulica americana`, and `Anas platyrhynchos`—produce eight photos and eight calls.
- `Anser rossii` and `Pelecanus erythrorhynchos` use non-Arizona global fixtures and are labeled `Global example`; the other six independently report United States/Arizona geography and remain Arizona-scoped.
- GBIF requests are exact-species, United States/Arizona, `StillImage`, and limited to 50 candidates; returned occurrence country and state are independently validated before an Arizona label is assigned.
- Active photos use only the exact `api.gbif.org/v1/image/cache/500x500/occurrence/{key}/media/{md5(identifier)}` path with verified numeric key and lowercase identifier MD5 relation. Discovery/root/original paths, key/hash mismatch, query, fragment, credentials, traversal, and other sizes fail closed. The original identifier remains persisted for server-side provenance/validation but is removed from public evidence payloads; only its MD5 is returned.
- Photo ND licenses are unavailable because no exact-original display policy exists. Xeno audio may use the explicit BY-ND/BY-NC-ND allowlist only for unchanged streaming.
- Selector and API license parsing accept only CC0/BY/BY-SA/BY-NC/BY-NC-SA plus audio-only ND variants with explicit sane versions. Unknown slugs, `999.999`, `4..0`, and invalid CC0 versions fail closed.
- Photo and call ranking include normalized immutable fields followed by every exact persisted output field after semantic preference keys. Dedicated reversed duplicates for `Alice`/`ALICE`, `Call`/`CALL`, and `Arizona`/`ARIZONA` return fully identical selected evidence while preserving the deterministic winner's original attribution spelling.
- Wrong species/geography, unsupported media/MIME, missing attribution, identity/source/audio mismatches, arbitrary active hosts, and unrecognized licenses fail closed.
- Direct HTTPError, URLError, and timeout probes produce only `recommendation-media discovery failed`, with no retained cause/context, URL, key, or private transport detail.
- The default transport has a 10-second timeout, one-MiB response bound, fixed HTTPS endpoints, and 50-candidate bound.

### Planner and persistence fixtures

`tests/test_birding_trip_planner.py` runs injected deterministic GBIF/Xeno discovery twice for the same plan ID and verifies:

- every persisted recommendation has exactly one `recommendation_photo` and one `recommendation_call`,
- both rows are available in the positive fixture,
- a second run does not duplicate evidence,
- ranks remain contiguous and unchanged,
- model recommendation semantics and core evidence counts remain identical,
- media does not enter model evidence grounding,
- the aggregate trace contains bounded counts/scopes only and excludes the injected API key,
- failed model or persistence paths retain existing cleanup behavior.

### API/reload fixture

`tests/test_api.py` creates a Western Bluebird plan with injected media getters and verifies persisted photo/call metadata, attribution, Creative Commons links, Arizona scope, safe Xeno source/audio identity, and identical reload results. The media getter counter remains unchanged across GET, proving reload is network-free. Existing plans without enrichment receive typed unavailable response objects without mutation.

## Commands and results

```text
uv run --no-sync ruff check <focused media/planner/API files>
All checks passed.

uv run --no-sync mypy packages/databox/databox/agent_tools/recommendation_media.py packages/databox/databox/agents/birding_trip_planner.py packages/databox/databox/api.py
Success: no issues found in 3 source files

uv run --no-sync pytest --no-cov -q tests/test_recommendation_media.py tests/test_birding_trip_planner.py tests/test_api.py
53 passed

cd app && npm run typecheck && npm test -- --run && npm run build
TypeScript passed; 27 tests passed; 30-module production build passed.

uv run --no-sync pytest --no-cov -q tests/evals/test_birding_trip_copilot_deepeval.py
2 passed

task ci
239 passed; 83.90% coverage; Ruff, formatting, MyPy, secret, generated-staging, and platform-health checks passed.

task app:audit-bundle
3 configuration names and 3 configured values absent.

task docs:build
Strict documentation build passed.

uv run --no-sync pytest --no-cov -q tests/test_recommendation_media.py
28 passed after final total-order repair.

git diff --check && git diff --cached --quiet
Passed; no staged files.
```

## What this supports

- Request-time discovery is bounded, deterministic, strict, server-side, metadata-only, and non-fatal.
- Exactly one photo and call result per new recommendation is durable and reloadable.
- URL, identity, license, attribution, MIME, and geographic-scope constraints fail closed.
- Recommendation rank/model grounding and atomic persistence behavior are preserved.
- Browser assets contain no discovery credentials or browser-side discovery configuration.

## Limits

- This ticket does not mutate or backfill existing plan rows; missing historical media is represented only as typed unavailable API output.
- Remote image/audio availability after selection can change; source and license metadata remain persisted.
- Photo display depends on GBIF's derived cache endpoint; an eligible publisher original may still fail to resolve through that remote cache.
- License versions are deliberately explicit and finite; newly published Creative Commons versions require a reviewed allowlist update.
