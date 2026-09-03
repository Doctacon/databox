Status: done
Created: 2026-09-03
Updated: 2026-09-03
Parent: .10x/tickets/done/2026-09-03-extract-rufous-repository.md
Depends-On: .10x/tickets/done/2026-09-03-bootstrap-standalone-rufous.md, .10x/tickets/done/2026-09-03-migrate-rufous-models-and-backend.md

# Migrate Rufous web, public release, and deployment

## Scope

Reconcile the copied React app, Cloudflare worker, public/media scripts, workflows, docs, configs, and infra with the standalone repository. Remove source-refresh UI/API controls, Databox checkout-relative paths, stale Quack/source-loading commands, and Databox package names. Preserve every public privacy/media safety gate and production `if: ${{ false }}`.

## Acceptance criteria

- Source-refresh controls and tests are removed without a runtime Databox launcher.
- All commands/workflow paths are destination-relative and consume the local product artifact contract.
- App typecheck, all 537 remaining tests, and production/public builds pass after the required removal of eight source-refresh tests; worker 71 tests pass.
- Public Python suites, workflow tests, audits, and credential-free synthetic checks pass.
- Production remains fail-closed and existing deployment is untouched.
- npm audit findings are reviewed and resolved or explicitly accepted with bounded follow-up.

## Explicit exclusions

- Databox deletion.
- Production enablement.
- Remote artifact distribution.

## Evidence expectations

Record path/coupling scans, app/worker/public checks, workflow diff, dependency audit, and review.

## Progress and notes

- 2026-09-03: Removed source-refresh UI/API/control tests, rewrote workflow triggers/commands for standalone paths, removed Databox/Quack/source-launch coupling, preserved production `if: ${{ false }}`, repaired all eleven workflow contract tests, and updated product operations/public-release documentation.
- 2026-09-03: Python 1,072/1,072, app 537/537 plus typecheck/production/public builds, worker 71/71, and SQLMesh 11/11 passed. Credential-free synthetic export/local immutable publication/public safety audit passed. Ruff, format, MyPy, pre-commit, secret, and diff checks passed. Safe lockfile updates reduced npm audit findings from four to zero without test/build regressions. Evidence: `.10x/evidence/2026-09-03-rufous-web-public-deployment-migration.md`.
- 2026-09-03: Independent review blocked closure on a missing Rufous-owned R2 dependency, an untested artifact/model-preparation workflow seam, and stale standalone documentation. Added the `rufous[r2]` extra (`boto3>=1.40.0,<2`, locked to 1.43.56), corrected the package error, and proved no-network R2 client initialization. The still-disabled production job now validates an explicitly configured local `RUFOUS_DATABOX_PRODUCT_PATH` and runs Rufous public model preparation when enabled; it does not acquire a remote artifact. Updated workflow assertions, README, and public-release links/instructions. Focused 43 tests, `uv sync --extra r2 --locked`, Ruff, MyPy, pre-commit, secret scan (268 files), and diff check passed.
- 2026-09-03: Second review found residual nonexistent Task/Databox bootstrap commands in standalone operator docs. Replaced them with current Rufous commands and artifact instructions; workflow/public-release tests (43), both npm audits, and diff checks passed. Closure review: `.10x/reviews/2026-09-03-rufous-web-public-deployment-review.md`.

## Blockers

None.
