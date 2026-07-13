Status: recorded
Created: 2026-07-12
Updated: 2026-07-12
Relates-To: `.10x/tickets/done/2026-07-12-repair-curated-photo-frontend-contracts.md`, `.10x/specs/superseded/curated-representative-bird-photos.md`

# Curated-photo frontend contract repair evidence

## What was observed

Catalog/profile/map/planner browser paths now share `app/src/curatedPhotoValidation.ts` for available representative-photo validation. The shared boundary enforces exact scientific identity; provider and record identity; canonical allowed CC code/URL; bounded normalized plain-text creator and selection reason; dimensions; exact iNaturalist paths; and exact Wikimedia QID/file title, supported extension, MD5 path buckets, repeated filename, canonical source page, and thumbnail width no greater than 1024. Provider URLs reject credentials, explicit ports, query, fragment, traversal-shaped mismatches, and noncanonical forms.

Trip Planner unavailable and image-failure states render decorative Rufous artwork with meaningful visible text. Only the asynchronous failure state receives `role=status`. Field Map keeps its native encounter button and places canonical source/license links as siblings rather than invalid nested interactive controls; the links and attribution remain after an image failure, whose changed text receives a restrained status role.

## Procedure and results

- `cd app && npm run typecheck`: passed.
- Focused `vitest` run for `curatedPhotoValidation.test.ts`, `App.test.tsx`, `FieldMap.test.tsx`, `BirdPages.test.tsx`, and `tripPlanValidation.test.ts`: 5 files and 150 tests passed.
- The focused tests include direct Wikimedia MD5/title/hash/width/source/license/authority/traversal mutations, planner whole-response rejection including an extra photo field, Rufous placeholder/failure assertions, and Field Map persistent source/license/status assertions.
- `cd app && npm test`: 19 files and 300 tests passed.
- `cd app && npm run build`: strict TypeScript build and Vite production build passed. Vite emitted only the existing large lazy MapLibre chunk advisory.
- `cd app && ../.venv/bin/python ../scripts/audit_app_bundle.py`: passed; 12 configured names and 10 configured values were absent.
- `git diff --check`: passed.
- `git diff --name-only --cached`: empty.
- `app/src/FieldMap.test.tsx` contains 344 lines and a bounded `+48/-2` diff from repository base. An intermediate accidental empty-file edit was reconstructed from repository base plus the pre-existing independent hover/focus, photo fixture, and layer-order changes before adding this ticket's link/status assertions; focused and full suites passed afterward.

## What this supports

This supports the ticket criteria for one equivalent strict browser contract, adversarial planner/Wikimedia validation, Rufous planner placeholders, Field Map source/license retention, restrained semantic failure announcements, preserved native controls/focus/alt/lazy behavior, and complete frontend gates without live/network/project-database work.

## Limits

jsdom verifies response rejection, DOM semantics, links, alt text, and event-driven failure states, not physical rendering, actual remote image loading, responsive wrapping, contrast rasterization, or screen-reader announcement quality. No physical browser or assistive-technology session was performed. Provider-hosted images can later become unavailable; Rufous persists metadata, not binaries.
