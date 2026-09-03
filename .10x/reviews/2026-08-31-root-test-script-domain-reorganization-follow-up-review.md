Status: recorded
Created: 2026-08-31
Updated: 2026-08-31
Target: .10x/tickets/done/2026-08-31-organize-root-tests-and-scripts-by-domain.md
Verdict: concerns

# Root test/script domain reorganization follow-up review

## Target

The repaired implementation of `.10x/tickets/done/2026-08-31-organize-root-tests-and-scripts-by-domain.md`, following the first independent review's findings about moved SQLMesh shell-script root resolution and metrics-test allocation.

## Reviewer provenance

Independent read-only reviewer run `aab82364-898e-44f5-82b2-d5b9c5673a32` inspected the repaired diff, ticket, evidence, scripts, tests, and active references. The reviewer returned this assessment in its run output but could not itself persist the claimed record because its tool set was read-only; the parent recorded the returned assessment here.

## Findings

### Resolved: SQLMesh repository-root calculation

All four moved scripts now resolve two parent levels from their domain directories:

- `scripts/analytics/sqlmesh_plan_prod.sh`
- `scripts/rufous_media/sqlmesh_plan_rufous_public.sh`
- `scripts/rufous_media/sqlmesh_plan_rufous_media.sh`
- `scripts/rufous_media/sqlmesh_plan_rufous_inaturalist_media.sh`

`tests/platform/test_repository_layout.py` parametrizes all four scripts, copies them into a temporary repository, supplies fake Python/SQLMesh executables, and verifies invocation count, working directory, and executable path without opening production state or running a real SQLMesh plan.

### Resolved: metrics allocation

The metrics test now resides at `tests/platform/test_metrics.py`, matching the ratified taxonomy. `docs/metrics.md` uses the corrected path, and the reviewer found no stale active reference to either `tests/test_metrics.py` or `tests/analytics/test_metrics.py`.

### Satisfied implementation properties

- Root `tests/` and `scripts/` contain only domain directories.
- Recursive pytest discovery remains configured.
- Active path scans found no unintended stale old path.
- Task, CI, hook, scaffold, documentation, Python resource, and shell-root path-sensitive consumers were repaired.
- No compatibility wrapper, duplicate implementation, reorganized-directory cache, staged file, or generated output was reported.
- Focused repair tests passed 10/10; collection found 1,498 tests; Ruff, formatting, `bash -n`, strict MkDocs, secret scans, and `git diff --check` passed.

No remaining defect introduced by the reorganization was found.

## Acceptance mapping

1. Satisfied: root tests are grouped and recursively discoverable.
2. Satisfied: root scripts and templates are grouped under ratified domains.
3. Satisfied: active reference scans are clean; remaining old paths are historical evidence.
4. Satisfied: path-sensitive consumers and shell root calculations are repaired and regression-tested.
5. Not literally satisfied: the recorded default suite has three separately owned, pre-existing failures under `.10x/tickets/done/2026-08-31-repair-preexisting-default-python-test-failures.md`.
6. Not literally satisfied: the separately owned pre-existing USFWS source-contract mismatch under `.10x/tickets/done/2026-08-31-reconcile-usfws-source-contract-checker.md` keeps source-layout/matrix gates red; other relevant safe gates pass.
7. Satisfied by implementation evidence and attestation.
8. Satisfied: independent review found coherent allocation and no orphaned moved command or test after repair.

## Verdict

**Concerns.** The implementation itself is acceptable and the review's two in-scope findings are resolved. The owning ticket cannot close because acceptance criteria 5 and 6 remain literally unsupported by green aggregate gates, even though evidence attributes both failures to separately ticketed pre-existing conditions.

## Residual risk

- The complete default network-blocked suite was not rerun after the bounded repair; its three known failures remain separately ticketed.
- The USFWS source-contract mismatch remains unresolved.
- No live provider, real production SQLMesh plan, `task verify`, `task full-refresh`, publication, or deployment ran.
- Executable-mode preservation and final Git state rely partly on implementation attestation; parent inspection confirmed no staged files and the expected moved/untracked working-tree shape but did not rerun all verification.
