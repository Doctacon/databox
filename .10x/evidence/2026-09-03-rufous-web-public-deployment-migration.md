Status: recorded
Created: 2026-09-03
Updated: 2026-09-03
Relates-To: .10x/tickets/2026-09-03-migrate-rufous-web-public-deployment.md

# Rufous web, public release, and deployment migration evidence

## Result

Standalone Rufous owns the React app, Workers AI worker, public/media scripts, Cloudflare workflow/configuration, and product operations documentation. Source-refresh UI/API files and the private control were removed. Workflow commands and triggers are destination-relative; Databox source launch, Quack, package, and working-database commands are absent. Production remains exactly `if: ${{ false }}` and no deployment occurred.

## Safety preservation

The existing public exporter, privacy audit, immutable object publisher, media approvals, licensing/attribution checks, audio sanitizer separation, R2 credential separation, and provider-contact restrictions remain covered by the complete Python and workflow test suite. The production job now fails explicitly at the artifact-delivery boundary even if its outer fail-closed guard were accidentally changed.

## Verification

- Python: 1,072/1,072 passed, including 11/11 repaired workflow tests.
- React: typecheck passed; 537/537 tests passed after removing eight source-refresh tests; production and public builds passed.
- Worker: 71/71 passed.
- Product SQLMesh: 11/11 passed.
- Credential-free public synthetic export created 2 species/2 observations and seven files; local immutable publication succeeded; public release safety audit passed.
- Ruff, format, MyPy (53 source files), pre-commit, secret scan, and `git diff --check` passed.
- npm audit initially reported one high app advisory and two moderate/one high worker advisories. Lockfile-only safe upgrades resolved all; both app and worker now report zero vulnerabilities, with app tests/build and worker tests passing afterward.
- Search found no active Databox package/path, Quack, Databox database, or source-refresh runtime coupling. References remaining in tests are forbidden-token assertions; `databox_sources.usfws` is the ratified public dependency.

## Independent review repairs

Review found that workflow use of `--extra r2` had no matching Rufous dependency, the disabled production job did not express the local artifact/model seam, and standalone docs retained Databox source/Dagster instructions. Rufous now owns an `r2` extra with boto3 locked to 1.43.56; a no-network test constructs the real S3 client and verifies its endpoint. Production remains `if: ${{ false }}`, but its tested seam requires `RUFOUS_DATABOX_PRODUCT_PATH`, validates the local v1 artifact, and runs `sqlmesh_plan_rufous_public.sh` when eventually enabled. README and public-release instructions now use the artifact and local repository links. Focused public-release/workflow tests passed (43), as did locked r2 sync, Ruff, MyPy, pre-commit, secret scan (268 files), and diff validation.

## Limits

Production artifact delivery remains intentionally undefined and disabled. No cloud credentials, provider refresh, R2 write, Pages deployment, or production activation occurred.
