Status: open
Created: 2026-09-09
Updated: 2026-09-09
Parent: .10x/tickets/2026-09-04-run-timed-catalog-recovery-drill.md
Depends-On: .10x/tickets/done/2026-09-04-verify-disaster-recovery-automation.md

# Add interactive catalog recovery drill command

## Scope

Extend `scripts/platform/catalog_recovery.py` with an interactive `drill` subcommand and add a thin `task catalog:recovery-drill` entry. Reuse the existing restore and validation implementations. Obtain MFA-issued role credentials through the operator's interactive AWS CLI profiles and keep them in process memory only. Orchestrate the established marker-bracketed isolated drill and emit a bounded secret-free report.

## Acceptance criteria

- No new orchestration script or credential file is created.
- The command requires a TTY and fails before mutation if authentication or preconditions fail.
- AWS CLI output containing temporary credentials is captured, parsed, redacted from every diagnostic, and passed only through child-process environment.
- The command uses the reviewed operator and backup-role profiles and never mounts AWS profiles into containers.
- Marker creation, target selection, WAL proof, new ownership-labeled volume restore, archive-disabled isolated PostgreSQL, no-bootstrap/unexposed Polaris, 25-table validator, RPO/RTO measurement, and active marker cleanup occur in reviewed order.
- Failure preserves recovery artifacts, never retries blindly, never cuts over, and never deletes recovery resources.
- Hermetic tests cover non-TTY/auth failure, secret redaction, mutation ordering, restore/start/validation failure, successful timing, active cleanup, and retained artifacts.
- Focused tests, Ruff, formatting, MyPy, secret scan, Task rendering, and diff checks pass.

## Exclusions

- Live drill execution in the implementation turn.
- AWS infrastructure mutation or a new credential broker.
- Production cutover.
- Recovery-resource cleanup.
- Changing routine WAL credential architecture.

## References

- `.10x/decisions/use-existing-recovery-tool-for-interactive-drills.md`
- `.10x/specs/polaris-catalog-continuity.md`
- `.10x/tickets/2026-09-04-run-timed-catalog-recovery-drill.md`

## Evidence expectations

Record changed files, exact tests/checks, command interface, credential boundary, mutation order, failure behavior, and explicit no-live-operation limits.

## Progress and notes

- 2026-09-09: Opened after the user rejected both a temporary credential handoff file and another one-off Python script, and explicitly authorized extending the existing recovery tool.
- 2026-09-09: Ten-minute bounded slice implemented the TTY-gated in-memory AWS authentication seam in the existing recovery tool with exact reviewed profiles, complete/unexpired session validation, child-environment mapping, and bounded secret redaction. Thirty-eight focused tests and static/security checks pass. Evidence: `.10x/evidence/2026-09-09-interactive-drill-authentication-slice.md`. No CLI/Task entry or live operation was added; full orchestration remains required.

## Blockers

Complete the marker/restore/start/validate/cleanup orchestration, Task target, failure-order tests, documentation, and independent review before live use.
