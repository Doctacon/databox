Status: recorded
Created: 2026-07-11
Updated: 2026-07-11
Relates-To: .10x/tickets/done/2026-07-11-add-catalog-card-and-profile-media.md, .10x/specs/arizona-catalog-media.md

# Catalog card and profile media UI

## What was observed

Arizona Birds catalog cards and profiles render only strictly validated media supplied by the existing browser API boundary:

- Cards render responsive lazy 4:3 photos or an original Rufous silhouette unavailable state, compact source/license attribution, and accessible Play/Stop controls with `preload="none"`.
- Profiles render larger photos and full creator/publisher or recordist/type/quality/location/scope/source/license/selection/freshness attribution.
- Image and audio load failures retain attribution and expose visible bounded errors.
- Exactly one call can be active. Search, category, pagination, route changes, and component unmount stop and rewind active playback.
- Hybrid, taxonomy-drift, unavailable, malformed, unsafe-host/license/identity, and extra-field payloads remain unavailable or are rejected by the existing strict browser validator; no parent inference or partial URL activation occurs.
- Native buttons, pressed state, link navigation, heading focus, responsive single-column profile media, and existing mobile layouts remain intact.

The focused lifecycle regression initially failed on pagination because React cleared the unmounted audio element's DOM ref before passive cleanup invoked the stop callback. The player now retains only the currently playing element in a separate ref until stop/end. Cleanup therefore pauses and rewinds the actual element even after its render ref is detached. The lifecycle test was not weakened.

## Procedure and results

```text
cd app && npm test -- --run src/BirdPages.test.tsx
22 passed

 task app:check
TypeScript passed
205 Vitest tests passed across 11 files
Vite production build passed (40 modules; 256.22 kB JS, 14.13 kB CSS)
bundle configuration audit passed: 12 names and 10 configured values absent

.venv/bin/python scripts/check_secrets.py .
git diff --check
test -z "$(git diff --cached --name-only)"
passed; no staged files
```

The 22 focused cases include available/unavailable card media, original placeholder, lazy loading, concise and full attribution, one-active playback, search/filter/page/route/unmount cleanup, image/audio failure states, profile scope/selection/freshness, direct/history/focus behavior, hybrid and taxonomy-drift safety, and adversarial media identity/URL/license/shape/date validation.

## What this supports

This evidence supports every acceptance criterion in `.10x/tickets/done/2026-07-11-add-catalog-card-and-profile-media.md` and the browser behaviors in `.10x/specs/arizona-catalog-media.md`. The complete frontend regression, strict TypeScript, production build, bundle privacy audit, repository secret scan, diff check, and no-stage gate passed.

## Limits

Automated DOM behavior and responsive CSS contracts were verified. No separate screenshot or physical-device visual audit was run. Ticket closure and independent review remain parent-owned.
