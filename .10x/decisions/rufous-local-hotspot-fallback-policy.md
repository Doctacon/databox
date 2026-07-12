Status: active
Created: 2026-07-11
Updated: 2026-07-11

# Rufous local hotspot fallback policy

## Context

`.10x/decisions/rufous-local-place-suggestions-and-feedback.md` originally selected merging Open-Meteo results whenever local suggestions left spare response capacity. The subsequently ratified eBird-first behavior requires `lake watson` and every other query with at least one valid local hotspot match to make zero upstream calls. The prior capacity-fill wording conflicts with that privacy and determinism boundary.

## Decision

This decision supersedes only item 1's capacity-fill fallback behavior in `.10x/decisions/rufous-local-place-suggestions-and-feedback.md`; its other decisions remain active.

Rufous MUST call Open-Meteo only after local hotspot search returns zero valid matches. Any valid local match suppresses the upstream request. Suggestion deduplication treats rows as near-identical only when their normalized display labels are equal and both latitude and longitude differ by no more than 0.001°; the local hotspot wins.

## Alternatives considered

- Fill remaining capacity after local matches: rejected because it adds a runtime network request despite a successful local answer and violates the explicit Watson zero-upstream criterion.
- Suppress fallback only for exact normalized-name matches: rejected because it makes network behavior depend on query phrasing and would not suppress fallback for the token-order-reversed `lake watson` query.
- Distance-only deduplication: rejected because distinct named places can share or nearly share coordinates.

## Consequences

Queries with local matches remain fully local, deterministic, and network-free but do not mix city results into the same response. Open-Meteo remains a bounded zero-local fallback. The 0.001° same-label rule is mechanically testable and local-wins behavior is stable.
