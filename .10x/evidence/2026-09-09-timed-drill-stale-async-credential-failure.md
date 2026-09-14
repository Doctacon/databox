Status: recorded
Created: 2026-09-09

# Timed drill stale asynchronous archive credential failure

The interactive drill passed authentication and preflight, then committed marker `databox_recovery_drill_y0puu4ucgfgbx81p`: `before=2026-09-09 20:55:29.078868+00`, `after=2026-09-09 20:55:29.191962+00`. Marker WAL archival failed with S3 `ExpiredToken` before restore. The active pgBackRest configuration has `archive-async=y`; PostgreSQL's active `archive_command` inherited expired startup credentials, and the explicit archive push entered the shared asynchronous spool instead of proving the fresh MFA session synchronously.

No recovery container, volume, or network was created. The marker remains and must be reconciled before rerun. The repair adds exact `--no-archive-async` to explicit marker and cleanup archive pushes while retaining OS user `postgres`. The existing tool now exposes `cleanup-marker`, which validates the active preflight, drops only an explicitly named drill-owned marker, and synchronously archives cleanup WAL with MFA-issued credentials. No live cleanup or drill ran during repair.
