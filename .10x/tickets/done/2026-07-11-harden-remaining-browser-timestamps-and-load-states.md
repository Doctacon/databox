Status: done
Created: 2026-07-11
Updated: 2026-07-11
Parent: .10x/tickets/done/2026-07-10-verify-local-birding-pokedex.md
Depends-On: .10x/tickets/done/2026-07-11-harden-trip-planner-browser-boundary.md

# Harden remaining browser timestamps and load states

## Scope

Repair final aggregate UX trust-boundary findings: replace Date.parse-only validation in target, bird, and alert-delivery clients with strict ISO calendar/time validation that rejects impossible and non-ISO values; prevent My Birds empty states from rendering when initial collection or alert-history loading failed.

## Acceptance criteria

- Shared or equivalent strict validators reject impossible leap days/month days, non-ISO values such as `0`, invalid offsets/times, nonfinite/oversized input, while accepting exact backend date/date-time forms.
- Target, bird catalog/profile, and alert-delivery response boundaries use strict validators for every date/timestamp field and fail without partial rendering.
- Adversarial tests cover February 29 in a non-leap year, April 31, invalid offset/time, non-ISO numeric string, valid leap/date/time/UTC/offset forms, and nested timestamp fields.
- My Birds initial load failure renders one safe error and no life-list/observation/wishlist/watch/alert empty claims; successful empty loads retain existing empty states. Retry/revision behavior remains coherent.
- Complete frontend tests, TypeScript, build, bundle/secret audit, relevant API tests, hooks, and accessibility contracts pass.

## Explicit exclusions

No backend contract, product workflow, styling redesign, planner logic, data mutation, or side effect.

## Evidence expectations

Record strict timestamp matrix, failed-load versus valid-empty DOM assertions, full gates, and independent review.

## Progress and notes

- 2026-07-11: Added one strict ISO date/timestamp utility with exact leap/month/time/offset validation and microsecond normalization; target, bird, and alert-delivery clients now use it for every governed field.
- 2026-07-11: Target duration uses parsed microseconds; date-only GBIF/Xeno fields reject timestamps, alert timestamps require timezone offsets, and nullable fields retain their backend contracts.
- 2026-07-11: My Birds now distinguishes successful empty collection/alert loads from initial failures and suppresses false empty sections after failure while preserving successful-empty and revision behavior.
- 2026-07-11: Focused adversarial browser gate passed 85 tests; complete frontend gate passed 199 tests plus TypeScript/build/bundle audit; 87 relevant backend/API tests, secret scan, and MyPy passed. Evidence: `.10x/evidence/2026-07-11-remaining-browser-timestamps-and-load-states.md`.
- 2026-07-11: Final independent UX review passed. Review: `.10x/reviews/2026-07-11-remaining-browser-timestamps-and-load-states-review.md`.
- 2026-07-11: Retrospective preserved strict ISO parsing and failed-load-versus-empty state invariants in a shared utility and adversarial UI tests; no additional skill record is needed.

## Blockers

None.
