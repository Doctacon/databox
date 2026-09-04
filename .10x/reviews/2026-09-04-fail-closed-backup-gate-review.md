Status: recorded
Created: 2026-09-04
Updated: 2026-09-04
Target: commit 8c54a59
Verdict: concerns

# Fail-closed Polaris backup gate review

## Target

Commit `8c54a59` against `.10x/decisions/fail-closed-polaris-backup-gate.md` and `.10x/specs/polaris-catalog-continuity.md`.

## Findings

### Significant: documented credential process is unavailable inside the image

`.env.example` configures `aws configure export-credentials --profile databox-backup --format process`, while `scripts/platform/polaris-postgres.Dockerfile` installs only pgBackRest and Python and does not include AWS CLI or mount host AWS profile/configuration. `scripts/platform/run-pgbackrest.sh` executes the configured command inside the container. The documented default therefore cannot succeed in the built image, so the fail-closed gate can keep PostgreSQL permanently unhealthy.

Smallest repair: provide a pinned renewable credential helper inside the image with an explicit safe credential source, or mount/inject a narrowly defined executable and configuration contract; test the exact documented command path rather than an arbitrary fake helper.

### Significant: initial backup occurs before Polaris initializes its catalog

`compose.iceberg.yml` makes `polaris-bootstrap` depend on PostgreSQL health, while PostgreSQL health runs `catalog-backup-readiness.py` and creates the initial full backup. The first base backup therefore precedes Polaris realm/schema bootstrap. This conflicts with the decision/spec requirement to back up the newly initialized catalog before making Polaris available.

Smallest repair: separate database liveness from backup readiness. Sequence PostgreSQL liveness → Polaris bootstrap → one-shot backup gate/initial full backup → Polaris service readiness. Do not expose the Polaris service before the gate succeeds.

### Significant: readiness marker disables ongoing backup-health enforcement

`ensure_catalog_backup_ready()` returns immediately whenever `/var/run/postgresql/.databox-catalog-backup-ready` exists. Credential expiry, repository loss, or WAL archival failure after initial startup no longer affects container health, so Polaris can remain available while backup protection is broken. This contradicts the ratified requirement that missing, expired, or failed backup health keep Polaris unavailable.

Smallest repair: cache only expensive initial-backup creation. Health must continue to validate credential freshness, repository/stanza status, and WAL/archive health on a bounded cadence, with tests proving a post-start failure makes Polaris unhealthy.

## Verdict

Concerns raised. The static tests establish control flow but the gate is not ready for live use or ticket closure. No live AWS, image build, Compose, backup, or restore operation was performed.

## Residual risk

The environment still lacks a Docker Compose plugin, so image/package compatibility and actual dependency sequencing remain unproven after repair.
