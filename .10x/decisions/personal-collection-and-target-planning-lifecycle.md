Status: active
Created: 2026-07-10
Updated: 2026-07-10

# Personal collection and target-planning lifecycle

## Context

The local single-user Pokédex needs durable manual observations, derived life-list membership, independent wishlist/watch state, and species-first planning. Earlier records settled catalog identity and required per-request origin/radius but left mutation, retention, timing, and radius bounds unresolved.

## Decision

- Manual observation events require an Arizona catalog species code and observation date. Optional location and notes remain local personal data.
- A user may edit date, location, and notes. Deletion is a hard delete. Life-list membership is always derived from remaining observation events and disappears when the last event for a taxon is deleted.
- Personal observations, wishlist entries, and watch definitions remain until the user explicitly removes them; there is no automatic expiration.
- Wishlist, observed/life-list, and watched states are independent.
- “Find this bird” requires the existing planner date, local time, and duration inputs plus an Arizona origin and a travel radius from 1 through 300 miles. Results display both miles and kilometers.
- No global home location is persisted. Request origins remain attached only to the target-planning artifact they created.

## Alternatives considered

- Append-only or soft-deleted observations were rejected as unnecessary complexity for a single-user local product.
- Automatic personal-data expiration was rejected because it would undermine a durable life list.
- Unbounded or globally saved radius/origin settings were rejected for usability and privacy.
- Automatic next-five-day target timing was rejected in favor of explicit outing inputs consistent with the existing planner.

## Consequences

Personal APIs need transactional mutation and catalog validation; list membership must not be stored as an independent truth. Target planning can reuse Arizona resolution and timing conventions but needs a separate target-specific report, distance filtering, and persistence contract. Hard delete means deleted observation details are not recoverable by the app.
