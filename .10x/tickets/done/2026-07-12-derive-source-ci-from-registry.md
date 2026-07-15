Status: done
Created: 2026-07-12
Updated: 2026-07-14
Parent: .10x/tickets/done/2026-07-12-unify-dlt-source-contract-and-ci.md
Depends-On: .10x/tickets/done/2026-07-12-consolidate-canonical-dlt-source-registry.md, .10x/tickets/done/2026-07-12-complete-source-contract-test-suites.md

# Derive source CI from the canonical registry

## Scope

Replace hand-maintained per-source GitHub Actions routing/test enumeration with deterministic registry-derived source verification.

- Add a repository command that validates the source contract and emits the active source matrix as deterministic JSON.
- Make source-related changes run a matrix containing all registered sources.
- Replace the current eBird/NOAA/USGS-only source jobs with the registry-derived matrix.
- Include every registry source in aggregate coverage through isolated sequential pytest processes.
- Add tests that prove omitted-source path regressions and future registry entries cannot silently bypass source verification.
- Keep source VCR processes isolated according to active knowledge.

## Acceptance criteria

- Matrix output contains exactly the seven canonical source names and declared profiles in deterministic order.
- GitHub Actions consumes the command output with `fromJSON` or an equivalent registry-derived mechanism; no workflow source-name list remains.
- Changes only to AVONET, GBIF, Xeno-canto, or USGS Earthquakes source/test/domain paths require the complete source matrix.
- Shared source/orchestration/test-harness/dependency changes also require the complete source matrix.
- Aggregate coverage runs all seven source suites in separate pytest processes before enforcing the workspace threshold.
- Contract validation fails on missing profile tests, unregistered source implementations, invalid profiles, or matrix/registry mismatch.
- Workflow YAML, action pins, local CI checks, and all source suites pass without provider network access.

## Evidence expectations

Record old/new workflow enumeration, generated matrix output, path-classification tests for all omitted-source regressions, aggregate coverage command/results, workflow validation, and limits of local GitHub Actions emulation.

## Explicit exclusions

- Fine-grained changed-source skipping
- CI provider calls or fixture recording
- Runtime source, Dagster schedule, SQLMesh, Soda, API, or warehouse behavior changes
- Dependency upgrades not required for the registry-derived matrix

## Progress and notes

- 2026-07-12: Official GitHub Actions documentation confirms job outputs can define a downstream matrix. The broad all-source matrix was user-ratified as part of the Python-registry architecture.
- 2026-07-14: Added `scripts/source_ci.py`: deterministic seven-source profile matrix, contract validation, root shared-harness coverage, and isolated sequential coverage for every registered source.
- 2026-07-14: Replaced three manual source filters/jobs with one broad `source_related` classifier, one registry matrix-output job, and one `fromJSON` source matrix. Source jobs and aggregate coverage are recording-disabled and network-blocked; all 24 action uses remain pinned.
- 2026-07-14: Added matrix determinism/future-entry/invalid-profile/artifact-gap/workflow/path/action-pin tests and corrected the layout checker to fail invalid profiles without crashing.
- 2026-07-14: Validation passed: 44 focused tests; 58 offline source tests in eight isolated coverage processes (2 shared plus 56 across seven sources); deterministic 7/7 matrix/layout; Ruff; formatting; MyPy; YAML/action-pin checks; diff check; empty staging. Evidence: `.10x/evidence/2026-07-14-registry-derived-source-ci.md`.
- 2026-07-14: Parent and fresh reviewer reproduced the matrix, workflow, focused tests, isolated source coverage, static checks, and empty staging. Review passed: `.10x/reviews/2026-07-14-registry-derived-source-ci-review.md`.
- 2026-07-14: Retrospective complete. Registry-derived enumeration and broad source-related routing are fully captured by the active decision/specification and executable regression tests. GitHub-hosted integration remains an explicitly bounded verification limit, not unfinished local implementation; no additional ticket, knowledge, or skill record is required.

## Blockers

None.

## References

- `.10x/specs/registry-derived-source-verification.md`
- `.10x/decisions/python-source-registry-as-canonical-contract.md`
- `.github/workflows/ci.yaml`
