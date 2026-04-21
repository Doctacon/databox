# ADR-0006: MotherDuck as the cloud path

**Status:** Accepted · 2026-04

## Context

The local stack (ADR-0001) is good enough for daily operation but
breaks down for two use cases: sharing the data with another laptop,
and handing a recruiter a live dashboard they can click without cloning
the repo.

The candidate cloud paths considered:

1. **Managed Postgres / Snowflake / BigQuery** — wrong workload fit
   (OLTP / expensive / egress costs), requires rewriting models off
   DuckDB dialect.
2. **Parquet-on-S3 + Athena** — works but forces the dashboard layer
   to speak a different dialect than the local stack, doubling the
   test surface.
3. **MotherDuck** — cloud DuckDB. Accepts `md:` URIs as drop-in
   replacements for local paths. Same SQL dialect, same extensions,
   same features as local DuckDB.
4. **Self-hosted DuckDB on a VM** — defeats the "no always-on infra"
   constraint (ADR-0001).

## Decision

Use **MotherDuck** as the cloud path. Keep the local path as default.

Architecture is gateway-based: `DATABOX_BACKEND=local` or `=motherduck`
switches `settings.database_path` and `settings.raw_*_path` between
file paths and `md:` URIs. SQLMesh gateways (`local`, `motherduck`)
mirror the same split. No SQL changes between modes.

## Consequences

**Positive:**
- Identical SQL. The same transforms and the same Soda contracts run
  locally and in MotherDuck. No dialect split.
- Free hobbyist tier covers the portfolio use case without any upfront
  cost.
- Shared dashboards resolve `md:` URIs directly — no ETL-to-dashboard
  copy step.
- Backup is a `COPY FROM LOCAL TO md:` on demand. Switching backends is
  an environment-variable flip, reversible.

**Negative:**
- MotherDuck is proprietary SaaS. The *data* and *SQL* are portable;
  the *service* is not. If MotherDuck's pricing or service changes,
  the fallback is "stay on local DuckDB and publish static Parquet
  snapshots".
- Some DuckDB extensions load in a different order on MotherDuck than
  locally (the H3 community extension was the first example). The
  metrics layer hit this during implementation (see the semantic-metrics
  research record) — working-around requires invoking extension loading
  explicitly.
- Network round-trips are now a thing. Local DuckDB queries returned in
  milliseconds; MotherDuck queries are typically 10–100× slower for the
  same shape due to network, though still comfortably under a second
  for the dashboards in this repo.

**Neutral:**
- This violates the project's default preference for open-source over
  proprietary (noted in the root CLAUDE.md). The trade-off is
  explicit: proprietary service acceptable **only because** the data
  and SQL layer above it are fully portable — the same stack keeps
  running on local DuckDB if MotherDuck goes away.
