Status: done
Created: 2026-07-11
Updated: 2026-07-11
Parent: .10x/tickets/done/2026-07-10-verify-local-birding-pokedex.md
Depends-On: None

# Harden Trip Planner browser boundary

## Scope

Repair aggregate UX/security findings in the preserved Trip Planner browser client: strict bounded exact-shape runtime validation for location suggestions, plan summaries, and plan details; fixed client-side messages for allowlisted backend errors; rejection of unknown/extra/malformed payloads; and an announced busy state for alert reconciliation.

## Acceptance criteria

- Browser validators enforce exact keys, IDs, dates/timestamps, finite numbers, cardinality, nested relationships, media/evidence/traces, and configured contract bounds before rendering.
- Error handlers map allowlisted status/code combinations to fixed safe messages and never render backend-provided arbitrary text; unknown/malformed errors use a generic safe message.
- Adversarial tests cover exact-shaped secret/path/raw-model messages, extra/missing/wrong-type/oversized/nonfinite success payloads, cross-record identity mismatch, and no partial render.
- Alert reconciliation exposes native `aria-busy` and live updating status while preserving disabled actions/focus/success/error behavior.
- Existing planner/catalog/My Birds/target/alert tests, TypeScript, build, bundle/secret audit, and accessibility contracts pass.

## Explicit exclusions

No backend API change, product behavior change, planner ranking/model/persistence change, or visual redesign.

## Evidence expectations

Record validator/error allowlists, adversarial cases, accessibility behavior, full frontend gates, and independent review.

## Progress and notes

- 2026-07-11: Added exact bounded runtime validators for location suggestions, plan summaries, complete plan details, nested JSON, impossible dates, IDs, relationships, and cardinalities. Plan lists remain capped at 100.
- 2026-07-11: Added fixed client-owned status/code error mappings and generic fallback handling; adversarial tests prove backend path, secret, and raw-model strings do not render.
- 2026-07-11: Reconciled stale browser fixtures with the actual FastAPI-derived media/weather contract. Contradictory available media now fails closed without partial plan rendering; valid weather uses independent JSON values.
- 2026-07-11: Added `aria-busy`, live mutation status, and disabled-action coverage for alert reconciliation.
- 2026-07-11: Focused browser boundary passed 88 tests; complete browser gate passed 159 tests plus TypeScript/build/bundle audit; relevant FastAPI tests passed 16. Evidence: `.10x/evidence/2026-07-11-trip-planner-browser-boundary.md`.
- 2026-07-11: Final independent review passed. Review: `.10x/reviews/2026-07-11-trip-planner-browser-boundary-review.md`.
- 2026-07-11: Retrospective preserved client-owned errors and exact bounded relational validation as reusable browser trust-boundary tests; no additional skill record is needed.

## Blockers

None.
