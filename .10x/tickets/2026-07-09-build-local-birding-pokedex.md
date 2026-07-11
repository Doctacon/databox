Status: open
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
- `.10x/decisions/avonet-atomic-staged-publication.md`
- `.10x/decisions/personal-collection-and-target-planning-lifecycle.md`
- `.10x/decisions/bird-alert-retry-and-event-lifecycle.md`
- `.10x/research/2026-07-09-local-birding-pokedex-watch-architecture.md`
- `.10x/specs/avonet-bird-traits-source.md`
- `.10x/specs/arizona-bird-catalog-and-profile.md`
- `.10x/specs/personal-bird-collection.md`
- `.10x/specs/target-bird-planning.md`
- `.10x/specs/watched-bird-matching-and-reports.md`
- `.10x/specs/bird-alert-calendar-and-smtp-delivery.md`
- `.10x/specs/local-only-databox-platform.md`
- `.10x/specs/local-birding-trip-copilot-app.md`
- `.10x/specs/birding-agent-data-integrations.md`

## Planned specification and delivery sequence

0. Compact the existing planner independently through `.10x/tickets/done/2026-07-09-compact-and-paginate-trip-plan-results.md`.
1. Add the AVONET source through `.10x/tickets/done/2026-07-09-add-avonet-bird-traits-source.md`.
2. Build modeled traits/catalog through `.10x/tickets/done/2026-07-09-model-avonet-traits-and-arizona-catalog.md`.
3. Build the read-only catalog/profile UI through `.10x/tickets/done/2026-07-09-build-arizona-bird-catalog-and-profile.md`.
4. Implement personal collection storage/API through `.10x/tickets/done/2026-07-10-implement-personal-bird-collection-storage-and-api.md`, then My Birds/profile controls through `.10x/tickets/done/2026-07-10-build-my-birds-and-profile-controls.md`.
5. Implement species-first planning through `.10x/tickets/done/2026-07-10-implement-target-bird-planning.md` (parallelizable after catalog completion).
6. Implement post-refresh matching/reporting through `.10x/tickets/done/2026-07-10-implement-watched-bird-evaluator-and-reports.md`.
7. Build event/outbox mechanics through `.10x/tickets/done/2026-07-10-build-bird-alert-calendar-and-outbox.md`, then Proton Bridge delivery/operations through `.10x/tickets/2026-07-10-implement-proton-bridge-alert-delivery-and-operations.md`.
8. Run aggregate verification through `.10x/tickets/2026-07-10-verify-local-birding-pokedex.md`.

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
- 2026-07-09: Planner compaction completed with independent four-card recommendation pages, collapsed 20/50/100 evidence pagination, 58 frontend tests, and independent pass review.
- 2026-07-09: User rejected external narrative profiles and selected AVONET v7 as the only new modeled bird-trait source. Source inspection established CC BY 4.0, exact pinned file identity, 10,661 eBird-aligned rows, and current exact Arizona coverage of 600/624 species with 24 taxonomy-drift species and 82 hybrids explicitly unavailable.
- 2026-07-09: Activated focused AVONET source and Arizona catalog/profile specifications and opened three dependency-ordered implementation tickets.
- 2026-07-10: AVONET source child completed after critical repair from unsupported direct replacement to transient Quack staging plus validated atomic post-Quack publication; 105 focused tests and independent final review passed.
- 2026-07-10: Trait/catalog model child completed after repairs for complete-snapshot membership and coherent public-location tuples; 13 SQLMesh tests, exact 706/624/82/600/24 coverage measurement, and independent final review passed.
- 2026-07-10: Live AVONET bootstrap and production model apply completed. A production-only external-schema star-expansion lint blocker was repaired with explicit projections; prod now has no diff and live catalog counts/privacy/location checks pass.
- 2026-07-10: Read-only Arizona catalog/profile completed with exact 706/624/82 browser/API guards, 600 exact AVONET matches, accessible native routes, strict modeled profiles, privacy/access semantics, 27 focused Python tests, 72 browser tests, a green 307-test Python suite, and independent pass review.
- 2026-07-10: User ratified manual observation edit plus hard delete, personal collection retention until explicit deletion, 90-day alert-history retention, existing planner date/time/duration inputs for target-bird planning, and freshness-first watched-bird morning selection.
- 2026-07-10: User ratified 1–300-mile target radius, stable-UID sliding event updates, cancellation on paused/deleted watches, natural expiry, 1/5/15-minute pre-acceptance retries, and manual reconciliation of delivery-unknown outcomes. Four focused active specifications and seven dependency-ordered implementation/verification tickets now govern the remaining work.
- 2026-07-10: Personal collection storage/API completed with transactional observation/life-list/wishlist/watch state, stale identity handling, strict monotonic mutation time, generation-safe cancellation handoffs, 324-test full-suite evidence, and independent pass review.
- 2026-07-10: My Birds/profile controls completed with strict collection validation, accessible local mutation flows, shared cross-route serialization/invalidation, 103 browser-test evidence, and independent pass review.
- 2026-07-10: Target-bird planning completed with exact public candidate ranking, full strict GLM grounding, atomic weather/report persistence, 344 Python and 122 browser tests, and independent pass review.
- 2026-07-11: Watched-bird evaluator/reporting completed with post-refresh-only exact matching, privacy-safe deterministic/GLM reports, generation-bound event intent, 362 Python tests, and independent pass review.
- 2026-07-11: Calendar/outbox mechanics completed with RFC REQUEST/CANCEL MIME, fail-closed relational state, atomic claims/recovery, 390 Python tests, and independent pass review.

## Blockers

None; execute the open child tickets in dependency order.
