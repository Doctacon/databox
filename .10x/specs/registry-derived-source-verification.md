Status: active
Created: 2026-07-12
Updated: 2026-07-12

# Registry-derived source verification

## Purpose and scope

This specification defines the mandatory offline test contract and GitHub Actions coverage for every source in the canonical registry governed by `.10x/specs/canonical-dlt-source-registry.md`.

It covers test profiles, sanitized fixture capture, source-test isolation, CI matrix derivation, aggregate coverage, and failure behavior. It does not authorize a full source refresh, warehouse mutation, SQLMesh execution, provider content use outside tests, or runtime schema-policy changes.

## Verification profiles

Every source MUST declare exactly one profile in the canonical registry.

### HTTP profile

Applies to eBird, GBIF, NOAA, USGS, USGS Earthquakes, and Xeno-canto.

Each HTTP source MUST have profile-equivalent coverage for:

1. resource extraction and required row/provenance fields;
2. an inferred dlt schema snapshot committed to the repository;
3. an in-memory pipeline smoke run with successful load jobs and nonzero bounded rows;
4. repeat-run/idempotency behavior against the same fixture data and declared primary key/write disposition;
5. offline VCR replay with all live network access blocked by default;
6. source configuration/build behavior through the canonical source builder rather than the retired generic YAML loader.

VCR-marked tests MUST follow `.10x/knowledge/dlt-vcr-http-client-isolation.md`: use a fresh public dlt HTTP client per test, close it at teardown, disable telemetry, and never depend on another source's cassette/session.

Bespoke request mocks MAY remain for pure transformation/error unit tests, but MUST NOT substitute for the profile's provider-session, schema, idempotency, or smoke evidence.

### File-snapshot profile

Applies to AVONET.

The profile MUST verify:

1. pinned manifest parsing and immutable identity fields;
2. bounded local parser/resource behavior;
3. schema and required columns;
4. deterministic idempotency and atomic staged publication invariants using local fixtures/test databases;
5. smoke behavior without downloading or publishing the full source during routine CI.

It MUST NOT require an HTTP VCR cassette merely to mimic the HTTP profile.

## Authorized fixture capture

The user authorized bounded metadata-only provider requests to create missing sanitized test fixtures for:

- GBIF;
- Xeno-canto;
- USGS Earthquakes.

Capture MUST:

- request no more than one bounded page/feed per test capture path;
- avoid `task full-refresh`, Dagster source jobs, SQLMesh, and the shared warehouse;
- use temporary/in-memory dlt destinations only where a pipeline is needed;
- use the Xeno-canto credential only server-side through the existing environment and never print or persist it;
- redact authorization headers, tokens, API-key query parameters, and response echoes before writing fixtures;
- inspect fixtures for secrets and unnecessary sensitive fields before acceptance;
- record provider URL, capture command, bounded request count, and redaction evidence without recording credentials;
- rerun the completed source suites with recording disabled and network forbidden.

No new live capture is authorized for eBird, NOAA, USGS, or AVONET under this work because their existing fixtures/local test mechanics are sufficient unless execution uncovers a concrete blocker. Such a blocker returns to the Outer Loop.

## CI derivation

GitHub Actions MUST obtain its active source test matrix from a repository command that reads the canonical registry and emits deterministic JSON. The workflow MUST consume that output with a matrix rather than maintaining source names manually.

A source-related change MUST run the complete source matrix. Source-related scope includes at least:

- any file under `packages/databox-sources/`;
- canonical source registry or source-domain orchestration changes;
- shared dlt destination/client/test harness changes;
- source scaffold/contract scripts and templates;
- source-related CI workflow changes;
- dependency changes capable of affecting dlt, Dagster, DuckDB, Quack, VCR, or source tests.

At seven sources, fine-grained changed-source skipping is explicitly excluded. Matrix jobs SHOULD remain independent so VCR/dlt client state cannot leak across sources and all source failures are visible.

The aggregate coverage job MUST execute every registered source suite in isolated sequential pytest processes and combine coverage. It MUST NOT enumerate only a subset of source directories.

CI MUST fail if:

- a registered source is omitted from the matrix;
- a source profile's required test artifacts are missing;
- a source-only path change is classified as requiring no source verification;
- any source test attempts an unmatched live request with recording disabled;
- a cassette or snapshot changes unexpectedly during offline verification;
- a source suite fails even if other source suites pass.

## Acceptance scenarios

### Omitted source regression

Given a change only under `databox_sources/gbif`, `databox_sources/xeno_canto`, `databox_sources/usgs_earthquakes`, or `databox_sources/avonet`, when CI classifies the change, then the complete registry-derived source matrix runs.

### New registry entry

Given a future eighth source is added to the registry but no workflow source list is edited, when CI builds its matrix, then that source appears automatically. If its profile tests are incomplete, CI fails.

### Offline replay

Given no provider credentials and network access denied, when the routine source matrix runs, then every HTTP source passes from sanitized fixtures or fails explicitly on missing fixture coverage; none silently contacts a provider.

### Aggregate coverage

Given all seven active sources, when the aggregate coverage job runs, then each source test directory contributes coverage through an isolated pytest process before the workspace threshold is evaluated.

## Explicit exclusions

- No runtime dlt schema contract (`evolve`, `freeze`, or discard mode) changes.
- No provider pagination/load-volume expansion beyond bounded fixture capture.
- No source refresh or warehouse/database mutation.
- No CI optimization that can omit a registered source based on hand-maintained per-source paths.
- No replacement of Soda or SQLMesh model validation; this specification governs ingestion-source verification only.
