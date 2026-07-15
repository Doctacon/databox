Status: recorded
Created: 2026-07-15
Updated: 2026-07-15
Target: .10x/tickets/done/2026-07-12-verify-unified-source-contract-and-ci.md
Verdict: fail

# Unified source contract privacy, security, and source review

## Findings

New GBIF/Xeno/USGS Earthquakes fixtures pass credential/session/personal-field controls, offline CI is correct, bounds/defaults are preserved, and protected AVONET/warehouse hashes are unchanged.

Closure blockers:

1. Mature eBird cassettes retain exact private-location names, coordinates, location IDs, and submission IDs for rows marked `locationPrivate=true`.
2. The shared sanitizer handles dictionary-shaped new provider payloads but not eBird top-level lists, so recurrence is not prevented.
3. Aggregate privacy evidence scanned 12 new cassettes while the repository contains 24 HTTP cassettes; the current 16-entry manifest excludes mature eBird/NOAA/USGS artifacts.

`.10x/tickets/done/2026-07-15-sanitize-ebird-private-location-fixtures.md` owns these findings.

## Verdict

Fail for closure. Offline fixture sanitization and complete aggregate scanning are required.

## Residual risk

Final artifacts cannot independently prove every historical network event. Hosted CI behavior remains a separate integration limit.
