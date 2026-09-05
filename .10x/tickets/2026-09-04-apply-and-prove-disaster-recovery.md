Status: blocked
Created: 2026-09-04
Updated: 2026-09-04
Parent: .10x/tickets/2026-09-04-build-polaris-iceberg-disaster-recovery.md
Depends-On: .10x/tickets/2026-09-04-simplify-recovery-infrastructure-to-catalog-only.md

# Provision and prove Polaris catalog backups

## Scope

After explicit user approval of a fresh catalog-only OpenTofu plan, apply only the reviewed infrastructure in the authenticated AWS account, preserve local OpenTofu state, assume the least-privilege backup role, initialize and verify the pgBackRest repository, and create and inspect the first physical backup plus WAL archive before restore automation begins.

## Acceptance criteria

- The user reviews and explicitly approves the exact non-secret OpenTofu plan before apply.
- Apply creates only the reviewed same-account, `us-west-1` resources and policies.
- Local state is preserved at `infra/recovery/terraform.tfstate` on the FileVault-protected host and its encrypted machine backup.
- OpenTofu creates `databox-recovery-operator` without access keys or login-profile secrets, grants only assumption of the catalog-backup role, and restricts that role's trust to the exact user ARN. Console access/password and MFA enrollment remain manual and never enter state.
- Root is used only for reviewed bootstrap/repair applies and role-access verification, then logged out; Compose receives only short-lived catalog-backup-role credentials.
- pgBackRest stanza check, first full backup, WAL archive check, and repository verification/info complete successfully.
- Evidence records successful repository access, first physical backup, WAL archive round trip, and repository metadata without claiming restore or RPO/RTO proof.
- Retained catalog backups and local state are preserved.

## Explicit exclusions

- Unreviewed `tofu apply`.
- Restore automation, restore execution, timed RPO/RTO proof, or production catalog cutover.
- Destructive testing against authoritative warehouse objects.
- Iceberg recovery buckets, replication, object restoration, or source-bucket versioning.
- Cross-account or cross-region changes.

## References

- `.10x/decisions/startup-only-catalog-backup-gate.md`
- `.10x/specs/polaris-catalog-continuity.md`
- `.10x/decisions/catalog-backup-with-rebuildable-iceberg-warehouse.md`
- `.10x/tickets/2026-09-04-simplify-recovery-infrastructure-to-catalog-only.md`

## Evidence expectations

Record the approved replacement catalog-only plan hash/summary, durable local-state location and backup confirmation, apply result, resource identities without secrets, root logout, assumed-role identity, backup/WAL status, and remaining same-account/same-region risk.

## Progress and notes

