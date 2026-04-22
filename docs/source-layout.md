# Source Layout Convention

Every registered dlt source in Databox follows the same on-disk shape. Consistency means new sources cost a predictable amount to add, drift is visible to CI, and the [new-source generator](#new-source-generator) has a precise target.

`scripts/check_source_layout.py` enforces the convention — it runs as the `source-layout-lint` CI job on every PR and as `python scripts/check_source_layout.py` locally.

## The shape

For a source named `<name>` (e.g. `ebird`, `noaa`, `usgs`):

```
packages/databox-sources/databox_sources/<name>/
  ├── source.py              # dlt @source / @resource definitions
  └── config.yaml            # pipeline config (dataset, schedule hints)

transforms/main/models/<name>/
  ├── staging/
  │   └── stg_*.sql          # at least one staging model
  └── marts/
      └── (fct_*|dim_*).sql  # at least one mart model

soda/contracts/<name>_staging/
  └── *.yaml                 # at least one staging contract

soda/contracts/<name>/
  └── *.yaml                 # at least one mart contract

packages/databox/databox/orchestration/domains/<name>.py
                             # Dagster assets, schedules, asset checks
```

Intermediate models under `transforms/main/models/<name>/intermediate/` are optional — the lint does not require them.

## What the linter checks

The script walks `packages/databox-sources/databox_sources/*/` looking for directories that contain a `source.py`. For each, it asserts the seven components above exist and contain at least one matching file.

Output format is line-oriented so CI logs stay diffable:

```
  ✓ ebird
  ✗ noaa
      missing: soda/contracts/noaa/*.yaml
  ✓ usgs

2 ok · 0 skipped · 1 failing (of 3)
```

`--json` emits the same data in machine-readable form for generator tooling.

## Escape hatch: `scaffold-lint: skip`

Experimental or in-flight sources that don't yet satisfy the full layout can opt out by adding a line within the first 10 lines of `source.py`:

```python
# scaffold-lint: skip=experimental
```

The reason after `=` is free text — common values: `experimental`, `in-flight`, `wip-domain-refactor`. Skipped sources appear in the lint output marked `~ (skipped: <reason>)` but do not fail CI.

Do not use the skip marker to silence drift in a finished source. If the lint complains about an existing source, the right answer is almost always "add the missing file" — the convention exists because each component has a concrete job.

## Why each file is required

| Component | Why it is required |
| --- | --- |
| `source.py` | Anchor file — if this doesn't exist, the source isn't loadable |
| `config.yaml` | Pipeline configuration (dataset name, schedule hints, source-specific options) |
| `staging/stg_*.sql` | At least one staging model turning raw into typed |
| `marts/(fct_*|dim_*).sql` | At least one consumer-facing mart |
| `soda/contracts/<name>_staging/` | Data-quality contract for the staging layer |
| `soda/contracts/<name>/` | Data-quality contract for the mart layer |
| `domains/<name>.py` | Dagster wiring — assets, schedules, asset checks |

Dropping any of these creates a source that half-works. The lint makes that state unshippable.

## New-source generator

`ticket:new-source-generator` (Phase 2) will scaffold this layout given just the source name. Whatever the linter requires is what the generator creates — the two stay in lockstep.

Until that ticket lands, adding a source by hand means copying the shape above. See `CLAUDE.md` for the current manual checklist.

## Typing the resource boundary

Sources that hit external APIs should validate each yielded record through a
Pydantic model so upstream schema drift fails closed at extract. See
[`source-typing.md`](source-typing.md) for the convention and the eBird
`RecentObservation` pilot.
