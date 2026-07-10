Status: recorded
Created: 2026-07-09
Updated: 2026-07-09
Relates-To: .10x/tickets/done/2026-07-09-verify-recommendation-card-media.md, .10x/tickets/done/2026-07-09-add-recommendation-card-photos-and-calls.md, .10x/specs/recommendation-media-enrichment.md, .10x/specs/recommendation-card-media-layout.md

# Recommendation-card media aggregate verification

## Verification boundary

This was verification-only. It made no product-code or test changes, performed no live Cloudflare or media discovery request, and did not regenerate a plan. The only apply command was the already-complete backfill's verified zero-target/no-lookup path.

The parent and all three done children, both governing specs, all three child evidence records, and all three pass reviews were read before verification. The focused graph resolves to one active parent, one active verification child, and three done implementation/data children with existing pass reviews.

## Criterion mapping

### Parent aggregate criteria

| Parent criterion | Current evidence |
|---|---|
| Exactly one photo and call result per recommendation | Read-only DuckDB join found 16 recommendations, 32 media rows, and zero bad cardinality. Every result is available. |
| Exact Arizona GBIF photos with attribution/license/source | All 16 persisted photos passed normalized species, finite CC parsing, exact occurrence source, and exact GBIF 500x500 occurrence-key/identifier-MD5 validation. All use `CC BY-NC 4.0`. |
| Arizona-first/global Xeno calls with labels | All 16 calls passed canonical ID/source/audio and finite license validation; scopes are 14 Arizona and 2 Global example. Queen Valley has the expected two global fallbacks. |
| Failure cannot change recommendations | Deterministic selector/planner tests cover partial/unavailable outcomes, identical recommendation/model semantics, contiguous ranks, and cleanup. |
| Single DuckDB; metadata only; no binaries | Every registered source resolves to `data/databox.duckdb`; `birding_agent` has zero binary columns. Tracked/product media-extension scan and embedded data-URI scan found zero files/values. |
| One lazy photo/placeholder and native call/placeholder per card | All 50 React tests pass, including mixed unavailable states, lazy image, native controls, `preload="none"`, no autoplay, attribution retention, and independent failures. |
| No standalone media section and exact result order | Rendered tests assert Field Plan; Weather and Elevation; High-likelihood Species; Uncommon but Plausible Targets; final Evidence and Provenance, with no standalone section. |
| Workflow accessible in final provenance | React tests verify visible evidence plus native `details`/`summary` Agent Workflow in the final section. |
| Explicit idempotent backfill and read-only GET | Dry-run and apply both report zero targets, inserts, replacements, and lookups. Queen Valley GET made zero injected discovery calls and left the full application-table snapshot unchanged. |
| Cross-stack gates and no unowned child defect | Three child reviews are pass; focused, SQLMesh, frontend, DeepEval, full CI, docs, pre-commit, bundle, secret, binary, architecture, graph, and diff checks pass. Aggregate independent review remains pending. |

### Verification-ticket criteria

- **New-plan sequencing and invariance:** source inspection shows rank at step 5, media at step 6, core evidence at step 7, model at step 8 using `core_evidence` only, and completed-plan persistence at step 9. Planner tests prove media outcomes do not alter recommendation identity/rank/group/confidence/rationale or model grounding and persistence failures clean partial completed artifacts.
- **Selector and transport security:** 30 selector tests cover exact Queen Valley species, order-independent total ranking, Arizona/global behavior, identity/geography/MIME/attribution/license rejection, exact GBIF cache relationships, exact Xeno IDs/paths, finite CC policies including photo-ND rejection, typed unavailable results, fixed endpoints, 50-candidate cap, 10-second timeout, one-MiB response cap, and safe error suppression.
- **Backfill safety:** 14 backfill tests cover read-only dry-run, partial failure, no model path, immutable plan/recommendation hashes, second-run no-op, exact v2-only compatibility repair, rollback, duplicate preflight, and external lock failure.
- **API/GET behavior:** 16 API tests plus the live read-only snapshot probe cover typed persisted media reconstruction, source/audio sanitization, cardinal identity, stable failures, and zero GET discovery/write.
- **Current Queen Valley:** read-only warehouse/API verification found eight cards and 16 media rows; every photo and call is available.
- **Frontend runtime trust:** 50 React tests cover exact recommendation-ID attachment, untrusted nested JSON, species/cross-ID mismatch suppression, license label/URL consistency including CC0, canonical URLs, attribution-preserving load failures, placeholders, responsive containment, semantic ordering, and disclosure accessibility.
- **SQLMesh and architecture:** 11 SQLMesh tests pass and `sqlmesh diff prod` reports no changes. Six independently scheduled source domains (`ebird`, `gbif`, `xeno_canto`, `noaa`, `usgs`, `usgs_earthquakes`) expose their own dlt assets/schedules and resolve to one database. Shared-server Quack overlap/single-server and destination tests pass.

