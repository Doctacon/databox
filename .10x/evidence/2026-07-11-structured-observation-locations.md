Status: recorded
Created: 2026-07-11
Updated: 2026-07-11
Relates-To: .10x/tickets/done/2026-07-11-persist-structured-observation-locations.md, .10x/specs/structured-observation-locations.md

# Structured observation locations verification

## What was observed

Private observations now support nullable structured location source, canonical source ID, latitude, longitude, Arizona timezone, and Arizona region columns. The storage service and API enforce all-or-none values, strict source/type/ID relationships, exact selected display-name matching, finite exact-polygon Arizona coordinates, `America/Phoenix`, and `US-AZ`. Free text remains valid with all structured fields null. Updating without a selection clears all structured fields atomically; updating with another selection replaces them atomically.

The private observation response is expanded with the six nullable fields. Browser validation rejects extra, partial, source-inconsistent, nonfinite, and out-of-bounds rows. The browser request type can carry the exact completed suggestion contract, while the observation combobox remains excluded from this ticket.

## Migration preflight and live application

Before mutation, the live warehouse contained exactly one observation in the legacy seven-column schema. Its optional free-text location was present and notes absent. The live byte hash was:

```text
87d45ece558cd248aa6efdd295798276775093a4906eeac40f8c41a9eea245bc
```

After focused tests and both complete Python/browser suites passed, the migration was rehearsed on an isolated `/tmp` copy:

1. Begin, apply all six additive columns, roll back, and prove the original schema and all original rows match exactly.
2. Apply the migration twice in one transaction and commit.
3. Prove exactly six columns were added, original seven-column row values match exactly, and every structured field is null.

The same SQL was then applied twice in one live transaction. Results:

```text
copy_rollback=passed
copy_apply_twice=passed
live_observation_count=1
original_columns_preserved=True
structured_null_rows=1
safe presence-only checksum before=aeee03cbd2c809dcbdcf4bb270baf96043eb094bed7b6193c5bf5c34d3017b65
safe presence-only checksum after =aeee03cbd2c809dcbdcf4bb270baf96043eb094bed7b6193c5bf5c34d3017b65
```

No location text was printed or recorded. The post-migration warehouse hash is expectedly different because of the authorized schema addition:

```text
0dc79f3596c9bd5698c4c9f40d91dd0cfbda82f2093a85611c4aacfedcd003ce
```

A final read-only check returned `migration_required=False`, the exact six new column names, one private observation with null structured fields, and unchanged warehouse hash. The private fields were absent from live `/api/birds`, `/api/life-list`, and `/api/map-snapshot` responses.

## Automated verification

Focused backend:

```text
PYTHONDONTWRITEBYTECODE=1 .venv/bin/pytest -q --no-cov tests/test_personal_collection_api.py
21 passed
```

This covers selected Watson create, free-text create, clear, Open-Meteo replacement, mismatch, invalid source, inconsistent type, out-of-polygon coordinates, partial raw fields, transaction rollback, fresh-table storage constraints, service rejection, legacy reads, migration rollback, migration idempotency, original-row preservation, and privacy surface absence.

Complete backend and browser:

```text
network-proxied-offline PYTHONDONTWRITEBYTECODE=1 .venv/bin/pytest -q
709 passed; 3 snapshots passed; 86.74% coverage

cd app && npm test -- --run
251 passed across 15 files

cd app && npm run typecheck
passed
```

Additional gates:

```text
cd app && npm run build
passed; 51 modules transformed

.venv/bin/python scripts/audit_app_bundle.py app/dist
bundle configuration audit passed: 12 names and 10 configured values absent

.venv/bin/mypy packages/databox/databox packages/databox-sources/databox_sources
Success: no issues found in 71 source files

.venv/bin/python scripts/generate_docs.py --check
docs/dictionary is in sync (20 files)

.venv/bin/python scripts/check_secrets.py <changed implementation and migration files>
passed with no findings

.venv/bin/pre-commit run --all-files
all 11 hooks passed

git diff --check
passed

git diff --cached --name-only
no output
```

The Vite build retained the pre-existing lazy Field Map chunk-size advisory. A standalone `detect-secrets` executable is not installed; the repository-native `scripts/check_secrets.py` scan and all-files pre-commit gate passed.

## What this supports

- The existing personal observation, free-text presence, timestamps, identity, and safe logical checksum were preserved exactly; all new fields are null.
- Migration application is additive, idempotent, and transactionally rollback-safe.
- Structured selected locations persist and read only through private observation APIs.
- Invalid and partial states do not write; clear and replacement are atomic.
- Catalog, life-list aggregation, Field Map, evidence, model, trace, and logging behavior remain outside the structured private response.
- No file was staged or committed.

## Limits

No observation combobox UI was added because the executable ticket explicitly excludes it. The browser contract and private API are ready for that separately owned UI slice. Independent review remains required before ticket closure.
