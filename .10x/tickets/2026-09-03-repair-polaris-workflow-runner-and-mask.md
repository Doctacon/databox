Status: active
Created: 2026-09-03
Updated: 2026-09-03
Parent: None
Depends-On: .10x/tickets/done/2026-09-03-repair-hermetic-ci-and-iceberg-integration-gate.md

# Repair Polaris integration runner and credential masking

## Scope
Repair the manual Polaris/S3 integration workflow after run 33793123271 reached compose startup but failed because the hosted runner lacks the Task CLI. Mask job-generated disposable Polaris/Postgres values before writing them to GitHub Actions environment output.

## Acceptance criteria
- The workflow installs a SHA-pinned Task CLI action before `task verify`.
- Every generated Polaris/Postgres value is registered with GitHub Actions masking before it is exported.
- Workflow tests prove both requirements structurally.
- No trigger, production, IAM, or source behavior changes.

## Evidence expectations
Focused workflow tests and hosted manual rerun after merge.

## Progress and notes
- 2026-09-03: Run 33793123271 successfully assumed OIDC and started the disposable compose stack, then failed at `task verify` with `task: command not found`. Generated values appeared unmasked in logs; the stack was torn down and no verification/publication command ran.
- 2026-09-03: Added a SHA-pinned Task setup action before verification and GitHub Actions masking for every generated Polaris/Postgres value. Focused structural workflow test passes with coverage disabled; full hosted CI and a new protected manual run remain required.

## Blockers
None.
