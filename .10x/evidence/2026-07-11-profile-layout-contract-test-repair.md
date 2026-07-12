Status: recorded
Created: 2026-07-11
Updated: 2026-07-11
Relates-To: .10x/tickets/done/2026-07-11-repair-profile-layout-contract-test.md, .10x/tickets/done/2026-07-11-fix-bird-profile-information-layout.md, .10x/specs/bird-profile-information-layout.md

# Profile layout contract-test repair evidence

## Observed failure

The first full Python run for the Field Map data ticket executed 700 other tests successfully but failed:

```text
tests/test_bird_catalog_api.py:544
assert ".catalog-profile-media-grid { grid-template-columns: 1fr; }" in styles
```

That assertion required the old 820px override. The done profile-layout implementation intentionally replaced it with an explicit all-width base declaration: `.catalog-profile-media-grid { display: grid; grid-template-columns: minmax(0, 1fr); ... }`. The frontend contract already tested that there is exactly one such base declaration.

## Exact repair

Only `tests/test_bird_catalog_api.py` changed under the separately authorized repair ticket. The static test now:

- requires the base profile media `minmax(0, 1fr)` declaration;
- requires the base profile main `minmax(0, 1fr)` declaration;
- rejects the former `minmax(240px` positive media track;
- retains the 1100px two-column catalog, 820px breakpoint presence, 540px one-column controls/grids, mobile navigation, and stacked button protections.

No CSS, markup, product behavior, accessibility semantic, or layout implementation changed.

## Verification

- Focused repaired assertion plus map backend/artifact tests: 23/23 passed.
- Full network-blocked Python: 701/701 passed, three snapshots, 86.63% coverage.
- Full frontend: 245/245 passed plus typecheck, build, and bundle audit.
- Ruff and format checks pass for 153 files; MyPy, secrets, generated drift, and strict MkDocs build pass.

## Limits

This is a static contract repair, not fresh visual screenshot evidence. The governing frontend DOM/CSS/long-metadata tests remain the primary responsive layout proof. Independent review remains required before closure.
