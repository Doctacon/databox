Status: active
Created: 2026-07-11
Updated: 2026-07-11

# Rufous product identity and retro visual direction

## Context

The local product is functionally complete but visually generic and still presents the original Birding Trip Copilot working title. The user wants it named after the Rufous Hummingbird and wants the feel of the handheld Pokédex interfaces from the Game Boy Advance-era Pokémon Ruby, Sapphire, and Emerald games.

## Decision

- The user-facing product name is **Rufous**. Repository, Python package, database, source, model, and internal compatibility names remain unchanged unless they are directly user-visible.
- The interface will use an original GBA-era field-device visual language: rust-orange outer surfaces, teal/ocean screen panels, warm cream highlights, dark pixel borders, compact status modules, stepped corners, grid rhythm, and original bird/device motifs.
- The implementation MUST NOT copy Pokémon logos, sprites, fonts, icons, text, sounds, exact screen compositions, or other copyrighted assets. It MUST remain recognizably Rufous-specific rather than a replica.
- Styling will use local CSS and original inline SVG/CSS artwork. No proprietary theme, remote font service, tracking asset, or new runtime styling dependency is required.
- Native semantic controls, focus visibility, keyboard behavior, readable type, contrast, responsive layouts, reduced-motion preferences, and existing media safety remain stronger constraints than visual imitation.

## Alternatives considered

- Keeping the generic Birding Trip Copilot shell was rejected because the user explicitly wants a cohesive product identity.
- A closer Pokémon replica was rejected due to unnecessary copyright/trade-dress risk and weaker Rufous identity.
- Remote retro-font/theme dependencies were rejected in favor of local, auditable styling.

## Consequences

All product routes need one shared visual-system pass and user-visible naming audit. Snapshot/DOM/CSS tests must protect semantics and responsive behavior without encoding copyrighted layouts. Historical records and repository names continue using Databox where technically accurate.
