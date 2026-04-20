---
id: packet:source-test-harness-iter1
kind: packet
status: active
created_at: 2026-04-20T00:00:00Z
updated_at: 2026-04-20T00:00:00Z
target_ticket: ticket:source-test-harness
style: snapshot-first
scope:
  kind: workspace
links:
  ticket: ticket:source-test-harness
  initiative: initiative:staff-portfolio-readiness
  plan: plan:staff-portfolio-readiness
---

# Mission

Stand up a pytest test harness for `packages/databox-sources` covering all three dlt sources (eBird, NOAA, USGS). Every source gets: one unit test against a VCR cassette, one dlt schema snapshot, one in-memory DuckDB smoke test. CI job `pytest` in `.github/workflows/ci.yaml` gets its exit-5 tolerance removed once tests land. Evidence includes a deliberate schema-drift failure showing clean diff output.

# Bound Context

Governing chain:

- constitution: `/Users/crlough/Code/personal/databox/.loom/constitution/constitution.md`
- initiative: `/Users/crlough/Code/personal/databox/.loom/initiatives/20260420-staff-portfolio-readiness.md`
- plan: `/Users/crlough/Code/personal/databox/.loom/plans/20260420-staff-portfolio-readiness.md`
- ticket: `/Users/crlough/Code/personal/databox/.loom/tickets/20260420-fcj2gpg6-source-test-harness.md`

Phase 1 reliability ticket 2/3. CI exists (`ticket:ci-github-actions` shipped). `ticket:observability-pass` is sibling; ticket:schema-contract-ci (Phase 2) rides on this test infrastructure.

# Source Snapshot

## Source package layout

```
packages/databox-sources/
├── pyproject.toml              # dependencies only; no test config yet
├── databox_sources/
│   ├── __init__.py
│   ├── base.py                 # PipelineSource protocol
│   ├── registry.py             # auto-discovery
│   ├── ebird/
│   │   ├── source.py           # 7 @dlt.resource definitions
│   │   └── config.yaml
│   ├── noaa/
│   │   ├── source.py           # 3 @dlt.resource definitions
│   │   └── config.yaml
│   └── usgs/
│       ├── source.py           # 2 @dlt.resource definitions
│       └── config.yaml
```

No `tests/` directory currently exists inside `packages/databox-sources/`.

## Dev deps already available (root pyproject)

`pytest>=8.0`, `pytest-cov>=5.0`, `pytest-mock>=3.14`, `faker>=30.0`, `responses>=0.25`.

Missing: `pytest-recording` (vcrpy wrapper). Must add.

## HTTP client

All three sources call `from dlt.sources.helpers import requests as dlt_requests`. Underlying is the `requests` library, which urllib3 backs. VCR intercepts urllib3, so `@pytest.mark.vcr` will capture these calls without any source-code changes.

## Auth

- **eBird**: `EBIRD_API_TOKEN` → header `X-eBirdApiToken` (confirm in source)
- **NOAA**: `NOAA_API_TOKEN` → header `token`
- **USGS**: no auth required

Both tokens already live in `.env` (recorded from prior work; check `.env` before re-recording).

## Resources per source (for smoke-test expectations)

- ebird: `recent_observations`, `notable_observations`, `species_list`, `hotspots`, `taxonomy`, `region_stats` (6 that ship via `ebird_source()`; confirm list by reading `@dlt.source` return)
- noaa: `daily_weather`, `stations`, `datasets`
- usgs: `daily_values`, `sites`

## CI surface

`.github/workflows/ci.yaml` `tests` job currently tolerates pytest exit 5. Remove that tolerance once tests land. File path:

```yaml
- name: pytest
  run: |
    set +e
    uv run pytest
    code=$?
    if [ "$code" -eq 5 ]; then
      echo "::warning::pytest collected zero tests — source-test-harness ticket pending."
      exit 0
    fi
    exit $code
```

Replace with a plain `uv run pytest`.

## Existing pytest config (root pyproject)

```toml
[tool.pytest.ini_options]
testpaths = ["tests"]
python_files = ["test_*.py"]
```

