Status: done
Created: 2026-07-11
Updated: 2026-07-11
Parent: .10x/tickets/2026-07-10-verify-local-birding-pokedex.md
Depends-On: None

# Repair Trip Planner eBird evidence privacy

## Scope

Implement `.10x/decisions/trip-planner-ebird-evidence-eligibility.md`: filter the planner eBird model and Python lookup to valid, reviewed, non-private evidence; add adversarial tests; apply the reviewed model change to production; and atomically delete complete saved-plan aggregates influenced by any ineligible authoritative source record.

## Acceptance criteria

- SQLMesh planner view and Python query independently enforce `is_valid IS TRUE`, `is_reviewed IS TRUE`, and `is_location_private IS FALSE` before ranking/persistence.
- Tests prove private/invalid/unreviewed rows have zero effect on recommendations, model input, persisted evidence, API output, and empty/degraded states.
- Remediation identifies tainted plans by source record ID joined to authoritative modeled facts, deletes complete aggregates in one transaction, is idempotent, rolls back on failure, and performs no network call.
- Production apply changes only the intended planner model with no restatement/full refresh; post-apply prod diff is clean.
- Live remediation records only counts/IDs in redacted aggregate form, leaves zero ineligible persisted eBird evidence and zero partial orphan rows, and does not alter the warehouse outside tainted runtime plan aggregates plus intended view metadata.
- Full planner/API/frontend/SQLMesh/privacy/secret/hook regressions pass.

## Explicit exclusions

No plan rebuild, model/media call, source refresh, unrelated planner redesign, personal/watch/alert mutation, or adjacent cleanup.

## Evidence expectations

Record pre/post counts without private content, test and rollback results, reviewed SQLMesh diff/apply, transaction/idempotency, orphan checks, warehouse scope limits, and independent review.

## Progress and notes

- 2026-07-11: Implemented SQLMesh and Python valid/reviewed/non-private defense-in-depth plus adversarial model/ranking/persistence/API/empty-state tests.
- 2026-07-11: Added explicit aggregate-only inspect/apply remediation with authoritative source-ID joins, complete aggregate deletion, unmatched-identity fail closure, transactional rollback, idempotency, deleted-child verification, preservation of unrelated incomplete-invocation traces, and no-network tests.
- 2026-07-11: Reviewed pre-apply diff contained exactly `birding_agent.recent_observation_evidence`; applied that view only with skip-backfill/select-model. SQLMesh reported no model batches, no restatement/full refresh, and post-apply prod diff is clean.
- 2026-07-11: Live aggregate-only remediation removed three tainted plans, 24 recommendations, 376 evidence rows, and 27 associated traces; zero plans remain as expected. Second apply deleted zero. View and persisted evidence have zero ineligible rows; deleted aggregates left zero recommendation/evidence child rows. Evidence: `.10x/evidence/2026-07-11-trip-planner-ebird-evidence-privacy-repair.md`.
- 2026-07-11: Complete network-disabled Python passed 413/413 at 86.34%; frontend 125, SQLMesh 13/lint/clean prod diff, MyPy 90 files, bundle, secret, Ruff/format, hooks, and diff gates passed.
- 2026-07-11: Final review repair now taints/deletes complete plans for null, blank, missing, or duplicate/ambiguous authoritative identities; `unmatched_source_records` includes every class. New rollback/idempotency tests pass 5/5, full Python passes 414/414 at 86.33%, static/privacy/hooks pass, prod diff remains clean, and authorized live inspect/apply found zero affected rows with an unchanged warehouse hash.
- 2026-07-11: Final independent review passed. Review: `.10x/reviews/2026-07-11-trip-planner-ebird-evidence-privacy-review.md`.
- 2026-07-11: Retrospective preserved fail-closed authoritative identity and complete-tainted-aggregate deletion rules in the active planner specification, decision, remediation module, and adversarial tests; no additional skill record is needed.

## Blockers

None.
