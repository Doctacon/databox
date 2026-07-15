Status: recorded
Created: 2026-07-14
Updated: 2026-07-14
Target: .10x/tickets/done/2026-07-12-complete-source-contract-test-suites.md
Verdict: pass

# Source contract test-suite correctness review

## Target

Implementation and evidence for `.10x/tickets/done/2026-07-12-complete-source-contract-test-suites.md`.

## Findings

Initial review found two correctness blockers: bounded GBIF/Xeno suites bypassed canonical production builders, and AVONET profile tests did not invoke production staged publication. Both were repaired without provider calls.

- GBIF resource/schema/smoke/idempotency tests use `gbif._build_source(max_records=2)`; a focused builder test pins US/Arizona, Aves key 212, coordinate requirement, 1,000-record production default, and the sole bounded override.
- Xeno-canto profile tests use `xeno_canto._build_source(max_records=2, per_page=2)`; focused coverage pins the established query, 1,000-record production default, page size 100, and bounded overrides.
- AVONET profile coverage directly invokes production `avonet_staged_publish`, `quack_ingest_session`, `prepare_dlt_source`, and `avonet._build_source` against temporary local workbooks/DuckDB. It proves publication, atomic replacement, validation-failure preservation, staging removal, and Quack-client cleanup.
- Parent-observed offline replay passed 58 tests and seven snapshots with recording disabled and network blocked. Layout, Dagster definitions, Ruff, formatting, MyPy, hashes, and diff checks passed.

## Verdict

Pass. Profile suites exercise the intended production boundaries and satisfy resource, schema, smoke, idempotency, builder, and AVONET atomic-publication requirements.

## Residual risk

Fixtures prove captured provider shapes and local behavior, not future upstream availability/schema. AVONET intentionally uses generated bounded workbooks rather than the full pinned download.