`testpaths = ["tests"]` is workspace-root-relative and too narrow. Add `"packages"` so tests under `packages/databox-sources/tests/` discover. Or use `rootdir`/conftest auto-discovery. Worker picks the cleanest path.

# Task For This Iteration

Produce:

1. **Tooling**
   - Add `pytest-recording>=0.13` to root `[dependency-groups].dev` in `/Users/crlough/Code/personal/databox/pyproject.toml`.
   - Extend `[tool.pytest.ini_options].testpaths` to cover `packages/` tests. Do not break any tests discovery the root path already owned.
   - `uv sync --all-extras --dev` to install.

2. **Test layout**
   - Create `packages/databox-sources/tests/` with subdirs `ebird/`, `noaa/`, `usgs/`, plus shared `conftest.py`.
   - `conftest.py` provides `vcr_config` fixture: `filter_headers=['authorization', 'x-ebirdapitoken', 'token', 'x-api-key']`, `filter_query_parameters=['token', 'api_key']`, `record_mode='none'` (CI replay-only).
   - Cassette dir convention: `packages/databox-sources/tests/<source>/cassettes/`.

3. **Per-source test suite (×3 sources)**
   - `test_resources.py` — one representative `@dlt.resource` unit test per source:
     - ebird: `recent_observations` (region="US-AZ", small `back` value for fast cassette)
     - noaa: `daily_weather` (1 station, 1 day window)
     - usgs: `daily_values` (1 site, 1 day window)
     - Assert: row count > 0, required keys present, types match expected (lat/lng float, dates ISO).
   - `test_schema.py` — pipeline load + schema snapshot diff:
     - `dlt.pipeline(destination=duckdb(":memory:"), dataset_name="main").run(source(...))`
     - Serialize `pipeline.default_schema.to_pretty_yaml()` (strip non-deterministic fields: `version_hash`, `previous_hashes`, `engine_version`, timestamps, `_dlt_load_id` col stats).
     - Compare against `tests/<source>/snapshots/<source>_schema.yaml`. First run writes; subsequent runs diff.
     - Worker chooses: `syrupy` (pytest-snapshot lib, already common) vs hand-rolled golden-file diff. Ticket prefers `syrupy`.
   - `test_smoke.py` — full pipeline run into `:memory:` DuckDB:
     - Load every resource the `@dlt.source` exposes via `pipeline.run(source(...))`.
     - Assert load info reports 0 errors and row_counts > 0 for expected tables.

4. **Cassette recording (one-time live)**
   - Execute `uv run pytest packages/databox-sources --record-mode=once` with live tokens from `.env`.
   - Verify cassettes under `tests/<source>/cassettes/` contain no secrets. Grep for token values:
     - `grep -r "$(grep EBIRD_API_TOKEN .env | cut -d= -f2 | tr -d '"')" packages/databox-sources/tests/cassettes/ || echo clean`
     - Same for NOAA.
   - If a token leaks into a response body (e.g. API echoes it), add `before_record_response` callable that strips it. Document the choice.
   - Commit cassettes. Size budget: 100KB total across all sources; flag if larger.

5. **Documentation**
   - Create `packages/databox-sources/README.md` (or extend if it exists) with:
     - How to add a new source test
     - How to re-record cassettes: `uv run pytest packages/databox-sources/tests/<source> --record-mode=rewrite`
     - How schema snapshots work and how to regenerate: `--snapshot-update` (syrupy) or equivalent.

6. **CI wire-up**
   - Edit `.github/workflows/ci.yaml` `tests` job: replace the bash exit-5 guard with `uv run pytest`.
   - Confirm job works with no env tokens (cassettes are replay-only by virtue of `record_mode='none'`).

7. **Schema-drift evidence**
   - After tests pass, simulate drift: add a bogus column to the `columns=` hint in one resource (ebird `recent_observations`), re-run the schema test, capture the failing diff.
   - Revert the drift. Paste the captured diff to `.loom/evidence/20260420-schema-drift-proof.md`.

# Stop Conditions

