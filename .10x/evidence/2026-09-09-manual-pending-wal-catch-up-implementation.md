Status: recorded
Created: 2026-09-09
Updated: 2026-09-09
Relates-To: .10x/tickets/2026-09-09-upload-pending-wal-before-local-recovery.md

# Manual pending-WAL catch-up implementation

## Implementation

The existing `scripts/platform/catalog_recovery.py drill` command now performs an authenticated pending-WAL catch-up after fail-closed preflight and before creating its marker. It enumerates only `pg_wal/archive_status/*.ready` basenames from the exact active PostgreSQL container, bounds the result at 4,096 entries, rejects duplicates and anything other than an exact 24-uppercase-hex `.ready` name, sorts by numeric WAL order, and proves each corresponding `pg_wal/<segment>` is a regular file before uploading any segment.

Every pending segment is passed oldest-first to the pinned pgBackRest wrapper as OS user `postgres`, with fresh MFA credential names only and `--no-archive-async`. The command never renames, deletes, or manually marks a WAL/archive-status file. Successfully uploaded segments are tracked in process memory so the marker push cannot redundantly upload one during the same run; a later command safely reissues duplicate archive pushes if `.ready` state remains.

Only after pending catch-up does the command create the before/target/after bracket, switch WAL, synchronously upload that selected marker segment, and proceed to restore. Ordered successful pgBackRest pushes through the marker are the continuity proof. Catch-up failure identifies only the segment and one-based position, stops before marker/restore, and remains credential-redacted.

The result reports pending count, oldest/newest pending segments, accepted pre-catch-up local-loss policy, continuity-through marker segment, and `marker_target_inclusion_seconds`. It no longer emits `achieved_rpo_seconds` or a five-minute objective. End-to-end 3,600-second RTO remains the sole objective and failed results remain quiesced.

## Validation

- Focused recovery/validator suite: 127 passed without coverage.
- Ruff format/check passed for the recovery implementation and tests.
- MyPy passed for 91 package files and separately for `catalog_recovery.py`.
- Secret scan passed across 933 eligible files.
- Task dry-run rendered only the existing recovery entrypoint.
- `git diff --check` passed.
- A read-only invocation of the exact live enumeration and regular-file checks observed six valid pending files, segments 15 through 1A. No AWS call or upload occurred.

Tests cover empty backlog, the exact live six-file shape in unsorted order, an ordered list with a gap, malformed/path/duplicate output, safe-count overflow, missing/nonregular WAL files, first failed ordered push, within-process marker deduplication, later-process duplicate-safe pushes, catch-up-before-marker/restore ordering, reporting terminology, and all prior recovery safety behavior.

## Safety boundary

No AWS call, active SQL mutation, WAL upload, marker, restore, Docker resource creation/deletion, recovery-artifact cleanup, or drill occurred. Existing failed-recovery artifacts and unrelated `uv.lock` were untouched.
