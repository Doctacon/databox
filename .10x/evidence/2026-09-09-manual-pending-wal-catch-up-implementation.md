Status: recorded
Created: 2026-09-09
Updated: 2026-09-09
Relates-To: .10x/tickets/done/2026-09-09-upload-pending-wal-before-local-recovery.md

# Manual pending-WAL catch-up implementation

## Implementation

The existing `scripts/platform/catalog_recovery.py drill` command now performs an authenticated pending-WAL catch-up after fail-closed preflight and before creating its marker. It enumerates only `pg_wal/archive_status/*.ready` basenames from the exact active PostgreSQL container, bounds the result at 4,096 entries, rejects duplicates and anything other than an exact 24-uppercase-hex `.ready` name, sorts by numeric WAL order, and proves each corresponding `pg_wal/<segment>` is a regular file before uploading any segment.

Every pending segment is passed oldest-first to the pinned pgBackRest wrapper as OS user `postgres`, with fresh MFA credential names only and `--no-archive-async`. The command never renames, deletes, or manually marks a WAL/archive-status file. Successfully uploaded segments are tracked in process memory so the marker push cannot redundantly upload one during the same run; a later command safely reissues duplicate archive pushes if `.ready` state remains.

Only after pending catch-up does the command create the before/target/after bracket, switch WAL, and synchronously upload that selected marker segment. It then derives a bounded same-timeline sequence from the predecessor of the oldest pending segment (or marker predecessor for an empty backlog) through the marker. Every segment is synchronously retrieved with pgBackRest `archive-get` using fresh name-only credentials into one exact per-segment `/dev/shm` path. pgBackRest retrieval is repository presence/checksum proof; only that transient path is removed after every attempt. Missing remote segments, malformed/timeline/order state, sequences over 4,096, or temp cleanup failure stop before restore. No `pg_wal` or `archive_status` path is deleted or renamed.

The result reports pending count, oldest/newest pending segments, oldest pending UTC mtime and age at command start, ordered uploaded segments/count, informational observed repository maximum, continuity anchor, verified-through marker, accepted pre-catch-up local-loss policy, and `marker_target_inclusion_seconds`. Repository maximum is never used as continuity proof. It no longer emits `achieved_rpo_seconds` or a five-minute objective. End-to-end 3,600-second RTO remains the sole objective and failed results remain quiesced.

## Validation

- Focused recovery and validator tests: 135 passed without coverage. They cover the exact observed segment-14 anchor plus 15–1A backlog and marker sequence, empty backlog, noncontiguous pending files retrieved from remote, hexadecimal rollover, timeline/order/count rejection, archive-get failure, exact temp cleanup failure/order, no WAL/status deletion, and restore only after all remote gets. The separately authorized live drill remains the real S3 stateful integration proof; no second credentialed S3 environment was created.
- Ruff format/check passed for the recovery implementation and tests.
- MyPy passed for 91 package files and separately for `catalog_recovery.py`.
- Secret scan passed across 934 eligible files.
- A disposable `--network none` pinned-image probe proved pgBackRest 2.59.1 accepts synchronous `--no-archive-async archive-get`; it used no credentials or mounts.
- Task dry-run rendered only the existing recovery entrypoint.
- `git diff --check` passed.
- A read-only invocation of the exact live enumeration and regular-file checks observed six valid pending files, segments 15 through 1A. No AWS call or upload occurred.

Tests additionally cover informational repository maximum without treating it as proof, oldest pending age at command start, name-only fresh credential delivery for archive-get, synchronous archive behavior, and guaranteed exact `/dev/shm` cleanup.

## Safety boundary

No AWS call, active SQL mutation, WAL upload, marker, restore, Docker resource creation/deletion, recovery-artifact cleanup, or drill occurred. Existing failed-recovery artifacts and unrelated `uv.lock` were untouched.