- 2026-09-04: Opened as the live rollout owner; automation was authorized before AWS mutation.
- 2026-09-04: Default-profile authentication failed before planning; no mutation occurred.
- 2026-09-04: Three generated plans were invalidated in sequence by removal of Iceberg replication, addition of TLS enforcement, and then independent findings for multipart abort, rollout ordering, and state ownership. None was applied.
- 2026-09-04: User ratified proof-first ordering: approved infrastructure and a real pgBackRest backup/WAL round trip must succeed before isolated restore automation. Local state is operator-owned at `infra/recovery/terraform.tfstate`, protected by FileVault and normal encrypted machine backup; no remote backend is added.
- 2026-09-04: Repaired plan evidence `.10x/evidence/2026-09-04-catalog-only-final-opentofu-plan.md` records binary hash `77cf23e243859dac24974be21adfb7f5bdf94bb6ec8168cf70039ddda3b69212` and 8 create / 0 change / 0 destroy. It is not approved or applied.
- 2026-09-04: Independent review `.10x/reviews/2026-09-04-catalog-only-final-plan-review.md` passed with no findings. Parent immediately reproduced the exact binary hash. The plan is safe to present but remains unauthorized until the user explicitly approves this hash for apply.
- 2026-09-04: User explicitly approved exact plan hash `77cf23e243859dac24974be21adfb7f5bdf94bb6ec8168cf70039ddda3b69212` using root only for bootstrap. Preconditions matched and exact-plan apply succeeded: 8 added, 0 changed, 0 destroyed. Root-side checks passed for all bucket controls and IAM policy; local state is mode 0600 with hash recorded in `.10x/evidence/2026-09-04-catalog-backup-infrastructure-apply.md`. Role verification then failed because AWS rejects `AssumeRole` by a root account. Root was intentionally not logged out so a reviewed trust/operator repair remains possible. No object, backup, WAL, service, volume, or restore operation ran.
- 2026-09-04: User approved step 1 of the operator repair: declare console-only `databox-recovery-operator`, no access key/login profile/password/MFA state, permission only to assume the catalog-backup role, and exact user trust. Manual console access and MFA remain step 2.
- 2026-09-04: Implemented step 1 and generated the normal-refresh repair plan recorded at `.10x/evidence/2026-09-04-recovery-operator-repair-plan.md`: binary hash `677f9ce7a6b5ee499f8bebb71b96115d8e443a31b1cbcf6f6f4eb2767fc96bcc`, 2 create / 1 in-place role-trust update / 0 destroy, no bucket action or unexpected drift. Twenty-five focused tests plus OpenTofu/Ruff/format/diff validation pass. Root remains active; no apply, credential, password, MFA, backup, or AWS mutation occurred.
- 2026-09-04: Independent review `.10x/reviews/2026-09-04-recovery-operator-repair-plan-review.md` rejected that plan because MFA was documented but absent from the role trust policy. The replacement must require `aws:MultiFactorAuthPresent=true`; the CLI path uses the console-login operator as `source_profile` and an MFA-configured role profile so AssumeRole explicitly prompts for a token.
- 2026-09-04: Added the exact-user MFA trust condition, focused coverage, and runbook explanation that the human supplies MFA during AssumeRole while pgBackRest receives only resulting short-lived credentials. Fresh state-aware plan evidence `.10x/evidence/2026-09-04-recovery-operator-mfa-repair-plan.md` records hash `a65f87e7a160e26ffd9932e48e71431c7c7158ca8b3c0aab49d27187eaf7fcc4`, 2 create / 1 update / 0 destroy, and no bucket changes. Prior repair plan is invalid; no apply occurred.
- 2026-09-04: Independent review `.10x/reviews/2026-09-04-recovery-operator-mfa-plan-review.md` passed with no findings. The exact plan is safe to present but remains unauthorized pending explicit user approval.
- 2026-09-04: User explicitly approved plan hash `a65f87e7a160e26ffd9932e48e71431c7c7158ca8b3c0aab49d27187eaf7fcc4`. Exact preconditions matched, but OpenTofu rejected the saved binary before mutation because its dependency selections and state lineage did not match the actual local working directory/state. Evidence `.10x/evidence/2026-09-04-recovery-operator-mfa-repair-apply.md` confirms unchanged state hash/mode/resources, absent operator user, active root, and no AWS mutation. The unusable binary must not be retried.
- 2026-09-04: Recovered with a plan generated literally inside `infra/recovery/` and retained there as ignored `recovery-operator-mfa-repair.tfplan`; no `tofu init` ran before or after. Evidence `.10x/evidence/2026-09-04-recovery-operator-mfa-local-plan.md` records binary hash `45a78d799032c227b1d525433515e2093b452be0f346ea4c2a6d14d9ae5bbc35`, exact matching embedded/current state lineage `4303cf7d-c96f-55db-0ba3-a1ff1f492194`, serial `2`, lock hash `02d2b020180bf03e77af58e54b0539ff0da8e5b4f06db21ff347be0cf092cfd3`, and 2 create / 1 update / 0 destroy with no bucket drift.
- 2026-09-04: Independent review `.10x/reviews/2026-09-04-recovery-operator-lineage-safe-plan-review.md` passed with no findings. The exact local binary is safe to present but remains unauthorized pending explicit user approval.
- 2026-09-04: User explicitly approved local plan hash `45a78d799032c227b1d525433515e2093b452be0f346ea4c2a6d14d9ae5bbc35`. Exact lineage/serial/lock/identity preconditions matched; exact apply completed 2 added / 1 changed / 0 destroyed. Evidence `.10x/evidence/2026-09-04-recovery-operator-mfa-repair-apply-success.md` proves zero access keys/login profile, assume-only user policy, exact-user MFA trust, unchanged bucket controls, state serial `3`/mode `0600`, and active root. No credential, backup, WAL, service, volume, or restore operation ran.
- 2026-09-04: Manual console access plus passkey and TOTP enrollment succeeded, but live `aws login --remote` exposed that the assume-only user policy omitted AWS's required OAuth actions. The user ratified exactly `signin:AuthorizeOAuth2Access` and `signin:CreateOAuth2Token` on `arn:aws:signin:us-west-1:734815189723:oauth2/public-client/remote`. Evidence `.10x/evidence/2026-09-04-recovery-operator-login-repair-plan.md` records lineage-safe plan hash `276b5ad36a1a6a13577a2b4b9a3e985c0e0ff1d0fe41340ec61221860f945f45`, 0 add / 1 user-policy update / 0 destroy, and no role or bucket changes.
- 2026-09-04: User explicitly approved and exact-plan apply succeeded: 0 added / 1 changed / 0 destroyed. Evidence `.10x/evidence/2026-09-04-recovery-operator-login-repair-apply.md` proves the exact scoped sign-in and AssumeRole permissions, unchanged exact-user/MFA role trust, state serial `4`/mode `0600`, active root, and no bucket action or S3 operation.

## Blockers

Prove operator `aws login`, MFA-protected role assumption, and root logout before injecting role credentials into Compose. Preserve `infra/recovery/terraform.tfstate` and include it in the operator's encrypted machine backup.
