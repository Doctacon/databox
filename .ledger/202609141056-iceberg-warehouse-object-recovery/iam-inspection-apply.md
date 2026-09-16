Status: applied, exact policy read-back and stage-1 operator capability verified; root CLI logout verified
Created: 2026-09-14

# IAM inspection grant: approved apply

The user explicitly approved the exact saved plan presented in [plan evidence](iam-inspection-plan.md):

- Binary: `infra/recovery/warehouse-writer-inspection-20260914T195033Z.tfplan`.
- SHA-256: `0b11a2c04f8d80fd62d1dc02a77de1a416d11261ad11022a8afb9d3f437230a8`.

## Pre-apply and execution

Rechecked the binary hash; configuration, tfvars, lock and state hashes; exact infrastructure/auto-loaded-variable file sets; plan/state mode `0600`; local account equality; configured and live root identity/account; exact writer ARN; and absence of the same-named operator policy. Root cached access credentials had more than five minutes remaining. All checks passed. No replan, init or import was run.

From literal `infra/recovery/`, with umask `077`:

```bash
tofu apply -input=false -lock-timeout=10s -no-color \
  warehouse-writer-inspection-20260914T195033Z.tfplan
```

Apply returned success. Private output is in Git-ignored `infra/recovery/warehouse-writer-inspection-apply-20260914T195611Z.log`; no raw output or credential/deployment identifier was emitted publicly.

## Verified outcome

- Root-authorized IAM GetUserPolicy read-back exactly matched the approved Version, single statement, Sid, five actions and account-qualified writer Resource, with the correct policy name and operator attachment. This is configuration verification, not a claim about effective operator access.
- State added only `aws_iam_user_policy.warehouse_writer_inspection`; no resource addresses were removed, and lineage was preserved.
- State serial: 4 → 5; mode remains `0600`.
- New state SHA-256: `99825764b85e0dd94b3c0e07cc37477fe4113299ee6cbabc6d6e43c12c8c387b`.
- Existing login/backup permissions, roles and bucket settings had no planned mutation. This plan approval is consumed; do not apply the saved plan again.

## Operator verification and session cleanup

The initial post-apply check stopped **before any operator AWS call** because cached access credentials were expired or nearly expired. The user then ran the recommended profile-based STS command and reported success, allowing normal AWS CLI resolution to refresh/exercise the existing operator session without root fallback.

A subsequent guarded check verified exact expected non-root STS identity/account. All four bounded stage-1 calls succeeded without truncation:

- GetUser: no permissions boundary.
- ListUserPolicies: zero inline policies.
- ListAttachedUserPolicies: two attached managed policies.
- ListGroupsForUser: zero groups.

Because there were no inline policies, no GetUserPolicy document call was needed. No raw policy response, policy name/ARN, account identifier or target ARN was emitted publicly. The two managed policy documents remain unread under stage-1 access, so control-plane, version-delete and role-assumption capabilities remain unknown; do not infer effective permissions from attachment count.

A local cache check confirms the root CLI login cache is absent and the operator cache is present. Root browser-console logout remains a human responsibility and is not technically verified here.

This stage-1 apply did not authorize further access. A later stage-2 operator grant was planned but abandoned before apply; the user instead chose direct root-backed inspection and infrastructure work for the recovery effort. See [current access decision](iam-inspection-access.md). All warehouse ownership/retention/rollout gates remain open. This historical stage-1 apply itself authorized no role assumption, bucket mutation or recovery drill.
