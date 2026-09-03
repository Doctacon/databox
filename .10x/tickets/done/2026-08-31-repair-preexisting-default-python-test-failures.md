Status: done
Created: 2026-08-31
Updated: 2026-08-31
Parent: None
Depends-On: None

# Repair pre-existing default Python test failures

## Scope

Repair three deterministic failures observed in the complete network-blocked default Python suite:

- `test_ebird_and_gbif_lookups_enforce_inside_boundary_and_outside_radius` returns no rows instead of the expected inside/boundary rows.
- `test_loader_can_validate_against_hydrated_active_public_catalog` fails because fixture species `gbif-2476855` has an unsupported taxonomic category.
- `test_hydrated_public_catalog_mismatch_fails_before_table_replacement` fails for the same fixture category.

The test files were pure renames in the root layout reorganization, with no test-body changes, and all three failures reproduce in a focused run. Fix underlying fixture/contract drift without weakening radius, taxonomy, or public-export safety behavior.

## Acceptance criteria

- The three focused tests pass deterministically and preserve their intended safety assertions.
- The complete default network-blocked Python suite passes.
- No live provider calls or production data mutation occurs.

## Progress and notes

- 2026-08-31: Discovered while verifying `.10x/tickets/done/2026-08-31-organize-root-tests-and-scripts-by-domain.md`. Full result was 1,491 passed and 3 failed at 84.89% coverage; all three failures reproduced focused. Their moved files had no implementation/body changes relevant to the assertions at discovery time.
- 2026-08-31: Diagnosed the radius failure as test-clock drift: the fixed 2026-07-08 eBird rows had aged outside the production 30-days-back window by the current date, so the date filter correctly ran before radius assertions. Injected a fixed 2026-07-31 UTC clock in that one test; inside, inclusive-boundary, outside, missing-coordinate, privacy/review, and radius behavior remain unchanged.
- 2026-08-31: Reconciled the hydrated public-catalog fixture with the current fail-closed export contract by supplying exact `species` category, family/order, empty traits, and explicit zero/null occurrence evidence for both fixture species. No production validator was weakened and no evidence was invented.
- 2026-08-31: Focused verification passed 3/3. Complete `uv run pytest --block-network` passed 1,498 tests and 7 snapshots at 85.00% coverage. Ruff, format, and diff checks passed; no file is staged. Evidence: `.10x/evidence/2026-08-31-default-python-test-fixture-drift-repair.md`.
- 2026-08-31: Acceptance re-read: all focused tests and the complete default network-blocked suite pass, with no live provider call or production mutation. Ticket closed.
- 2026-08-31: Follow-up review found the fixture's family common names were plausible but invented rather than production-representative. Replaced `Hummingbirds` and `Trogons` with `None` while retaining exact scientific family/order identity and all fail-closed catalog metadata. The two affected hydrated-catalog tests passed 2/2; Ruff, format, and diff checks passed. Evidence supplement: `.10x/evidence/2026-08-31-default-python-test-fixture-drift-repair.md`.

## Blockers

None.
