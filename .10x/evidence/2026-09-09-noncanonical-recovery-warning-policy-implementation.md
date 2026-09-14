Status: recorded
Created: 2026-09-09
Updated: 2026-09-09
Relates-To: .10x/tickets/done/2026-09-09-classify-noncanonical-restored-catalog-state.md

# Noncanonical recovery warning policy implementation

Implemented decision `.10x/decisions/classify-noncanonical-recovery-namespaces-as-warnings.md` without live execution. The validator derives canonical namespaces from its registry-derived expected identifiers. Tables and namespaces outside that set are emitted in bounded `noncanonicalTables` and `noncanonicalNamespaces` lists with `warningCount`; their presence alone does not fail validation. Undeclared tables inside canonical namespaces remain `unexpectedTables` and fail. Missing namespaces/tables, malformed identifiers, and unreadable canonical tables retain failure behavior. No identifier allowlist, deletion, Docker, AWS, or live catalog operation was added.

Validation: 13 focused tests passed with `--no-cov`; focused Ruff check/format, mypy, secret scan, and `git diff --check` passed.
