Status: active
Created: 2026-07-09
Updated: 2026-07-09

# Local-only Databox Platform

## Purpose and scope

This spec governs removal of active MotherDuck support and establishes the single local DuckDB platform boundary.

## Platform contract

- Databox MUST use `data/databox.duckdb` as its only warehouse and application-state database.
- Quack MUST be the only dlt write path to the shared local warehouse during source ingestion.
- SQLMesh MUST use the local DuckDB gateway only.
- The local React product MUST access data through the local Python API, not by opening DuckDB in the browser.
- The local Python API MAY read/write persisted `birding_agent.*` artifacts directly when no Quack source ingest is active.

## MotherDuck decommission contract

Active MotherDuck support MUST be removed from:

- runtime settings and backend selection,
- SQLMesh gateway configuration,
- dlt destination selection,
- Dagster startup/bootstrap behavior,
- environment examples,
- task commands and runbooks,
- active architecture docs and ADR indexes,
- executable tests and dependencies used only for MotherDuck,
- MotherDuck Dive source and local Dive preview artifacts.

Historical changelog entries, terminal `.10x` records, and superseded ADR/decision rationale MAY retain factual MotherDuck references. They MUST be clearly historical rather than active instructions.

`DATABOX_BACKEND` SHOULD be eliminated if it no longer selects meaningful supported behavior. A legacy local per-source backend MUST NOT remain merely to preserve unused configurability.

## Local safety

- The API and frontend development servers MUST bind to loopback by default.
- `.env`, `.venv/`, `data/`, `.dagster/`, and `.logs/` MUST remain ignored and preserved by normal cleanup.
- Secrets MUST NOT be printed, committed, or returned from readiness endpoints.
- Database reset commands MUST clearly state that they delete local persisted trip plans as well as warehouse data.

## Acceptance criteria

- Active source/config/docs/tests contain no supported MotherDuck or Dive path.
- Local ingest, SQLMesh, Dagster, API, and React app all use `data/databox.duckdb`.
- Historical references are clearly historical and do not instruct users to configure MotherDuck.
- Existing local verification and CI pass after removal.
- Secret scan confirms no credentials were introduced.
