Status: recorded
Created: 2026-09-04
Updated: 2026-09-04
Relates-To: .10x/tickets/2026-09-04-declare-aws-recovery-infrastructure.md

# AWS recovery infrastructure automation

## What was observed

`infra/recovery/` now declares two distinct versioned, encrypted, public-blocked S3 buckets in the existing `us-west-1` account: one for pgBackRest catalog backups and one for Iceberg recovery objects. The source warehouse bucket and prefix are inputs. Replication covers that prefix, explicitly disables delete-marker replication, omits `s3:ReplicateDelete`, and grants the replication role only object/tag replication at the destination.

Separate operator-assumable roles own catalog backup access and read-only Iceberg recovery. The routine writer principal is explicitly denied `DeleteObject` and `DeleteObjectVersion` against the recovery bucket. Noncurrent Iceberg object versions are retained for 45 days; deleted catalog backup versions are retained for 30 days. The OpenTofu provider is restricted to the explicit 12-digit account and `us-west-1`, and consumes a shared-config profile paired with a non-secret renewable credential-process command.

## Procedure and results

- Installed open-source OpenTofu 1.12.6 locally with Homebrew so native validation could run.
- `cd infra/recovery && tofu init -backend=false -input=false` — passed; installed the bounded HashiCorp AWS provider and generated the committed lock file. No backend or AWS resources were created.
- `cd infra/recovery && tofu fmt -check -recursive && tofu validate` — passed.
- `.venv/bin/pytest -q -o addopts='' tests/platform/test_recovery_infrastructure.py` — 5 passed.
- `.venv/bin/ruff check tests/platform/test_recovery_infrastructure.py` — passed.
- `.venv/bin/ruff format --check tests/platform/test_recovery_infrastructure.py` — passed after formatting.
- `.venv/bin/python scripts/platform/check_secrets.py .` — passed, 819 eligible files checked.
- `git diff --check` — passed.

Static tests assert version bounds, account/region inputs, distinct buckets, versioning/encryption/public blocks, 30/45-day version retention, prefix-bounded replication, disabled delete-marker replication, absence of replicate-delete authority, explicit routine-writer delete denial, separate backup/read-only recovery roles, and placeholder-only example values.

## What this supports

This supports the automation-first acceptance criteria in `.10x/tickets/2026-09-04-declare-aws-recovery-infrastructure.md`. No `tofu plan` was generated because real account/profile/bucket inputs were intentionally not supplied in this phase. The configuration and provider schema were validated locally.

## Limits

No `tofu apply`, AWS API write, bucket creation, policy mutation, replication, provider refresh, backup upload, or restore occurred. OpenTofu owns the complete replication configuration for the existing source bucket; the eventual plan must be checked for pre-existing rules before apply. Same-account and same-region recovery cannot survive complete account compromise or a regional outage. The pre-existing unstaged deletion `.pi/skills/turbo-search-engineering-research/SKILL.md` was not modified or staged by this work.
