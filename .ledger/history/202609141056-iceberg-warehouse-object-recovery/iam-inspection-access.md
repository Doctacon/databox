Status: stage 1 applied and verified; stage 2 abandoned without apply
Created: 2026-09-14

# Narrow warehouse-writer IAM inspection access

## Decision and authority

The user authorized drafting a narrow read-only IAM policy for review after the authenticated non-root `databox-recovery-operator` received `AccessDenied` on the four writer-discovery calls. That initial authorization was drafting-only. The user subsequently directed use of the existing OpenTofu ownership instead of console changes. Local implementation and tests are complete. Following user-performed root CLI authentication, the agent generated a fresh live-refresh plan; independent review found no blocking findings. See [exact-plan evidence](iam-inspection-plan.md). The user then explicitly approved that saved binary/hash; freshness checks passed, the apply succeeded, and exact policy read-back matched. See [apply evidence](iam-inspection-apply.md). No import was needed, and that plan approval is consumed. Non-root capability verification succeeded, and root CLI cache absence was verified; see [apply evidence](iam-inspection-apply.md). The user later authorized preparation and planning—but not apply—of an exact-policy-document follow-up. After reviewing where that plan would leave recovery, the user abandoned it and chose direct root-backed inspection/infrastructure work until warehouse recovery goals are complete. The saved stage-2 binary/log were deleted; see [cancelled stage-2 plan evidence](iam-managed-policy-inspection-plan.md).

Review [the JSON policy template](warehouse-writer-iam-inspection.policy.json) with [the inspection evidence](inspection.md). The JSON describes only deployed stage 1, deliberately contains `<ACCOUNT_ID>`, and is **not deployable as supplied**. The user selected the local `.env` as the account-ID input, rather than manually editing the JSON template:

```dotenv
# Local .env only; replace this illustrative value with the actual account ID.
DATABOX_AWS_ACCOUNT_ID=123456789012
```

The JSON remains a review illustration, not the deployment artifact. The selected implementation uses OpenTofu's native `jsonencode` and existing validated `var.aws_account_id`; no standalone JSON renderer is needed for that path. The `.env` value was locally checked for 12 digits and equality with both the configured operator account and existing tfvars, without emitting its value. Do not publish rendered deployment identifiers here. AWS IAM and OpenTofu do not automatically load this `.env` setting.

No additional `.env` renderer/application setting is implemented; the user's local setting has been checked, not edited. Do not add an unused runtime setting to `.env.example`. Infrastructure already uses validated `var.aws_account_id`, supplied by ignored local `recovery.auto.tfvars`. A bounded local check confirmed that value matches the new `.env` account ID. For the proposed infrastructure implementation, reuse `var.aws_account_id` for the IAM resource ARN and provider account guard; do not introduce a second Terraform account variable or an independent `.env` lookup inside resources. Any local preparation/rendering workflow that reads `.env` must fail on disagreement with the selected infrastructure account before rendering or planning, not silently override either value. The guarded stage-2 plan preflight performed that check; no reusable wrapper is added. Moving infrastructure's account source entirely to `.env` would be a separate explicit migration, not part of this grant.

Recipient: the existing `databox-recovery-operator` IAM user, not the routine writer or catalog-backup role. The Resource names the **subject of inspection**, `databox-lake-user`; it is not the identity receiving the grant. This is an identity policy, with no `Principal` field.

Packaging: a separately named inline policy, `databox-warehouse-writer-inspection`, managed through the agreed infrastructure owner. Stage 1 is deployed and remains represented in HCL. The abandoned stage-2 statement/input were removed locally, restoring configuration parity with live stage 1. Do not attach broad managed policies, replace existing policies, or change the catalog-backup role or trust policy.

## Stage 1: exact-user discovery only

All five actions are scoped to the one verified writer user ARN, with no wildcard action, wildcard resource, or account-wide listing:

| Action | Purpose |
| --- | --- |
| `iam:GetUser` | Inspect user metadata and discover any permissions-boundary ARN. |
| `iam:ListUserPolicies` | Discover the writer's inline policy names. |
| `iam:GetUserPolicy` | Read those inline policy documents. |
| `iam:ListAttachedUserPolicies` | Discover attached managed-policy ARNs. |
| `iam:ListGroupsForUser` | Discover the writer's group memberships. |

This exposes security-sensitive metadata and policy documents for this writer. Keep full responses private; public evidence must be sanitized. It does not grant object access, IAM/S3 mutation, credential retrieval, `sts:AssumeRole`, `iam:PassRole`, policy simulation, or reading other users' policies. It does not restrict or revoke permissions the operator already has: the existing catalog role-assumption grant remains intact but is outside this inspection's execution authority.

