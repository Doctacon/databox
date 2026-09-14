Status: recorded
Created: 2026-09-09
Updated: 2026-09-09
Relates-To: .10x/tickets/done/2026-09-09-add-interactive-catalog-recovery-drill-command.md

# Interactive drill authentication slice

## Scope completed

Added the security-sensitive authentication seam to the existing `catalog_recovery.py`; no new script or credential file was created. `acquire_backup_role_environment()` requires both input and error TTYs before invoking AWS, runs the reviewed `databox-recovery-operator` remote login attached to the terminal, captures only the `databox-polaris-catalog-backup` credential export stdout, validates a complete unexpired session, merges it into pgBackRest child environment in memory, and reduces authentication errors to bounded credential-redacted diagnostics.

No CLI drill command or Task target is exposed yet because complete marker/restore/start/validate/cleanup orchestration could not be implemented safely within the ten-minute cutoff. Existing prepare/execute CLI behavior is unchanged.

## Validation

- `uv run pytest --no-cov -q tests/platform/test_catalog_recovery.py` — 38 passed.
- Focused Ruff check and format check — passed.
- `MYPYPATH=packages/databox uv run mypy scripts/platform/catalog_recovery.py` — passed.
- Focused secret scan — passed.
- `git diff --check` — passed.

Tests cover TTY refusal before AWS, exact reviewed profiles and interactive/captured process boundaries, in-memory credential mapping without command exposure, credential-export redaction, and expired-session refusal.

## Review repair

Independent review found that `capture_output=True` also hid AWS MFA/error stderr and that non-string `Expiration` values could escape as an unbounded attribute error. The export now captures only stdout with `stdout=subprocess.PIPE`, explicitly inherits operator-terminal stderr, and validates `Expiration` is a string before parsing. Four malformed-expiration cases and exact subprocess-boundary assertions were added. The repaired focused suite passes 42 tests plus Ruff, format, MyPy, secret scan, and diff checks.

## Boundaries and residual work

No AWS, Docker, `.env`, marker, backup, restore, or live-service operation ran. Full drill orchestration, thin Task target, orchestration failure tests, runbook update, and independent review remain required. The ticket remains open and the timed drill remains blocked.
