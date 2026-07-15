Status: recorded
Created: 2026-07-15
Updated: 2026-07-15
Relates-To: .10x/tickets/done/2026-07-12-verify-unified-source-contract-and-ci.md, .10x/tickets/done/2026-07-12-unify-dlt-source-contract-and-ci.md, .10x/specs/canonical-dlt-source-registry.md, .10x/specs/registry-derived-source-verification.md

# Unified source contract and CI final aggregate verification

## Verdict

**All final local implementation and verification gates pass after the completed enforcement repair. Independent closure architecture, correctness, and privacy/source reviews pass.**

This clean rerun includes the canonical name-pattern and retired-authority checker/matrix repairs closed under `.10x/tickets/done/2026-07-15-repair-source-contract-enforcement.md`. Privacy-owned implementation did not change after the passing review `.10x/reviews/2026-07-15-unified-source-contract-final-privacy-security-source-review.md`; complete privacy/hash checks were nevertheless rerun and remain passing.

No implementation was changed under this verification ticket. Closure reviews: `.10x/reviews/2026-07-15-unified-source-contract-closure-architecture-review.md`, `.10x/reviews/2026-07-15-unified-source-contract-closure-correctness-review.md`, and `.10x/reviews/2026-07-15-unified-source-contract-final-privacy-security-source-review.md`.

## Procedure and results

Complete command logs are retained under `/tmp/source-contract-final2/` as ephemeral supporting output.

### Full Python suite and aggregate coverage

Command:

`RUNTIME__DLTHUB_TELEMETRY=false SQLMESH__DISABLE_ANONYMIZED_ANALYTICS=true CONFIDENT_OPEN_BROWSER=false DEEPEVAL_TELEMETRY_OPT_OUT=true XENO_CANTO_API_KEY=test-token-for-vcr-replay EBIRD_API_TOKEN=test-token-for-vcr-replay NOAA_API_TOKEN=test-token-for-vcr-replay .venv/bin/pytest`

Result: **871 passed**, 28 warnings, seven snapshots passed, **87.82% coverage** against the 70% gate in 112.38 seconds. The increase from the prior 844 count is the added legacy-path/import and shared-name-pattern regression coverage. Log: `/tmp/source-contract-final2/full-pytest.txt`.

### Complete source profiles, offline

Command:

`XENO_CANTO_API_KEY=test-token-for-vcr-replay EBIRD_API_TOKEN=test-token-for-vcr-replay NOAA_API_TOKEN=test-token-for-vcr-replay RUNTIME__DLTHUB_TELEMETRY=false .venv/bin/pytest --no-cov -q packages/databox-sources/tests --record-mode=none --block-network`

Result: **60 passed**, 11 warnings, seven snapshots passed. Recording was disabled and network was blocked. Log: `/tmp/source-contract-final2/offline-source-profiles.txt`.

Registry-derived isolated execution used a temporary coverage file:

`COVERAGE_FILE=/tmp/source-contract-final2/isolated-coverage ... .venv/bin/python scripts/source_ci.py coverage`

Result: one shared harness process plus seven isolated source processes passed **60 tests total**: shared 4, AVONET 27, eBird 4, GBIF 6, NOAA 4, USGS 4, USGS Earthquakes 4, and Xeno-canto 7. Every subprocess used recording-disabled/network-blocked pytest options. Coverage emitted expected no-data/module warnings for processes that only exercise the shared sanitization harness; test execution passed. Log: `/tmp/source-contract-final2/isolated-source-coverage.txt`.

### Final checker, matrix, scaffold, builder, Quack, and refresh suite

Command:

`.venv/bin/pytest --no-cov -q tests/test_check_source_layout.py tests/test_source_ci.py tests/test_new_source.py tests/test_source_builders.py tests/test_source_registry.py tests/test_quack_destinations.py tests/test_parallel_refresh.py tests/test_avonet_orchestration.py packages/databox-sources/tests/usgs_earthquakes --record-mode=none --block-network`

Result: **145 passed**, 13 warnings, one snapshot passed. This includes:

- every canonical registry/domain/profile/resource/builder/export/schedule invariant;
- all eight exact retired authority paths and all four retired modules across full, direct, parent-child, and relative import forms;
- checker and matrix fail-closed behavior for legacy reintroduction;
- shared canonical source-name validation and malformed scaffold-name rejection;
- all seven builder resource/default contracts;
- exact 14-relation Quack/parallel-registry membership parity with key values still Quack-owned;
- scaffold fail-until-complete behavior, refresh inspection without execution, AVONET isolation, and canonical USGS Earthquakes profile construction.

Log: `/tmp/source-contract-final2/focused-contract.txt`.

### Registry, Dagster, workflow, and authority inventory

Commands:

- `.venv/bin/python scripts/check_source_layout.py`
- `.venv/bin/python scripts/source_ci.py matrix --pretty`
- `.venv/bin/dg check defs --use-active-venv`
- bounded Python/YAML inventory inspection

Results:

- checker: **7 ok, 0 incomplete, 0 failing, 0 registry errors**;
- deterministic matrix: AVONET `file_snapshot` plus six HTTP sources;
- exact source set: AVONET, eBird, GBIF, NOAA, USGS, USGS Earthquakes, and Xeno-canto;
- six scheduled and six shared-parallel sources, both excluding AVONET; NOAA remains the single analytics anchor;
- every domain exposes one asset collection/ingest job and schedule exports agree with registry flags;
- Dagster definitions loaded successfully with no explicit source-domain list;
- workflow parsed with **12 jobs** and **24/24 action uses pinned to 40-character commit SHAs**;
- matrix remains generated and consumed through `fromJSON`; no legacy per-source workflow authority was restored.

