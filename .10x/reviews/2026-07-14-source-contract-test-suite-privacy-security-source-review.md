Status: recorded
Created: 2026-07-14
Updated: 2026-07-14
Target: .10x/tickets/done/2026-07-12-complete-source-contract-test-suites.md
Verdict: pass

# Source contract test-suite privacy, security, and source review

## Target

Captured fixtures, VCR harness, tests, manifest, and evidence for `.10x/tickets/done/2026-07-12-complete-source-contract-test-suites.md`.

## Findings

Initial review found persisted Xeno-canto PHP session cookies and resolvable GBIF occurrence links. Both were repaired offline without provider recapture.

- Future recordings filter request `Cookie`, response `Set-Cookie`, credential headers/query parameters, and credential echoes; regression tests cover the filters.
- Existing Xeno-canto `PHPSESSID`, request cookie, and response cookie data is absent.
- GBIF references use the deterministic non-resolvable `https://example.invalid/gbif-occurrence` placeholder while preserving field shape.
- The 12 cassettes contain 15 final interactions on only the three authorized hosts. GBIF and Xeno requests are one bounded page of two rows; USGS Earthquakes is one feed bounded to two features.
- Xeno keys are persisted only as `REDACTED`. Exact local credential scans and unnecessary personal-field scans returned zero findings.
- All 16 cassette/snapshot hashes validate against `.10x/evidence/.storage/2026-07-14-source-contract-fixture-sha256.txt`.
- Parent-observed offline replay passed 58 tests with recording disabled/network blocked and did not alter fixture hashes.
- Evidence chronology was corrected to 2026-07-14 to agree with provider/filesystem timestamps; shaping authorization remains dated 2026-07-12.

## Verdict

Pass. Final artifacts satisfy the authorized-source, request-bound, credential, session-state, personal-data minimization, and reproducibility contracts.

## Residual risk

Repository artifacts substantiate final requests and offline repairs, but cannot independently prove every historical network event. VCR fixtures remain bounded snapshots and do not guarantee future provider behavior.
