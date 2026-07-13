Status: recorded
Created: 2026-07-12
Updated: 2026-07-12
Relates-To: .10x/tickets/done/2026-07-12-repair-map-wheel-refresh-review-findings.md, .10x/reviews/2026-07-12-map-wheel-refresh-architecture-review.md, .10x/reviews/2026-07-12-map-wheel-refresh-correctness-review.md, .10x/reviews/2026-07-12-map-wheel-refresh-privacy-security-source-review.md, .10x/reviews/2026-07-12-map-wheel-refresh-ux-accessibility-review.md

# Map, wheel, and refresh review repairs

## What was observed

- The refresh API and durable runner derive the routine scope from the canonical `SOURCES` registry, pin every source explicitly at both subprocess boundaries, and expose bounded per-source status.
- A fake runner completed the exact six-source lifecycle, entered SQLMesh only after all six success markers, survived independently of an app waiter through atomic status writes, and rejected noncanonical scope before process launch.
- A fake GBIF failure remained source-attributed, never entered the SQLMesh phase, and persisted only safe bounded log markers. Injected credential-like text, a private URL, and a 20,000-byte arbitrary line were absent from the durable log.
- API tests covered hostile Host and Origin, false/extra/form bodies, fixed command/environment, canonical scope, active conflict, pre-PID grace, stale-process failure, malformed status, and oversized status.
- Frontend tests covered strict bounded progress validation, source and SQLMesh progress, persisted failure/log disclosure, reconfirmed retry, polling failure sanitation, 3,000-ms success dismissal, independent hover/focus preview, selected-over-preview layer authority, thumbnail load-failure attribution, and reduced-motion wheel centering.
- `app/src/BirdPages.test.tsx` was restored from HEAD after an aborted edit and differs only by the focused reduced-motion test plus test-global cleanup (14 additions, no deletions).

## Procedure and results

- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/pytest --no-cov -p no:cacheprovider tests/test_source_refresh_api.py tests/test_source_refresh_runner.py tests/test_parallel_refresh.py tests/test_map_snapshot_api.py -q` — 37 passed.
- `cd app && npm test -- --run src/sourceRefreshApi.test.ts src/SourceRefreshControl.test.tsx src/FieldMap.test.tsx src/BirdPages.test.tsx` — 4 files, 40 tests passed.
- `cd app && npm run typecheck` — passed without diagnostics.
- `.venv/bin/ruff check ...` — passed for the four changed Python/test files.
- `.venv/bin/ruff format --check ...` — all four files formatted.
- `.venv/bin/mypy packages/databox/databox/source_refresh_api.py packages/databox/databox/source_refresh_runner.py` — no issues.
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python scripts/check_secrets.py .` — passed with no findings.
- `git diff --check` — passed; tracked diff numstat showed no accidental file deletion, and the restored BirdPages test showed `14 0`.
- `git diff --cached --name-only` — empty.

## What this supports

This supports every acceptance criterion in `.10x/tickets/done/2026-07-12-repair-map-wheel-refresh-review-findings.md` at focused unit/component/static scope. The tests use fake processes and in-memory provider-like output; they do not launch the real refresh command.

## Side-effect limits

No live provider request, routine source refresh, Quack server, SQLMesh apply, AVONET/media refresh, model call, email, or image/binary download ran. No warehouse, personal observation, Watch, planner, calendar, outbox, call-media, credential, or curated-photo record was read or mutated by the tests beyond normal read-only source imports. Pre-existing untracked curated-photo records and runtime artifacts were preserved.

## Limits

No physical browser, MapLibre paint inspection, screen reader, assistive technology, process-kill integration, or live refresh was performed. Final aggregate full-suite, docs/Soda/hooks, state-integrity, and independent review reruns remain owned by `.10x/tickets/done/2026-07-11-verify-map-wheel-and-refresh-controls.md`.
