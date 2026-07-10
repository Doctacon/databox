Status: active
Created: 2026-07-09
Updated: 2026-07-09

# Local birding Pokédex and watched-bird architecture

## Question

What existing Databox data and open standards can support an Arizona species catalog, manual life list, origin/radius target planning, and eBird-triggered email/calendar invitations without weakening the local-only architecture or inventing notification semantics?

## Sources and methods

- Inspected active Databox decisions/specifications and current eBird source, Dagster schedule, SQLMesh species conformance model, and local DuckDB read-only state.
- Inspected the official eBird API 2.0 reference and Arizona region/product entry points:
  - https://documenter.getpostman.com/view/664302/S1ENwy59?version=latest
  - https://ebird.org/region/US-AZ
  - https://science.ebird.org/en/use-ebird-data/download-ebird-data-products
- Inspected Arizona Field Ornithologists resources, including https://www.azfo.org/ebirdgapsproject. The inspected material did not establish a machine-readable formal official Arizona checklist contract.
- Inspected open calendar/email standards:
  - RFC 5545 iCalendar: https://datatracker.ietf.org/doc/rfc5545/
  - RFC 5546 iTIP scheduling: https://datatracker.ietf.org/doc/rfc5546/
  - RFC 6047 iMIP email transport: https://datatracker.ietf.org/doc/rfc6047/
- Surveyed open-source invitation/outbox examples including `adrium/icsinviter`, `python-caldav`, and outbox/idempotent event-ID patterns. These are implementation references, not selected dependencies.

## Findings

### Existing Arizona catalog substrate

Databox already ingests eBird's `product/spplist/US-AZ` regional species list and complete eBird taxonomy. On 2026-07-09 the local warehouse contained:

```text
raw_ebird.species_list = 706 regional codes
joined taxonomy category=species = 624
joined taxonomy category=hybrid = 82
raw_ebird.taxonomy = 17,891 rows
```

This is a strong reproducible catalog substrate, but “all Arizona birds” still needs a product definition: recognized species only versus inclusion of hybrids and whether regional-list membership means ever recorded rather than expected/current.

### Existing watch substrate

The eBird source loads Arizona recent and notable observations by `subId`, with latitude/longitude, location ID/name, observation timestamp, provisional/reviewed flags, private-location flag, and normalized species code. It currently requests a 30-day window and runs daily at `0 6 * * *` when the Dagster scheduler is active.

Read-only state on 2026-07-09:

```text
recent observations: 389; date range 2026-06-08 through 2026-07-09; 139 private
notable observations: 2,143; date range 2026-06-08 through 2026-07-09; 371 private
```

Because every refresh rereads an overlapping window and dlt merges by submission ID, an alert evaluator MUST use durable source natural keys and an alert/match ledger. It cannot equate “present in the latest load” with “new sighting.”

Private-location records should not produce actionable destination alerts. A safe first contract should exclude `location_private=true`, require valid Arizona coordinates, and prefer named public hotspots when available.

### Trigger/source semantics

The user's eBird-only selection is appropriate:

- eBird recent observations represent direct sighting evidence.
- GBIF occurrence records can be delayed or historical.
- Xeno-canto represents recordings and is not equivalent to a current sighting signal.

The current source includes provisional observations. Alert eligibility must explicitly decide whether provisional/unreviewed records are allowed. Notable status alone is not sufficient evidence quality.

### Calendar delivery

A standard calendar invitation can remain provider-neutral:

- RFC 5545 defines the event payload.
- RFC 5546 defines scheduling semantics such as `METHOD:REQUEST`, stable `UID`, and sequence/update behavior.
- RFC 6047 defines email/MIME transport.

The recipient can be configured server-side while SMTP remains configurable. Direct Google Calendar API access is unnecessary for the selected first contract.

Email is not transactionally atomic with DuckDB. A durable outbox is required with a deterministic calendar UID/message identity, explicit pending/sent/failed states, attempt timestamps, sanitized failure details, and bounded retry policy. “Exactly once” delivery cannot be claimed across an ambiguous SMTP outcome; the contract must define deduplication and operator-visible uncertainty.

### Local operational boundary

Alerts only evaluate when the local scheduler and source refresh run. The product must say this plainly; a local-only laptop process cannot guarantee continuous monitoring while stopped or asleep. SQLMesh must complete successfully before matches use conformed species/location evidence. DuckDB/Quack ownership must remain single-writer-safe.

### Turbo-search

Turbo-search is suitable for retrieving cited context from approved indexed sources and for implementation research against indexed ADK/DeepEval documentation. Runtime species dossiers require separately approved bird-information namespaces, source licensing/attribution rules, freshness, retrieval failure behavior, and a decision about whether retrieved summaries are persisted. Retrieval capability does not grant content-reuse rights.

## Current recommendations

1. Define the first catalog as eBird `US-AZ` regional membership joined to eBird-first conformed taxonomy; show recognized species by default and make non-species categories an explicit policy choice.
2. Store manual observation events, not a life-list boolean; derive unique life-list membership from those events.
3. Require origin and maximum distance per target-bird request initially; do not persist a home location without an explicit privacy choice.
4. Evaluate watches only after successful eBird ingestion and transformation, against newly observed public/non-private records and a durable watermark/match ledger.
5. Aggregate matches and persist an outbox before SMTP delivery; use stable iCalendar UID and no direct Google API.
6. Separate factual match/routing from report prose. Model failure, SMTP failure, retries, deduplication, and event timing remain blocked semantics.

## Limits and unresolved questions

- The official eBird reference must be rechecked for exact current endpoint/result/radius limits before implementation.
- AZFO material inspected did not establish a formal machine-readable checklist authority.
- Gmail-specific invitation rendering/acceptance was not treated as a protocol guarantee.
- Catalog category policy, observation required fields, target-planning distance units/limits, provisional-observation eligibility, freshness, deduplication, cadence, event timing, retry/failure behavior, retention, and operational ownership remain unratified.
