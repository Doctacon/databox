Status: recorded
Created: 2026-07-11
Updated: 2026-07-11
Relates-To: .10x/tickets/done/2026-07-11-stabilize-field-map-heading-focus-test.md, .10x/tickets/done/2026-07-11-build-rufous-field-map-ui.md

# Field Map heading-focus test stabilization evidence

## Observed failure

The first aggregate full frontend run passed 248 tests and failed one Field Map assertion. `findByRole` observed the lazy-loaded `<h1 tabindex="-1">Field Map</h1>` immediately after commit, before React ran the component's existing mount effect. Focus was still on `body` at that instant. Prior focused/full runs had passed, identifying a scheduling race in the assertion rather than missing product behavior.

## Exact repair

Only `app/src/FieldMap.test.tsx` changed:

```text
expect(heading).toHaveFocus()
```

became:

```text
await waitFor(() => expect(heading).toHaveFocus())
```

Testing Library's bounded default wait is used. No production source, timing, route, focus effect, accessibility behavior, or UI changed.

## Verification

- Focused `FieldMap.test.tsx`: 4/4 passed in three consecutive independent Vitest runs.
- Full frontend: 249/249 passed across 15 files.
- TypeScript passed.
- Vite production build and expanded bundle/privacy audit passed.
- Aggregate network-blocked Python, static, SQLMesh, Soda, docs, and hooks gates subsequently passed without warehouse or personal-state change.

## Limits

This repair stabilizes observation of the existing asynchronous lazy-route mount effect. It does not alter or broaden the focus contract. Independent review remains required before closure.
