Status: active
Created: 2026-07-11
Updated: 2026-07-11

# Rufous local place suggestions and transient feedback

## Context

Open-Meteo autocomplete primarily returns cities, so birding/natural places such as “lake watson” are not discoverable. Rufous already stores 2,912 Arizona eBird hotspots, including Watson Lake. Personal observations accept only free-text location. Success banners persist indefinitely. Field Map boundaries render but encounter data can miss initial source load, and Selected Encounter is outside the intended right rail.

This decision supersedes only the free-text-only/no-geocoding portions of `.10x/decisions/personal-collection-and-target-planning-lifecycle.md`; observation lifecycle, retention, privacy, and all unrelated decisions remain active.

## Decision

1. Location suggestions search local Arizona eBird hotspots first using token-order-independent deterministic matching, then merge the existing Open-Meteo Arizona city fallback when capacity remains.
2. Suggestions expose canonical source, source ID, type label, display name, coordinates, timezone, and region through one strict contract. Local results require no runtime network. Open-Meteo failure does not hide valid local results.
3. Trip Planner, target planning, Watches, and observation entry reuse the same combobox/API.
4. Observation location remains optional. Selecting a suggestion persists canonical structured identity/coordinates/timezone plus the display label. Unselected text remains a private free-text location with structured fields null. No background or save-time geocoding occurs.
5. Every Rufous success message auto-dismisses exactly three seconds after it appears. Repeated success resets the timer; errors persist; unmount clears timers.
6. Field Map encounter data is applied only after MapLibre source readiness and on every filter change. Selection visibly highlights and pans/zooms to the encounter. Desktop uses map left and right rail with Selected Encounter above Accessible Encounter List; narrow screens stack selected card before list.
7. Overture, local OSM/Nominatim, and GeoNames are deferred. They require separate evidence, licenses, ingestion/update ownership, and user-ratified source scope.

## Alternatives considered

- Overture Places/Base now: rejected as unnecessary release/license/ingestion complexity for a case already covered locally.
- Local OSM/Nominatim: broad but operationally heavy.
- GeoNames: lightweight but weaker observed coverage for the named case.
- Store observation display text only: rejected because it discards selected coordinates/source identity.
- Require structured observation location: rejected because optional private notes and legacy rows remain valid.
- Auto-dismiss only observation creation: rejected because the user explicitly selected all Rufous success messages.
- Map overlay or three-column selected card: rejected in favor of the selected-above-list right rail.

## Consequences

The private observation schema/API gains nullable all-or-none structured location fields and an idempotent migration. Existing rows remain free text. Location API/client contracts expand source metadata. Timer behavior becomes universal and test-clock-sensitive. No new dataset or runtime geocoder dependency is introduced.
