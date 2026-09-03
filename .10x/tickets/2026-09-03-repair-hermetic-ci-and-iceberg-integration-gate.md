Status: active
Created: 2026-09-03
Updated: 2026-09-03
Parent: None
Depends-On: None

# Repair hermetic CI and add protected Iceberg integration gate

## Scope

Repair Databox CI exposed by PR #41. Make real Dagster/source graph construction credential-free and side-effect-free while preserving real fixture-backed source tests and fail-closed Iceberg execution. Repair source-layout validation so it checks retained source structure without deployment configuration. Add a manual-only protected GitHub Actions Polaris/S3 integration workflow that performs real destination verification with environment secrets. Add required schema-removal acknowledgements to PR #41 for the intentionally removed Rufous contracts.

## Acceptance criteria

- GitHub-hosted ordinary CI collects and passes with no Polaris/S3 credentials, network source calls, or destination writes.
- Real Dagster definitions, asset keys, jobs, source builders, and source-layout contracts are exercised without mocking a source or destination execution result.
- Attempting real Iceberg destination execution without credentials fails before any publication; a focused regression test proves this.
- `check_source_layout.py` passes for all retained sources in an empty credential environment and remains strict about structural source requirements.
- A dedicated `workflow_dispatch` workflow targets a protected environment, accepts no secret values as inputs, and runs the real Polaris/S3 integration verification using only environment secrets.
- The manual integration workflow is not called by PR CI, push CI, schedules, or deployment workflows.
- PR #41 contains exact `accept-breaking-change:` acknowledgements for the ten intentional product-contract removals.
- Local empty-environment hosted-equivalent commands, `task ci`, docs/pre-commit/secret checks, and the changed workflow lint pass.

## Explicit exclusions

- Mocking or weakening real source contract tests.
- Automatic integration execution on PRs, pushes, schedules, or `main`.
- Production deployment changes.
- Changing Polaris/S3 authority or artifact semantics.

## References

- `.10x/decisions/manual-protected-iceberg-integration-gate.md`
- `.10x/tickets/done/2026-09-03-extract-rufous-repository.md`
- PR #41: https://github.com/Doctacon/databox/pull/41

## Evidence expectations

Record failed CI diagnosis, import/execution boundary tests, empty-environment output, workflow trigger/environment inspection, protected integration launch instructions, PR acknowledgement diff, and residual limitation that protected dispatch requires an operator.

## Progress and notes

- 2026-09-03: Opened after PR #41 failed schema acknowledgement, source-layout, and pytest collection gates. User selected manual protected dispatch for real Polaris/S3 integration.
- 2026-09-03: Implemented deferred, fail-closed writer credential validation at real asset execution boundaries; graph import remains real but no-I/O. Repaired post-extraction source-layout invariants and added public-interface-only USFWS recognition, AVONET atomic-replace coverage, empty-credential graph/layout regressions, and a structural manual-workflow test. Added the manual protected Polaris/S3 workflow and exact ten PR #41 acknowledgements. Focused tests passed 54; schema gate acknowledged all removals; `task ci` passed 388 tests at 85.29%. Evidence: `.10x/evidence/2026-09-03-hermetic-ci-and-iceberg-integration-gate.md`.
- 2026-09-03: Review initially found the empty-environment subprocess could still read local `.env`; `DATABOX_ENV_FILE` now explicitly bypasses it in the regression. Final review passed. Final `task ci` passed 390 tests at 85.31%, with pre-commit, secret, generation, and diff checks; commit `824c8b1` was pushed to PR #41.
- 2026-09-03: Reopened after confirming the repository has `DATABOX_AWS_ROLE_ARN` rather than static AWS keys. Updated the manual workflow to use GitHub OIDC, short-lived role credentials, and job-generated disposable Polaris/Postgres values. The existing `DATABOX_AWS_S3_BUCKET` secret supplies the bucket; provider tokens remain secret references.

## Blockers

Independent review and hosted CI rerun remain required before closure.
