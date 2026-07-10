Status: recorded
Created: 2026-07-10
Updated: 2026-07-10
Relates-To: .10x/tickets/done/2026-07-10-repair-source-vcr-and-schema-snapshot-suite.md

# Source VCR and schema-suite isolation repair

## What was observed

A network-disabled full-suite reproduction failed with two distinct test-harness defects:

1. `test_usgs_daily_values_idempotent` attempted to replay a USGS request from NOAA's smoke-test cassette. dlt's module-level requests client shares one `HTTPAdapter` across its thread-local sessions. urllib3 pools created while vcrpy is patched retain cassette-bound VCR connection classes; reusing that adapter can therefore carry an earlier test's cassette into a later source.
2. SQLMesh's import-time asynchronous analytics collector attempted to flush through the final USGS cassette after pytest finished. dlt telemetry has the same import-time risk. Fixture-time environment changes occur too late to guarantee those collectors were never initialized.

The full suite also exposed a stale AVONET schema-artifact assertion: the checked-in ontology now correctly uses `normalized_scientific_name` across raw and modeled trait tables, while the test still expected the earlier raw-only `avibase_id`/single-table shape. Updating that assertion changes no AVONET runtime behavior or artifacts.

## Repair

- Repository pytest bootstrap disables dlt and SQLMesh analytics before test modules import either library.
- Every VCR-marked source test receives a fresh public dlt `Client`, including a fresh adapter/pool, with all module-level request methods rebound for that test and the session closed at teardown.
- The AVONET schema-artifact assertion now protects the checked-in two-table ontology and governed normalized-scientific-name conformance.
- No source implementation, cassette, snapshot, or live warehouse was changed.

## Procedure and results

### Reproduction before repair

```text
uv run --no-sync pytest --no-cov -q --record-mode=none --block-network
305 passed, 2 failed
- AVONET ontology assertion expected avibase_id but artifact contained normalized_scientific_name
- USGS idempotency request was routed to NOAA smoke cassette
```

The cassette-tree SHA-256 aggregate was unchanged:

```text
dfb052e422991a00c56b9fc38b5f41a50345a8645f8702838ebfd32ab7f48aa3
```

### Varied source order

```text
uv run --no-sync pytest --no-cov -q --record-mode=none --block-network \
  packages/databox-sources/tests/usgs/test_schema.py \
  packages/databox-sources/tests/noaa/test_idempotency.py \
  packages/databox-sources/tests/ebird/test_schema.py \
  packages/databox-sources/tests/usgs/test_idempotency.py \
  packages/databox-sources/tests/noaa/test_schema.py \
  packages/databox-sources/tests/ebird/test_idempotency.py
6 passed; 3 snapshots passed
```

### Isolated nodes and complete source suite

Each eBird, NOAA, and USGS idempotency/schema node was also run in its own pytest process with `--record-mode=none --block-network`: all six passed individually and all three snapshots passed.

```text
uv run --no-sync pytest --no-cov -q packages/databox-sources/tests \
  --record-mode=none --block-network
43 passed; 3 snapshots passed
```

### Full Python suite with coverage

```text
uv run --no-sync pytest -q --record-mode=none --block-network
307 passed; 3 snapshots passed; coverage 85.94%
```

All three post-repair runs left the cassette aggregate unchanged at `dfb052e422991a00c56b9fc38b5f41a50345a8645f8702838ebfd32ab7f48aa3`. No live response was recorded. The final run emitted no post-session telemetry/VCR error.

### Static and repository gates

```text
uv run --no-sync ruff check conftest.py packages/databox-sources/tests/conftest.py tests/test_avonet_orchestration.py
uv run --no-sync ruff format --check conftest.py packages/databox-sources/tests/conftest.py tests/test_avonet_orchestration.py
.venv/bin/mypy packages/
.venv/bin/pre-commit run --files conftest.py packages/databox-sources/tests/conftest.py tests/test_avonet_orchestration.py
git diff --check
all passed
```

## What this supports

- Source VCR/idempotency/schema tests are isolated from prior cassette-bound HTTP pools.
- Source idempotency tests still execute their real two-run merge and primary-key assertions.
- Schema snapshots and ontology assertions remain protective and resource/entity-specific.
- The entire Python suite passes with recording disabled and unchanged committed cassettes.

## Limits

- Validation covered isolated processes, the repository's current sequential pytest execution, and an explicit mixed source order; it did not run pytest-xdist.
- Independent review passed and is recorded at `.10x/reviews/2026-07-10-source-vcr-schema-suite-isolation-review.md`.
