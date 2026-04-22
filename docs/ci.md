# CI Routing

Databox CI runs per-PR and on every push to `main`. Most changes only touch one source or just the docs — the workflow uses path-based routing so a docs typo or an `ebird`-only change doesn't drag the full test matrix through a cold install.

The routing logic lives in `.github/workflows/ci.yaml`; this page explains *why* it's shaped the way it is and what to expect when a PR runs.

## The classifier

A first job, `Classify changed paths`, runs on every event. It uses [`dorny/paths-filter`](https://github.com/dorny/paths-filter) to label the diff with a set of boolean outputs:

| Output | Matches |
| --- | --- |
| `docs` | `docs/**`, any root `*.md`, `mkdocs.yml` |
| `src_ebird` | `packages/databox-sources/databox_sources/ebird/**`, `packages/databox-sources/tests/ebird/**`, `transforms/main/models/ebird/**`, `soda/contracts/ebird{,_staging}/**`, `domains/ebird.py` |
| `src_noaa` | same shape, scoped to `noaa` |
| `src_usgs` | same shape, scoped to `usgs` |
| `cross_cutting` | `packages/databox/**`, shared source plumbing (`__init__.py`, `base.py`, `registry.py`, `_*.py`), `scripts/**`, top-level `tests/**`, analytics models & contracts, `pyproject.toml`, `uv.lock`, `Taskfile.yaml`, `.pre-commit-config.yaml` |
| `ci_config` | `.github/workflows/**` |

Two composed outputs are derived from those:

- `needs_full` — `true` on every push to `main`, on any `cross_cutting` change, or on any `ci_config` change
- `needs_any_source` — `true` when any `src_*` filter matched

## Routing rules

| Job | Runs when |
| --- | --- |
| `lint` (ruff), `typecheck` (mypy) | `needs_full \|\| needs_any_source` |
| `tests-core` | `needs_full` only (runs `tests/` + `packages/databox`) |
| `tests-ebird` / `tests-noaa` / `tests-usgs` | `needs_full \|\| src_<source>` |
| `sqlmesh-lint` | `needs_full \|\| needs_any_source` |
| `staging-codegen-drift` | `needs_full \|\| needs_any_source` |
| `soda-validate` | `needs_full \|\| needs_any_source` |
| `source-layout-lint` | always (cheap; the layout is the scaling invariant) |
| `schema-contract-gate` | always on `pull_request` (protects downstream consumers) |

The always-on jobs are intentional — they cost a fraction of a minute each and enforce invariants that must not drift silently.

## What each routing decision looks like

**Docs-only PR** (`docs/**` or `*.md`):
`source-layout-lint` + `schema-contract-gate` only. Everything else skips.

**Single-source PR** (e.g. `ebird` only):
`lint`, `typecheck`, `sqlmesh-lint`, `staging-codegen-drift`, `soda-validate`, `tests-ebird`, `source-layout-lint`, `schema-contract-gate`. `tests-core`, `tests-noaa`, `tests-usgs` skip.

**Cross-cutting PR** (anything in `packages/databox/**`, `scripts/**`, etc.):
Full matrix.

**CI config PR** (`.github/workflows/**`):
Full matrix — routing bugs must be visible before they're merged.

**Push to `main`**:
Full matrix, always. The event_name check in `needs_full` enforces this independently of the filter.

## Why `tests-core` is gated on `needs_full` only

`tests/` and `packages/databox/**/tests/**` exercise the shared infrastructure — config, orchestration, quality engine, schema gate, staging codegen. A source-only PR can't reach any of that code path, so running it would only burn minutes.

Per-source tests live under `packages/databox-sources/tests/<source>/` and are wired to their matching `src_<source>` filter. The filter includes the test directory so a test-only change still triggers the source's job.

## When routing is wrong

The classifier is an approximation. If a PR changes only `soda/contracts/ebird/` but should also re-run NOAA tests (e.g. because a shared utility silently regressed), `needs_full` won't flip.

The guardrails:

1. **`.github/workflows/**` forces `needs_full`.** Any routing refinement flows through the workflow file itself, and the refinement PR sees the full matrix.
2. **Pushes to `main` always run the full matrix.** Per-PR routing is the fast path; the post-merge run is the safety net.
3. **Any shared library change lives under `packages/databox/**` or `scripts/**`**, both in `cross_cutting`. If you find yourself sharing logic across sources without putting it there, the routing will start lying — move it.

If you add a new source, three things change:

- Add a `src_<name>` filter block mirroring the existing three
- Add a `tests-<name>` job gated on `needs_full || src_<name>`
- Update the `needs_any_source` compose step to include the new filter output

The `source-layout-lint` job will already enforce the directory shape.
