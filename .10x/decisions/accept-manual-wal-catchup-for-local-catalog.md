Status: active
Created: 2026-09-09
Updated: 2026-09-09

# Accept manual WAL catch-up for the local catalog

## Context

The local PostgreSQL container receives short-lived MFA-issued catalog-backup credentials at startup. Those credentials expire while a multi-day local stack may continue running, so WAL files remain safely retained on the local disk but are not continuously copied off-machine. The timed drill proved that uploading only the newest segment cannot bridge an older retained gap.

The user explicitly accepts loss of catalog changes that exist only on the local machine if that machine or disk is lost before the next authenticated catch-up. They reject long-lived AWS backup credentials and do not require unattended continuous off-machine protection for this local deployment.

## Decision

For the local Databox deployment, off-machine catalog durability is established at explicit operator-authenticated catch-up points, not continuously. One MFA session MUST enumerate every locally retained pending WAL segment, upload it oldest-first, verify remote continuity through a fresh marker, and only then perform backup or recovery work.

Databox MUST NOT claim a continuous five-minute off-machine RPO for this local deployment. Drill evidence MUST distinguish the marker target-inclusion gap from the age of the previous successful off-machine catch-up. Loss between catch-ups is an explicitly accepted local-only risk.

Short-lived MFA-issued backup-role credentials remain required. Long-lived backup access keys, profile mounts, in-container credential brokers, and unattended renewal are not introduced.

This decision supersedes only the continuous five-minute local RPO claims in `.10x/decisions/startup-only-catalog-backup-gate.md`; its startup gate, visibility, one-Compose, backup cadence, and other constraints remain active.

## Alternatives considered

- **Long-lived bucket-scoped backup key:** rejected by the user.
- **IAM Roles Anywhere or another renewable workload identity:** not required for the accepted manual local durability model and would add certificate/helper operations.
- **Upload only the newest WAL during a drill:** rejected because PostgreSQL recovery requires a contiguous sequence.

## Consequences

A healthy local primary can catch up all retained WAL with one MFA session. A laptop or disk failure before catch-up can lose changes made since the last successful off-machine archive point. Operators must run an authenticated catch-up before relying on a backup or starting a recovery drill. Continuous five-minute RPO can be reinstated only through a new decision providing renewable unattended identity.
