# Read-only warehouse protection inspection

> Historical pre-rollout snapshot. Its retention-rollout blockers were later resolved by explicit user decisions, audit, exact-plan approval and the verified [warehouse protection apply](warehouse-object-protection-apply.md). Restore design and live-drill gates remain open.

Date: 2026-09-14. Live observation batches began at **18:12:18 UTC** and **18:13:28 UTC**.
Branch: `feature/warehouse-file-recovery` at `747d4d2`.

## Authority and disposition

The user authorized read-only prerequisite inspection after the planning handoff. This report is a sanitized adoption assessment, not implementation or deployment authority. **Inspection completed with explicit blockers; implementation/planning and rollout are not released.** No live configuration change or recovery capability is claimed.

The existing configured primary credentials authenticated as the exact expected `databox-lake-user` IAM user. No other profile, role assumption, login, cache refresh, credential creation or external credential store was used. Credentials were passed only in child-process environment variables, never argv, output or a new file. AWS shared config/credential files and metadata lookup were disabled for these calls, so the CLI could not silently select another identity. Raw CLI failure diagnostics were suppressed; only extracted error codes were reported.

Exact account, bucket, role and object identifiers are intentionally omitted from this public record. Their comparisons were performed in memory against current local configuration. No private historical evidence bundle was read.

## Verified identity and configuration

| Check | Observation | Meaning / limit |
| --- | --- | --- |
| STS caller identity | Exact expected IAM user ARN matched | Not an assumed backup role; validates identity, not effective permissions |
| Account comparison | Caller account matched configured warehouse-role account and recovery `aws_account_id` input | Exact identifiers compared, not published |
| Bucket owner | `HeadBucket` succeeded with `ExpectedBucketOwner` set to verified caller account | Ownership matched that account |
| Region | HeadBucket and GetBucketLocation confirmed `us-west-1` | Matches primary config and recovery variable default |
| Warehouse prefix | Configured default `warehouse/` | Other bucket prefixes also exist |
| Catalog separation | Primary bucket differs from catalog bucket in local state | Local recovery state does not manage primary-bucket settings |
| Local credentials | Primary key/secret configured; no primary session token | Existing credentials only; no policy change or new credential exception |

An initial local comparison reported a false region-match boolean because `recovery.auto.tfvars` has no explicit region override. Reading `variables.tf` resolved this: its default is `us-west-1`, matching the live bucket. There is **no observed region mismatch**.

## Live S3 protection state

| API | Observed result |
| --- | --- |
| `get-bucket-versioning` | Success, empty configuration `{}`: versioning has not been enabled, rather than `Suspended` |
| `get-bucket-lifecycle-configuration` | `NoSuchLifecycleConfiguration` — absent, not access denied |
| `get-bucket-policy` | `NoSuchBucketPolicy` — absent, not access denied |
| `get-bucket-policy-status` | `NoSuchBucketPolicy` |
| `get-public-access-block` | All four flags true |
| `get-bucket-encryption` | Default `AES256`; `BucketKeyEnabled=true` also returned; `BlockedEncryptionTypes` contains `SSE-C` |
| `get-object-lock-configuration` | `ObjectLockConfigurationNotFoundError` — no Object Lock configuration |
| `get-bucket-ownership-controls` | `BucketOwnerEnforced` |
| `get-bucket-acl` | One grant, owner-only `FULL_CONTROL` |
| `get-bucket-tagging` | `NoSuchTagSet` — no tags identifying a configuration owner |

No existing bucket-policy statement or lifecycle rule needs to be merged **at this observation time**. That does not establish exclusive infrastructure ownership or authorize a new policy. In particular, the catalog backup's TLS-deny policy is not a policy on this primary bucket. Adding a primary TLS/control-plane restriction would require its own explicit decision; none was inferred here.

## Bounded inventory and scope

No object payload was read. No metadata-file download, table scan, object write or deletion probe occurred.

