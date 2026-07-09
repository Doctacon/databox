# Birding Trip Copilot Dive

This is the MotherDuck Dive surface for persisted Birding Trip Copilot plans.

The Dive is intentionally SQL-only in the browser: Python/Google ADK generates
trip plans and persists them into `birding_agent.*`; this React component only
queries and renders those persisted artifacts with `useSQLQuery`.

## SQL dependencies

The component expects the `databox` MotherDuck database to contain these tables
or views:

- `databox.birding_agent.trip_plans`
- `databox.birding_agent.trip_plan_recommendations`
- `databox.birding_agent.trip_plan_evidence`
- `databox.birding_agent.trip_plan_tool_traces`

If the production database name changes, update `DATABASE_NAME` in
`dives/birding-trip-plan/birding-trip-plan.tsx` before saving the Dive.

## Sections

- latest/selected trip plan selector
- plan summary KPIs and caveats
- field-plan narrative
- Open-Meteo weather/elevation context
- ranked high-likelihood and uncommon-plausible species
- Xeno-canto media/license links
- evidence/provenance table
- agent tool-trace timeline

## Local preview

The existing local preview scaffold points at this Dive:

```bash
cd .dive-preview
npm install
printf 'VITE_MOTHERDUCK_TOKEN=<token>\n' > .env
npm run dev
```

For non-interactive validation of the local preview bundle:

```bash
cd .dive-preview
npm run build
```

Do not commit `.dive-preview/.env` or any MotherDuck token.

## Save/update path

When MotherDuck MCP or the workspace UI is available, save the content of
`dives/birding-trip-plan/birding-trip-plan.tsx` with the metadata in
`dives/birding-trip-plan/dive_metadata.json` as a normal workspace Dive titled
`Birding Trip Copilot`.

This repo currently keeps the Dive as code because this implementation run did
not have live MotherDuck MCP/save tooling available.