Dagster definition loading emitted normal SQLMesh adapter construction metadata but ran no SQLMesh command/materialization/query. Log: `/tmp/source-contract-final2/contract-defs-workflow.txt`.

### Static, code generation, docs, and secrets

- `.venv/bin/ruff check .` — passed.
- `.venv/bin/ruff format --check .` — **177 files already formatted**.
- `MYPYPATH=packages/databox:packages/databox-sources .venv/bin/mypy packages/` — success for **110 source files**; one informational untyped-fixture note.
- `.venv/bin/python scripts/generate_staging.py --check` — passed.
- `.venv/bin/python scripts/generate_platform_health.py --check` — passed.
- `.venv/bin/python scripts/generate_docs.py --check` — **20 files in sync**.
- `.venv/bin/mkdocs build --strict` — passed; only ignored `site/` output plus informational upstream/nav messages.
- `.venv/bin/python scripts/check_secrets.py .` — passed.

Logs: `/tmp/source-contract-final2/static.txt` and `/tmp/source-contract-final2/codegen-docs-integrity.txt`.

### Complete fixture integrity and privacy inventory

The manifest contains exactly **31 unique tracked artifacts**: 24 HTTP cassettes and seven schema snapshots. `shasum -a 256 -c .10x/evidence/.storage/2026-07-14-source-contract-fixture-sha256.txt` passed 31/31 after every test command.

A structured parse covered **24 cassettes and 44 interactions** and found:

- zero exact configured replay-credential matches;
- zero request-cookie, response-cookie, or PHP session artifacts;
- zero unnecessary named personal response fields;
- zero resolvable GBIF occurrence links;
- 50 private eBird row occurrences conforming to the required non-resolvable placeholder/name/coordinate contract;
- zero private-placeholder violations.

Log: `/tmp/source-contract-final2/privacy-scan.txt`.

### Protected state, diff, and staging

Before and after the complete rerun:

- AVONET manifest SHA-256: `2995f2e8a37caa7ca2014bdc1acbd75d2b8a7a7067c89a380a8c910a3ad3bf97`;
- fixture manifest SHA-256: `e1fc8e745e12692136e3d185b81f637ed98b1431b0cee9641ca276878f5b91de`;
- shared warehouse SHA-256: `de4562f0ea5820f3c0a562e538ba32a2841b57709efebe059480099d80f74bb4`.

All three remained byte-identical. `git diff --check` passed and `git diff --cached --name-only` remained empty. Log: `/tmp/source-contract-final2/final-integrity.txt`.

## Criterion mapping

### Canonical dlt source registry

- One seven-source canonical Python authority, unique identity/profile/raw inventory, schedule/parallel/anchor flags, shared name rule, singular builders/defaults, canonical Dagster export shapes, and bidirectional drift rejection: supported by 145 focused tests and live 7/7 checker/matrix.
- Registry-derived Dagster and CI composition without a manual active-source list: supported by Definitions loading, inventory inspection, matrix output, workflow parsing, and checker/matrix tests.
- Legacy generic authority remains retired and cannot be reintroduced through the exact retired files/templates or ordinary static import forms without checker/matrix failure: supported by the final enforcement tests/review and 145-test replay.
- Shared Quack/process behavior remains registry-derived: supported by six-source eligibility inspection, orchestration tests, and exact 14-relation dedupe-membership parity; no refresh was run.
- AVONET remains specialized, unscheduled, atomic, and pinned: supported by 27 isolated tests and unchanged manifest hash.
- Raw inventory/generated SQL/docs remain coherent: supported by registry tests and all codegen/docs drift checks.

### Registry-derived source verification

- Six HTTP profiles and one AVONET file-snapshot profile satisfy resource/schema/smoke/idempotency and builder/staged-publication contracts: supported by 60 complete offline tests, seven snapshots, 145 focused tests, and isolated shared-plus-seven execution.
- Routine verification is offline and isolated: supported by recording-disabled/network-blocked source commands and registry-derived subprocess construction.
- CI matrix/routing/omission/future-entry/incomplete-artifact/legacy-reintroduction behavior is registry-derived and fail-closed: supported by deterministic output, workflow inventory, and adversarial checker/matrix tests.
- Aggregate coverage includes all source suites: supported by **871 passing tests at 87.82%** plus the isolated source execution.
- Fixture integrity/privacy covers the complete tracked inventory: supported by 31/31 hashes and structured 24-cassette/44-interaction scanning.

## Side-effect boundary and limits

- No provider capture/request, source refresh, live Dagster source job, `task verify`, SQLMesh command/apply, shared-warehouse query/write, model call, email, staging action, or product runtime action was performed.
- Full/profile tests used mocks, cassettes, memory destinations, or temporary files. Source replay was recording-disabled/network-blocked. AVONET staged-publication tests used generated local workbooks and temporary DuckDB files.
- Dagster definition loading created adapter metadata for the configured warehouse path but did not issue a query/materialization; the warehouse remained byte-identical.
- MkDocs wrote only ignored `site/`; isolated coverage wrote only under `/tmp/source-contract-final2/`.
- Hosted GitHub expression evaluation, `dorny/paths-filter` event behavior, matrix-output transport, and runner provisioning remain unproven until a real Actions run.
- Static legacy-import enforcement intentionally does not analyze dynamic import strings; exact retired local authority paths are independently rejected.
- Provider fixtures prove captured shapes/offline behavior, not future provider availability/schema. Historical warehouses may lack newly inventoried tables until a future separately authorized normal refresh.
- Final review/retrospective/closure reconciliation remains with the parent orchestrator.
