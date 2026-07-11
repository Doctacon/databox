Status: recorded
Created: 2026-07-11
Updated: 2026-07-11
Relates-To: .10x/tickets/done/2026-07-11-repair-trip-planner-ebird-evidence-privacy.md, .10x/decisions/trip-planner-ebird-evidence-eligibility.md, .10x/specs/birding-trip-copilot.md

# Trip Planner eBird evidence privacy repair

## What changed

- `birding_agent.recent_observation_evidence` now requires `is_valid IS TRUE`, `is_reviewed IS TRUE`, and `is_location_private IS FALSE` and exposes the private flag needed by the independent runtime boundary.
- `BirdingTripPlanner.lookup_recent_observation_evidence` repeats all three predicates before ranking, model grounding, persistence, or API replay.
- A bounded offline remediation joins persisted `ebird` / `recent_observation` evidence to `environmental_observations.fact_bird_observation.source_observation_id`. It fails closed by tainting the complete containing plan when identity is null, blank, missing from authoritative facts, duplicated/ambiguous in authoritative facts, or uniquely matched but ineligible. It builds one temporary tainted-plan set, deletes traces/evidence/recommendations/plan rows in one transaction, verifies no child row for a deleted aggregate survives, and rolls back on any failure.
- The CLI supports aggregate-only `--inspect` and explicit `--apply`; neither path performs source, weather, model, media, or SMTP calls.

## Adversarial validation

The SQLMesh test supplies one eligible and three otherwise dominant private/invalid/unreviewed rows and returns only the eligible row. Python planner tests insert the same three ineligible classes with high counts and verify they have zero effect on lookup, recommendations, strict model input, persisted evidence, API output, and the evidence-empty caveat path.

Remediation tests cover:

- two tainted plans and one eligible plan;
- deletion of every child family and the plan rows;
- idempotent second apply;
- forced post-delete rollback;
- fail-closed null, whitespace-only, missing, and duplicate/ambiguous authoritative identity, with `unmatched_source_records` counting all four identity classes;
- malformed-identity rollback followed by complete deletion and idempotent replay;
- preservation of unrelated historical traces that never belonged to a completed plan;
- rollback if any row belonging to a tainted plan is reintroduced before commit;
- socket-disabled offline behavior.

Focused result:

```text
34 planner/API/eval/remediation tests passed
5 remediation-only tests passed after the final identity repair
13 SQLMesh tests passed; lint passed
```

Complete gates after production remediation:

```text
uv run --no-sync pytest -q --record-mode=none --block-network
414 passed; 3 snapshots passed; coverage 86.33%

task app:check
125 frontend tests, TypeScript, production build, and bundle audit passed

cd transforms/main && sqlmesh test && sqlmesh lint && sqlmesh diff prod
13 passed; lint passed; no prod diff

mypy packages/
90 source files passed

secret scan, focused Ruff/format, all hooks, generated dictionary freshness,
MkDocs strict, and git diff checks
passed
```

## Reviewed production diff and apply

The pre-apply `sqlmesh diff prod` contained exactly one direct modification: `birding_agent.recent_observation_evidence`, adding the private flag projection and three eligibility predicates. No other model appeared.

Applied with:

```text
sqlmesh plan prod --skip-backfill --no-prompts --auto-apply \
  --select-model birding_agent.recent_observation_evidence
```

SQLMesh ran all 13 tests, updated exactly one view in the physical and virtual layers, reported `SKIP: No model batches to execute`, and performed no restatement or table/incremental full refresh. Post-apply `sqlmesh diff prod` is clean.

## Live aggregate remediation

All live inspection and output were aggregate-only; no source record ID, location, personal content, or private value was printed or recorded.

Pre-remediation after the intended SQLMesh view apply:

```json
{
  "planner_view_rows": 1676,
  "planner_view_ineligible": 0,
  "plans": 3,
  "recommendations": 24,
  "evidence": 376,
  "traces": 35,
  "tainted_plans": 3,
  "unmatched_source_records": 0,
  "warehouse_sha256": "24fd0cbc9e3542fd595298b37a16e34d860b4e981a7d99dae67962ef24515093"
}
```

The first apply attempt rolled back fully because its verification treated eight pre-existing traces from incomplete/failed historical invocations as generic orphans. Those traces do not belong to any completed saved plan and are deliberately retained by the existing planner failure contract. The repair narrowed the postcondition to the ticket-owned invariant—zero child rows for any deleted tainted aggregate—and added tests proving both preservation of unrelated traces and rollback if a tainted child survives. Inspection still reported the original three tainted plans before the successful apply.

Successful apply:

```json
{
  "tainted_plans": 3,
  "deleted_plans": 3,
  "deleted_recommendations": 24,
  "deleted_evidence": 376,
  "deleted_tool_traces": 27,
  "remaining_plans": 0,
  "unmatched_source_records": 0
}
```

Immediate second apply was idempotent with every deleted count and tainted count equal to zero.

Post-remediation:

```json
{
  "planner_view_ineligible": 0,
  "ineligible_persisted_ebird": 0,
  "plans": 0,
  "recommendations": 0,
  "evidence": 0,
  "partial_recommendations": 0,
  "partial_evidence": 0,
  "historical_incomplete_invocation_traces_preserved": 8,
  "warehouse_sha256": "2a916fb3f8f6e5269e73fda986366c88927eb8079f3f2c93af11639bf2bf2e0d"
}
```

No plan was rebuilt. No model, media, source, weather, watch, alert, personal-state, or SMTP action ran. The changed warehouse scope is the intended SQLMesh view/version metadata and the four runtime saved-plan aggregate tables; the remediation module contains no other write target. Post-run structural checks still show zero `birding_personal` tables, zero target-plan tables, exactly two pre-existing SMTP verification ledger rows, no AVONET staging schema, and no `main._dlt*` relation.

## Final malformed-identity repair and live rerun

Final review found that the first remediation query excluded null identities, stopped rather than deleting plans with missing authority, and did not reject ambiguous duplicate authoritative identities. The repaired query classifies all four identity failures before eligibility evaluation. Aggregate inspection counts each distinct class/value without recording the underlying value, and the same predicate creates the transactional tainted-plan set.

A fixture with null, whitespace-only, missing, and duplicated authoritative identities reports four unmatched identities and six tainted plans (the four malformed cases plus two quality/privacy cases). An injected failure rolls all six aggregates back; the subsequent apply deletes all six; a second apply reports zero.

The authorized live rerun found no newly affected row because the earlier remediation had already removed every saved plan:

```json
{
  "inspect": {"tainted_plans": 0, "unmatched_source_records": 0, "remaining_plans": 0},
  "apply": {"tainted_plans": 0, "unmatched_source_records": 0, "deleted_plans": 0, "remaining_plans": 0},
  "warehouse_sha256_before": "2a916fb3f8f6e5269e73fda986366c88927eb8079f3f2c93af11639bf2bf2e0d",
  "warehouse_sha256_after": "2a916fb3f8f6e5269e73fda986366c88927eb8079f3f2c93af11639bf2bf2e0d"
}
```

The post-rerun prod diff remains clean. Complete network-disabled Python validation now passes 414/414 at 86.33%; MyPy, secret scan, focused hooks, Ruff/format, and diff checks pass.

## Limits

- All three current saved plans were tainted and were permanently removed as ratified; expected remaining completed plan count is zero.
- Eight traces from earlier incomplete/failed planner invocations remain intentionally because they are not partial children of a deleted completed aggregate and are outside this remediation scope.
- Final independent review passed and is recorded at `.10x/reviews/2026-07-11-trip-planner-ebird-evidence-privacy-review.md`.
