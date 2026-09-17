Status: approved and applied; approval consumed; see iam-inspection-apply.md
Created: 2026-09-14

# Warehouse writer inspection grant: saved-plan evidence

## Scope and authority

After directing OpenTofu ownership rather than console editing, the user reported completing root authentication and asked for the next step. This run performed identity/collision preflight and a fresh live-refresh plan only. It did not apply permissions or warehouse protection.

## Guarded preflight

- Local `DATABOX_AWS_ACCOUNT_ID` is exactly 12 digits and matches the sole automatically loaded `infra/recovery/recovery.auto.tfvars` account input. The input selects `databox-debug`; the provider still uses the existing `var.aws_account_id` guard and shared-config profile.
- The configured root login session matches that account, with no alternate credential-process/role/static-key configuration in that profile. Its existing cached access credentials had over five minutes remaining before planning.
- Live STS matched the exact expected account-root ARN. Live IAM GetUser matched the exact routine-writer ARN used by the planned policy; neither identifier was emitted publicly.
- IAM GetUserPolicy for `databox-warehouse-writer-inspection` on `databox-recovery-operator` returned `NoSuchEntity`. No manual policy collision was found; no import is indicated by that check.
- Local state was mode `0600`, serial 4, without the new resource. The only auto-loaded variable file was `recovery.auto.tfvars`. Inherited AWS and Terraform variable/CLI-argument overrides were cleared for the plan; the explicitly configured existing profile supplied credentials.

## Exact plan

Run from literal `infra/recovery/`, with a private mode-`0600` log and umask `077`:

```bash
tofu plan -input=false -lock-timeout=10s -detailed-exitcode -no-color \
  -out=warehouse-writer-inspection-20260914T195033Z.tfplan
```

- OpenTofu: 1.12.6.
- Plan timestamp: 2026-09-14T19:50:35Z.
- Saved binary: `infra/recovery/warehouse-writer-inspection-20260914T195033Z.tfplan`.
- SHA-256: `0b11a2c04f8d80fd62d1dc02a77de1a416d11261ad11022a8afb9d3f437230a8`.
- Private console output: `infra/recovery/warehouse-writer-inspection-20260914T195033Z.log`.
- Both artifact paths are Git-ignored; the binary is mode `0600`. Neither raw output nor raw plan JSON is public evidence.

A bounded in-memory `tofu show -json` inspection verified:

| Property | Result |
| --- | --- |
| Resource changes | Exactly one create: `aws_iam_user_policy.warehouse_writer_inspection` |
| Existing-resource mutations/deletions | None |
| Resource drift reported | None |
| Output changes | None |
| Recipient | Exactly `databox-recovery-operator` |
| Policy name | Exactly `databox-warehouse-writer-inspection` |
| Policy | Exact five-action, one-user policy described below |
| Persisted local state | Byte-for-byte unchanged; still serial 4 |
| Configuration, tfvars and lock bytes | Unchanged during planning |

The complete planned policy was structurally compared against a single Allow statement with Sid `InspectOnlyWarehouseWriter`, Version `2012-10-17`, and only:

- `iam:GetUser`
- `iam:ListUserPolicies`
- `iam:GetUserPolicy`
- `iam:ListAttachedUserPolicies`
- `iam:ListGroupsForUser`

The sole Resource equals the verified account-qualified `databox-lake-user` ARN, exactly the existing account variable plus `:user/databox-lake-user`. No wildcard, additional statement or action, principal change, or broad managed-policy attachment was present. The [JSON illustration](warehouse-writer-iam-inspection.policy.json) is sanitized; the saved plan already contains the correctly resolved value.

## Input fingerprints for approval freshness

These hashes identify existing private/local inputs without publishing their contents. Apply must use the named saved binary, not a regenerated plan under the same approval.

| Input | SHA-256 |
| --- | --- |
| `main.tf` | `7eafaeaf9237ca0821b258b9666cc1454b3a6d7445d44639cfd636e143655c14` |
| `outputs.tf` | `a937505be234bfbcf543b3ad1f38e476fd70c33a771fcba425049a20ac301f53` |
| `variables.tf` | `afe5d103f9f9ab08963f867a893b596bf598a06bb0de101390821ada09508de9` |
| `versions.tf` | `7aa040e6c7ed59fa3ea680c2fa7e8945643b29db95daef23412e36f7704842b8` |
| `recovery.auto.tfvars` | `5f9073f8cbed967a7db481882181be6c6990fe39af31a0e818616ad62d52d475` |
| `.terraform.lock.hcl` | `02d2b020180bf03e77af58e54b0539ff0da8e5b4f06db21ff347be0cf092cfd3` |
| `terraform.tfstate` | `2bf4b47d79eb374ebb25963547bb0345323cf229508f85d2ac110fa7a76b6ac4` |

Before any approved apply: reverify the exact plan hash, source/private-input/lock/state fingerprints, expected identity/account, and no newly created same-named policy. A changed input/state/live condition requires stopping and reassessing freshness; do not silently replan/apply or import. No guaranteed drift-free interval is claimed by these checks.

## Validation and remaining approval

Local checks: nine relevant static tests passed, Ruff passed, and OpenTofu format/validate passed without init. The full test file retains one pre-existing FileNotFoundError for intentionally deleted `.10x/specs/public-catalog-recovery-content.md`; it was observed before this implementation and remains reported, not repaired or masked.

Independent consultant review (session `1e31e9eb-078e-49d`) found **no blocking findings for presenting this exact plan for user approval**. It confirmed scoped recipient/action/resource composition, preserved existing infrastructure, discovery-only limits and visibility of the pre-existing test failure. Review covered code/docs and this sanitized exact-plan projection, not the raw binary, private inputs/state or live AWS; the reviewer did not recompute hashes or rerun checks. The agent's guarded plan inspection above supplies those observations. This review is not apply authorization.

The scope is discovery-only; managed/group/role policy documents and effective bypass analysis still require separately bounded evidence/access. Warehouse versioning/lifecycle settings and other warehouse rollout gates remain unchanged. The user subsequently approved this exact saved binary/hash and the apply completed with exact policy read-back. See [apply evidence](iam-inspection-apply.md). This approval is consumed; do not apply the saved plan again.

No apply, import, role assumption, service operation, object access, new credential issuance or agent-run login was performed. Root CLI authentication was performed by the user. At this stage, root was not to be used for the routine IAM audit after the bootstrap grant. The user's later [current access decision](iam-inspection-access.md) supersedes that restriction for the remaining warehouse-recovery work.
