Status: recorded
Created: 2026-09-04
Updated: 2026-09-04
Relates-To: .10x/tickets/2026-09-04-apply-and-prove-disaster-recovery.md

# Recovery operator step-1 repair plan

## Result

Step 1 declares a non-root console-only IAM operator path and produced a state-aware non-mutating repair plan using authenticated root profile `databox-debug` in account `734815189723`, region `us-west-1`.

- Binary plan: `/tmp/databox-recovery-operator-repair.tfplan`
- Binary SHA-256: `677f9ce7a6b5ee499f8bebb71b96115d8e443a31b1cbcf6f6f4eb2767fc96bcc`
- Exact text: `.10x/evidence/.storage/2026-09-04-databox-recovery-operator-repair.tfplan.txt`
- Text SHA-256: `78b80e6fd2619d40482fb0b4869f37574d5517bc153359a2f4d7eccca9a5dbaa`
- Actions: 2 create, 1 in-place update, 0 destroy, plus one deferred local policy-document read.

No apply or AWS mutation ran.

## Exact actions

- Create IAM user `databox-recovery-operator` with `force_destroy=false`.
- Create its inline policy allowing only `sts:AssumeRole` on `arn:aws:iam::734815189723:role/databox-polaris-catalog-backup`.
- Update only the existing catalog-backup role trust in place, removing account-root trust and deriving the exact new user ARN.
- Add non-secret output `recovery_operator_user_arn`.

OpenTofu declares no access key, login profile, password, MFA seed/device, group membership, or other operator permission. Console access/password and MFA enrollment are manual step 2 and must never enter configuration or state.

## State-aware refresh and drift

This plan used normal refresh against existing local state, not `-refresh=false`. All eight applied bucket/role resources refreshed successfully. The complete non-no-op action inventory contains only the three expected remote actions above; no bucket action, replacement, destroy, or unexpected drift exists.

## Approval boundary and limits

This plan is not approved for apply. It requires independent review and explicit user approval of binary hash `677f9ce7a6b5ee499f8bebb71b96115d8e443a31b1cbcf6f6f4eb2767fc96bcc`. Any code, state, input, account/profile, or plan change invalidates the hash.

Root remains authenticated because the live role path is still blocked. No credential, password, login profile, MFA material, service, object, backup, WAL, volume, or restore was created or touched.
