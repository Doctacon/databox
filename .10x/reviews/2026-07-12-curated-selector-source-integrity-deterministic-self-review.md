Status: recorded
Created: 2026-07-12
Updated: 2026-07-12
Target: `.10x/tickets/cancelled/2026-07-12-repair-curated-selector-source-integrity.md` deterministic implementation phase
Verdict: concerns

# Curated selector source-integrity deterministic self-review

## Findings

No deterministic code blocker remains in the implemented phase.

- The selector no longer contains the reviewed relevance-limited `wbsearchentities` translation. Exact P225 equality is resolved by the bounded SPARQL query already defined by the selector, retaining the two-row ambiguity boundary.
- Redirect following is disabled at the HTTP client and the final response endpoint is checked before body processing. Deterministic changed-origin tests cover the reviewed private-network and credential/origin cases.
- The Commons request moved to the next lower provider tier while the existing exact provider URL validator still rejects any returned width above 1024. The fixture models the reviewed 1280 rounding behavior and proves Wikimedia activation/no iNaturalist call under the lower request.
- Provider observability is bounded to fixed derived keys and is updated atomically with the persisted catalog photo checkpoint. Existing run tables receive a safe empty-counter backfill; interrupted lookups that never checkpoint do not falsely increment outcomes.

## Concern

The Commons and Wikidata fixes are necessarily unconfirmed against current live provider behavior because this phase explicitly prohibited live probes. The ticket therefore cannot close and current catalog/planner rows must not be treated as repaired until serialized live re-evaluation, preservation fingerprints, provider counts, and aggregate rereview complete after the other persistence repairs.

## Verdict

Concerns: deterministic implementation and focused tests pass, but the ticket remains blocked on its explicitly deferred live/provider and migration evidence. No full-suite or live claim is made.

## Residual risk

Provider endpoint behavior can change, the Query Service may be operationally unavailable, and the provider may return no acceptable <=1024 derivative for a candidate. All such cases remain fail closed, but only the deferred live phase can establish current production selection counts.
