Status: active
Created: 2026-07-09
Updated: 2026-07-09

# Define Arizona catalog, manual observation, and watch-match boundaries

## Context

The product expansion ratified in `.10x/decisions/local-single-user-birding-pokedex-expansion.md` requires concrete definitions for Arizona catalog membership, manual life-list entry, target-planning origin privacy, and which eBird records may cause an external watch alert.

Current source inspection found 706 eBird `US-AZ` regional taxa in the warehouse: 624 taxonomy rows categorized as species and 82 categorized as hybrids. eBird records expose stable submission IDs, reviewed/valid flags, private-location flags, observation timestamps, and coordinates; refreshes overlap a rolling 30-day window.

## Decision

1. The initial Arizona catalog will include all 706 taxa currently returned by eBird's `product/spplist/US-AZ`: recognized species and named hybrids. Category MUST remain visible/filterable so hybrids are not represented as ordinary species.
2. A manual observation MUST identify one conformed catalog taxon and an observation date. Arizona location and notes are optional.
3. A life list will be derived as the unique taxa represented by non-deleted manual observation records; it will not be stored as a boolean on the species catalog.
4. Target-bird planning MUST require an origin and maximum travel radius for each request. Those inputs MAY persist with that report but Databox will not create a global home-location setting in the first workflow.
5. A watch match may use only a newly eligible eBird Arizona record that is valid, reviewed/confirmed, non-private, and has usable public destination coordinates or a public hotspot location.
6. Refresh overlap MUST NOT recreate matches. Source submission/natural keys, watch identity, and a durable match/alert ledger will govern deduplication.

## Alternatives considered

- **Species-only catalog:** rejected; the user explicitly selected species and hybrids.
- **Recently observed catalog:** rejected because it would omit legitimate regional taxa and fluctuate with the rolling window.
- **Species-only life-list flag:** rejected because it loses observation date/history and cannot represent repeat sightings.
- **Require location for every manual observation:** rejected; species and date are sufficient for the initial personal record.
- **Persist a home location:** rejected for the first slice in favor of per-request origin privacy.
- **Allow provisional/unreviewed sightings:** rejected because external calendar/email side effects require stronger match quality.
- **Notable-only alerts:** rejected because watched targets may be ordinary in the reported locality and absent from the notable feed.

## Consequences

- Species/category labels and hybrid handling must remain explicit throughout catalog, search, life list, wishlist, watches, and reports.
- Manual observation deletion/editing semantics and audit retention still require specification.
- Watch area, freshness, cooldown/deduplication, event scheduling, report failure, SMTP retry, retention, and operational ownership remain blocked before the alert specification can become active.
- Private eBird locations must never be emitted as alert destinations or exposed to the browser through this workflow.
