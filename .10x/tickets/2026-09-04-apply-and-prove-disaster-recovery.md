Status: blocked
Created: 2026-09-04
Updated: 2026-09-04
Parent: .10x/tickets/2026-09-04-build-polaris-iceberg-disaster-recovery.md
Depends-On: .10x/tickets/2026-09-04-verify-disaster-recovery-automation.md

# Apply and prove Polaris/Iceberg disaster recovery

## Scope

After explicit user approval of the exact OpenTofu plan, apply the reviewed infrastructure in the authenticated AWS account, initialize and verify the pgBackRest repository, create the first backups, confirm Iceberg recovery-copy behavior, and execute a timed isolated point-in-time restore drill with conventional application and table validation.

## Acceptance criteria

- The user reviews and explicitly approves the exact non-secret OpenTofu plan before apply.
- Apply creates only the reviewed same-account, `us-west-1` resources and policies.
- Renewable short-lived credential-process authentication works; no long-lived keys are introduced.
- pgBackRest stanza check, first full backup, WAL archive check, and repository verification/info complete successfully.
- Iceberg recovery replication/copy and 45-day version protection are observed on bounded non-sensitive test objects without targeting production data for deletion.
- A selected recovery point is restored into an isolated empty environment.
- Polaris identity and permissions validate; restored tables match expectations derived from the corresponding source-registry revision; and every registered Iceberg table, metadata/snapshot pointer, and representative read validates.
- Evidence records achieved catalog RPO and end-to-end RTO. RPO over five minutes or RTO over 60 minutes fails rather than redefining the targets.
- Recovery environment and bounded test objects are cleaned only through reviewed non-destructive procedures; retained backups are preserved.

## Explicit exclusions

- Unreviewed `tofu apply`.
- Production catalog cutover unless a real incident separately authorizes it.
- Destructive testing against authoritative warehouse objects.
- Cross-account or cross-region changes.

## References

- `.10x/decisions/startup-only-catalog-backup-gate.md`
- `.10x/specs/polaris-catalog-continuity.md`
- `.10x/specs/iceberg-object-recovery.md`
- `.10x/tickets/2026-09-04-verify-disaster-recovery-automation.md`

## Evidence expectations

Record the approved plan hash/summary, apply result, resource identities without secrets, backup/WAL status, bounded replication observation, exact timed drill procedure/results, achieved RPO/RTO, cleanup, and remaining same-account/same-region risk.

## Progress and notes

- 2026-09-04: Opened as the durable owner for live rollout and proof. The user authorized automation first, not live AWS mutation.
- 2026-09-04: User authorized generating a non-mutating plan with the default AWS profile, current caller as operator, existing `.env` primary bucket/writer role, and primary-derived recovery bucket names. Preflight `aws sts get-caller-identity --profile default` failed with `InvalidClientTokenId`; execution stopped before writing tfvars, initializing providers, generating a plan, or mutating AWS.
- 2026-09-04: User authenticated profile `databox-debug` and approved it as the replacement plan profile. Plan evidence `.10x/evidence/2026-09-04-recovery-opentofu-plan.md` records binary hash `7698bf7f60cd0d250d7e13c880265ec15663e26ff6e39b4cc6de7b2c79970922`, exact text, concrete inputs, and 18 create / 0 change / 0 destroy. No apply ran. Review found that the existing primary bucket has no replication configuration to overwrite, but also has no enabled versioning; the plan does not enable source versioning and is expected to fail replication creation. Root operator trust is also a prominent review risk.

## Blockers

Do not approve or apply the generated plan. Repair missing primary-bucket versioning management, decide whether root operator trust is acceptable, regenerate the exact plan, complete automation verification, and obtain explicit approval before any live apply.
