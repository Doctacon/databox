Status: recorded
Created: 2026-07-12
Updated: 2026-07-12
Relates-To: .10x/tickets/done/2026-07-12-close-refresh-recovery-edge-cases.md, .10x/tickets/done/2026-07-11-verify-map-wheel-and-refresh-controls.md

# Refresh recovery edge-case closure

## What was observed

- A new `databox.source_refresh_gate` waits for an exact run-ID handshake before starting the established orchestration. The runner atomically publishes its own PID plus the gate/process-group PID before sending that handshake. If the runner dies before publication/handshake, EOF prevents mutation; after publication, stale recovery verifies the exact gate/run identity, terminates the process group, waits for disappearance, and only then releases ownership. Inspection uncertainty remains fail closed.
- A bounded local hard-exit test launched a real runner-harness/gate process tree with a fake `time.sleep` child, used `os._exit` to simulate abrupt runner death, proved the fake mutation began only after durable publication, and proved GET terminated the orphan before a retry could launch. No provider, Quack, DuckDB, or SQLMesh process ran. No stale fake process remained after tests.
- Backend status validation now requires exact canonical ordered source rows, strict source states, run ID grammar, timezone-aware timestamps, bounded one-line safe messages, safe Rufous log basenames, and state/finish/source coherence. Adversarial tests reject empty/reordered/duplicate sources, invalid time/run ID, oversized messages, unsafe paths, and incoherent success. Runner `all()` predicates therefore receive only validated canonical rows.
- Recovery re-reads the same run after process inspection before publishing failure, preserving a concurrent terminal success. A different-run owner is never released and blocks launch.
- Frontend progress accepts 1–16 unique bounded server-owned names instead of freezing six identities/cardinality. Confirmation names the exact current server-provided sources and launch stays disabled while status is unknown.
- Both exact-six success and failure paths start from API-derived arguments, feed output from the real `execute_parallel_refresh` seam through the durable runner, assert one Quack server plus maintenance order, and prove SQLMesh occurs only after successful maintenance.
- Search, sort, filter, and reset now reset and recenter the first wheel option; reduced-motion tests prove `behavior: auto` while ARIA active/selected state remains synchronized.
- The restored parent ticket remained nonempty: 3,136 bytes, SHA-256 `bbff1853ba806d8196b9eccb3f3ef7107cf3db0e645bffedca85af5156665969` before final record updates.

## Procedure and results

- Focused refresh/API/runner/orchestration: 27 passed.
- Full Python: 726 passed, three snapshots passed, 86.30% coverage.
- Focused frontend refresh/wheel: 36 passed.
- Full frontend: 18 files, 273 tests passed; production build and bundle audit passed. Vite emitted only the existing large MapLibre chunk advisory.
- Ruff check and format: all passed; 160 files formatted.
- MyPy: 98 source files passed, with one existing unchecked-body informational note.
- TypeScript: passed without diagnostics.
- Secret scan, `git diff --check`, and no-staged-file check passed.

## Side-effect limits

No live provider request, routine refresh, real Quack server, project DuckDB/SQLMesh mutation, AVONET/media refresh, model call, email, or image/binary request occurred. The hard-kill test used only temporary files and a bounded fake sleep process; process inspection afterward found no matching stale fake gate/harness.

## Limits

No real provider-backed hard kill, multi-worker server, physical browser, MapLibre paint inspection, screen reader, or assistive-technology session was performed. Stale recovery depends on the local `ps` command and process-group signaling; inspection or termination uncertainty deliberately keeps ownership locked.
