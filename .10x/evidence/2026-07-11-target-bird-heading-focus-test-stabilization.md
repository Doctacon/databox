Status: recorded
Created: 2026-07-11
Updated: 2026-07-11
Relates-To: .10x/tickets/done/2026-07-11-stabilize-target-bird-heading-focus-test.md

# Target Bird heading focus test stabilization

## Observation

The first Target Bird result test used `findByRole(...).toHaveFocus()` as one immediate assertion. During two full parallel frontend runs, the heading had rendered but the existing mount focus effect had not completed, so focus was still on `body`. The same file passed 6/6 when focused, demonstrating an assertion timing race rather than product behavior drift.

## Change

Only `app/src/TargetBird.test.tsx` changed: the test stores the found heading and uses bounded Testing Library `waitFor(() => expect(heading).toHaveFocus())`. The accessible focus requirement remains identical. No production source, focus effect, timing, route, data, or UI behavior changed.

## Verification

```text
focused TargetBird run 1: 6/6 passed
focused TargetBird run 2: 6/6 passed
focused TargetBird run 3: 6/6 passed
full frontend after repair: 253/253 passed across 15 files
typecheck: passed
production build: passed
bundle audit: passed
```

## Limits

This evidence supports only test stabilization. Independent review remains required before ticket closure.
