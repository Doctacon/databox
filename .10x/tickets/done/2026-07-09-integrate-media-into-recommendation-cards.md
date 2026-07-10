Status: done
Created: 2026-07-09
Updated: 2026-07-09
Parent: .10x/tickets/done/2026-07-09-add-recommendation-card-photos-and-calls.md
Depends-On: .10x/tickets/done/2026-07-09-implement-request-time-recommendation-media.md

# Integrate media into recommendation cards

## Scope

Implement `.10x/specs/recommendation-card-media-layout.md` against the stable persisted recommendation-centric media API.

Required work:

- reorder result sections to Field Plan; Weather and Elevation; High-likelihood Species; Uncommon but Plausible Targets; Evidence and Provenance,
- remove the standalone Call and Media Examples section and obsolete list/card styling,
- attach media strictly by recommendation ID,
- render one responsive lazy photo or explicit placeholder in every recommendation card,
- render one native `controls`/`preload="none"`/non-autoplay call player or explicit placeholder in every card,
- preserve common/scientific names, rank, confidence, rationale, and recommendation caveats,
- display photo creator/rights-holder, publisher, license, and safe source link,
- display call scope, type, quality, recordist, license, and safe Xeno-canto source link,
- preserve attribution and source/license links when image/audio loading fails,
- independently fail closed for malformed photo and call objects,
- move Agent Workflow into an accessible native disclosure inside the final Evidence and Provenance section,
- add React tests for exact section order, absent standalone media section, available/unavailable mixed media, global scope label, attribution, load failures, URL defense-in-depth, keyboard/screen-reader semantics, and responsive behavior.

## Explicit exclusions

- No carousel, gallery, lightbox, multiple-call list, waveform, autoplay, or custom audio engine.
- No browser-side discovery or persistence.
- No recommendation/ranking changes.
- No removal of evidence rows or tool traces.
- No binary media storage/proxying.
- No backfill execution in this ticket.

## Acceptance criteria

- Every high-likelihood and uncommon-plausible card has a photo area and call area.
- Available media renders with complete attribution/source/license; unavailable media renders explicit placeholders without removing the recommendation.
- Images use lazy loading and bounded responsive layout; audio uses native controls, `preload="none"`, and no autoplay.
- `Arizona recording` or `Global example` is visible for available calls.
- No Call and Media Examples section appears.
- Weather and Elevation follows Field Plan; Evidence and Provenance is final.
- Agent Workflow is accessible inside the final section and evidence remains independently visible.
- Existing loading/error/history behavior and bundle credential isolation remain intact.
- Strict TypeScript, React tests, build, bundle audit, accessibility/security review, full CI/docs, and independent review pass.

## Evidence expectations

Record rendered DOM/order/accessibility assertions, screenshots if useful, malformed-media security cases, responsive checks, exact commands/results, and independent review.

## Progress and notes

- 2026-07-09: Reordered result panels to Field Plan, Weather and Elevation, High-likelihood Species, Uncommon but Plausible Targets, and final Evidence and Provenance.
- 2026-07-09: Removed the standalone Call and Media Examples UI and obsolete media list/card styling. The stable legacy API/type field remains for compatibility but is not read by the view.
- 2026-07-09: Added recommendation-linked photo/call areas with strict browser URL/license revalidation, lazy responsive images, accurate alt text, native non-autoplay audio, complete attribution, Arizona/global labels, independent placeholders, and attribution-preserving load failure states.
- 2026-07-09: Moved Agent Workflow into a native details/summary disclosure inside final Evidence and Provenance while keeping the evidence table visible.
- 2026-07-09: Added React coverage for exact order, absent standalone media, mixed states, recommendation-ID attachment, global fallback, attribution, runtime errors, raw URL attacks, native semantics, and responsive media classes.
- 2026-07-09: Validation passed strict TypeScript, 34 frontend tests, production build, bundle audit, full CI with 242 tests at 83.90% coverage, strict docs, pre-commit, and diff/no-stage checks. Evidence recorded at `.10x/evidence/2026-07-09-recommendation-card-media-layout.md`.
- 2026-07-09: Independent review found runtime trust gaps for species/cross-ID attachment, malformed nested JSON/caveats, license label/URL consistency, and narrow-grid overflow.
- 2026-07-09: Repaired all findings with authority-free species matching plus exact common-name fallback, canonical source/typed/URL recording-ID agreement, unknown-object guards and safe caveat normalization, exact derived license-code matching including CC0, and explicit min-width/wrapping CSS across grid/card/media children.
- 2026-07-09: Added adversarial React coverage for different species, XC/cross IDs, null/missing/nonobject/wrong nested values, malformed caveats, missing/mismatched licenses, CC0, independent failure, and long unbroken metadata. Final validation passed strict TypeScript, 49 frontend tests, production build, bundle audit, full CI with 242 tests at 83.90% coverage, strict docs, and pre-commit.
- 2026-07-09: Final review found that rejected identity-mismatched media still displayed metadata from the wrong species/recording. Repaired the UI to suppress all photo attribution/license/source when species identity is untrusted and all call scope/type/quality/recordist/license/source when species or canonical IDs disagree. Rejected media now shows only its placeholder and one generic medium-specific caveat; identity-consistent image/audio runtime failures still retain attribution. Focused validation passed strict TypeScript, 50 frontend tests, and the production build.
- 2026-07-09: Independent final review passed exact order, native accessibility, runtime media guards, identity/license/URL security, mismatch suppression, attribution-preserving load failures, and responsive containment. Review: `.10x/reviews/2026-07-09-recommendation-card-media-layout-review.md`.
- 2026-07-09: Retrospective: browser types are not runtime trust, and failing closed must suppress semantically misleading attribution as well as active media. Runtime guards and adversarial rendered tests preserve this lesson; no separate knowledge/skill record is needed.

## Blockers

None.
