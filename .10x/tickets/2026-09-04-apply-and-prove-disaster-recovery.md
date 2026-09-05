Status: blocked
Created: 2026-09-04
Updated: 2026-09-04
Parent: .10x/tickets/2026-09-04-build-polaris-iceberg-disaster-recovery.md
Depends-On: .10x/tickets/2026-09-04-verify-disaster-recovery-automation.md

# Apply and prove Polaris catalog disaster recovery

## Scope

After explicit user approval of a fresh catalog-only OpenTofu plan, apply the reviewed infrastructure in the authenticated AWS account, initialize and verify the pgBackRest repository, create the first backups, and execute a timed isolated point-in-time restore drill with conventional application and table validation when the primary warehouse remains readable.

## Acceptance criteria

- The user reviews and explicitly approves the exact non-secret OpenTofu plan before apply.
- Apply creates only the reviewed same-account, `us-west-1` resources and policies.
- Renewable short-lived credential-process authentication works; no long-lived keys are introduced.
- pgBackRest stanza check, first full backup, WAL archive check, and repository verification/info complete successfully.
- A selected recovery point is restored into an isolated empty environment.
- Polaris identity and permissions validate; when the primary warehouse remains readable, restored tables match expectations derived from the corresponding source-registry revision and every registered Iceberg table, metadata/snapshot pointer, and representative read validates.
- Evidence records achieved catalog RPO and end-to-end RTO. RPO over five minutes or RTO over 60 minutes fails rather than redefining the targets.
- Recovery environment is cleaned only through reviewed non-destructive procedures; retained catalog backups are preserved.

## Explicit exclusions

- Unreviewed `tofu apply`.
- Production catalog cutover unless a real incident separately authorizes it.
- Destructive testing against authoritative warehouse objects.
- Iceberg recovery buckets, replication, object restoration, or source-bucket versioning.
- Cross-account or cross-region changes.

## References

- `.10x/decisions/startup-only-catalog-backup-gate.md`
- `.10x/specs/polaris-catalog-continuity.md`
- `.10x/decisions/catalog-backup-with-rebuildable-iceberg-warehouse.md`
- `.10x/tickets/2026-09-04-verify-disaster-recovery-automation.md`

## Evidence expectations

Record the approved replacement catalog-only plan hash/summary, apply result, resource identities without secrets, backup/WAL status, exact timed drill procedure/results, achieved catalog RPO/RTO, cleanup, and remaining same-account/same-region plus full-warehouse-rebuild risk.

## Progress and notes

- 2026-09-04: Opened as the durable owner for live rollout and proof. The user authorized automation first, not live AWS mutation.
- 2026-09-04: User authorized generating a non-mutating plan with the default AWS profile, current caller as operator, existing `.env` primary bucket/writer role, and primary-derived recovery bucket names. Preflight `aws sts get-caller-identity --profile default` failed with `InvalidClientTokenId`; execution stopped before writing tfvars, initializing providers, generating a plan, or mutating AWS.
- 2026-09-04: User authenticated profile `databox-debug` and approved it as the replacement plan profile. Plan evidence `.10x/evidence/2026-09-04-recovery-opentofu-plan.md` records binary hash `7698bf7f60cd0d250d7e13c880265ec15663e26ff6e39b4cc6de7b2c79970922`, exact text, concrete inputs, and 18 create / 0 change / 0 destroy. No apply ran. Review found that the existing primary bucket has no replication configuration to overwrite, but also has no enabled versioning; the plan does not enable source versioning and is expected to fail replication creation. Root operator trust is also a prominent review risk.
- 2026-09-04: User rejected the Iceberg recovery bucket and replication plane in favor of source rebuild. The recorded 18-create plan is invalidated and MUST NOT be applied. Source-bucket versioning is no longer required by the recovery architecture.
- 2026-09-04: User ratified account root only for initial bootstrap and the created least-privilege catalog-backup role for runtime credentials. Fresh catalog-only plan evidence `.10x/evidence/2026-09-04-catalog-only-recovery-opentofu-plan.md` records binary hash `9f01f222d146efa13ef66d13992b8bb9f190198a9caa1a9bca30d1d53fd91292`, exact text hash `f12b1ffca8cd4562099589673427a59537d4bab71f96649fa3d1d4757168e0b9`, and exactly 7 create / 0 change / 0 destroy. It contains no primary-bucket, Iceberg, or replication resource. No apply ran.

## Blockers

Blocked until independent review of the fresh exact catalog-only plan, completion of automation verification, and explicit user approval of this exact plan. The recorded 18-create plan remains rejected and must not be applied.
