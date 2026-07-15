Status: done
Created: 2026-07-12
Updated: 2026-07-14
Parent: .10x/tickets/done/2026-07-12-unify-dlt-source-contract-and-ci.md
Depends-On: .10x/tickets/done/2026-07-12-consolidate-canonical-dlt-source-registry.md

# Complete source contract test suites

## Scope

Implement the HTTP and file-snapshot verification profiles in `.10x/specs/registry-derived-source-verification.md` for all seven canonical sources.

- Retain and reconcile mature eBird, NOAA, and USGS suites.
- Upgrade GBIF and Xeno-canto from mock-only resource coverage to protective offline VCR, schema snapshot, pipeline smoke, and idempotency coverage.
- Add the missing USGS Earthquakes source-package suite with the same HTTP obligations.
- Make AVONET's pinned-file profile explicit and complete without requiring HTTP VCR behavior.
- Use the canonical source builders introduced by the dependency ticket.
- Capture only the user-authorized bounded GBIF, Xeno-canto, and USGS Earthquakes metadata fixtures.

## Side-effect inventory and provenance

- **Provider requests:** user-ratified for bounded fixture capture only for GBIF, Xeno-canto, and USGS Earthquakes.
- **Credentials:** Xeno-canto key may be read only from the local environment by the existing client; it must never be printed, persisted, or recorded.
- **Data writes:** temporary/in-memory test destinations and committed sanitized fixture/snapshot files only.
- **Prohibited:** shared warehouse writes, Dagster source jobs, `task full-refresh`, SQLMesh, email/model calls, AVONET download/refresh, and unrelated provider calls.
- **Operational owner:** local user; no automated fixture refresh is added.

## Acceptance criteria

- All six HTTP source directories have resource, schema, smoke, idempotency, and offline replay coverage equivalent to the profile.
- AVONET satisfies every file-snapshot obligation with bounded local fixtures/test databases.
- Provider capture is one bounded page/feed per capture path, with request counts and URLs recorded.
- Cassettes redact headers/query credentials and are scanned for known token values and sensitive leakage.
- Completed suites pass with recording disabled, telemetry disabled, provider network forbidden, and varied source order where isolation matters.
- Schema snapshots and cassettes remain unchanged on a second offline run.
- Existing raw schema, primary key, write disposition, retry/client behavior, and source semantics are not weakened to make tests pass.

## Evidence expectations

Record capture commands, provider/request bounds, redaction checks, fixture hashes, schema snapshots, per-source test results, offline network-forbidden reruns, and limits. Do not record secrets or vault metadata.

## Explicit exclusions

- Runtime schema freezing/discard behavior
- Source query/product semantics changes
- CI workflow changes owned by the next child
- Full source refresh or warehouse mutation
- Re-recording mature eBird/NOAA/USGS fixtures without a separately surfaced blocker

## Progress and notes

- 2026-07-12: User explicitly authorized bounded metadata fixture capture for the three named providers. Environment presence of the Xeno-canto credential was confirmed without reading its value.
- 2026-07-14: Added AVONET schema/smoke coverage; GBIF and Xeno-canto VCR-backed resource/schema/smoke/idempotency suites; and the complete USGS Earthquakes HTTP profile suite.
- 2026-07-14: Captured bounded GBIF, Xeno-canto, and USGS Earthquakes fixtures. Initial functional capture was rewritten once after inspection found unnecessary public personal metadata; final fixtures are deterministically reduced to two rows/features and approved verification fields. Exact request counts and rationale are recorded in evidence.
- 2026-07-14: Initial offline source verification passed 53 tests with recording disabled and network blocked; forward/reverse mixed-source isolation runs passed 6 tests each; fixture hashes were unchanged by replay.
- 2026-07-14: Independent review found closure blockers: persisted Xeno session cookies, resolvable GBIF references, bounded tests bypassing canonical builders, and missing AVONET profile-local production publication coverage.
- 2026-07-14: Repaired all findings without provider calls. Request/response cookies are filtered and regression-tested; Xeno session values are absent; GBIF references use a deterministic `.invalid` placeholder; GBIF/Xeno suites use canonical builders with exact default/override tests; and AVONET profile coverage proves production atomic replacement, failure preservation, and cleanup in temporary storage.
- 2026-07-14: Post-repair offline verification passed 58 tests plus forward/reverse 6-test isolation runs. Source layout is 7/7; all 16 fixture hashes validate; privacy scan reports zero credential/cookie/session/personal-field leakage; Ruff, formatting, MyPy, diff check, and empty staging pass. Corrected evidence: `.10x/evidence/2026-07-14-source-contract-test-suite-completion.md`.
- 2026-07-14: Fresh correctness and privacy/security/source re-reviews passed: `.10x/reviews/2026-07-14-source-contract-test-suite-correctness-review.md` and `.10x/reviews/2026-07-14-source-contract-test-suite-privacy-security-source-review.md`.
- 2026-07-14: Retrospective complete. The reusable VCR isolation convention already exists in `.10x/knowledge/dlt-vcr-http-client-isolation.md`; new cookie/session and payload-minimization requirements are captured by the active verification spec and regression tests. No unfinished work or additional skill/knowledge owner remains from this ticket.

## Blockers

None.

## References

- `.10x/specs/registry-derived-source-verification.md`
- `.10x/specs/canonical-dlt-source-registry.md`
- `.10x/knowledge/dlt-vcr-http-client-isolation.md`
- `packages/databox-sources/README.md`
