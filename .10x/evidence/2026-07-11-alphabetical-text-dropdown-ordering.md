Status: recorded
Created: 2026-07-11
Updated: 2026-07-11
Relates-To: .10x/tickets/done/2026-07-11-alphabetize-text-dropdown-options.md, .10x/specs/alphabetical-text-dropdown-ordering.md

# Alphabetical text dropdown ordering evidence

## Select inventory

All 12 current native selects are mechanically counted and classified by `app/src/visibleLabel.test.ts`:

| Surface | Select | Governed order |
|---|---|---|
| Trip evidence | rows per page | numeric |
| Trip form | duration | numeric |
| Trip form | skill | ordinal; sentinel first |
| Trip history | saved plan | chronological; sentinel/loading first |
| Target bird | duration | numeric |
| My Birds observation | bird | alphabetical visible identity, species-code tie |
| My Birds Watch | available bird | alphabetical visible identity, species-code tie |
| Catalog | sort action | authored semantic action order |
| Catalog | category | sentinel then alphabetical text |
| Catalog | family | sentinel then alphabetical text |
| Catalog | habitat | sentinel then alphabetical text |
| Catalog | weight | numeric bucket progression; sentinel first |

There is no current Field Map select in source; it remains a future surface governed by the active specification.

## What was observed

- `app/src/visibleLabel.ts` is the only `Intl.Collator` in app source. It deterministically compares English labels case-insensitively with numeric segments, then optional explicit tie labels.
- Catalog name sorting uses visible common/scientific/species-code identity and species-code ties. Family and habitat options use the same comparator with governed option-value ties; their All sentinels remain outside the sorted option list and first.
- My Birds creates a copied alphabetical bird array without mutating API input. Both new-observation and edit-observation selectors receive it. Available Watch birds filter the same ordered copy without changing watch exclusion semantics.
- An adversarial reverse-ordered 706-row catalog proves `alpha 2`, `Alpha 10`, scientific-name fallback, species-code fallback, and remaining names order by visible identity. A stale watch remains excluded from available Watch choices. Selecting the last Zebra option submits its unchanged `bird000` value.
- Empty observation/watch behavior and all pre-existing collection mutations, edit selection, stale identities, fallback display, navigation, tabs, numeric controls, and history regressions pass.

## Procedure and results

- `cd app && npm run typecheck && npm test -- --run src/visibleLabel.test.ts src/MyBirds.test.tsx src/BirdPages.test.tsx` — typecheck and 45/45 focused tests passed.
- `cd app && npm run typecheck && npm test -- --run && npm run build && ../.venv/bin/python ../scripts/audit_app_bundle.py` — 228/228 frontend tests, typecheck, production build, and bundle privacy audit passed.
- `env -u HTTP_PROXY -u HTTPS_PROXY -u ALL_PROXY NO_PROXY='*' PYTHONDONTWRITEBYTECODE=1 .venv/bin/pytest -q tests/test_personal_collection_api.py --block-network -p no:cacheprovider --no-cov` — 17/17 collection API tests passed without network.
- `git diff --check && uv run ruff check . && uv run python scripts/check_secrets.py .` — passed.
- `rg -n 'Intl\.Collator|localeCompare' app/src --glob '*.{ts,tsx}'` — exactly one application comparator, in `app/src/visibleLabel.ts`.

A prior targeted collection invocation without `--no-cov` executed all 17 tests successfully but exited nonzero because a targeted subset cannot satisfy the repository-wide 70% coverage threshold (32.70% observed). The corrected targeted command above passed.

## Limits

The inventory covers native `<select>` elements currently present in application TSX. Location comboboxes are custom suggestion controls rather than selects and are outside this ticket. Independent review remains required before closure.
