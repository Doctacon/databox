Status: done
Created: 2026-07-08
Updated: 2026-07-09
Parent: .10x/tickets/done/2026-07-08-build-birding-trip-copilot.md
Depends-On: .10x/tickets/2026-07-08-implement-adk-trip-planner-persistence.md

# Build trip-plan MotherDuck Dive

## Scope

Build the first MotherDuck Dive surface for persisted Birding Trip Copilot plans.

In scope:

- Validate the SQL queries needed for latest/selected trip plan display.
- Build a Dive that shows plan summary, field plan narrative, ranked species, evidence/provenance, media/license context, weather/elevation context, and tool-trace summary.
- Use MotherDuck Dive patterns: React + SQL, `useSQLQuery`, loading/empty/error states, no browser-side secrets.
- Support local preview before save/publish where the environment allows.
- Document preview/update/save workflow.

Out of scope:

- Running the Python ADK agent inside the Dive.
- Embedding the Dive in a separate app.
- Implementing authentication/user accounts.
- Agent or data-source implementation.

## Acceptance criteria

- The Dive renders from persisted trip-plan SQL artifacts without invoking the Python agent in-browser.
- The Dive displays all required sections from `.10x/specs/birding-trip-plan-dive.md`.
- The Dive exposes evidence/provenance, not only the final generated prose.
- The Dive handles loading, empty, and error states.
- The Dive implementation contains no API secrets.
- Preview/save/update instructions are documented.

## Evidence expectations

Record evidence with:

- validated SQL queries,
- local preview result or save/update result,
- screenshot path if available,
- residual Dive/MotherDuck limitations.

## Progress and notes

- 2026-07-08: Ticket opened from parent Birding Trip Copilot plan.
- 2026-07-09: Added Dive-as-code artifact under `dives/birding-trip-plan/`, pointed `.dive-preview/src/dive.tsx` at it, and documented local preview/save path.
- 2026-07-09: Added SQL contract test for the latest/selected plan, recommendations, evidence/provenance, Open-Meteo, Xeno-canto, and tool-trace queries.
- 2026-07-09: Validated SQL with pytest and local Dive preview with Vite build. See `.10x/evidence/2026-07-09-trip-plan-motherduck-dive.md`.
- 2026-07-09: Review fix: aligned tool-trace status display and SQL seed data with real planner-persisted `ok` success status instead of synthetic `success`.

## Blockers

None.
