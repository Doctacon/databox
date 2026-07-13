Status: done
Created: 2026-07-12
Updated: 2026-07-12
Parent: `.10x/tickets/done/2026-07-11-verify-curated-representative-photos.md`
Depends-On: `.10x/tickets/done/2026-07-11-migrate-catalog-and-map-curated-photos.md`, `.10x/tickets/done/2026-07-11-migrate-trip-planner-curated-photos.md`

# Repair curated-photo frontend contracts and accessibility

## Scope

Unify strict browser validation for catalog/profile/map/planner curated photos and repair the UX/accessibility gaps identified by aggregate reviews: exact Wikimedia identity/path/license validation, Rufous Trip Planner placeholder, Field Map source/license destinations, and restrained image-failure announcements.

## Acceptance criteria

- Catalog and planner reuse one equivalent strict curated-photo validation contract for provider, exact record/file/photo identity, host/path/hash/title/width grammar, no credentials/port/query/fragment/traversal, supported extension, dimensions, creator, allowed canonical CC code/text/URL, and scientific identity.
- Planner tests reject independently mutated Wikimedia record title, thumbnail title/hash/width, source page, explicit port, credentials, unsupported or invented license, noncanonical license URL, query, fragment, and extra fields before partial rendering.
- Trip Planner unavailable photos render the Rufous placeholder for both new and saved plans with meaningful accessible text.
- Field Map exposes canonical safe source and license destinations for available metadata and retains them after image-load failure.
- Planner and Field Map asynchronous image-load failures use restrained semantic status announcements without making persistent attribution noisy.
- Existing native controls, keyboard/focus semantics, alt text, lazy loading, and fail-closed whole-response behavior remain intact.
- Focused frontend tests, strict TypeScript, full frontend suite, production build, bundle audit, and relevant Python/API gates pass.

## Explicit exclusions

No visual redesign, provider expansion, manual moderation UI, MapLibre control changes, or unrelated accessibility refactor.

## Evidence expectations

Record adversarial validator tests, DOM/accessibility assertions, focused/full frontend gate results, build/bundle audit, and explicit residual physical-browser/responsive/assistive-technology limits.

## References

- `.10x/specs/superseded/curated-representative-bird-photos.md`
- `.10x/reviews/2026-07-12-curated-representative-photo-ux-accessibility-review.md`
- `.10x/reviews/2026-07-12-curated-representative-photo-correctness-review.md`
- `.10x/reviews/2026-07-12-curated-representative-photo-privacy-security-source-review.md`
- `.10x/reviews/2026-07-12-curated-representative-photo-architecture-review.md`

## Progress and notes

- 2026-07-12: Opened from aggregate frontend review findings. No repair has begun.
- 2026-07-12: Added one shared strict curated-photo browser validator and reused it in catalog, planner validation, and planner presentation. Added exact Wikimedia MD5/title/path/width and canonical license adversarial coverage; Rufous planner fallback; Field Map source/license links; and restrained failure announcements.
- 2026-07-12: Focused strict TypeScript and 150 tests passed. Full frontend passed 300 tests, production build, and bundle audit. Evidence: `.10x/evidence/2026-07-12-curated-photo-frontend-contract-repair.md`. Self-review: `.10x/reviews/2026-07-12-curated-photo-frontend-contract-repair-self-review.md`.
- 2026-07-12: Re-read acceptance criteria; every criterion maps to the evidence and no unresolved review finding remains within scope. Ticket closed.

## Blockers

None.
