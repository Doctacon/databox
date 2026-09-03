Status: done
Created: 2026-07-10
Updated: 2026-07-11
Parent: .10x/tickets/done/2026-07-09-build-local-birding-pokedex.md
Depends-On: .10x/tickets/done/2026-07-10-build-my-birds-and-profile-controls.md, .10x/tickets/done/2026-07-10-implement-target-bird-planning.md, .10x/tickets/done/2026-07-10-implement-proton-bridge-alert-delivery-and-operations.md

# Verify local birding Pokédex

## Scope

Run aggregate adversarial verification across the completed catalog, personal collection, target planning, watched matching/reporting, calendar/outbox, SMTP operations, and preserved Trip Planner. Reconcile active specifications, child evidence, reviews, dependency/status graph, and retrospective learning.

## Acceptance criteria

- Full Python/frontend/SQLMesh/Soda/docs/hooks/typecheck/build suites pass with no recording or unintended warehouse/source mutation.
- Catalog remains 706/624/82 with 600 exact AVONET matches; personal, target, watch, and alert identity all use exact catalog species code without hybrid/parent guesses.
- Privacy and side-effect matrix proves private eBird rows, recipient/SMTP/Cloudflare/source secrets, and arbitrary model/raw payloads do not leak across API/log/trace/bundle/record boundaries; personal locations/notes, watch centers, and target origins remain available only through authorized typed local APIs and absent from unrelated/public APIs, prompts, traces, logs, bundles, and committed fixtures.
- Replay/concurrency/crash tests prove observation transactions, target-plan atomicity, watch novelty, event UID/sequence, outbox claim/retry/unknown reconciliation, and retention behavior.
- Accessibility/direct/history/focus/responsive/empty/error behavior passes across Trip Planner, Arizona Birds, My Birds, target reports, and alert operations.
- Only explicitly authorized live test email/invitation are sent, if still needed; acceptance evidence is redacted and no inbox-rendering guarantee is claimed.
- Independent aggregate architecture, correctness, privacy/security, and UX reviews pass or every residual risk has a durable accepted owner.
- Parent plan, specs, decisions, evidence, reviews, tickets, and retrospective records agree before closure.

## Explicit exclusions

No new product behavior, broad refactor, remote deployment, accounts, social features, or unratified external integration.

## Evidence expectations

Create one aggregate evidence record and independent review records mapping every parent/spec criterion to reproducible artifacts and commands.

## Progress and notes

- 2026-07-10: Verification ticket opened after all remaining focused contracts were ratified.
- 2026-07-11: Read all active specifications/decisions, parent/child tickets, evidence, reviews, and committed implementation. All six implementation children are done with pass reviews and coherent dependencies.
- 2026-07-11: Full network-disabled Python passed 408/408 at 86.26% coverage; frontend passed 125 tests plus TypeScript/build/12-name bundle audit; SQLMesh passed 13 tests, lint, and clean prod diff; 25/25 production Soda contracts, source layout, CI, secret scan, and all hooks passed. Live warehouse hash remained unchanged and reconciled exact 706/624/82/600 catalog identity, 10,661 AVONET rows, zero public-aggregate mismatches, 337/337 qualifying top public tuples, no staging, and no `main._dlt*`.
- 2026-07-11: Safe exact-value scans found zero configured credential/address/path occurrences in tracked files, logs, warehouse, or compiled bundle. The redacted durable Bridge ledger contains exactly one accepted test-email kind and one accepted test-invitation kind with no sensitive columns; verification sent nothing.
- 2026-07-11: Aggregate evidence and adversarial identity/privacy/side-effect/idempotency/concurrency/crash/accessibility matrix recorded at `.10x/evidence/2026-07-11-local-birding-pokedex-aggregate-verification.md`.
- 2026-07-11: MkDocs strict build passed, but the canonical dictionary freshness command failed because `bird_species_traits_sk` is committed as `UNKNOWN` while deterministic generation produces `TEXT`. Generated/checksum artifacts were restored; no implementation repair was made.
- 2026-07-11: Reviewed dictionary repair committed as `6db35d9`. Canonical freshness now passes for all 20 files, MkDocs strict and affected hooks pass, the live warehouse hash remains unchanged, and the redacted two-kind Bridge verification ledger remains exactly bounded. The intervening commit changed only the generated dictionary and its ticket/evidence/review records; prior aggregate evidence remains valid. No send or mutation command ran.
- 2026-07-11: Re-read the completed evidence and pass reviews for privacy repair `47d88bf` and browser-boundary repair `78493fb`, then reran aggregate verification from the repaired committed state.
- 2026-07-11: Complete network-disabled Python passed 414/414 at 86.33%; frontend passed 159/159 plus TypeScript/build/12-name bundle audit; SQLMesh passed 13 tests, lint, and clean prod diff; 25 Soda contracts passed 125 checks; docs freshness/MkDocs strict, source/layout generation, secret scan, all hooks, Ruff, and MyPy passed.
- 2026-07-11: Live read-only reconciliation retained exact 706/624/82/600 catalog identity, 10,661 AVONET rows, zero public aggregate/top-tuple mismatches, zero planner-view or persisted ineligible eBird evidence, zero saved plans containing ineligible evidence, eight intentional incomplete-invocation traces, no staging or `main._dlt*`, and an unchanged warehouse hash `2a916f…e0d`.
- 2026-07-11: Verification sent nothing and ran no refresh/remediation/model/source/application mutation. The bounded ledger remains exactly one accepted test-email row and one accepted test-invitation row. Ten configured sensitive values had zero exact hits across 542 tracked files, 68 logs, three bundle files, and warehouse bytes.
- 2026-07-11: Corrected aggregate privacy wording: personal locations, observation notes, watch centers, and target origins are intentionally confined to authorized typed local APIs and absent from unrelated/public APIs, model prompts, traces, logs, bundles, and committed fixtures; they are not claimed absent from all APIs. Updated aggregate evidence/matrix: `.10x/evidence/2026-07-11-local-birding-pokedex-aggregate-verification.md`.
- 2026-07-11: Final UX repair `a643b80` added strict ISO date/time validation across target/bird/alert browser boundaries and prevented failed My Birds loads from rendering false empty state; its focused ticket and independent review passed.
- 2026-07-11: Post-`a643b80` aggregate rerun passed 414 network-disabled Python tests at 86.33%, 199 frontend tests plus TypeScript/build/12-name bundle audit, secrets, all hooks, docs freshness/MkDocs strict, and source/layout checks. Warehouse hash remained `2a916f…e0d`; saved/persisted/ineligible Trip Planner rows remain zero; eight incomplete traces and the exact accepted email/invitation ledger remain unchanged. No send or mutation command ran.
- 2026-07-11: Fresh aggregate architecture, correctness, and privacy/security/side-effect reviews passed and are recorded under `Status: done
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
`.
- 2026-07-11: Final aggregate UX/accessibility review passed after `a643b80`. Review: `.10x/reviews/2026-07-11-local-birding-pokedex-aggregate-ux-accessibility-review.md`.
- 2026-07-11: Retrospective confirmed every execution defect became a reviewed repair ticket and durable invariant. Screenshot/manual assistive-technology validation is accepted as unnecessary for this local single-user release because native semantics, keyboard/focus behavior, and responsive contracts have direct automated coverage. Absence of current live personal/watch/outbox state is an evidence limit, not unfinished behavior; reviewed adversarial transaction/replay/concurrency tests own those contracts.

## Blockers

None.
