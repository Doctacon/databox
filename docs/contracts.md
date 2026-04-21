# Schema Contracts

Databox treats Soda contracts under `soda/contracts/` as the public schema for every SQLMesh-owned dataset. Contracts are enforced three ways:

1. **Structural validation** — every PR runs `soda-validate` to confirm each contract parses as YAML and has `dataset` + `columns` keys.
2. **Runtime checks** — after each materialization, a Dagster asset check invokes `soda contract verify` against the materialized table. A contract violation fails the check (and the run).
3. **Schema-contract gate** — on every PR, `schema-contract-gate` diffs the contracts at HEAD against `origin/<base>` and fails the build if a breaking change is not explicitly acknowledged.

This page covers #3 — the gate, what it catches, and how to override it when you really mean to break downstream consumers.

## What counts as breaking

The gate classifies each contract change into one of two buckets.

### Breaking (fail closed)

- **Model removed** — a contract file under `soda/contracts/**` deleted
- **Column removed** — a column that existed at the base is gone at HEAD
- **Type narrowed** — a column's `data_type` changed to a non-widening type (e.g. `bigint` → `int`, `text` → `varchar` is fine but `timestamp` → `date` is not)
- **Model renamed** — the top-level `dataset` identifier changed

### Additive (always safe)

- New contract file
- New column
- Widened type (`int` → `bigint`, `date` → `timestamp`, etc.)
- New check

The classifier lives in `databox.quality.schema_gate`; `scripts/schema_gate.py`
is a thin CLI wrapper. Type-widening is delegated to sqlglot's dialect-aware
parser (`sqlglot.exp.DataType.build`) — the same parser SQLMesh uses — rather
than a hand-rolled widening table. Covered families: integer widths
(`smallint → int → bigint`), integer → numeric (`int → float/double/decimal`),
any `varchar`/`text`/`char` ↔ any other text type, and `date → timestamp`.
Anything else classifies as narrowing (fail-closed).

## How the gate runs

The `schema-contract-gate` CI job:

1. Checks out with `fetch-depth: 0` so `origin/<base_ref>` resolves.
2. Reads every `*.yaml` under `soda/contracts/` at the base and at HEAD.
3. Classifies each change.
4. Exits `0` if clean or fully acknowledged, `1` if any breaking change is unacknowledged, `2` on invocation error (git failure, invalid YAML).

The job only runs on `pull_request` events — pushes to `main` have no sensible base to diff against.

## Acknowledging a breaking change

Breaking changes are sometimes the right call — retiring a deprecated column, collapsing a mart, renaming a model after a domain change. When that happens, add an `accept-breaking-change` line to the PR body, one per model:

```
accept-breaking-change: ebird.fct_daily_bird_observations
accept-breaking-change: noaa.fct_daily_weather
```

The token the gate matches on is the contract's `dataset` field (not the file path). The gate prints the full report either way — acknowledged breaking changes are annotated `(ACKED)` in the output so reviewers can still see them at a glance.

Use the escape hatch when:

- the consumer of the removed column/model is being retired in the same PR
- the breaking change is the intended outcome of a versioned migration
- you have coordinated with downstream readers out of band

Do not use it to silence a drift you did not intend. If the diff surprises you, that is the gate doing its job.

## Running the gate locally

```bash
uv run python scripts/schema_gate.py --base origin/main
```

Flags:

- `--base <ref>` — revision to compare HEAD against (default `origin/main`)
- `--pr-body-file <path>` — file containing the PR body, for parsing `accept-breaking-change` tokens
- `--accept a.b,c.d` — comma-separated list of models whose breaking change is acknowledged; overrides the `ACCEPT_BREAKING_CHANGE` env var
