Status: recorded
Created: 2026-09-08
Updated: 2026-09-08
Target: .10x/evidence/2026-09-08-isolated-catalog-restore-files-success.md
Verdict: concerns

# Isolated catalog file-restore review

## Finding

**P2 — owning ticket contradicted the later authorization.** The ticket still excluded every live restore and live-backup download even though the user separately authorized exact isolated file-restore attempts. The ticket must record that narrow supersession while continuing to exclude unauthorized restore, restored-service startup, validation, cutover, and timed claims.

## Technical assessment

Pass. Evidence coherently supports a new ownership-verified volume, successful pgBackRest file restore, PostgreSQL 17 files, exact recovery target/action/configuration, unchanged active services/data, untouched prior volumes, credential secrecy, and no restored-service startup or recovery-objective overclaim.

## Residual risk

PostgreSQL has not replayed WAL or reached the target. Polaris/catalog/table validation and end-to-end RPO/RTO remain unproven. All recovery volumes remain preserved and require authorization before read-write reuse or deletion.
