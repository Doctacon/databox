Status: blocked
Created: 2026-07-09
Updated: 2026-07-09
Parent: None
Depends-On: None

# Build the local birding Pokédex

## Aggregate outcome

Expand Databox from a Trip Planner into a local, single-user Arizona birding Pokédex while preserving the planner, one-DuckDB architecture, server-side credentials, strict Cloudflare/ADK contract, and open-source-first posture.

This is a parent plan and is not executable directly.

## Governing records

- `.10x/decisions/local-single-user-birding-pokedex-expansion.md`
- `.10x/decisions/arizona-catalog-observation-and-watch-match-boundaries.md`
- `.10x/decisions/watched-bird-alert-delivery-policy.md`
- `.10x/decisions/proton-bridge-smtp-for-bird-alerts.md`
- `.10x/research/2026-07-09-local-birding-pokedex-watch-architecture.md`
- `.10x/specs/local-only-databox-platform.md`
- `.10x/specs/local-birding-trip-copilot-app.md`
- `.10x/specs/birding-agent-data-integrations.md`

## Planned specification and delivery sequence

0. Compact the existing planner independently through `.10x/tickets/2026-07-09-compact-and-paginate-trip-plan-results.md`.
1. Specify the local app shell/navigation and Arizona species catalog/profile.
2. Specify manual observation records, derived life list, wishlist, and per-species watch management.
3. Specify origin/radius target-bird planning and its relationship to species profiles and existing planner artifacts.
4. Specify post-refresh watched-bird matching, report generation, calendar selection, outbox, SMTP delivery, update/cancel behavior, and operations.
5. Create bounded implementation children from those focused active specifications.
6. Run aggregate data/privacy/security/accessibility/side-effect verification and independent review.

Catalog/profile must precede personal collection and target workflows because they require a stable conformed taxon identity. Watch management requires catalog identity and local personal-state APIs. Alert execution requires watches, transformed eBird evidence, persisted species profiles, and a hardened operational specification.

## Aggregate acceptance direction

- Navigation exposes Trip Planner, Arizona Birds/species detail, and My Birds surfaces without accounts.
- The catalog includes eBird `US-AZ` species and hybrids with explicit category labels.
- Manual species/date observations derive a unique life list; optional Arizona location/notes remain personal local data.
- Wishlist and watch state remain independent from observed state.
- Bird-first planning requires per-request origin and maximum radius.
- Watches use only new, public, valid, reviewed eBird evidence within their radius and 48-hour freshness window.
- One active five-day calendar event per watched taxon is created/updated through stable iCalendar identity and a durable SMTP outbox after successful full refresh.
- Deterministic persisted facts produce an honest degraded report if GLM 5.2 is unavailable; no alternate model is used.
- Turbo-search retrieval uses approved namespaces with citations, source licensing, freshness, and persistence boundaries explicitly specified.
- No private eBird location, SMTP secret, recipient address, personal origin/observation data, or arbitrary retrieved content leaks into browser bundles, logs, traces, or committed files.

## Explicit exclusions

- Multi-user accounts, remote profiles, social features, public deployment, Google Calendar API, image recognition, automated eBird life-list import in the first personal-observation slice, and alerts from GBIF/Xeno-canto.

## Progress and notes

- 2026-07-09: User ratified the local single-user expansion, manual-only first life-list input, origin/radius target planning, and eBird-triggered email/iCalendar alerts.
- 2026-07-09: User ratified species+hybrid Arizona catalog membership, species/date observation grain, per-request origin privacy, and public reviewed/confirmed match eligibility.
- 2026-07-09: User ratified per-watch center/radius, 48-hour freshness, one updateable five-day event per watched taxon, best morning window, post-full-refresh execution, confirmed-location clustering, deterministic degraded report behavior, and bounded safe SMTP retries.
- 2026-07-09: Existing source inspection established 706 Arizona regional taxa, daily/30-day eBird ingestion, source natural keys, reviewed/private flags, and the need for a durable watermark/match/outbox ledger.
- 2026-07-09: User configured generic SMTP through local Proton Mail Bridge and authorized one bounded test message plus one bounded iCalendar invitation during verification. No configuration value or personal address was recorded.

## Blockers

- Approved/licensed bird-information sources and turbo-search runtime versus refresh-time persistence policy.
- Species-profile content contract and citation/freshness behavior.
- Exact morning-window scoring and calendar update/expiration/cancellation semantics.
- Manual observation edit/delete behavior and personal/alert retention policy.
- Retry timing and delivery-unknown operator workflow; Proton Bridge SMTP setup and bounded live-test authorization are complete.
