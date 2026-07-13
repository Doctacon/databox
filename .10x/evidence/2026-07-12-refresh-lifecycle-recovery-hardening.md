Status: recorded
Created: 2026-07-12
Updated: 2026-07-12
Relates-To: .10x/tickets/done/2026-07-12-harden-refresh-lifecycle-and-recovery.md, .10x/tickets/done/2026-07-11-verify-map-wheel-and-refresh-controls.md

# Refresh lifecycle and recovery hardening

## What was observed

- The API atomically creates a bounded owner file before publishing running status or spawning a runner. A valid/fresh owner blocks launch even when status is missing, malformed, or oversized; malformed owner state also fails closed.
- The runner verifies the exact run/status/owner identity and publishes its own PID before launching the warehouse-mutating orchestration. Owner-publication failure starts no child, persists safe failure, and releases ownership.
- Ownership uses a bounded heartbeat plus stale-owner process-command verification containing the exact runner module and run ID. A fresh or verified runner remains active; a stale owner with a live but mismatched PID is released. This avoids trusting PID liveness alone and detects PID reuse/unrelated processes.
- The actual Quack orchestration emits `PHASE_START phase=sqlmesh` only after server shutdown, dedupe, client cleanup, overlap validation, and warehouse inspection, immediately before SQLMesh. The durable runner changes phase only on this marker and only after all six sources succeeded.
- One connected fake starts at the real API command, extracts its exact six canonical source arguments, feeds output produced by the real `execute_parallel_refresh` seam through the durable runner, and proves one server plus cleanup/dedupe/inspection before SQLMesh. A connected exact-six failure test proves no phase marker or SQLMesh call and preserves GBIF attribution.
- The browser retries initial status restoration while disabling launch, clears transient request errors on every valid status, and retains durable failure semantics. Wheel regressions cover Arrow Up/Down, Page Up/Down, Home, End, `aria-activedescendant`, and `aria-selected` synchronization.
- The aggregate parent child plan and blocker/progress text now include both review-repair children and current review state.

## Procedure and results

- `PYTHONDONTWRITEBYTECODE=1 PYTEST_ADDOPTS='--no-cov' .venv/bin/pytest -q -p no:cacheprovider tests/test_source_refresh_api.py tests/test_source_refresh_runner.py tests/test_parallel_refresh.py` — 23 passed.
- `cd app && npm test -- --run src/sourceRefreshApi.test.ts src/SourceRefreshControl.test.tsx src/BirdPages.test.tsx` — 3 files, 35 tests passed.
- `cd app && npm run typecheck` — passed without diagnostics.
- `.venv/bin/ruff check .` — passed.
- `.venv/bin/ruff format --check .` — 159 files already formatted.
- `.venv/bin/mypy packages/` — 97 source files passed; one existing unchecked-body informational note.
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python scripts/check_secrets.py .` — passed with no findings.
- `git diff --check` — passed; `git diff --cached --name-only` was empty.

## Adversarial coverage

Tests cover invalid/oversized status plus active owner, pre-runner owner publication, malformed/oversized owner fail-closed behavior, spawn failure cleanup, runner owner-publication failure, terminal restart recovery, stale heartbeat with mismatched live PID, stale heartbeat with verified runner identity, canonical scope/order rejection, bounded safe logs, status-write failure terminating the isolated orchestration process group before ownership release, authoritative phase ordering, source failure suppression, transient polling recovery, initial restoration retry, and wheel keyboard/ARIA state.

## Side-effect limits

No live provider request, routine source refresh, Quack server, project SQLMesh plan/apply, AVONET/media refresh, model call, email, or image/binary download ran. All orchestration processes, servers, providers, warehouse paths, and SQLMesh calls in focused tests were fakes. Project warehouse, SQLMesh state, personal observations, Watches, plans, calendar, outbox, call media, credentials, and curated-photo records were not mutated.

## Limits

No real process-kill/restart integration, physical browser, MapLibre paint inspection, screen reader, or assistive-technology run was performed. The documented single-app-worker assumption remains; multi-worker support is excluded. Heartbeat recovery relies on the local platform `ps` command after staleness; inability to inspect a stale owner fails closed rather than permitting another refresh.