## Current warehouse observation

The read-only verifier used the same license and canonical URL validators as product code while activating no remote requests:

```text
plans=2 recommendations=16 media_rows=32 bad_cardinality=0
queen_media_rows=16 queen_cards=8
photo_licenses={'CC BY-NC 4.0': 16}
call_licenses={'CC BY-NC-ND 2.5': 3, 'CC BY-NC-ND 4.0': 1, 'CC BY-NC-SA 3.0': 3, 'CC BY-NC-SA 4.0': 9}
call_scopes={'Arizona': 14, 'Global example': 2}
binary_columns=0
get_status=200 get_network_calls=0 snapshot_unchanged=True
snapshot_sha256=d537844b8568975574111bd5dd4e546cfd0d7380421d56eafa7f1a7e54392d44
```

Three source recommendation names retain authority strings while persisted media identity uses the required normalized binomial. The verifier initially compared raw strings, then correctly applied the shared binomial normalizer; this is expected conformance, not a product mutation.

## Commands and outputs

```text
uv run --no-sync pytest tests/test_recommendation_media.py tests/test_recommendation_media_backfill.py tests/test_birding_trip_planner.py tests/test_api.py tests/test_parallel_refresh.py tests/test_source_registry.py tests/test_quack_destinations.py --no-cov -q
100 passed.

task media:backfill -- --dry-run
2 plans; 16 recommendations; 0 targets; 0 missing; 0 duplicates; 0 lookups.

task media:backfill -- --apply
2 plans; 16 recommendations; 0 targets; 0 inserts; 0 replacements; 0 lookups.

cd transforms/main && ../../.venv/bin/sqlmesh test && ../../.venv/bin/sqlmesh diff prod
11 tests passed; project files match prod.

cd app && npm run typecheck && npm test -- --run --reporter=dot && npm run build
TypeScript passed; 50 tests passed; 30 modules built.

task app:audit-bundle
3 configured names and 3 configured values absent.

uv run --no-sync pytest tests/evals/test_birding_trip_copilot_deepeval.py -q
2 passed.

task ci
258 passed; 84.09% coverage; Ruff, format, MyPy, secret, generated-staging, and platform-health checks passed.

tracked/product binary-media scan; embedded media data scan; browser discovery/credential scan
0 tracked media files; 0 product media files; 0 embedded image/audio data; 0 discovery endpoints/credential names in bundle.

focused record graph/reference/status and git diff checks
parent active; verification active; three children done; eight governing evidence/spec/review references exist; no staged files.
```

## Limits and review attention

- No remote media bytes were requested. Browser error behavior is simulated, and remote cache/audio availability remains temporal.
- Responsive behavior is DOM/CSS tested rather than screenshot-regressed.
- The warehouse deliberately retains validated original photo identifiers as server-side provenance; “no arbitrary URL” is verified as no arbitrary **active browser URL**. Public API activation remains limited to exact GBIF/Xeno/source/license contracts.
- The active photo geography spec says `US`/`United States`; the reviewed implementation also recognizes GBIF's exact `United States of America` spelling as the same country. This was explicitly exercised and accepted in the backfill child, but aggregate review should decide whether the spec wording needs a non-behavioral clarification before parent closure.
- Independent aggregate review passed and is recorded at `.10x/reviews/2026-07-09-recommendation-card-media-aggregate-review.md`.
