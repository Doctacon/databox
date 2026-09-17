Status: applied and verified; writer pause released
Applied: 2026-09-14

# Warehouse object-version protection: apply evidence

## Authorization and maintenance

The user explicitly approved only `infra/recovery/warehouse-object-protection-20260914T224021Z.tfplan` with SHA-256 `0deb607f3bd3407d838a610544788f2603ecda27733d226b1e9f99f0034a2a7a`. The user accepted bucket-wide impact across all three prefixes, owned the maintenance window, and explicitly confirmed every PUT/DELETE path was paused before apply.

An initial apply preflight stopped before mutation because the existing short-lived root credential had insufficient remaining lifetime under an over-conservative 25-minute gate. The user refreshed the AWS-login-backed profile using the remote flow. AWS login issues short-lived credentials and refreshes them from its login cache; the corrected gate required enough time for the mutation/immediate read-back and reverified exact root through the same profile after the propagation hold.

## Fresh apply-time gates

Immediately before apply, guarded checks reverified without emitting private values:

- The exact saved binary existed, was mode `0600`, and matched the approved SHA-256.
- All plan-time Terraform source, private-input, lock and pre-apply state fingerprints matched the approval record. No unexpected `.tf` or auto-loaded variable file appeared.
- Private target/account inputs matched local private configuration, the catalog and warehouse buckets differed, and the selected profile was AWS-login backed with no static-key, role, source-profile, credential-process, web-identity or environment override.
- Live STS was the exact expected account-root ARN.
- The saved binary still structurally projected exactly three creates, 11 existing managed-resource no-ops, no resource drift, no output changes, and no update/replacement/delete.
- The target remained in the expected account/region and accepted three-prefix scope, never-versioned/unset, with no lifecycle or bucket policy. Public-access block, AES256 encryption, BucketOwnerEnforced ownership, owner-only ACL, and absence of tags, replication, logging, notifications and Object Lock remained as inspected.
- Local state was mode `0600`, serial 5, and contained 11 managed resources with none of the warehouse setting addresses.

## Exact apply

OpenTofu applied only the approved saved binary, noninteractively and with state locking. The private ignored apply log is:

`infra/recovery/warehouse-object-protection-20260914T224021Z.tfplan.apply.log`

It is mode `0600` and reports exactly `3 added, 0 changed, 0 destroyed`. No retry, replan, import, rollback, suspension, delete or cleanup apply occurred. The approved plan binary remained byte-for-byte unchanged.

Post-apply state is serial 7 with exactly 14 managed resources: the prior 11 plus only these three addresses:

1. `aws_s3_bucket_policy.warehouse`
2. `aws_s3_bucket_versioning.warehouse`
3. `aws_s3_bucket_lifecycle_configuration.warehouse`

Post-apply state SHA-256 is `9a020621fe534808d88ce735cf03535e4cee95e00057427babb04b04ac51bda8`. OpenTofu created `terraform.tfstate.backup` with mode `0644`; the verifier stopped before the propagation timer and that local private file alone was immediately tightened to `0600`. Both state files are now mode `0600`. No S3 retry or mutation accompanied that permissions correction.

## Read-back and propagation hold

The first verifier correctly established that apply succeeded but rejected AWS's serialization of the empty lifecycle filter. Sanitized read-back showed the canonical bucket-wide representation `Filter: {Prefix: ""}`. The verifier was corrected to accept that semantic equivalent; the infrastructure was not changed or reapplied.

A fresh full read-back then started a conservative propagation interval:

- Hold began: `2026-09-14T23:16:06.112473Z`.
- Hold duration: 905 seconds.
- Final verification completed: `2026-09-14T23:31:31.735888Z`.

Exact account-root identity was verified before apply and again after the hold. Before and after the hold, authoritative live reads verified:

- Versioning is `Enabled`; MFA Delete remains unset.
- The bucket policy has no Allow and exactly the approved two Denies, five total actions, wildcard principal, exact root-ARN exception and exact bucket/object resource split.
- Lifecycle has exactly one enabled bucket-wide rule and only 30-day noncurrent-version expiration; no current expiration, transition, keep-N limit, multipart-abort rule or delete-marker cleanup exists.
- All three top-level prefixes remain present.
- Public-access block, AES256 encryption, BucketOwnerEnforced ownership, owner-only ACL, and absent tags, replication, logging, notifications and Object Lock remain unchanged.
- State remained serial 7 and byte-for-byte unchanged throughout the hold; the approved plan hash also remained unchanged.

The maintenance pause may now be released, and the user was told writes could resume.

## Result and remaining limits

The retention-control rollout succeeded. Non-root principals are denied permanent version deletion and mutation/removal of versioning, lifecycle and bucket policy. The bucket policy adds no Deny for ordinary `PutObject` or `DeleteObject`; after versioning, an ordinary delete normally creates a delete marker instead of permanently removing prior versions. Account root and S3 Lifecycle remain intentional permanent-deletion paths, and a principal with historical-version read plus ordinary write can promote old content as a new current version. This is not Object Lock, root-only recovery or coherent Iceberg recovery.

No object payload was accessed. No live non-root denial attempt, lifecycle expiration observation, cost/alert control, backup-account copy or coherent Iceberg recovery drill was performed. Those remain separate reviewed/authorized work. Versioning is prospective: it cannot recreate already-lost history, and existing null versions gain protected history only after future overwrite/delete. Lifecycle eligibility begins after 30 noncurrent days and is UTC-rounded/asynchronous, not immutable or an exact 720-hour guarantee.

After final read-back and local evidence checks, `aws logout --profile databox-debug` succeeded and ended the temporary root-backed CLI login. No further AWS operation occurred.
