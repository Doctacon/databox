Status: done
Created: 2026-07-11
Updated: 2026-07-11
Parent: .10x/tickets/2026-07-11-improve-catalog-and-add-field-map.md
Depends-On: .10x/tickets/done/2026-07-11-evolve-product-into-rufous.md

# Repair stale Rufous artwork contract test

## Scope

Update the stale static originality test that still requires the superseded inline SVG after the user supplied `app/src/assets/rufous.png`. Validate the current bundled-local-image, no-remote-asset, technical naming, and accessibility boundary without weakening originality/privacy checks.

## Acceptance criteria

- Test requires local `rufous.png` import/use and decorative accessible treatment.
- Test rejects remote image/theme/font URLs and prohibited copied-brand strings as before.
- Full theme/frontend/Python gates pass.

## Exclusions

No artwork, UI, theme, or product behavior change.

## Evidence expectations

Record stale failure, repaired focused/full gates, and review.

## Progress and notes

- 2026-07-11: Reproduced the committed stale contract failure: the static test required the superseded inline SVG while `App.tsx` intentionally imports and renders the bundled `assets/rufous.png` artwork.
- 2026-07-11: Updated only the contract test to require the exact local PNG import/use, decorative empty alt plus `aria-hidden`, valid bounded PNG bytes, and continued rejection of remote image/theme/font URLs and copied-brand strings. Focused theme passes 4/4; full Python passes 674/674; frontend passes 222/222 with typecheck/build. Evidence: `.10x/evidence/2026-07-11-rufous-artwork-contract-test.md`.
- 2026-07-11: Independent review passed. Review: `.10x/reviews/2026-07-11-rufous-artwork-contract-test-review.md`; final aggregate gates after the catalog review repair pass 679/679 Python and 222/222 frontend.
- 2026-07-11: Retrospective found a stale static contract after intentional asset replacement; the repaired test now follows the durable local-asset boundary, so no additional record is needed.

## Blockers

None.
