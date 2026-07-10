Status: open
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

## Blockers

None identified; requires separate execution authorization/ownership.
