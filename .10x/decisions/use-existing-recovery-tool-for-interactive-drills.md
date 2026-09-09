Status: active
Created: 2026-09-09
Updated: 2026-09-09

# Use the existing recovery tool for interactive drills

## Context

The timed drill requires a human MFA session, but Pi workers are non-interactive and cannot inherit credentials created later in an operator terminal. A mode-0600 temporary credential file would bridge the processes but adds credential-at-rest handling. A new one-off orchestration script would further fragment recovery logic.

## Decision

Extend `scripts/platform/catalog_recovery.py` with an interactive `drill` subcommand and expose it through a thin `task catalog:recovery-drill` target. The command MUST run from an operator TTY, perform the reviewed AWS login/role-profile flow, capture temporary role credentials through an in-memory pipe, inject them only into required child processes, and never emit or persist credential values.

The command MUST orchestrate the existing marker-bracketed restore, isolated PostgreSQL/Polaris startup, registry-derived validation, and RPO/RTO measurement. It MUST stop before production cutover and MUST preserve recovery resources. Active marker cleanup is part of the drill; recovery-resource deletion remains separately authorized.

## Alternatives considered

- Temporary credential file: rejected by the user as an undesirable handoff and unnecessary credential persistence.
- New drill script: rejected as repository clutter and duplicated orchestration ownership.
- Manual command sequence: rejected as error-prone and difficult to review or time consistently.

## Consequences

The operator launches one repeatable command from the same interactive process tree that performs MFA. Recovery logic gains one durable owner rather than another script. The command becomes a security-sensitive interface and requires hermetic process, TTY, credential-redaction, mutation-order, and failure-preservation tests before live use.
