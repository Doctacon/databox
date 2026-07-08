Status: cancelled
Created: 2026-07-07
Updated: 2026-07-07
Parent: None
Depends-On: None

# Wire dlt MCP tools for annotate-sources

## Scope

Make the project-level `annotate-sources` skill executable through its intended MCP path by ensuring Pi exposes the dlt MCP tools used by the skill:

- `list_pipelines`
- `export_schema`

## Cancellation rationale

The user explicitly does not plan to use the dlt MCP server. The successful skill test showed local dlt schema JSON is sufficient for the intended project workflow: it preserves normalized table/column names, data types, `primary_key`, `nullable`, `unique`, and `row_key` hints.

The skill was updated to be local-schema-first instead of MCP-based, so this ticket is no longer valid work.

## Progress and notes

- 2026-07-07: During the skill test, `mcp({})` showed only the `socraticode` server. No `list_pipelines` or `export_schema` tool was available. The test proceeded from local `data/dlt/*/schemas/*.schema.json` files instead. See `.10x/evidence/2026-07-07-annotate-sources-skill-test.md`.
- 2026-07-07: User confirmed they do not plan to use the dlt MCP server. `.10x/skills/annotate-sources/SKILL.md` was revised to use local dlt schema JSON as the primary extraction path.

## Blockers

None.

## Explicit exclusions

- Do not wire dlt MCP tools for this workflow.
- Do not change Databox ingestion or transform behavior.

## References

- `.pi/skills/annotate-sources/SKILL.md`
- `.10x/skills/annotate-sources/SKILL.md`
- `.10x/evidence/2026-07-07-annotate-sources-skill-test.md`

## Evidence expectations

Cancelled; no further evidence required.