- A top-level `ListObjectsV2` with delimiter `/`, `MaxKeys=100`, and no automatic pagination returned **three common prefixes**, zero root objects, and `IsTruncated=false`.
- `warehouse/` and `integration/` are present. **One additional prefix exists whose purpose/ownership has not been established.** Its exact name was suppressed along with other deployment identifiers. Ownership must be confirmed before bucket-wide retention adoption.
- A root object listing returned 100 integration objects totaling **2,731,221 bytes**, with `IsTruncated=true`.
- A root version listing returned 100 integration versions, all current `null` versions, no returned delete markers, and `IsTruncated=true`.
- A separate `warehouse/` version listing returned 100 current `null` versions totaling **1,724,578 bytes**, all `STANDARD`, no returned delete markers, and `IsTruncated=true`.

These samples are not bucket totals or full historical inventories. The successful unversioned status and sampled `null` versions are consistent with no existing retained version history, but no exhaustive version enumeration was performed. No immediately expiration-eligible history was observed; recheck versioning/history for drift before apply rather than promise a fresh grace period. The new retention rule would affect integration and the third prefix, not just canonical table files.

## Storage and cost exposure

Read existing `AWS/S3` daily CloudWatch metrics over the preceding seven days with `Period=86400`, statistic `Average`:

| Metric / storage dimension | Returned evidence |
| --- | --- |
| `BucketSizeBytes` / `StandardStorage` | Seven daily points dated September 7–13, each **20,744,109 bytes** (about 19.8 MiB) |
| `NumberOfObjects` / `AllStorageTypes` | Seven daily points dated September 7–13, each **1,062 objects** |

These are delayed daily bucket-level storage metrics, not a current exact inventory, request-rate measurement or future cost estimate. Flat storage/count readings do not prove no overwrite/delete churn. Other storage-class metrics were not queried. No request metrics, billing data or future ingest/churn assumptions were gathered; no dollar estimate or budget cap is asserted.

Versioning retains full previous object versions and increases storage/request costs according to actual churn. Rollout still requires cost acknowledgement, affected-prefix confirmation, and review of any old-history expiration exposure then present.

## IAM visibility: blocked

The following read-only IAM calls for the exact routine writer each returned **`AccessDenied`**:

- `get-user`
- `list-user-policies`
- `list-attached-user-policies`
- `list-groups-for-user`

STS still verifies the writer ARN; denied `GetUser` is not an identity mismatch. However, attached/inline/group policies, permissions boundaries and relevant role-assumption paths could not be inspected. No identity-policy simulation or mutation-based permission probe was attempted. Ability to read S3 configuration does not establish ability to mutate it.

**Unknown:** whether the writer can delete specific versions, change versioning/lifecycle/bucket policy, change IAM, or assume another identity that bypasses the planned Deny. The broader primary-writer least-privilege audit remains open, not duplicated or closed by this report.

**Next access requirement:** an existing explicitly selected identity with sufficient IAM read visibility, or operator-supplied sanitized policy evidence. No new grant, administrator exemption, root use, login, role assumption or accepted bypass limitation is implied. If bypasses are found, the user must approve exact additional controls or accept the named limitation before protection sign-off/rollout.

## Infrastructure ownership and adoption

Repository discovery found one tracked OpenTofu root, `infra/recovery/`. Its source and the bounded local-state projection contain only catalog recovery resources; no primary bucket/versioning/lifecycle/policy resource was found there.

State projection: version 4, serial 4, mode `0600`. `fdesetup status` reported FileVault on. The state was read only in memory for selected resource addresses/bucket comparisons; no full-state output, backup copy, init, refresh, plan, import or mutation occurred. Recovery provider region default is `us-west-1`. Other checkouts, external state backends and infrastructure repositories were not exhaustively searched.