Stop and mark `continue` when:

- All 9 tests (3 unit + 3 schema + 3 smoke) pass locally with cassettes and no network.
- Cassettes contain no secrets (verified via grep).
- CI `tests` job is hard-fail (no exit-5 tolerance).
- Schema-drift evidence captured in `.loom/evidence/`.
- Ticket updated with work log.

Stop and mark `blocked` if:

- VCR cannot intercept `dlt.sources.helpers.requests` — verify this early with a tiny smoke cassette before writing full suite. If blocked, fall back to `responses` library (already in dev deps) and document why.
- A source's live API returns errors during recording that aren't a test problem (quota, outage). Capture the error, retry once, then mark `blocked` if persistent.
- Schema snapshot serialization is non-deterministic even after stripping known noise — capture the noisy fields and recommend a follow-up ticket.

Escalate if the worker discovers that one or more sources is fundamentally not testable as written (e.g., hardcoded global state that prevents a fresh `dlt.pipeline(":memory:")` run). That's a structural issue beyond this ticket.

# Output Contract

The child must return:

- `outcome`: one of `continue` | `stop` | `blocked` | `escalate`
- Files created or modified, absolute paths
- Commands run + trimmed output (pytest summary, cassette sizes, drift diff)
- Cassette secret-scan results (grep output, `clean` or hits)
- Any deviations from this packet and why
- Residual risks or follow-ups
- Recommended ticket state

Do not close the ticket. Parent reconciles.

# Allowed Writes

- `/Users/crlough/Code/personal/databox/pyproject.toml` (dev deps + testpaths only)
- `/Users/crlough/Code/personal/databox/packages/databox-sources/tests/**` (new)
- `/Users/crlough/Code/personal/databox/packages/databox-sources/README.md` (new or extend)
- `/Users/crlough/Code/personal/databox/.github/workflows/ci.yaml` (tests job only)
- `/Users/crlough/Code/personal/databox/.loom/tickets/20260420-fcj2gpg6-source-test-harness.md` (status + work log)
- `/Users/crlough/Code/personal/databox/.loom/evidence/20260420-schema-drift-proof.md` (new)
- `/Users/crlough/Code/personal/databox/uv.lock` (regenerated via uv sync)

Do not touch:

- `packages/databox-sources/databox_sources/**` source code (except the temporary drift perturbation in the evidence step, which must be reverted)
- `packages/databox-config/**`
- `packages/databox-orchestration/**`
- `packages/databox-quality/**`
- `transforms/**`
- `soda/**`
- `.pre-commit-config.yaml`
- `Taskfile.yaml`
- `.env` (read-only; do not commit its contents)

# Working Notes

- VCR cassettes default to YAML. Confirm. Not JSON.
- `pytest-recording` flags:
  - `--record-mode=none` — replay only, fail on new requests (CI default)
  - `--record-mode=once` — record if no cassette, else replay (first-time recording)
  - `--record-mode=rewrite` — always re-record (use when API changed)
- Use **small** query windows during recording to keep cassettes tight:
  - noaa: `startdate=2026-04-10&enddate=2026-04-11` one station
  - usgs: `startDT=2026-04-10&endDT=2026-04-11` one site
  - ebird: `back=1&maxResults=50`
- Deterministic schema snapshots: dlt writes `version_hash`, `engine_version`, `generated_at` into schema YAML. Strip before diff. Strategy: load YAML, delete known noisy keys, reserialize. See `dlt.Schema.to_pretty_yaml()` docstring.
- Syrupy: `pytest --snapshot-update` regenerates. Default extension is amber (pickle); use `YAMLSnapshotExtension` or just string-compare.
- Cassettes should commit to git but be flagged `-text` in `.gitattributes` if they cause diff noise (optional; worker picks).
- Root pytest `testpaths = ["tests"]` must be extended. Safest: `testpaths = ["tests", "packages"]`. Confirm this doesn't sweep any `site-packages`-like dir.

# Child Output

<!-- populated by worker -->

# Parent Merge Notes

<!-- populated by parent after reconcile -->
