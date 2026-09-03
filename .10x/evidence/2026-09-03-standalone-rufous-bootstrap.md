Status: recorded
Created: 2026-09-03
Updated: 2026-09-03
Relates-To: .10x/tickets/done/2026-09-03-bootstrap-standalone-rufous.md

# Standalone Rufous bootstrap evidence

## Result

Created `/Users/crlough/Code/personal/rufous` as a fresh Git repository. Root commit `6ba7593` contains 274 product-owned source files copied from Databox revision `572ca6191f598e323161cdadeec3898f10913d31`; no Databox product files were deleted. The destination package identity is `rufous`, and `databox-sources` is pinned by immutable local Git URL, subdirectory, and exact revision.

## Boundary evidence

Rufous settings expose separate `RUFOUS_DATABOX_PRODUCT_PATH` and `RUFOUS_DATABASE_PATH`. A 2.5 MiB credential-free v1 DuckDB fixture is committed and validated/attached read-only. Search found no private `databox.*` Python import. Product-owned iNaturalist implementation moved under `rufous.sources`; reusable USFWS uses the public pinned package. Source-refresh backend registration was removed rather than importing Databox runtime code. Production remains fail-closed with `if: ${{ false }}`.

Copied ownership includes app, worker, product Python modules/tests/scripts, product models/contracts, media configuration, Cloudflare workflows/infra, application migrations, and product operations docs. `.env`, local state/data, caches, generated docs, Git history, node modules, builds, and credentials were excluded by explicit copy rules and ignore policy.

## Validation

- Destination bootstrap Ruff, MyPy, and 3 artifact/settings tests passed.
- React typecheck, 545 tests, and production build passed.
- Worker 71 tests passed.
- Databox secret checker passed all 278 eligible destination files.
- npm reproducible installs passed; audits reported one high app issue and two moderate/one high worker issues for later review.
- Full Python discovery collected 580 tests and intentionally reported 18 migration-owned collection errors; no missing private module was copied to conceal them.
- Rufous working tree was clean after root commit. Databox had no staged files and changed only extraction records after its prerequisite boundary commit.

## Deferred work

`.10x/tickets/2026-09-03-migrate-rufous-models-and-backend.md` owns settings completion, destination replacement, artifact SQL rewrites, USFWS orchestration, and all Python test collection/execution. `.10x/tickets/2026-09-03-migrate-rufous-web-public-deployment.md` owns source-refresh UI removal, stale paths/workflow commands, app/worker naming, public checks, and npm audit disposition.
