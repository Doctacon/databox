Status: recorded
Created: 2026-09-04
Updated: 2026-09-04
Target: .10x/evidence/.storage/2026-09-04-databox-catalog-only-tls.tfplan.txt
Verdict: concerns

# Catalog-only TLS plan review

## Target

Exact binary plan SHA-256 `4656b197fd1039d4972c614e828ad0be92128fec6c6f83d4a6a6fd88abc98837` and its recorded text/evidence.

## Findings

### P1 — Backup role cannot abort failed multipart uploads

`infra/recovery/main.tf` grants bucket location/list and object get/put/delete but omits `s3:AbortMultipartUpload`. pgBackRest can use multipart upload for large backup objects; aborting an incomplete upload is a distinct object-scoped IAM action. Seven-day lifecycle cleanup does not allow prompt client cleanup. Add `s3:AbortMultipartUpload` on the catalog bucket object ARN and focused policy coverage. Version-history permissions remain intentionally omitted.

### P1 — Current rollout dependency forbids apply

The live apply ticket depends on final automation verification, but the user has since required provisioning and proving a real backup before restore automation. The graph must be explicitly reordered or split before apply; plan review alone cannot bypass the active dependency.

### P2 — Local OpenTofu state ownership is undefined

The configuration has no backend and the plan used `init -backend=false`. Applying from `infra/recovery` would create ignored local state, but the runbook does not define its durable secure location, backup, or recovery/import procedure. Resolve state ownership before apply, either with a reviewed backend or a documented securely preserved local-state procedure.

## Passed checks

The plan contains exactly eight creates, zero changes, and zero destroys. It targets account `734815189723`, `us-west-1`, and bucket `databox-lake-catalog-backup`; uses accepted root bootstrap trust and `force_destroy=false`; enables versioning, AES256, public-access blocking, HTTPS denial, 30-day noncurrent retention, and incomplete-upload cleanup; and contains no primary warehouse, Iceberg, or replication action.

## Verdict

Do not apply this plan. Repair multipart abort permission, resolve rollout ordering and state ownership, regenerate and independently review a new exact plan, then seek explicit approval.

## Residual risk

The review did not execute the binary plan or contact AWS. `-refresh=false` does not prove bucket-name availability or remote drift. Runtime role assumption, pgBackRest repository behavior, backup, WAL archival, and restore remain unproven.
