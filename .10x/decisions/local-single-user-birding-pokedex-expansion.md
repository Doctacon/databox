Status: active
Created: 2026-07-09
Updated: 2026-07-09

# Expand Databox into a local single-user birding Pokédex

## Context

Databox currently presents a local Birding Trip Copilot and its active workflow specifications explicitly exclude stored personal sightings, a life list, and separately user-facing species workflows. The user wants to retain the successful planner while expanding the product into a Pokémon-style Arizona bird catalog with personal collection and watch workflows.

The expansion must preserve the active local-only architecture: one local DuckDB, browser access only through FastAPI, Python/Google ADK, Cloudflare Workers AI model `@cf/zai-org/glm-5.2` only, open-source-first dependencies, and server-side credentials.

## Decision

Databox will expand into a local, single-user birding Pokédex with these product surfaces:

1. The existing Trip Planner remains a first-class page.
2. An Arizona Birds catalog and species-detail workflow will provide browsable, cited species information.
3. A local personal observation ledger will support a unique-species life list. Initial observation entry will be manual only.
4. Wishlist membership, observation history, and watch state will be modeled independently because one species may belong to all three simultaneously.
5. A bird-first planning workflow will require an Arizona origin and maximum travel radius before ranking locations and producing a finding report.
6. Watched-bird alerts will initially trigger only from newly ingested eBird observations, not GBIF occurrences or Xeno-canto recordings.
7. The first external delivery mechanism will be a standard iCalendar invitation sent by configurable SMTP to a server-side configured recipient. Direct Google Calendar API/OAuth integration is not selected.
8. User accounts, remote profile state, and multi-user authorization remain out of scope.

This decision explicitly supersedes the no-life-list, no-stored-sightings, and no-separate-species-workflow product exclusions in `.10x/specs/birding-trip-copilot.md` and `.10x/specs/local-birding-trip-copilot-app.md`. It does not authorize implicit use of life-list history by the existing trip planner; that requires a separate behavioral contract.

## Alternatives considered

- **Keep Trip Planner only:** rejected because it does not support the requested catalog, collection, target-finding, or watch workflows.
- **Add user accounts now:** rejected because the product remains local and single-user; authentication would add security and migration complexity without a named requirement.
- **Use one species status:** rejected because observed, wishlisted, and watched are independent facts.
- **Import eBird history first:** rejected for the first slice; manual entry is the selected initial life-list mechanism.
- **Choose the best location statewide:** rejected because target-finding must respect the user's origin and travel radius.
- **Trigger from every bird dataset:** rejected because GBIF can be delayed and Xeno-canto recordings are not equivalent to current sighting evidence.
- **Write directly to Google Calendar:** rejected for the first slice in favor of open iCalendar and SMTP, minimizing proprietary integration and credential scope.

## Consequences

- Existing active specifications must be reconciled so the planner remains behaviorally isolated while the broader app may store personal observations.
- Focused specifications are required for the app shell, Arizona species catalog/profile, observation/life-list behavior, target-bird planning, and watched-bird alerts.
- Personal observation data remains local in `data/databox.duckdb`; secrets and recipient configuration must not enter browser assets, traces, logs, or committed files.
- Watch delivery requires explicit contracts for match geography, freshness, deduplication, cadence, calendar timing, failure/retry behavior, retention, and operational ownership before execution.
- Turbo-search may be used for cited retrieval from approved indexed sources, but indexing/retrieval does not grant content-reuse rights; source licensing and attribution remain separate requirements.
