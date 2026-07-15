Status: recorded
Created: 2026-07-14
Updated: 2026-07-14
Relates-To: .10x/tickets/done/2026-07-12-complete-source-contract-test-suites.md, .10x/specs/registry-derived-source-verification.md

# Source contract test-suite completion evidence

## What was observed

All seven canonical sources satisfy the profile contract enforced by `scripts/check_source_layout.py`:

- HTTP profiles: eBird, GBIF, NOAA, USGS, USGS Earthquakes, and Xeno-canto each have resource, schema snapshot, in-memory smoke, and repeat-run/idempotency tests.
- File-snapshot profile: AVONET has pinned-manifest/resource, schema snapshot, bounded smoke, idempotency, and production staged-publication coverage using generated local workbooks and temporary DuckDB files only.

This work added the missing profile suites for AVONET, GBIF, Xeno-canto, and USGS Earthquakes. Existing eBird, NOAA, and USGS cassettes/snapshots were not re-recorded or modified.

## Canonical builder coverage

GBIF and Xeno-canto profile tests now construct every VCR/schema/smoke/idempotency source through the production domain `_build_source` contract. The builders retain their production defaults while accepting only bounded record/page overrides for tests:

- GBIF production: US/Arizona, Aves taxon key 212, coordinates required, 1,000 records; tests override only `max_records=2`.
- Xeno-canto production: the established United States/Arizona/birds query, 1,000 records, page size 100; tests override only `max_records=2` and `per_page=2`.

Focused mock-backed builder tests assert both the exact production literals and bounded override calls so those values cannot drift silently away from profile verification.

## AVONET production-path coverage

`packages/databox-sources/tests/avonet/test_staged_publish.py` invokes production `avonet_staged_publish`, `quack_ingest_session`, `prepare_dlt_source`, and `avonet._build_source` using only pytest temporary directories, local two-row/one-row workbooks, and temporary DuckDB files.

The test proves:

1. a two-row snapshot publishes;
2. a one-row replacement removes prior rows atomically;
3. a validation failure preserves the prior final snapshot;
4. staging schema and Quack client artifacts are cleaned after success and failure.

Existing broader core AVONET orchestration coverage remains unchanged.

## VCR privacy and credential hardening

The shared VCR harness now:

- creates/closes a fresh public dlt HTTP client for each VCR-marked test;
- injects a dummy Xeno-canto key when credentials are absent during replay;
- filters request `Cookie` and credential headers/query values;
- removes response `Set-Cookie` before persistence;
- redacts credential echoes;
- deterministically bounds GBIF, Xeno-canto, and USGS Earthquakes responses to two rows/features;
- removes GBIF/Xeno-canto observer/recordist, identifier, locality, catalog, remarks, device, and microphone metadata;
- replaces every retained GBIF `references` value with the non-resolvable shape-preserving placeholder `https://example.invalid/gbif-occurrence`.

Regression tests directly prove request-cookie configuration, response-session removal, credential redaction, personal-field removal, and the GBIF placeholder behavior.

Existing Xeno-canto cassette `PHPSESSID`/`Set-Cookie` values were removed offline. Existing GBIF cassette references were rewritten offline to the deterministic placeholder. No provider was contacted for these review repairs.

## Authorized live fixture capture

Only three user-authorized metadata endpoints were contacted during initial implementation:

| Provider | Endpoint | Per interaction bound | Live interactions |
|---|---|---|---:|
| GBIF | `https://api.gbif.org/v1/occurrence/search` | `limit=2`, `offset=0`; one page | 10 |
| Xeno-canto | `https://xeno-canto.org/api/3/recordings` | `per_page=2`, `page=1`; one page; key redacted | 10 |
| USGS Earthquakes | `https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/all_day.geojson` | one feed request; response bounded to two features | 10 |

Each provider had five interactions per capture pass: resource, schema, smoke, and two identical idempotency-run requests. Two bounded capture passes occurred. The first established functional fixtures/snapshots; inspection then found unnecessary public personal metadata, so a second provider-backed rewrite added deterministic response minimization. First-pass fixtures were overwritten, not retained. Independent-review repairs were offline only and did not add provider requests.

AVONET fixture/snapshot tests made no provider request or real AVONET download.

## Final fixture inspection

Final artifacts contain 12 provider cassettes, 15 interactions, and four new schema snapshots. A structured inspection verified:

- approved hosts only: GBIF, Xeno-canto, and USGS Earthquakes;
- GBIF requests use `limit=2`, `offset=0`;
- Xeno-canto requests use `per_page=2`, `page=1`, `key=REDACTED`;
- every response has at most two rows/features;
- zero exact local credential matches;
- zero request `Cookie` or response `Set-Cookie` headers;
- zero `PHPSESSID` values;
- zero retained unnecessary personal fields;
- all 10 retained GBIF reference fields equal the `.invalid` placeholder;
- zero resolvable `gbif.org/occurrence` references.

The reproducible per-artifact SHA-256 manifest is `.10x/evidence/.storage/2026-07-14-source-contract-fixture-sha256.txt`. Its updated SHA-256 is:

`45783afb0b07f2df16a368cc2ef421fb966ef284501be5849a8c630b6d238f04`

`shasum -a 256 -c` passed for all 16 listed cassette/snapshot artifacts.

## Offline verification

### Complete source package

Command used dummy replay credentials, recording disabled, and socket blocking:

`XENO_CANTO_API_KEY=test-token-for-vcr-replay EBIRD_API_TOKEN=test-token-for-vcr-replay NOAA_API_TOKEN=test-token-for-vcr-replay .venv/bin/pytest --no-cov -q packages/databox-sources/tests --record-mode=none --block-network`

Result: **58 passed**, with all seven schema snapshots passing.

Fixture/snapshot SHA-256 manifests generated immediately before and after were identical, proving offline replay did not rewrite tracked fixtures.

### Varied source order

Two recording-disabled/network-blocked runs executed six canonical-builder GBIF/Xeno-canto and USGS Earthquakes schema/smoke/idempotency nodes in forward and reverse mixed-source order.

Results: **6 passed** and **6 passed**.

### Static and contract checks

- `.venv/bin/python scripts/check_source_layout.py` — 7 ok, 0 skipped, 0 failing.
- Ruff check — passed for the source tests and changed GBIF/Xeno-canto domain builders.
- Ruff format check — 41 files formatted.
- MyPy — success for 41 source/test files.
- Focused canonical registry/parallel refresh/AVONET orchestration regression — 35 passed.
- `dg check defs --use-active-venv` — all definitions loaded successfully.
- Structured privacy scan — 12 cassettes, 15 interactions, 0 credential matches, 0 cookie/session headers, 0 unnecessary personal fields, 10 deterministic GBIF placeholders.
- `.venv/bin/python scripts/check_secrets.py` — no tracked-file findings; independent exact-value scan covered new untracked fixtures.
- `git diff --check` — passed.
- `git diff --cached --name-only` — empty; no files staged.

## What this supports

This supports every ticket criterion and resolves all independent-review blockers: cookie/session filtering, non-resolvable GBIF provenance placeholders, canonical builder use/default assertions, production AVONET staged publication, complete offline replay, privacy scans, and stable hashes.

## Limits

- VCR proves captured response shapes and dlt client behavior, not future provider availability or schema stability.
- Final cassettes intentionally omit public metadata unnecessary for verification; deterministic pure mapping tests cover those fields.
- No provider call occurred during review repair. No full source refresh, Dagster source job, SQLMesh command, shared warehouse connection, real AVONET download, model call, email, or product/runtime mutation occurred.
