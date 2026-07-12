Status: recorded
Created: 2026-07-11
Updated: 2026-07-11
Relates-To: .10x/tickets/done/2026-07-11-verify-place-search-feedback-and-map.md, .10x/tickets/2026-07-11-upgrade-place-search-feedback-and-map.md

# Place search, feedback, and Field Map aggregate verification

## Authority and graph inspected

Verification inspected the aggregate and parent tickets; all five done implementation children and their evidence; all five pass child reviews; the active Arizona place-suggestion, structured-observation-location, transient-success, and Field Map interaction specifications; and the local-place/fallback decisions. The focused fallback decision explicitly supersedes only the earlier capacity-fill wording: any valid local hotspot suppresses Open-Meteo.

The completed children are:

- local hotspot place suggestions;
- structured observation persistence and migration;
- observation location combobox reuse;
- transient success feedback;
- Field Map interaction/layout repair, including the reviewed generation-guard follow-up.

No provider, model, source, SMTP/delivery, refresh, remediation, SQLMesh apply/plan, personal mutation, stage, or commit command ran. The Python suite ran with network blocked, VCR recording disabled, proxies unset, and UV offline.

## Live-state isolation

Read-only state captured before and after every gate was byte/logically identical:

```text
warehouse_sha256=0dc79f3596c9bd5698c4c9f40d91dd0cfbda82f2093a85611c4aacfedcd003ce
warehouse_size=58470400
observation_count=1
safe_presence_only_checksum=aeee03cbd2c809dcbdcf4bb270baf96043eb094bed7b6193c5bf5c34d3017b65
structured_null_rows=1
all_six_structured_fields_null=true
pre_post_exact_match=true
sqlmesh_state_sha256=c4995254709053ebffabcc16fbfe235e1d47b93208a7a1b1a81bb77b75852a93
```

The safe checksum includes identity/date/timestamps and only presence booleans for private free-text fields; no private location or note value was printed or recorded.

## Full verification gates

- Network-blocked Python: 709/709 passed, three snapshots passed, 86.74% coverage.
- Frontend: TypeScript passed; 260/260 Vitest tests across 16 files passed.
- Production build: 52 modules transformed; bundle audit found all 12 server-only names and ten configured values absent. The existing lazy Field Map chunk advisory remains non-blocking.
- SQLMesh: 13/13 unit tests passed; lint passed; `diff prod` reported no changes. No plan/apply command ran.
- Production Soda: 25/25 contracts, 125 checks, zero failures.
- Static/repository: Ruff passed; 155 files were already formatted; MyPy passed 95 source files; secret scan passed; seven source layouts passed; staging, platform-health, and 20 dictionary files were current.
- MkDocs strict passed with only the upstream Material/MkDocs 2.0 warning and existing dictionary navigation notices.
- All pre-commit hooks and `git diff --check` passed; cached diff was empty.

## Live local search and ranking

A read-only query observed 2,912 `US-AZ` hotspots and 2,912 distinct hotspot IDs. A live-warehouse FastAPI `TestClient` received an injected getter that raises if called. Both `lake watson` and reversed-token `watson lake` returned HTTP 200 with exactly:

```text
Watson Lake and Riparian Preserve
source_id=L270303
place_type=Birding hotspot
latitude=34.5822319
longitude=-112.4259328
upstream_calls=0
```

The warehouse hash was unchanged. Passing attacks cover Unicode/case/punctuation normalization, every-token matching, exact/prefix/position/compactness/checklist/name/ID ranking, response bounds, malformed/duplicate/out-of-Arizona rows, zero-local-only fallback, safe fallback failure, and same-label/0.001-degree local-wins deduplication.

## Structured and free-text observation behavior

The live migration remains complete and idempotent: the one legitimate observation retains the same safe checksum and all six structured fields remain null. Focused and full backend/browser tests cover migration rollback/apply-twice, exact Watson source/name/coordinates/timezone/region persistence, optional free text with null structure, all-or-none and relationship attacks, atomic clear/replace, legacy initialization, typed-edit selection clearing, failed-save preservation and safe focus, and one collection invalidation per successful mutation.

Structured fields remain confined to private collection surfaces. Passing privacy/map/catalog tests reject personal observation fields from public catalog, map, evidence/model/log payloads. Observation free text triggers neither background nor save-time geocoding; no personal mutation ran during aggregate verification.

## Transient success feedback

Static inventory still finds exactly three production success-banner owners: My Birds, profile collection controls, and accepted trip-calendar actions. All use the one shared hook and exact `SUCCESS_DISMISS_MS = 3000`. Fake-timer tests prove immediate display, visibility through 2,999ms, exact 3,000ms dismissal, same-message replacement reset, action reset, and unmount cleanup. Errors, warnings, busy/pending, delivery-unknown, and persisted states remain untimed.

## Field Map reconciliation

The direct MapLibre adapter tests pass for pre-load filtered data retention, post-load `setData`, every filter's source/count/extent update, Arizona All/empty framing, selected highlight above points, shared point/list card/pressed/pan/zoom state, cluster expansion zoom, reduced motion, cleanup, no-results/history, and local inline style/request behavior.

The reviewed generation repair increments the source generation and invalidates marker readiness before every `setData`. `moveend` refresh is blocked until loaded encounter `sourcedata` confirms the current generation. The exact regression deliberately leaves old queried features available across 4→2→0 changes, fires filter-driven `moveend` before `sourcedata`, and proves stale 1/4/2 markers cannot reappear. Desktop remains map plus one right rail with Selected Encounter above the bounded list; narrow DOM/visual order is Map → Selected → List.

## Findings and limits

No implementation, architecture, correctness, privacy/security, local-only, accessibility-contract, persistence, migration, or record-graph blocker was found in aggregate execution. Child independent reviews all pass. Aggregate architecture, correctness, privacy/security, and UX/accessibility reviews remain required before closure.

Automated browser behavior is verified in jsdom and MapLibre through a typed adapter rather than a physical GPU/device or assistive-technology session. Open-Meteo and delivery behavior remain injection/fake-transport tested; verification deliberately made no live provider or delivery call.
