Status: blocked
Created: 2026-09-04
Updated: 2026-09-04
Relates-To: .10x/tickets/2026-09-04-apply-and-prove-disaster-recovery.md

# Catalog backup infrastructure apply

## Authorized plan

The user explicitly approved one-time root bootstrap apply of exact binary `/tmp/databox-catalog-only-final.tfplan`, SHA-256 `77cf23e243859dac24974be21adfb7f5bdf94bb6ec8168cf70039ddda3b69212`.

Immediately before mutation, the worktree was clean, the binary hash matched, and profile `databox-debug` authenticated exactly as `arn:aws:iam::734815189723:root` in account `734815189723`. Apply ran from `infra/recovery` using exactly:

`tofu apply -input=false /tmp/databox-catalog-only-final.tfplan`

No replan or alternate plan occurred.

## Apply result

OpenTofu reported `Apply complete! Resources: 8 added, 0 changed, 0 destroyed.` It created the catalog bucket `databox-lake-catalog-backup`, bucket versioning, AES256 encryption, complete public-access blocking, HTTPS-only bucket policy, 30-day noncurrent lifecycle plus seven-day incomplete-upload cleanup, IAM role `databox-polaris-catalog-backup`, and its inline bucket-scoped policy.

Root-side read-only verification observed region `us-west-1`, versioning `Enabled`, AES256, all four public-access flags true, the expected TLS-deny condition, 30/7 lifecycle values, root trust, and exactly the intended S3 actions including object-scoped `s3:AbortMultipartUpload` without `s3:DeleteObjectVersion`.

Local state exists at `infra/recovery/terraform.tfstate`, mode `0600`, SHA-256 `0794afe7339895a6b59b87c029c800775ea041cebb436fc63839304b0dbd5ab7`, with eight managed resources. It is ignored by Git. Inclusion in the operator's normal encrypted machine backup remains an explicit future obligation and was not claimed or executed here.

## Blocking role-assumption failure

Live verification exposed a design error: root calling `sts:AssumeRole` for `arn:aws:iam::734815189723:role/databox-polaris-catalog-backup` failed with `AccessDenied: Roles may not be assumed by root accounts.` Therefore the runtime role is not yet usable through the ratified root-bootstrap flow.

Per the safety contract, root was NOT logged out so the applied infrastructure can be repaired through a newly reviewed exact plan. Root authentication remained valid after the failure. No credentials were printed or persisted.

## Limits

No object was put or deleted. No Compose service, pgBackRest stanza, backup, WAL archive, volume, restore, or unrelated AWS resource was touched. Infrastructure exists, but catalog backup operation is blocked until a non-root operator principal is created/selected, trust is repaired through OpenTofu, a new exact plan is reviewed and approved, role assumption succeeds, and root is logged out.
