Status: recorded
Created: 2026-07-07
Updated: 2026-07-07
Relates-To: .10x/skills/annotate-sources/SKILL.md, .pi/skills/annotate-sources/SKILL.md, .schema/environmental_observations/taxonomy.json

# annotate-sources skill test on Databox dlt schemas

## What was observed

The project-level `annotate-sources` skill was loaded from `.pi/skills/annotate-sources/SKILL.md` and tested against Databox's local dlt schema artifacts.

Local dlt CLI discovery with `.venv/bin/dlt pipeline --pipelines-dir data/dlt --list-pipelines` reported:

- `noaa_api`
- `ebird_api`
- `pipelines`
- `usgs_earthquakes_api`
- `usgs_api`

The `pipelines` entry appears to be a stray nested directory with no source schema; the user confirmed testing the four real pipelines only.

This Pi session did not expose the dlt MCP tools named by the skill (`list_pipelines`, `export_schema`). The test used the existing local dlt schema JSON files as a fallback source of schema truth.

## Procedure

1. Confirmed source set, CDM folder name, and use-case framing with the user:
   - Sources: `ebird_api`, `noaa_api`, `usgs_api`, `usgs_earthquakes_api`
   - CDM name: `environmental_observations`
   - Use-case framing: date/location analysis
2. Generated DBML files under `.schema/environmental_observations/` from local dlt schema JSON files.
3. Proposed canonical entities grounded in the source schemas and confirmed them with the user.
4. Wrote `.schema/environmental_observations/taxonomy.json`.
5. Annotated DBML tables with concept/role notes and exclusion notes.
6. Validated `taxonomy.json` with `python3 -m json.tool`.

## Artifacts produced

- `.schema/environmental_observations/ebird_api.dbml`
- `.schema/environmental_observations/noaa_api.dbml`
- `.schema/environmental_observations/usgs_api.dbml`
- `.schema/environmental_observations/usgs_earthquakes_api.dbml`
- `.schema/environmental_observations/taxonomy.json`

## What this supports

The project-level skill is discoverable/readable through Pi and its core workflow can annotate Databox dlt source schemas into DBML plus a taxonomy file.

The local dlt schema JSON fallback was robust enough for the Databox workflow: it preserved normalized table names, normalized column names, data types, `primary_key`, `nullable`, `unique`, and `row_key` hints. This supported revising `.10x/skills/annotate-sources/SKILL.md` to be local-schema-first instead of MCP-based.

## Limits

The test used local dlt schema JSON, not live destination introspection. Remote-dataset-only sources still need the dlt ibis extraction path described in the skill.
