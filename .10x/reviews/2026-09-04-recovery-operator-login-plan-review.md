Status: recorded
Created: 2026-09-04
Updated: 2026-09-04
Target: .10x/evidence/.storage/2026-09-04-databox-recovery-operator-login-repair.tfplan.txt
Verdict: pass

# Recovery operator remote-login plan review

> Publication redaction (2026-09-12): deployment account/bucket literals are replaced by labeled placeholders; generic principal labels are retained. This historical record is not a fresh approval or an executable plan. Original conclusions and verification limits still apply.
> Source revision: `027af8b4271d60ffc193967d092b5d2497af13ad`. Original-artifact SHA-256 (NOT this redacted text): `4fb9f394e3609ceab0e01fe381bbebab1a76bf7b6160f1d226c91d7b2d328a7a`.
> Exact private original: `~/Private/databox/recovery-evidence/2026-09-11T235551Z-05aef1141954/`; `manifest.json` entry with `source_kind=committed-head` and `source_path` equal to this public path. Any preexisting plan/export hashes below identify original artifacts, not this changed counterpart.


## Findings

None.

## Verdict

Pass. Exact binary `infra/recovery/recovery-operator-login-repair.tfplan`, SHA-256 `276b5ad36a1a6a13577a2b4b9a3e985c0e0ff1d0fe41340ec61221860f945f45`, is safe to present for explicit authorization but is not yet authorized.

The sole action is an in-place operator-policy update adding only `signin:AuthorizeOAuth2Access` and `signin:CreateOAuth2Token`, scoped exactly to `arn:aws:signin:us-west-1:<REDACTED_ACCOUNT_ID>:oauth2/public-client/remote`. Existing `sts:AssumeRole` remains limited to the exact backup role. Role trust remains limited to the exact operator with MFA required. Plan inventory is zero creates, one update, zero destroys, with no role or bucket action.

Current and embedded state lineage `4303cf7d-c96f-55db-0ba3-a1ff1f492194`, serial `3`, and lockfile SHA-256 `02d2b020180bf03e77af58e54b0539ff0da8e5b4f06db21ff347be0cf092cfd3` match.

Do not initialize, refresh, regenerate, or edit configuration before applying this exact binary.