**Candidate adoption path, conditional on ownership confirmation:** keep catalog resources/state addresses unchanged; add only primary settings for versioning, noncurrent lifecycle and the exact writer Deny in this root. Do not import/manage the primary bucket itself or enable destructive bucket management. Current absent lifecycle/policy configurations have no existing live documents to import, but any existing external owner/state must be reconciled before planning. If adopting existing versioning state or any discovered resource requires import, settle exact resource addresses/import IDs and obtain separate state-only authorization first. No import command is approved by this assessment.

Required regression surfaces remain `tests/platform/test_recovery_infrastructure.py`, existing catalog-role restrictions, account/region, public-access/encryption/TLS, state and no-replication tests. Do not remove those protections to accommodate primary settings.

## Readiness matrix

| Concern | Disposition |
| --- | --- |
| Exact bucket/account/region/writer identity and catalog separation | Verified at observation time |
| Current versioning/lifecycle/policy/security settings | Read successfully; relevant absences distinguished from denials |
| Existing policy/lifecycle conflicts | None observed live; refresh before implementation/plan/apply |
| Bucket-wide data ownership | **Blocked:** additional prefix purpose/owner and retention obligations unconfirmed |
| Single configuration/state owner | **Blocked:** current repo/state scoped; external ownership not established |
| Writer control-plane/role bypasses | **Blocked:** IAM read denied; no risk acceptance assumed |
| Current storage baseline | Available with daily metric/sampling limitations |
| Future cost and expiration acknowledgement | **Outstanding:** no churn forecast, spend decision or rollout acknowledgement |
| Operator/write coordination | **Outstanding:** no maintenance owner or interruption authority selected |
| Plan/import/apply | **Not authorized:** no plan generated; separate review/approval required |
| Restore contract and live drill | **Blocked separately:** selection/destination/identity/failure/lifecycle choices remain unresolved |

## Reproduction and safety limits

Local inspection used `dotenv_values('.env')` merged with process environment (environment wins), emitted presence/comparison booleans only, and never sourced `.env` as shell code. Shared AWS config was projected to configuration-key names/authentication-type booleans only; no alternate identity was used. Existing recovery state/inputs were read via bounded Python parsing, not `tofu`.

AWS calls used the existing primary credentials in process environment and `--output json --no-cli-pager --no-paginate --cli-connect-timeout 5 --cli-read-timeout 10`, `AWS_MAX_ATTEMPTS=1`, a 20-second subprocess timeout, and no automatic retry. Each live batch checked STS identity; S3 calls used `--expected-bucket-owner <verified-account>`. Inspection scripts remained ephemeral shell/Python input, not new production tooling or credential files.

To reproduce after authorization, select the same configured target and explicit read identity, rerun the API names above, and preserve the same first-page bounds. Object-list arguments were `--max-keys 100`, with `--delimiter /` for prefix inventory or `--prefix warehouse/` for the warehouse sample. Metrics used the configured bucket dimension and seven-day start/end timestamps. Do not paste raw identity/config/state/policy output into public evidence.

No infrastructure code, credentials, AWS settings, source data, Docker resources, active services, private evidence or `uv.lock` were changed. No application tests were run (inspection only). Only this task's ledger records were updated.

## Follow-up: existing AWS profiles

In response to the user's profile-sufficiency question, local profile configuration and existing cached-auth metadata were checked without login, refresh, role assumption or cache writes. The installed AWS CLI's cache-key/directory implementation was consulted to resolve the exact configured login caches; no cache filenames or token contents were emitted.

