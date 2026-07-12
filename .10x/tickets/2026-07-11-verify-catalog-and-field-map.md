Status: open
Created: 2026-07-11
Updated: 2026-07-11
Parent: .10x/tickets/2026-07-11-improve-catalog-and-add-field-map.md
Depends-On: .10x/tickets/done/2026-07-11-build-catalog-sort-and-filters.md, .10x/tickets/done/2026-07-11-fix-bird-profile-information-layout.md, .10x/tickets/2026-07-11-alphabetize-text-dropdown-options.md, .10x/tickets/2026-07-11-build-rufous-field-map-ui.md

# Verify catalog discovery and Field Map

## Scope

Run aggregate correctness, privacy/source-authority, architecture/open-source, map network, and UX/accessibility verification across all children and preserved Rufous behavior.

## Acceptance criteria

- Full network-blocked Python/frontend/SQLMesh/Soda/type/build/bundle/docs/static/hooks gates pass with warehouse hashes unchanged.
- Live 706 summary and map eligible counts reconcile to strict source authority; no parent inference, private evidence, personal data, remote request, or excess geometry.
- All sort/filter/bucket/dropdown/layout/map interaction and accessible-list matrices pass.
- Independent architecture, correctness, privacy/security, and UX/accessibility reviews pass.
- Records/specs/decisions/tickets/evidence/reviews/retrospectives are coherent before parent closure.

## Exclusions

No new behavior, source refresh, live delivery/model/provider call, or unrelated refactor.

## Evidence expectations

One aggregate evidence record and focused independent reviews mapping every criterion.

## Blockers

Depends on all implementation children.
