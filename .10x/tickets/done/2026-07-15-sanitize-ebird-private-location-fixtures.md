Status: done
Created: 2026-07-15
Updated: 2026-07-15
Parent: .10x/tickets/done/2026-07-12-unify-dlt-source-contract-and-ci.md
Depends-On: .10x/tickets/done/2026-07-12-complete-source-contract-test-suites.md

# Sanitize eBird private-location fixtures

## Scope

Resolve the final aggregate privacy/source blocker without provider calls:

- remove or replace exact private-location names, coordinates, location IDs, and submission IDs from every mature eBird cassette row marked `locationPrivate=true`;
- add deterministic eBird top-level-list sanitization to the VCR harness so future recordings cannot reintroduce private-location values;
- add regression tests proving private rows preserve required field shape/flag while using non-resolvable synthetic placeholders;
- inspect all tracked HTTP cassettes, not only newly added providers;
- expand the reproducible fixture manifest/evidence to cover every tracked HTTP cassette and schema snapshot governed by the source verification contract.

## Privacy and side-effect contract

- Repair is offline only. Existing cassettes are rewritten deterministically; no eBird or other provider request is authorized or needed.
- Preserve species/date/count/validation fields needed for tests, but private location/submission identifiers MUST become deterministic non-resolvable placeholders and coordinates MUST become non-identifying synthetic values.
- Do not weaken runtime source behavior or tests that assert `location_private` semantics.
- Do not print or record provider credentials or original private values in evidence/reviews.

## Acceptance criteria

- Zero tracked cassette rows marked private retain original location name, location ID, submission ID, latitude, or longitude.
- VCR sanitizer and regression tests prevent recurrence for top-level eBird list payloads.
- All 24 HTTP cassettes and all seven schema snapshots are covered by a reproducible hash manifest and aggregate privacy scan.
- Complete source suites pass recording-disabled and network-blocked; mature eBird tests retain schema/idempotency/smoke behavior.
- Credential, cookie/session, named personal-field, private-location, fixture-hash, Ruff, format, MyPy, diff, and empty-staging checks pass.
- No provider request, source refresh, SQLMesh, warehouse, model, email, or runtime action occurs.

## Explicit exclusions

- Re-recording provider fixtures
- Changing runtime eBird privacy behavior or public data semantics
- Product/warehouse data mutation
- Sanitizing unrelated historical prose outside test fixtures/evidence

## Evidence expectations

Record affected cassette count/row count without reproducing private values, placeholder contract, complete manifest counts/hashes, offline tests, and no-network limits.

## Progress and notes

- 2026-07-15: Opened after parent inspection confirmed exact private-location data in mature eBird VCR payloads and aggregate scanning covered only 12 of 24 HTTP cassettes.
- 2026-07-15: Implemented top-level-list eBird response sanitization with fixed private name, deterministic non-resolvable response-local location/submission IDs, and synthetic `0.0` coordinates while preserving the privacy flag and public rows.
- 2026-07-15: Rewrote all four eBird cassettes offline. Parsed comparison found 50 private row occurrences changed in exactly the five approved fields, zero public rows changed, and zero other payload changes.
- 2026-07-15: Added recurrence and complete-inventory regression coverage. Expanded the manifest to all 24 HTTP cassettes and seven schema snapshots (31 entries); all hashes and the structured 44-interaction privacy scan passed.
- 2026-07-15: Focused sanitizer/eBird verification passed 8 tests; complete recording-disabled/network-blocked source verification passed 60 tests and seven snapshots. Ruff, format, focused MyPy, secret scan, protected hashes, diff, and empty staging passed. Evidence: `.10x/evidence/2026-07-15-ebird-private-location-fixture-sanitization.md`.
- 2026-07-15: Independent review `.10x/reviews/2026-07-15-ebird-private-location-fixture-sanitization-review.md` passed every acceptance criterion. Ticket closed.
- 2026-07-15 retrospective: Privacy scans must enumerate the entire tracked fixture inventory rather than a newly captured subset, and sanitizers must account for top-level payload shape. This lesson is encoded in the complete-manifest regression test and sanitizer; no separate skill/knowledge record is needed.

## Blockers

None.

## References

- `.10x/specs/registry-derived-source-verification.md`
- `.10x/knowledge/dlt-vcr-http-client-isolation.md`
- `.10x/reviews/2026-07-15-unified-source-contract-privacy-security-source-review.md`
- `.10x/evidence/2026-07-15-unified-source-contract-aggregate-verification.md`
