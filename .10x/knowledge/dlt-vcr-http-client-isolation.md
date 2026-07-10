Status: active
Created: 2026-07-10
Updated: 2026-07-10

# dlt HTTP isolation in VCR tests

## Context

dlt's module-level HTTP client can share one `HTTPAdapter` across thread-local sessions. urllib3 pools created while vcrpy is patched retain cassette-bound connection classes, so adapter reuse can route a later source test through an earlier test's cassette even when each test names its own cassette.

Import-time asynchronous telemetry can create a related leak by retaining sessions and flushing while a cassette is active or after its lifecycle ends.

## Project convention

- Disable dlt and SQLMesh telemetry in repository pytest bootstrap before test modules import those libraries.
- For every VCR-marked source test, replace dlt's module-level client and request methods with one fresh public `dlt.sources.helpers.requests.Client`.
- Close that client's session at test teardown.
- Do not replace source requests with bespoke mocks: retain dlt retry/session behavior and the protective cassette contract.
- Validate isolation with recording disabled and network blocked in standalone, varied-order, complete source-suite, and full-suite runs.
- Confirm tracked cassette and snapshot files are unchanged after verification.

## Limits

This convention proves the repository's sequential pytest contract. Parallel xdist execution requires separate validation before adoption.
