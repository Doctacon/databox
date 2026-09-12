Status: recorded
Created: 2026-09-04
Updated: 2026-09-04
Relates-To: .10x/tickets/done/2026-09-04-apply-and-prove-disaster-recovery.md

# Recovery operator MFA local state-compatible plan

> Publication redaction (2026-09-12): deployment account/bucket literals are replaced by labeled placeholders; generic principal labels are retained. This historical record is not a fresh approval or an executable plan. Original conclusions and verification limits still apply.
> Source revision: `027af8b4271d60ffc193967d092b5d2497af13ad`. Original-artifact SHA-256 (NOT this redacted text): `b3cde436125a1fdda71abf0f1a696963f2ab5b74d8a40e8851408608637f04e0`.
> Exact private original: `~/Private/databox/recovery-evidence/2026-09-11T235551Z-05aef1141954/`; `manifest.json` entry with `source_kind=committed-head` and `source_path` equal to this public path. Any preexisting plan/export hashes below identify original artifacts, not this changed counterpart.


## Result

A normal-refresh OpenTofu plan was generated literally from `infra/recovery/` as the ignored local file `infra/recovery/recovery-operator-mfa-repair.tfplan`. No `tofu init` ran before or after generation.

- Binary SHA-256: `45a78d799032c227b1d525433515e2093b452be0f346ea4c2a6d14d9ae5bbc35`
- Exact text: `.10x/evidence/.storage/2026-09-04-databox-recovery-operator-mfa-local-plan.txt`
- Text SHA-256: `ac69ca32d2e7a589d59b7bb5141de952996e80045f63d7850a78d7991a122365`
- Actions: 2 create, 1 in-place update, 0 destroy, plus one deferred local policy-document read.

The plan creates console-only IAM user `databox-recovery-operator` and its policy allowing only `sts:AssumeRole` on `databox-polaris-catalog-backup`. It updates that role to trust the exact user only when `aws:MultiFactorAuthPresent=true`. All bucket resources are no-op.

## State and dependency compatibility proof

Before generation:

- authenticated identity: `arn:aws:iam::<REDACTED_ACCOUNT_ID>:root` in account `<REDACTED_ACCOUNT_ID>`;
- state path/mode: `infra/recovery/terraform.tfstate`, `0600`;
- state SHA-256: `0794afe7339895a6b59b87c029c800775ea041cebb436fc63839304b0dbd5ab7`;
- current state lineage: `4303cf7d-c96f-55db-0ba3-a1ff1f492194`;
- current state serial: `2`;
- lockfile SHA-256: `02d2b020180bf03e77af58e54b0539ff0da8e5b4f06db21ff347be0cf092cfd3`;
- installed selection: OpenTofu 1.12.6 and AWS provider 6.63.0.

The saved plan is a ZIP archive containing its embedded prior `tfstate` and `.terraform.lock.hcl`. Direct inspection proved:

- embedded state lineage: `4303cf7d-c96f-55db-0ba3-a1ff1f492194` — exact match;
- embedded state serial: `2` — exact match;
- embedded lockfile SHA-256: `02d2b020180bf03e77af58e54b0539ff0da8e5b4f06db21ff347be0cf092cfd3` — exact match.

`*.tfplan` is now ignored. The mechanical ignore change was committed before generation, and the worktree was clean at plan time. The binary was never moved or copied outside `infra/recovery/`.

## Validation and limits

Before generation, 25 focused recovery tests, Ruff, formatting, and diff checks passed. JSON inspection after generation proved the exact managed action addresses, no bucket drift, exact assume-only user policy, exact MFA trust, and zero destroys.

No apply, initialization, user/password/MFA creation, credential issuance, backup, WAL, service, volume, or restore occurred. The plan is not approved pending independent review and explicit user approval of this new binary hash. The prior approved binary is unusable and must never be retried. Do not run `tofu init`, refresh state, or change configuration before applying this local binary.
