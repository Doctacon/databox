# CI Routing

Databox CI runs for pull requests and every push to `main`. Documentation-only
changes skip the heavy jobs. Any ingestion-source-related change runs the
**complete source matrix** derived from the canonical Python registry; CI never
maintains a per-source job or path list.

The workflow lives in `.github/workflows/ci.yaml`. The executable source
contract lives in `packages/databox/databox/config/sources.py` and is exposed to
CI by `scripts/source_ci.py`.

## Classifier

The `Classify changed paths` job uses the pinned `dorny/paths-filter` action and
publishes these relevant outputs:

| Output | Matches |
| --- | --- |
| `docs` | `docs/**`, root Markdown files, and `mkdocs.yml` |
| `source_related` | all source packages/tests, canonical registry, destinations, orchestration, scripts, top-level tests, CI workflows, and dependency/task configuration |
| `cross_cutting` | shared application/orchestration/scripts/tests and analytics/codegen surfaces |
| `ci_config` | `.github/workflows/**` |
| `needs_full` | every push to `main`, or any cross-cutting/CI workflow change |
| `needs_any_source` | exactly the broad `source_related` result |

The source filter is deliberately broad. At seven sources, running all source
suites is cheaper and safer than maintaining changed-source exceptions. A
change only to AVONET, GBIF, Xeno-canto, or USGS Earthquakes therefore receives
the same source verification as eBird, NOAA, or USGS.

## Registry-derived matrix

`python scripts/source_ci.py matrix` performs two operations atomically:

1. validates registry, package, domain, source-builder, raw-table, verification
   profile, manifest, and required-test-file coherence;
2. emits deterministic compact JSON for GitHub Actions.

Current output contains seven entries ordered by source name. GitHub Actions
passes that JSON through a job output and consumes it with `fromJSON(...)` in
one `tests-sources` matrix job. Each matrix entry runs on its own runner with
recording disabled and provider network blocked. `fail-fast: false` reports all
source failures rather than cancelling sibling sources.

Adding a future source requires its canonical registry entry, source/domain
implementation, and profile-required tests. It does **not** require editing a
CI source list. An incomplete source makes matrix generation fail.

## Routing rules

| Job | Runs when |
| --- | --- |
| Ruff and MyPy | `needs_full || needs_any_source` |
| Core pytest | `needs_full` |
| Source matrix generation | `needs_full || needs_any_source` |
| Registry-derived source pytest matrix | `needs_full || needs_any_source` |
| SQLMesh lint, codegen drift, Soda structure | `needs_full || needs_any_source` |
| Source contract/layout validation | every push and pull request |
| Schema contract gate | every pull request |
| Aggregate coverage | `needs_full` |

Workflow changes force the full matrix, and pushes to `main` always run it.

## Aggregate coverage

The aggregate coverage job first runs core tests, then calls:

```bash
python scripts/source_ci.py coverage
```

The command validates the same canonical contract, executes root-level shared
source-harness tests once, then executes every registered source suite through a
separate sequential `coverage run --append` process. This preserves the active
VCR/dlt HTTP-client isolation contract while ensuring shared harness behavior
and all seven sources contribute to the workspace coverage threshold. Every
process uses `--record-mode=none --block-network`.

## Local verification

```bash
# Validate and inspect the matrix
uv run python scripts/source_ci.py matrix --pretty

# Validate source layout/profile artifacts
uv run python scripts/check_source_layout.py

# Run all source suites offline without combining their HTTP clients
uv run python scripts/source_ci.py coverage
```

Local YAML/static tests validate matrix determinism, workflow consumption,
action pinning, broad path classification (including the four formerly omitted
sources), missing profile artifacts, and invalid profiles. They cannot fully
emulate GitHub's event expressions, hosted runner behavior, or `dorny` diff
calculation; the workflow run remains the final integration check.
