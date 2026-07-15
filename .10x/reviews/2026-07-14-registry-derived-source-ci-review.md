Status: recorded
Created: 2026-07-14
Updated: 2026-07-14
Target: .10x/tickets/done/2026-07-12-derive-source-ci-from-registry.md
Verdict: pass

# Registry-derived source CI review

## Target

Implementation and evidence for `.10x/tickets/done/2026-07-12-derive-source-ci-from-registry.md`.

## Findings

- Matrix output is deterministic and exactly matches seven canonical sources/profiles.
- Contract validation rejects invalid profiles, missing artifacts, skipped scaffolds, and unregistered implementations.
- Routing covers every source package—including the four previously omitted families—plus registry, destinations, orchestration, shared tests/scripts, workflow, and dependency/task configuration.
- GitHub consumes repository-generated JSON through a job output and `fromJSON`; no manual workflow source list remains.
- Shared root tests run offline, source suites run on independent matrix runners, and aggregate coverage executes one shared plus seven sequential source processes before the 70% report.
- All 24 action invocations remain pinned to 40-character commit SHAs.
- Parent and reviewer reruns confirmed 7/7 matrix/layout, 44 focused tests, 58 offline source tests across eight isolated processes, Ruff, workspace-root-configured MyPy, workflow parsing, diff checks, and empty staging.
- Documentation and `.10x/evidence/2026-07-14-registry-derived-source-ci.md` accurately describe the implementation and limits.

## Verdict

Pass. No blocker or significant implementation defect remains.

## Residual risk

Local validation cannot prove GitHub-hosted expression evaluation, `dorny/paths-filter` event-diff behavior, matrix output transport, or runner provisioning. The first real GitHub Actions run remains the integration proof; this is recorded as a limit rather than claimed complete.
