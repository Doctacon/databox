Status: recorded
Created: 2026-09-09
Updated: 2026-09-09

# Interactive drill WAL archive user repair

A proactive post-preflight audit found that both marker and cleanup WAL `archive-push` calls would execute as container root. The adapter now supplies `docker exec --user postgres` before every active-container archive push, matching pgBackRest's required operating-system user. Integrated coverage asserts all four in-container/image pgBackRest invocations select `postgres`, pass credentials only by environment-variable name, and retain the reviewed operation order. No live operation was run.
