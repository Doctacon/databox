Status: active
Created: 2026-07-11
Updated: 2026-07-11

# Rufous product shell and retro visual system

## Purpose

This specification governs the user-visible Rufous identity and cohesive original GBA-era birding-device visual system across every route. It changes presentation, not repository/package identity or product behavior.

## Naming

- Header brand, document titles, loading/error copy where product-named, API display title, README screenshots/descriptions, and local app documentation MUST use **Rufous**.
- “Trip Planner,” “Arizona Birds,” and “My Birds” remain functional section names.
- Repository name `databox`, Python imports, database path/schema names, environment names, source pipeline names, migration identity, and historical records MUST NOT be mechanically renamed.
- User-visible source attribution may still name Databox where it describes persisted technical provenance; it MUST not present Databox as the product brand.

## Visual tokens

Define one local CSS token system:

- rust-orange primary shell and action color inspired by Rufous Hummingbird plumage;
- deep teal and ocean-blue screen surfaces;
- warm cream/gold highlights;
- dark plum/navy ink and border;
- success/warning/error colors with accessible contrast independent of hue;
- stepped/pixel-like radii, 2–4px dark borders, offset shadows, compact 8px grid, and layered device panels.

Typography uses local system monospace/display stacks with readable body fallback. No remote font request. Uppercase/pixel styling is reserved for short labels; prose remains readable.

## Original artwork and motion

The shell MAY include original inline SVG/CSS Rufous bird silhouette, wing/device indicators, subtle screen texture/scanline, and pixel status icons. It MUST NOT include or trace Pokémon sprites, logos, fonts, sounds, names, copyrighted UI assets, or exact game layouts.

Animation is minimal, functional, and disabled/reduced under `prefers-reduced-motion`. No flashing, autoplay, parallax, or distracting infinite motion.

## Components and routes

Apply the system consistently to:

- primary header/navigation and responsive mobile navigation;
- planner form/history/results/recommendation cards/evidence;
- Arizona catalog media cards, filters, pagination, profiles;
- My Birds observation/life-list/watch panels and dialogs;
- target-plan forms/results/weather/evidence;
- alert/invite operation status and confirmations;
- loading, empty, error, unavailable-media, stale, busy, success, and caveat states.

Controls remain native where possible. Cards and panels MUST preserve semantic heading/list structures. Links/buttons/selects/inputs/dialogs/audio controls require visible hover, active, disabled, and `:focus-visible` states. Touch targets SHOULD be at least 44px where layout permits.

## Responsive and accessibility

The visual system MUST work at narrow mobile, tablet, and desktop widths without horizontal overflow, clipped media/audio, or inaccessible off-screen dialogs. Text zoom and long scientific/location strings must wrap. Contrast, focus, keyboard, dialog trap/return, live/busy announcements, reduced motion, native audio semantics, image alt text, and non-color statuses remain mandatory.

## Acceptance scenarios

- Every route shows Rufous identity and shared tokens without changing URLs or persisted IDs.
- Mobile catalog/planner/My Birds layouts remain operable at 320px and desktop layouts use available space coherently.
- Keyboard-only navigation exposes visible focus and all actions.
- Reduced-motion disables decorative movement/scanline animation.
- Missing media, source errors, stale taxa, and delivery unknown states remain explicit and readable.
- Exact scans find no copied Pokémon asset/name/font dependency and no remote theme/font request.

## Explicit exclusions

No repository/package/database rename, copyrighted Pokémon asset, exact replica, remote font/theme service, frontend framework/router replacement, canvas game, or product behavior change.
