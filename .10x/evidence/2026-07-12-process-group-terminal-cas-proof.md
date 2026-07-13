Status: recorded
Created: 2026-07-12
Updated: 2026-07-12
Relates-To: .10x/tickets/done/2026-07-12-prove-process-group-and-terminal-cas.md, .10x/tickets/done/2026-07-11-verify-map-wheel-and-refresh-controls.md

# Process-group cleanup and terminal CAS proof

## What was observed

- API recovery now checks process-group existence directly with `killpg(pgid, 0)`. A missing gate leader with a surviving process group is `unknown` and remains fail closed. A verified orphan receives group SIGTERM, then SIGKILL when needed, and ownership can release only after the entire group is proven absent. Inspection uncertainty never authorizes release.
- Runner caught-error cleanup now returns a proof result for whole-group disappearance. Its `finally` leaves durable ownership in place when group exit cannot be proven.
- Every durable status write uses a bounded cross-process `flock`. Recovery's same-run active-to-failed transition reads and conditionally writes under that lock. A deterministic threaded interleaving paused recovery at its failure write, queued terminal success behind the lock, and proved the terminal write wins without being overwritten.
- Connected exact-six success and failure tests now launch the API first, extract its ordered source arguments, and use those arguments to execute the real `execute_parallel_refresh` seam. Both then pass the resulting output through the durable runner. Success proves one Quack server and maintenance/inspection before SQLMesh; failure proves one server, cleanup/dedupe, and no inspection/SQLMesh.
- The restored parent remained nonempty at 3,686 bytes with SHA-256 `87eecbbced7edcc150c2e9c136c99a4f5646f58a4d7dc3b58309911c4480d903`.

## Procedure and results

- `PYTHONDONTWRITEBYTECODE=1 PYTEST_ADDOPTS='--no-cov' .venv/bin/pytest -q -p no:cacheprovider tests/test_source_refresh_api.py tests/test_source_refresh_runner.py tests/test_parallel_refresh.py` — 31 passed.
- `.venv/bin/ruff check packages/databox/databox/source_refresh_api.py packages/databox/databox/source_refresh_runner.py tests/test_source_refresh_api.py tests/test_source_refresh_runner.py` — passed.
- `.venv/bin/ruff format --check ...` — all four files formatted after one targeted format correction.
- `.venv/bin/mypy packages/databox/databox/source_refresh_api.py packages/databox/databox/source_refresh_runner.py` — no issues.
- `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python scripts/check_secrets.py .` — passed.
- `git diff --check` passed; `git diff --cached --name-only` was empty.

## Side-effect limits

No live provider request, routine refresh, Quack server, project DuckDB/SQLMesh mutation, model call, email, AVONET/media refresh, or image/binary request ran. Process-group behavior was tested with fakes and temporary bounded local processes only. No frontend file changed in this ticket.

## Limits

Process-group and lock behavior relies on POSIX `killpg`, `flock`, and the documented local single-user runtime. The tests do not run a provider-backed hard kill, multi-worker server, physical browser, MapLibre paint inspection, screen reader, or assistive technology.
