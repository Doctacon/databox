Status: active
Created: 2026-07-11
Updated: 2026-07-11

# Watch-only collection supersession scope

## Context

The user ratified Watch as the sole prospective-interest state and complete Wishlist removal. `.10x/decisions/catalog-media-and-watch-only-collection.md` recorded that semantic change but named only `.10x/decisions/personal-collection-and-target-planning-lifecycle.md` as partially superseded. `.10x/decisions/local-single-user-birding-pokedex-expansion.md` independently described Wishlist, observation, and Watch as separate states, leaving contradictory active authority despite correct implementation and specifications.

## Decision

The Wishlist portions of both active decisions are superseded:

- `.10x/decisions/personal-collection-and-target-planning-lifecycle.md`
- `.10x/decisions/local-single-user-birding-pokedex-expansion.md`

Only their Wishlist requirements and statements of Wishlist independence lose authority. Their observation, derived life-list, Watch, target-planning, retention, privacy, runtime-ownership, and other unrelated decisions remain active.

Watch is the sole prospective-interest state. Wishlist MUST NOT exist in current storage, API, browser state, UI, or product documentation, and retired Wishlist rows MUST NOT be converted into Watches because Watch requires explicit center/radius semantics.

## Alternatives considered

- Supersede either broad decision entirely: rejected because each still governs substantial implemented behavior.
- Edit the accepted historical decisions: rejected because accepted decisions are immutable.
- Treat the newer implementation as implicit precedence: rejected because contradictory active authority would remain for cold-start readers.

## Consequences

The decision graph now agrees with `.10x/specs/personal-bird-collection.md`, the completed migration, absence tests, and the current Watch-only product. Future changes to reintroduce Wishlist require a new explicit superseding decision and specification.
