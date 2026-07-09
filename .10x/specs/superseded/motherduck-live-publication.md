Status: superseded
Created: 2026-07-09
Updated: 2026-07-09

# MotherDuck Live Publication

Superseded by `.10x/specs/local-only-databox-platform.md` after the user removed MotherDuck and deployment from the product architecture.

## Purpose and scope

This spec governs how Databox publishes the local Quack-backed warehouse to MotherDuck so MotherDuck Dives and the live Cloudflare Worker agent can read current modeled data.

It applies to the live Birding Trip Copilot product mode described by `.10x/decisions/superseded/live-motherduck-cloudflare-agent-architecture.md`.

## Source of truth

The local refresh path remains the source-of-truth data build:

1. registered dlt sources load into the single local `data/databox.duckdb` file through Quack,
2. SQLMesh materializes modeled schemas in that local DuckDB file,
3. a publication step makes the required modeled data visible in MotherDuck.

MotherDuck publication is a product serving step, not a replacement for the local reproducible build.

## Local refresh behavior

A product refresh MUST use one local DuckDB data file: `data/databox.duckdb`.

Source ingestion MUST go through Quack; implementation MUST NOT reintroduce direct multi-process writes with `duckdb.connect("data/databox.duckdb")` from independent source processes.

The product refresh SHOULD run independent source loads concurrently through one Quack server when the Quack protocol and dlt metadata behavior are proven safe. If Quack's current metadata or attached-catalog behavior prevents safe true parallelism, the implementation MUST stop at a recorded blocker instead of silently degrading the product contract.

Each source remains hermetic:

- source-specific dlt state and resource configuration MUST remain isolated,
- raw tables MUST land physically in `raw_<source>` schemas,
- persistent `_dlt_*` operational metadata MUST NOT be exposed as Dagster assets,
- persistent `main._dlt*` tables/views MUST NOT remain after a refresh.

## MotherDuck publication behavior

The publication command MUST read `MOTHERDUCK_TOKEN` from environment-managed secrets.

The publication command SHOULD use a native DuckDB/MotherDuck client path because the source data starts in a local DuckDB file.

The publication command MUST make the Dive/Worker-required schemas available in MotherDuck, including at least:

- `environmental_observations`,
- `birding_agent` planner-ready evidence interfaces,
- any app artifact namespace used for cloud-generated trip plans.

Publication MUST be data-loss-safe for live generated artifacts:

- cloud-generated trip plans, recommendations, evidence, and tool traces MUST survive a warehouse snapshot publish,
- wholesale database replacement is allowed only for namespaces that do not contain cloud-only generated artifacts, or only after those artifacts are migrated/preserved,
- generated trip-plan artifacts SHOULD live in a namespace/database that is not replaced by local warehouse publication unless later records explicitly supersede this constraint.

The publication command MUST validate after publish:

- expected schemas/tables/views exist in MotherDuck,
- row counts for core modeled tables match the local source or explain intentional differences,
- `main._dlt*` relations are absent from the published serving namespace,
- a read-only query representative of the Dive succeeds.

## Operational behavior

The product publish command SHOULD be exposed as a `task` target and documented in the runbook.

Logs MUST redact tokens and MUST NOT print MotherDuck or Cloudflare secrets.

The implementation SHOULD record evidence for at least one successful local refresh plus MotherDuck publication.

## Acceptance criteria

- A single command can run the local Quack refresh and publish the serving dataset to MotherDuck.
- The command uses `MOTHERDUCK_TOKEN` from `.env`/environment without committing or logging it.
- MotherDuck contains the schemas/tables needed by the Birding Trip Copilot Dive and Worker.
- Publish validation records row-count and representative-query evidence.
- Cloud-generated trip-plan artifacts are not destroyed by subsequent warehouse publishes.
- The refresh path preserves Quack raw-schema and `_dlt_*` hygiene guarantees.
