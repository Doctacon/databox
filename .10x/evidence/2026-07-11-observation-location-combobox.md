Status: recorded
Created: 2026-07-11
Updated: 2026-07-11
Relates-To: .10x/tickets/done/2026-07-11-add-observation-location-combobox.md, .10x/specs/structured-observation-locations.md

# Observation location combobox verification

## What was observed

The shared strict `LocationCombobox` now supports an explicit optional free-text mode. New and edit observation forms in My Birds and direct bird profiles use that shared component without making location required. A selected suggestion is retained as the exact strict `location_selection`; typing in the field clears selection while preserving the private text; selecting another suggestion replaces it. Existing structured observations reconstruct the exact suggestion shape, while existing legacy/free-text rows initialize with no selection.

Successful new observations reset date, location text, structured selection, and notes. Failed saves preserve all form and selection state and focus the existing safe error region. Existing collection mutation locking and revision behavior remains unchanged.

## Focused browser evidence

`app/src/MyBirds.test.tsx` now covers:

- My Birds keyboard selection of Watson Lake and exact source/ID/name/coordinate/timezone/region request payload;
- optional empty/free-text behavior and explicit private-text help;
- new-form reset after success;
- existing structured initialization and unchanged save;
- editing text to clear structured selection;
- legacy/free-text initialization;
- Open-Meteo replacement selection;
- exactly one observation-list invalidation per successful mutation;
- direct profile selection;
- failed selected save preserving the exact field/selection and focusing a safe redacted error.

Focused My Birds passed 19/19. Existing shared-component tests continue to cover keyboard listbox behavior, debounced loading, aborted stale searches, Escape/cancellation, direct-coordinate bypass, safe fallback failure, and source/type coordinate display. Responsive theme verification passed 4/4, including the 320px minimum-width contract, overflow wrapping, narrow breakpoints, focus visibility, reduced motion, and 44px controls.

## Full gates

The first two combined frontend runs exposed the pre-existing immediate Target Bird heading focus race; focused Target Bird passed independently. The separately authorized test-only repair under `.10x/tickets/done/2026-07-11-stabilize-target-bird-heading-focus-test.md` changed the immediate assertion to bounded `waitFor` without production changes. After that repair:

```text
cd app && npm test -- --run
15 files passed; 253 tests passed

cd app && npm run typecheck
passed

cd app && npm run build
passed; 51 modules transformed

.venv/bin/python scripts/audit_app_bundle.py app/dist
bundle configuration audit passed: 12 names and 10 configured values absent
```

Collection/privacy gates:

```text
PYTHONDONTWRITEBYTECODE=1 .venv/bin/pytest -q --no-cov \
  tests/test_personal_collection_api.py tests/test_api.py tests/test_map_snapshot_api.py
58 passed

PYTHONDONTWRITEBYTECODE=1 .venv/bin/pytest -q --no-cov tests/test_rufous_theme.py
4 passed
```

The warehouse hash was identical before/after all collection/privacy tests:

```text
0dc79f3596c9bd5698c4c9f40d91dd0cfbda82f2093a85611c4aacfedcd003ce
```

Final live read-only reconciliation:

```text
personal observations=1
safe checksum=aeee03cbd2c809dcbdcf4bb270baf96043eb094bed7b6193c5bf5c34d3017b65
all six structured fields null=True
```

No live observation was created, edited, or deleted.

## What this supports

- The exact structured suggestion contract reaches private observation create/update calls.
- Optional free text remains usable and clears structured identity on edit.
- Existing structured and free-text rows initialize correctly.
- Failure, focus, loading, cancellation, keyboard, fallback, CRUD, invalidation, privacy, and narrow-screen protections remain coherent.
- The live personal observation is unchanged.
- No files were staged or committed.

## Limits

Automated browser behavior is verified in jsdom at the typed component/API boundary; no physical 320px screenshot was captured. The existing Vite lazy Field Map chunk advisory remains unrelated. Independent review remains required before closure.
