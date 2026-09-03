Status: done
Created: 2026-09-03
Updated: 2026-09-03
Parent: None
Depends-On: .10x/tickets/done/2026-09-03-split-polaris-integration-source-matrix.md

# Fix USGS daily-value natural key

## Scope
Preserve the USGS NWIS daily statistic code and include it in the Iceberg merge key so Maximum, Minimum, and Mean observations for the same site, parameter, and date remain distinct.

## Acceptance criteria
- `daily_values` extracts the source `Statistic` option code into `statistic_cd`.
- Natural key is `(site_no, parameter_cd, statistic_cd, observation_date)`.
- Schema snapshots and downstream model references remain coherent.
- Regression coverage proves multiple statistics on one date produce distinct keys and load without duplicate-key failure.
- No unrelated source or infrastructure behavior changes.

## Progress and notes
- 2026-09-03: Protected matrix run 33813273328 passed five sources; USGS failed PyIceberg upsert duplicate-key validation. Live two-day Arizona NWIS inspection found 423 rows and 9 duplicate old keys; an observed key contained statistic codes 00001 Maximum, 00002 Minimum, and 00003 Mean.
- 2026-09-03: Added source-backed `statistic_cd`, extended the Iceberg merge key and downstream fact grain/identities, updated the Soda contract and schema snapshot, and added a three-statistic regression. All five USGS tests, SQLMesh lint, source registry tests, codegen drift checks, pre-commit, and diff validation passed.

## Blockers
None.
