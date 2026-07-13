Status: recorded
Created: 2026-07-12
Updated: 2026-07-12
Relates-To: .10x/tickets/done/2026-07-12-require-empty-group-on-normal-exit.md, .10x/tickets/done/2026-07-11-verify-map-wheel-and-refresh-controls.md

# Normal-exit process-group proof

## What was observed

- After every ordinary gate exit, whether return code is zero or nonzero, the durable runner now directly probes the isolated process group. If the group still exists or inspection is uncertain, it runs the existing TERM/KILL whole-group cleanup and releases ownership only when group absence is proven.
- A real bounded POSIX regression created a new-session leader that spawned a descendant which installed `SIGTERM` ignore, published readiness, and then outlived the leader. With the leader gone and the PGID still present, GET left the run active, POST returned conflict, and ownership remained. Test cleanup sent group `SIGKILL`, waited for `killpg(pgid, 0)` to prove absence, and verified no matching process remained.
- Parameterized runner regressions cover ordinary zero and nonzero gate exits with an unproven surviving group; both invoke cleanup and retain ownership when cleanup cannot prove absence.
- Moved proof-ticket references now use `.10x/tickets/done/2026-07-12-prove-process-group-and-terminal-cas.md`; parent and verification graphs include this final proof child.

## Reopened unexpected-exception proof

- Post-launch ownership now defaults to retained. Normal exit sets release safety only after direct PGID absence or successful whole-group cleanup.
- An outer `BaseException` cleanup guard covers every unexpected post-launch exit. It proves cleanup before release and re-raises `KeyboardInterrupt`, `SystemExit`, and other unexpected failures rather than swallowing them.
- A `ValueError` injected after `SOURCE_START` proved cleanup was called and ownership remained when group cleanup returned uncertain. Parameterized `KeyboardInterrupt` and `SystemExit` regressions proved cleanup ran, ownership released only after proven cleanup, and each interrupt propagated.

## Procedure and results

- `PYTHONDONTWRITEBYTECODE=1 PYTEST_ADDOPTS='--no-cov' .venv/bin/pytest -q -p no:cacheprovider tests/test_source_refresh_api.py tests/test_source_refresh_runner.py tests/test_parallel_refresh.py` — final reopened run: 37 passed.
- Process inspection after the focused suite found no `descendant-ready`, `source_refresh_gate`, or test `time.sleep(30)` process.
- The real leader-gone/SIGTERM-ignoring-descendant test was repeated 3/3 successfully; post-repeat inspection again found no matching process.
- Ruff check and format passed for runner and focused test files.
- MyPy passed for `source_refresh_runner.py`.
- Secret scan, `git diff --check`, and no-staged-file check passed after the reopened repair.
- Parent ticket remained nonempty.

## Side-effect limits

No live provider request, routine refresh, Quack server, project DuckDB/SQLMesh mutation, frontend workflow, model call, email, AVONET/media refresh, or image/binary request ran. The real process test used only temporary Python processes/files and guaranteed cleanup in `finally`.

## Limits

The proof targets POSIX `killpg` semantics on the documented local macOS runtime. No provider-backed hard kill, multi-worker server, physical browser, screen reader, or assistive technology was exercised.
