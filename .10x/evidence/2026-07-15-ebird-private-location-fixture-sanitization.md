Status: recorded
Created: 2026-07-15
Updated: 2026-07-15
Relates-To: .10x/tickets/done/2026-07-15-sanitize-ebird-private-location-fixtures.md, .10x/specs/registry-derived-source-verification.md, .10x/reviews/2026-07-15-unified-source-contract-privacy-security-source-review.md

# eBird private-location fixture sanitization

## What was observed

The aggregate privacy review found that mature eBird VCR responses were top-level JSON lists, while the shared sanitizer only bounded dictionary-shaped provider responses. All four eBird cassettes contained rows marked `locationPrivate=true` whose exact location/submission values were unnecessary for source verification. The prior integrity/privacy scope covered only 12 newly added cassettes and 16 cassette/snapshot artifacts rather than the complete tracked inventory.

## Offline repair

`packages/databox-sources/tests/conftest.py` now recognizes top-level lists and sanitizes only eBird-shaped rows explicitly marked private. It preserves the privacy flag and field types while replacing the five private fields with:

- `locName`: `Private location (sanitized)`;
- `locId`: deterministic, response-local `PRIVATE-LOCATION-NNN` values;
- `subId`: deterministic, response-local `PRIVATE-SUBMISSION-NNN` values;
- `lat` and `lng`: synthetic `0.0` coordinates.

Repeated source identifiers map to the same synthetic identifier within a response, preserving grouping/idempotency shape without retaining a reversible hash or provider identifier. Public rows are returned unchanged.

The same sanitizer was applied offline to the four existing eBird cassette files. Parsed comparison against `HEAD` found:

- four changed cassettes and six affected response interactions;
- 50 private row occurrences changed in exactly `locName`, `locId`, `subId`, `lat`, and `lng`;
- zero public rows changed;
- zero other response payload fields changed.

No original private value is reproduced in this record.

## Regression coverage

`packages/databox-sources/tests/test_vcr_sanitization.py` now proves:

- a public eBird row remains byte-for-value equivalent after response scrubbing;
- private flags/field shape remain present;
- repeated private identifiers map stably while distinct identifiers remain distinct;
- private fields use only the explicit non-resolvable placeholder contract;
- synthetic test originals do not survive serialized output;
- every tracked HTTP cassette and schema snapshot appears in the manifest and matches its SHA-256;
- no tracked cassette retains request `Cookie`, response `Set-Cookie`, `PHPSESSID`, or the unnecessary personal response-field set;
- every tracked private eBird row conforms to the placeholder contract.

## Fixture inventory and privacy inspection

The expanded manifest `.10x/evidence/.storage/2026-07-14-source-contract-fixture-sha256.txt` contains exactly:

- 24 HTTP cassettes;
- seven schema snapshots;
- 31 total entries.

Manifest SHA-256: `e1fc8e745e12692136e3d185b81f637ed98b1431b0cee9641ca276878f5b91de`.

A structured scan parsed all 24 cassettes and 44 interactions and verified:

- 31/31 manifest membership and content hashes;
- zero exact configured credential matches;
- zero request/response cookie or PHP session artifacts;
- zero unnecessary personal response fields;
- zero resolvable GBIF occurrence links;
- all 50 private eBird row occurrences use the placeholder contract;
- zero private-placeholder violations.

## Commands and results

### Focused sanitizer and eBird profile

` .venv/bin/pytest --no-cov -q packages/databox-sources/tests/test_vcr_sanitization.py packages/databox-sources/tests/ebird --record-mode=none --block-network `

Result: **8 passed**, one snapshot passed.

### Complete source verification

`XENO_CANTO_API_KEY=test-token-for-vcr-replay EBIRD_API_TOKEN=test-token-for-vcr-replay NOAA_API_TOKEN=test-token-for-vcr-replay RUNTIME__DLTHUB_TELEMETRY=false .venv/bin/pytest --no-cov -q packages/databox-sources/tests --record-mode=none --block-network`

Result: **60 passed**, seven snapshots passed, 11 warnings; recording disabled and network blocked.

### Integrity, privacy, and static checks

- `shasum -a 256 -c .10x/evidence/.storage/2026-07-14-source-contract-fixture-sha256.txt` — 31/31 passed after all tests.
- Structured all-cassette privacy/credential/private-location scan — 24 cassettes, 44 interactions, all zero-hit assertions passed.
- Parsed cassette comparison against `HEAD` — exactly 50 private rows/five approved fields changed; zero public/other payload changes.
- `.venv/bin/ruff check ...` — passed.
- `.venv/bin/ruff format --check ...` — two changed Python files formatted.
- focused `mypy` — success for both changed Python files (one pre-existing untyped-fixture note).
- `.venv/bin/python scripts/check_secrets.py .` — passed.
- `git diff --check` — passed.
- `git diff --cached --name-only` — empty.

Protected SHA-256 values remained unchanged:

- AVONET manifest: `2995f2e8a37caa7ca2014bdc1acbd75d2b8a7a7067c89a380a8c910a3ad3bf97`;
- shared warehouse file: `de4562f0ea5820f3c0a562e538ba32a2841b57709efebe059480099d80f74bb4`.

## What this supports

This supports every acceptance criterion in `.10x/tickets/done/2026-07-15-sanitize-ebird-private-location-fixtures.md`: offline replacement of mature eBird private-location values, recurrence prevention, complete fixture/snapshot manifest coverage, complete offline source verification, privacy/credential/integrity/static checks, protected-state preservation, and empty staging.

## Limits

- VCR fixtures prove only the captured response shapes and offline client behavior, not future provider responses or availability.
- Response-local sequential placeholders intentionally preserve only grouping/order needed by tests; they do not preserve real coordinates or resolvable provider identities.
- The evidence proves no provider call occurred in the executed commands because all test commands used recording-disabled/network-blocked modes and the offline rewrite parsed local files only; it cannot independently reconstruct unrelated historical network activity.
- No provider request, source refresh, SQLMesh command/apply, shared warehouse connection, model call, email, or product/runtime action occurred.
- Independent acceptance review and ticket closure remain parent-owned.
