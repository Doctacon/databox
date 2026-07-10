Status: done
Created: 2026-07-10
Updated: 2026-07-10
Parent: None
Depends-On: None

# Repair source VCR idempotency and schema snapshot suite

## Scope

Restore hermetic full-suite behavior for the source VCR/idempotency/schema-snapshot tests. The exact failing node list is order-dependent; observed examples have included eBird/NOAA/USGS idempotency and schema nodes, while the same nodes can pass alone.

Independent review proved the defect predates AVONET: the current suite, a suite excluding every new AVONET test, and an isolated unmodified `HEAD` archive each failed different subsets with cross-source cassette leakage. AVONET changes may alter which secondary node exposes the shared ordering/state leak, so this ticket owns the systemic source-suite isolation contract rather than a fixed original four-node list. Repair only that proven test/source contract.

## Acceptance criteria

- All source VCR/idempotency/schema-snapshot tests pass hermetically together and alone with network recording disabled, regardless of collection order.
- Source idempotency assertions retain their protective meaning.
- Schema snapshots describe only the resources owned by each test.
- The full Python suite passes without recording new live responses.

## Explicit exclusions

- No AVONET source behavior, live warehouse mutation, or broad source refactor.

## Evidence expectations

Record reproduction, root cause, focused/full-suite commands, and cassette/snapshot diff review.

## Progress and notes

- 2026-07-10: Initial AVONET validation produced 283 passes and four source-node/cassette/snapshot failures while every AVONET test passed. Independent review then proved the exact failing node list is order-dependent: current full suite 285/2 failed, suite excluding all new AVONET tests 259/1 failed, and isolated unmodified `HEAD` 256/2 failed with cross-source cassette leakage. The defect therefore predates AVONET and is systemic. Evidence is summarized in `.10x/evidence/2026-07-10-avonet-bird-traits-source.md`.
- 2026-07-10: Reproduced USGS requests routed through a prior NOAA cassette under network-disabled full-suite execution. Root cause was dlt's shared module-level HTTP adapter retaining cassette-bound urllib3 pools across tests; import-time asynchronous telemetry could also bind unrelated sessions to an active cassette.
- 2026-07-10: Added import-time test telemetry disablement and a fresh dlt HTTP client per VCR test, preserving the real dlt retry/session behavior while isolating pools. Corrected the stale AVONET ontology assertion to the checked-in normalized-scientific-name/two-table contract without changing AVONET runtime behavior.
- 2026-07-10: Each of the six eBird/NOAA/USGS idempotency/schema nodes passed in its own process; mixed-order nodes passed 6/6; all source tests passed 43/43; and the full network-disabled Python suite passed 307/307 at 85.94% coverage. Cassette hashes remained unchanged. Evidence: `.10x/evidence/2026-07-10-source-vcr-schema-suite-isolation.md`.
- 2026-07-10: Independent review passed with no blocker or significant finding. Review: `.10x/reviews/2026-07-10-source-vcr-schema-suite-isolation-review.md`.
- 2026-07-10: Retrospective extracted the reusable dlt/vcrpy adapter-pool and import-time telemetry isolation convention into `.10x/knowledge/dlt-vcr-http-client-isolation.md`; no follow-up ticket is required for the accepted sequential pytest contract.

## Blockers

None.
