Status: recorded
Created: 2026-07-10
Updated: 2026-07-10
Target: .10x/tickets/done/2026-07-10-repair-source-vcr-and-schema-snapshot-suite.md
Verdict: pass

# Source VCR and schema-suite isolation review

## Target

The test-harness isolation repair in repository pytest bootstrap, source-test fixtures, and the stale AVONET ontology assertion.

## Findings

- Test telemetry is disabled before test-module imports, preventing asynchronous dlt and SQLMesh collectors from binding to active VCR cassettes.
- Each VCR-marked source test receives a fresh public dlt client, adapter, pool, and rebound module-level request methods; teardown closes the session. Non-VCR tests and production behavior remain untouched.
- eBird, NOAA, and USGS idempotency assertions still execute two runs and retain row-count, primary-key, and non-empty protections.
- The AVONET assertion now matches and strengthens the checked-in two-table normalized-scientific-name ontology contract without changing runtime behavior.
- Tests ran with network blocking and recording disabled. Six affected nodes passed alone and in mixed order, all 43 source tests passed, and the full suite passed 307/307 with unchanged tracked cassettes and snapshots.
- The evidence's aggregate cassette hash procedure is not documented, but direct tracked-file diff verification establishes that no cassette or snapshot changed.

## Verdict

Pass. No blocker or significant finding remains.

## Residual risk

Parallel pytest-xdist execution was not exercised. The repository's accepted sequential, standalone, and varied-order contract is proven.