- `databox-debug`: the profile selected in `infra/recovery/recovery.auto.tfvars`; **no cache file for its configured login session**. Subsequent bounded config inspection confirms this is a **root-backed profile**, not an ordinary audit identity. Historical role-proof evidence records its intentional logout. At this inspection stage it was rejected for routine auditing; the user's later [current access decision](iam-inspection-access.md) explicitly supersedes that restriction for completing warehouse-recovery work.
- `databox-recovery-operator`: at the initial profile check, its cached access credentials were **expired**. The user subsequently completed remote login, and an exact non-root STS identity check succeeded (see outcome below). Refresh-token viability was not tested. Its repository-declared permissions target login and assumption of the catalog-backup role, not the broader warehouse IAM audit.
- `databox-polaris-catalog-backup`: configured to assume the backup role through `databox-recovery-operator`. Its repository-declared scope is catalog-backup storage, not warehouse protection or IAM inspection. No role assumption or live effective-policy claim was made.
- `default`: has a configured static key pair different from the routine writer used earlier. A read-only STS identity check using those credentials returned **`InvalidClientTokenId`**; no account, identity or policy capability could be established. No further API call used that identity.

Thus no profile is currently confirmed usable for the IAM audit. Prefer the existing non-root operator login, then verify identity/account and read-only IAM capability before deciding whether an administrator must grant additional bounded access. Missing/expired authentication is distinct from lack of IAM permissions; the earlier primary-writer batch did not establish that no suitable identity exists.

## Login diagnosis: remote versus same-device flow

User-reported reproduction: `aws login --profile databox-recovery-operator`; browser accepts entry of account ID, username, password and MFA code, then displays **Authentication failed / Invalid request**. This is the observed failing human-operated loop; the exact cause is not yet proven. Do not assume password/MFA success or modify credentials from this generic error.

Initial hypotheses were stale browser request, browser/MFA sign-in trouble, and CLI-specific signin permission mismatch. Targeted inspection elevates the third:

- Current `infra/recovery/main.tf:106-109` and a bounded projection of existing local state grant the two signin actions only on `oauth2/public-client/remote` in `us-west-1`.
- Historical records at `8321475` (`.10x/evidence/2026-09-04-recovery-operator-login-repair-apply.md` and `2026-09-04-recovery-operator-live-role-proof.md`) record that exact remote-client grant being applied and successful `aws login --remote`. They also record root-profile logout after non-root proof.
- [AWS CLI signin documentation](https://docs.aws.amazon.com/cli/latest/userguide/cli-configure-sign-in.html), fetched 2026-09-14, explicitly distinguishes `oauth2/public-client/localhost` for ordinary `aws login` from `oauth2/public-client/remote` for `aws login --remote`.
- Installed CLI is 2.36.38, above the documented 2.32.0 minimum. No live IAM read has reverified current policy, so local state/history are not presented as current AWS proof.

Next operator-run diagnostic: start a fresh `aws login --remote --profile databox-recovery-operator --region us-west-1`, use its newly generated URL with the same operator, and paste the returned authorization code into the local terminal only. Never share the URL, authorization code, password, MFA code or token. Success means the CLI completes login; failure observation is only the redacted browser/terminal error and stage. Do not accept a prompt to replace the profile with a different identity.

This tests the flow mismatch without broadening IAM. The prior advice that plain `aws login` was sufficient for this particular operator was incomplete.

### Remote-login outcome and IAM capability check

The user reported successful login after using `--remote`, resolving the reported login blocker through the already-authorized flow. This supports the client-mode mismatch diagnosis; no policy broadening was needed for login.

Using only the newly cached, unexpired credentials in memory (no automatic refresh or role assumption), a read-only `sts:GetCallerIdentity` call matched the exact configured non-root recovery-operator IAM identity. The following reads targeting the routine warehouse writer each returned **AccessDenied**:

- `iam:GetUser`
- `iam:ListUserPolicies`
- `iam:ListAttachedUserPolicies`
- `iam:ListGroupsForUser`

Authentication is now verified, but the operator is not sufficient for the required IAM inspection with its current effective access. Writer policy and bypass authority remain unknown. Next requires an authorized administrator to supply sanitized policy evidence or separately approve/provision bounded inspection access; no new grant is implied by the successful login. The user performed the login; the agent did not run login, refresh credentials, alter caches, assume roles, change policies or modify AWS resources.
