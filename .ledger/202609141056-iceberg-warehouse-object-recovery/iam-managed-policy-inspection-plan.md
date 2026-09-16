Status: cancelled by user; never applied; private plan/log deleted
Created: 2026-09-14

# Attached managed-policy inspection: saved-plan evidence

## Scope and authority

The user selected preparation of a temporary OpenTofu grant and then completed root authentication for the plan step. This run performed guarded identity, attachment-freshness and deployed-policy checks; generated a saved live-refresh plan; reviewed its resolved change; and removed the root CLI cache. It did not apply permissions, read the attached policy documents, assume roles or change warehouse settings. The user later rejected this staged grant in favor of direct root-backed recovery work. The plan was never approved/applied and its private binary/log were deleted.

## Guarded preflight

- Ignored `recovery.auto.tfvars` is mode `0600`, is the only auto-loaded variable file and still selects the existing `databox-debug` provider profile. Its account input is 12 digits and matches the local `.env` consistency value without becoming a second Terraform source.
- The elevated profile is AWS-login backed, not a static-key, credential-process, role, source-profile, web-identity or other configured credential source. Live STS matched the exact expected account-root identity.
- Live STS matched the exact expected non-root `databox-recovery-operator`; live GetUser matched the exact routine writer in the same account.
- A fresh, single-service-page `ListAttachedUserPolicies` call explicitly reported `IsTruncated=false`. Its exact two-ARN set matched ignored tfvars; both are AWS-managed and neither identifier is recorded here. A mismatch or absent completion marker would have stopped before plan.
- Root read-back of deployed `databox-warehouse-writer-inspection` matched the exact five-action stage-1 statement. Local state was mode `0600`, serial 5 and contained the managed inspection resource.
- Inherited AWS credential/profile and Terraform variable/CLI argument environment overrides were removed for guarded commands. The existing provider account guard remained active.

## Cancelled saved live-refresh plan

Run from literal `infra/recovery/`, with umask `077`, noninteractive input, a state-lock timeout, detailed exit code and a private log:

```bash
tofu plan -input=false -lock-timeout=10s -detailed-exitcode -no-color \
  -out=warehouse-writer-managed-policy-inspection-20260914T202950Z.tfplan
```

- OpenTofu: 1.12.6.
- Timestamp: 2026-09-14T20:29:50Z.
- Saved binary: `infra/recovery/warehouse-writer-managed-policy-inspection-20260914T202950Z.tfplan`.
- SHA-256: `ad34ffd2996dea6e0d39e5c56ec8747e9960d5a9fa089e930d51f20e9890f766`.
- Private log: `infra/recovery/warehouse-writer-managed-policy-inspection-20260914T202950Z.log`.
- Binary and log were Git-ignored and mode `0600`; neither raw plan output nor raw plan JSON became public evidence. Both artifacts were deleted after cancellation.

Bounded in-memory `tofu show -json` inspection verified:

| Property | Result |
| --- | --- |
| Mutations | Exactly one in-place update: `aws_iam_user_policy.warehouse_writer_inspection` |
| Other managed resources | 10 no-op |
| Resource drift | None at plan generation |
| Output changes | None |
| Recipient/name | Existing `databox-recovery-operator` / `databox-warehouse-writer-inspection` |
| Non-policy attributes | Byte-for-byte equivalent before/after |
| Before policy | Exact deployed stage-1 five-action, one-writer statement |
| After policy | Stage 1 preserved plus the exact stage-2 statement below |
| Unknown target values | None material |
| Persisted state | Byte-for-byte unchanged; serial remains 5 |
| Configuration/private inputs/lock | Byte-for-byte unchanged during planning |

The added statement has only:

- Sid `InspectOnlyAttachedWarehouseWriterPolicies`.
- Effect `Allow`.
- Actions `iam:GetPolicy` and `iam:GetPolicyVersion`.
- Resources equal the exact two configured/live attached AWS-managed policy ARNs.

There is no wildcard, mutation action, role/group/user expansion, policy simulation, role assumption, managed-policy attachment, principal change, warehouse change or account-source change. IAM does not expose a version-specific resource ARN for GetPolicyVersion; post-apply execution remains procedurally restricted to each GetPolicy result's default version.

## Historical plan fingerprints

| Input | SHA-256 |
| --- | --- |
| `main.tf` | `95dc3c94e2489355df6471317aed1f65af41f79780479e9c2c8a7e9961fefc16` |
| `outputs.tf` | `a937505be234bfbcf543b3ad1f38e476fd70c33a771fcba425049a20ac301f53` |
| `variables.tf` | `2865d7b876584c8c600f15c1a83e41a655c2b329e94677b51477a2411bda59de` |
| `versions.tf` | `7aa040e6c7ed59fa3ea680c2fa7e8945643b29db95daef23412e36f7704842b8` |
| `recovery.auto.tfvars` | `08a645bb85999d46bdca7578bf97cfe1485bd97f392dd75bc532d1e816dc7a88` |
| `.terraform.lock.hcl` | `02d2b020180bf03e77af58e54b0539ff0da8e5b4f06db21ff347be0cf092cfd3` |
| `terraform.tfstate` | `99825764b85e0dd94b3c0e07cc37477fe4113299ee6cbabc6d6e43c12c8c387b` |

These fingerprints identify the historical cancelled plan only. Do not recreate or apply it: its source/private inputs were intentionally reverted and its binary no longer exists. The plan-time no-op/drift observations never proved a drift-free interval.

## Validation and review

Local validation before planning: both stage-2 focused tests passed; the full infrastructure test file had 10 passes and the same pre-existing failure reading intentionally deleted `.10x/specs/public-catalog-recovery-content.md`. Ruff, OpenTofu format/validate, example-tfvars formatting, ledger-link/whitespace, private-file mode, `.10x` absence and diff whitespace checks passed.

Independent code/security review first identified and then verified fixes for two issues: planning is now explicitly live-refresh rather than `-refresh=false`, and ARN validation rejects both `*` and `?`. It found no blocker to the saved-plan step. Independent review of this exact sanitized plan projection found the technical plan approval-ready and identified one documentation inconsistency; the older access record was then reconciled to this plan and plan-time-only drift claim before presentation. Review did not inspect private tfvars/state, raw plan artifacts, AWS configuration/cache or live AWS; guarded preflight and structural plan inspection above supply those observations.

## Cancellation and next gate

The root CLI cache was removed immediately after plan generation and an export-credentials probe confirmed it unusable. The user then explicitly course-corrected before apply. The stage-2 statement/variable/private inputs/example/test changes were removed, its saved binary/log were deleted, and deployed stage 1 was preserved. Do not reconstruct or apply this plan. Next, obtain a fresh user-performed root-backed login for direct writer-policy inspection, then design the actual warehouse-recovery controls. No stage-2 apply occurred.