Stage-1 verification found zero inline policies, zero groups, no permissions boundary, and exactly two attached managed policies; all results were untruncated. Both attached policies are AWS-managed. Raw names/ARNs and policy contents remain suppressed. The five discovery calls are effective, but stage 1 is not a complete effective-permission or bypass audit.

An added Allow may still be blocked by an SCP, session policy, resource control policy or explicit Deny. If a read remains denied, record the denial and ask the administrator to identify the restriction; do not automatically broaden the policy.

## Abandoned stage 2 and current root exception

A prepared stage-2 update would have added only `iam:GetPolicy` and `iam:GetPolicyVersion` on the exact two live-discovered AWS-managed policy ARNs. A fresh non-root untruncated listing matched the private inputs, and an exact saved plan was reviewed, but the user explicitly rejected the extra operator-grant ceremony before apply. No stage-2 permission reached AWS. Its HCL variable/statement, private tfvars values, example/test contracts and saved binary/log were removed.

The user instead authorized the root-backed profile for the remaining warehouse-recovery audit and infrastructure work, deferring non-root deployer-role design and other IAM cleanup until afterward. Root inspection should read the exact live writer attachments and only relevant references needed to determine versioning/lifecycle/bucket-policy/version-delete bypass authority. Keep raw policy documents, identifiers and account details private. Record unknown organization, resource-policy, session or cross-account controls rather than claiming complete effective permissions.

This exception avoids further temporary operator grants; it does not authorize unreviewed mutation. Warehouse versioning, lifecycle and bucket-policy changes still require an exact saved live-refresh plan, independent review, explicit apply approval and maintenance coordination.

## Superseded manual bootstrap suggestion

Do not add or edit this inspection policy in the console. The user rejected that earlier suggestion in favor of existing OpenTofu ownership, and live preflight found no manual same-named policy before stage-1 apply. Stage 1 is now OpenTofu-managed. Do not recreate the abandoned stage-2 grant, create a duplicate, import silently, or attach broad managed policies.

## Current execution gates

1. Preserve deployed stage 1 and existing catalog resources while using root only for the user-approved recovery exception; do not add the abandoned stage-2 grant or a deployer role now.
2. With a fresh root-backed login, re-list the writer's exact attachments without truncation, read their current default documents and inspect only relevant referenced control paths. Keep raw evidence private.
3. Use those findings to implement only the separately agreed warehouse controls in `infra/recovery/`, preserving other bucket settings/resources. Resolve maintenance timing and ownership conflicts before apply.
4. Generate a saved live-refresh plan and independently review exact resolved changes. Obtain explicit approval of that binary/hash; changed source/input/lock/state or live target conditions invalidate freshness.
5. Apply only after fresh root identity/account and plan/fingerprint checks. End root CLI/browser sessions afterward. Plan-time no-op/drift checks do not prove a drift-free interval.
6. After warehouse protection and recovery proof, separately design non-root deployment and remove/reduce temporary IAM inspection access.

## Local implementation and validation

- `infra/recovery/main.tf` now again matches deployed stage 1: one five-action exact-writer statement on the separately named inspection resource. The uninstalled stage-2 statement and variable were removed.
- Ignored `recovery.auto.tfvars` remains mode `0600`; the two temporary managed-policy ARN inputs were removed. `terraform.tfvars.example`, the JSON illustration and static tests again describe stage 1 only.
- `docs/runbook.md` records the abandoned stage 2, current root exception, existing OpenTofu ownership and continuing exact-plan gate.
- The cancelled saved plan had contained one in-place inspection-policy update, 10 no-ops, no plan-time drift and no output changes. Its private binary/log were deleted after the user changed course. [Cancelled plan evidence](iam-managed-policy-inspection-plan.md) retains only sanitized history.
- Post-reversion OpenTofu format/validate, Ruff, example formatting, links, whitespace, private mode, artifact removal and `.10x` absence checks passed. The full infrastructure test file returned 9 passes plus the known pre-existing deleted-`.10x` FileNotFoundError.

## Evidence and validation limits

- [AWS IAM service authorization reference](https://docs.aws.amazon.com/service-authorization/latest/reference/list_iam.html), checked 2026-09-14: the five deployed stage-1 actions support required `user` resources; GetPolicy/GetPolicyVersion are Read actions requiring `policy` resources but are no longer proposed for the operator.
- [GetUserPolicy API](https://docs.aws.amazon.com/IAM/latest/APIReference/API_GetUserPolicy.html): inline policy retrieval is distinct from managed-policy retrieval using GetPolicy and GetPolicyVersion.
- [AWS CLI login documentation](https://docs.aws.amazon.com/cli/latest/userguide/cli-configure-sign-in.html): the operator remote flow remains available, but the user chose root-backed work for the current recovery exception.
- Stage 1 is live-verified. The abandoned stage 2 never reached AWS. Root-backed inspection still cannot prove unavailable organization, cross-account, resource-policy or session context; retain exact limitations.
