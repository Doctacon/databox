Status: recorded
Created: 2026-07-13
Updated: 2026-07-13
Target: `.10x/tickets/cancelled/2026-07-12-repair-curated-selector-source-integrity.md` retry and `.10x/evidence/2026-07-13-curated-selector-wdqs-retry-blocker.md`
Verdict: concerns

# Curated selector WDQS retry review

## Findings

- Fresh process and DuckDB-writer preflight preceded the retry.
- The retry used the production selector and production metadata transport behind a counting wrapper; it did not substitute fixture data.
- Exact-P225 discovery contacted only the governed WDQS endpoint and failed closed.
- Attempted-source evidence and the counting callback prove no iNaturalist fallback occurred.
- The required available Wikimedia result and <=1024 thumbnail assertion were not reached, so the migration gate correctly remained closed.
- Pre/post read-only snapshots match exactly across current photo state, 86 protected fingerprints, photo-run values, and 19 external hashes.
- Neither authorized apply command ran, and no manual row deletion/reset occurred.

## Verdict

Concerns. The retry is safe and correctly bounded, but public WDQS availability still prevents the required live proof and serialized re-evaluations. The ticket must remain blocked.

## Residual risk

Provider availability can recur independently of Rufous. Existing 621 catalog and eight planner iNaturalist results remain valid curated rows but have not yet been re-evaluated under the repaired Wikimedia-primary selector.
