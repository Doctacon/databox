# ADR-0002: SQLMesh over dbt

**Status:** Accepted · 2026-02

## Context

The transformation layer needs to handle:

- dependency-aware DAG execution
- environment/virtual data mart separation (dev, staging, prod without
  copying data)
- model-level tests and audits
- incremental models for time-partitioned data (daily bird observations,
  daily weather)
- change detection (plan before apply)
- DuckDB dialect support

Two mature Python-native options exist: **dbt-core** and **SQLMesh**.
Both are open source. Both work with DuckDB.

## Decision

Use SQLMesh for all SQL transformations under `transforms/main/`.

## Consequences

**Positive:**
- **Virtual data environments out of the box.** SQLMesh's `plan` model
  creates cost-free virtual views per environment. Promoting to prod is
  a view-swap, not a materialized copy. dbt's equivalent (`defer`) is
  limited and much more manual.
- **Column-level change detection.** SQLMesh categorizes changes as
  breaking vs non-breaking automatically. A column rename shows up
  differently than a pure-SQL refactor. dbt sees only "the model
  changed".
- **Native semantic metrics.** SQLMesh's `METRIC` DDL lets the semantic
  layer live next to the models. The metrics layer in this repo
  (`transforms/main/metrics/`) exists because SQLMesh supports it
  natively. dbt's Semantic Layer requires dbt Cloud.
- **Python models work cleanly** without the dbt-python compatibility
  caveats.
- **Same mental model for local and MotherDuck** via gateways
  (see ADR-0006).

**Negative:**
- Smaller community than dbt. When looking up "how do I X in SQLMesh",
  answers are often thinner.
- Fewer packaged providers than dbt's hub.
- Staff-level engineers are statistically far more likely to have dbt
  experience than SQLMesh. This repo has to teach SQLMesh in the README,
  which adds one more concept to absorb.

**Neutral:**
- SQLMesh audits replace dbt's tests, but Soda contracts (see
  `soda/contracts/`) cover the cross-cutting quality checks separately,
  so the choice of SQLMesh vs dbt test syntax does not load-bear.
