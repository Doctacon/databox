Status: active
Created: 2026-07-12
Updated: 2026-07-12

# Warehouse-first cleanup policy

## Audience

Repository cleanup optimizes first for data engineers evaluating, running,
extending, or contributing to the DuckDB warehouse.

## First-wave boundary

The first cleanup wave covers the public repository surface and warehouse core:
README/docs, commands, repository layout, ingestion/modeling workflow, and
warehouse package boundaries. Rufous remains a reference consumer and its
internals stay behaviorally stable unless a warehouse-boundary cleanup requires
a narrow compatibility edit.

## Refactoring rule

Remove or consolidate only proven dead or duplicate paths. Evidence must show
that a candidate has no active consumer or that the replacement is behaviorally
equivalent. Preserve all existing functionality, tests, safety controls,
provider contracts, data semantics, and operational behavior.

Prefer deletion, direct naming, and existing boundaries over new abstraction.
Large-module decomposition is not a first-wave goal.
