Status: recorded
Created: 2026-07-09
Updated: 2026-07-09
Target: .10x/tickets/done/2026-07-09-integrate-media-into-recommendation-cards.md
Verdict: pass

# Recommendation card media layout review

## Target

React implementation and evidence for `.10x/specs/recommendation-card-media-layout.md`.

## Findings

### Passed — section order and accessibility

Field Plan, Weather and Elevation, both recommendation groups, and final Evidence and Provenance render in exact order. The standalone media section is absent. Evidence remains visible while Agent Workflow uses native details/summary inside the final section.

### Resolved significant — untrusted nested media

Initial review found species/canonical-ID mismatches, malformed nested objects/caveats, license label/URL inconsistencies, and narrow-card overflow. Runtime guards now require recommendation species identity, complete Xeno ID agreement, finite exact license label/URL derivation, and safe object/caveat shapes. Grid/media children use explicit min-width and wrapping constraints.

### Resolved significant — misleading rejected metadata

Follow-up review found rejected different-species/cross-ID media still displayed its attribution and semantic labels under the owning card. Final repair suppresses every creator/rights/publisher/license/source or scope/type/quality/recordist field when identity is untrusted. Only a generic placeholder/mismatch caveat remains. Identity-consistent binary load failures still preserve attribution and safe source links.

### Passed — native media and security

Images are lazy and responsive; audio uses native controls, preload none, and no autoplay. GBIF/Xeno paths, identifiers, licenses, and source links are revalidated in the browser. Fifty frontend tests, typecheck, build, bundle audit, full CI, docs, and pre-commit passed.

## Verdict

Pass. No blocker remains.

## Residual risk

Responsive behavior is DOM/CSS-tested rather than screenshot-tested. Remote binary availability can change, but validated attribution persists and runtime failure states are covered.
