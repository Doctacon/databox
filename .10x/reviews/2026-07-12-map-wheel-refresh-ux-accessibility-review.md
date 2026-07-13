Status: recorded
Created: 2026-07-12
Updated: 2026-07-12
Target: commit a70af1c and .10x/tickets/done/2026-07-11-verify-map-wheel-and-refresh-controls.md
Verdict: fail

# Map, wheel, and refresh UX and accessibility review

## Findings

- **Significant:** Field Map thumbnail load failure removes attribution/license instead of preserving metadata with an unavailable visual state.
- **Significant:** shared preview state lets mouse leave cancel an active keyboard-focus preview and blur cancel an active pointer preview.
- **Significant:** preview marker paints above an identical selected marker, violating selected-style authority.
- **Significant:** refresh UI omits current source/SQLMesh progress and reload-preserved failure message/log reference.
- **Significant:** refresh component lifecycle has no component-level tests.
- **Minor:** explicit smooth wheel scrolling remains active under reduced motion.

Listbox semantics, keyboard commands, single active preview/call controls, focusable map cluster controls, native refresh confirmation, busy state, and baseline status/alert semantics were sound.

## Verdict

Fail. Findings are owned by `.10x/tickets/done/2026-07-12-repair-map-wheel-refresh-review-findings.md`.

## Residual risk

No physical browser, touch, zoomed-text, forced-colors, keyboard-only browser, screen-reader, or assistive-technology session was performed. JSDOM cannot prove actual scroll snap, MapLibre paint behavior, or announcement quality.

## Evidence inspected

Governing records; changed frontend surface in commit `a70af1c`; focused frontend tests (34 passed) and TypeScript (passed). No repository mutation or live workflow occurred.
