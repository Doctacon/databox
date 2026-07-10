Status: recorded
Created: 2026-07-09
Updated: 2026-07-09
Target: .10x/tickets/done/2026-07-09-backfill-existing-plan-media.md
Verdict: pass

# Existing plan media backfill review

## Target

Backfill implementation, live mutation evidence, and final warehouse state governed by `.10x/specs/recommendation-media-enrichment.md`.

## Findings

### Passed — dry-run, transactional apply, and idempotency

Dry-run is read-only with zero discovery. Apply delegates to the shared selector, persists in one transaction, verifies cardinality, and rolls back on selector or mid-insert failure. Duplicate evidence aborts before discovery/writes; an external writer lock prevents mutation. Deterministic IDs and a second zero-target run prove idempotency.

### Resolved significant — live GBIF compatibility

The initial live run produced 16 available calls but rejected all photos because GBIF returned exact recognized Creative Commons licenses using HTTP links and the country label `United States of America`. The selector now canonicalizes only exact allowlisted Creative Commons HTTP host/path values to HTTPS and accepts that exact US spelling while retaining finite license, state, species, attribution, cache-key/MD5, and URL checks. Final selective photo repair made no Xeno/model calls.

### Resolved significant — overbroad one-time repair

Initial review found the temporary unavailable-photo replacement matched arbitrary legacy/future prefixes. Final logic matches only exact defective `media_backfill_v2_` IDs plus the exact unavailable status/caveat. Tests reject generic, v1, unknown, current v3, changed-caveat, and available variants. Current rows are outside the repair predicate.

### Passed — live state

Read-only inspection confirms 2 plans, 16 recommendations, 16 available photos, 16 available calls, zero bad cardinality, and Queen Valley 8/8. GET makes zero discovery calls and leaves all application tables unchanged. No binary media or credential output exists.

## Verdict

Pass. No blocker remains.

## Residual risk

Remote metadata availability is temporal. Operators must stop API/source writers before apply; DuckDB lock acquisition fails before writes otherwise.
