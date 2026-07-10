Status: active
Created: 2026-07-10
Updated: 2026-07-10

# Target-bird planning

## Purpose and scope

This specification governs “Find this bird” from an Arizona catalog profile. It creates a target-specific local plan from modeled public eBird evidence, request-time weather, and the sole Cloudflare model `@cf/zai-org/glm-5.2`. It does not change the existing multi-bird Trip Planner or use personal observation history.

## Request contract

A request MUST include:

- one current Arizona catalog species code;
- one origin resolved through the existing Arizona polygon boundary, including display name and coordinates;
- radius in miles, inclusive 1 through 300;
- naive Arizona local start date/time and duration in minutes using the existing planner contract (1 through 1440 minutes).

No global origin is loaded or saved. Responses display distance in miles and kilometers. A date outside available forecast coverage is allowed; weather becomes explicitly unavailable rather than changing the requested outing.

## Candidate evidence

Candidates MUST come only from persisted `environmental_observations.fact_bird_observation` rows for the target species that are valid, reviewed, non-private, have coordinates, and fall inside the requested Haversine radius. The source's current retained/recent window is authoritative; the product MUST display observation dates and source/model freshness and MUST NOT describe the evidence as a guarantee of presence.

Cluster by stable public location ID. Rank locations deterministically by independent submission count descending, newest observation descending, distance ascending, location name, and location ID. Return at most ten candidates. Location display name/coordinates MUST come from one coherent newest ranked row. Private rows MUST affect neither candidates nor counts.

If no candidate exists, persist and show an honest empty-evidence plan; do not broaden radius, use private rows, infer a parent taxon, or query the network for sightings.

## Weather and report

Open-Meteo MAY be called only after candidate ranking and only for the requested origin/window using the existing bounded tool. Weather status is available, partial, or unavailable with caveats.

The GLM report MUST use strict bounded JSON Schema and only the exact target identity, request, ranked candidate facts, distances, source freshness, and normalized weather evidence. It MUST NOT add sightings, field marks, habitat claims, access permission, seasonality, or safety claims absent from inputs. Only `@cf/zai-org/glm-5.2` is permitted; no fallback model, parser repair, retry weakening, or timeout weakening.

Model failure MUST fail plan creation atomically and expose a safe retryable error, matching the existing planner contract. An evidence-empty request may still produce a bounded report that says no qualifying modeled location exists; the model may not invent alternatives.

## Persistence and API

One transaction MUST persist the plan request, exact resolved origin, target identity, candidates, weather evidence, model report, provenance, and sanitized tool/model traces. Partial plans MUST roll back. GET list/detail endpoints are network-free and read-only. POST creation is serialized and returns busy/conflict safely.

The plan artifact stores origin because it is necessary to reproduce the plan; it MUST NOT update a global setting or influence later planner requests. Personal collection state MUST NOT be read or included in prompts.

## Browser behavior

Every current species/hybrid profile exposes “Find this bird.” The form requires origin, radius, start, and duration. Results clearly separate target, travel boundary, candidate public locations/distances, evidence dates/counts, weather, deterministic caveats, GLM guidance, and provenance. Hybrids without exact AVONET traits remain valid targets; no parent inference occurs.

Native controls, loading/errors, focus, direct route/history behavior, responsive layout, and units MUST be accessible. No credential/config value enters the bundle.

## Acceptance scenarios

- Candidate locations inside 300 miles rank by the exact deterministic rules and display both units.
- Outside-radius/private/invalid/unreviewed/wrong-species rows have zero effect.
- Equal-count/equal-date candidates use distance then stable text/ID tie-breaks.
- No evidence returns a persisted honest empty plan without radius expansion.
- Weather unavailable remains a valid evidence state; GLM failure rolls back all new artifacts.
- GET replay performs no source/weather/model lookup or write and reproduces the persisted report.
- Existing Trip Planner recommendations remain independent from personal history and target plans.

## Explicit exclusions

No saved home location, route optimization, map, driving-time API, access guarantee, push notification, personal-history personalization, external bird-fact retrieval, alternate model, or automatic watch creation.
