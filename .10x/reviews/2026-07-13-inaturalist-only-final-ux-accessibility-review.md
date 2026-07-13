Status: recorded
Created: 2026-07-13
Updated: 2026-07-13
Target: `.10x/tickets/done/2026-07-11-verify-curated-representative-photos.md`, current iNaturalist-only representative-photo frontend, tests, diff, and aggregate/child evidence
Verdict: pass

# Final iNaturalist-only representative-photo UX/accessibility rereview

## Review

### Correct

- **The reported whole-catalog `invalid unavailable photo` failure is resolved.** `app/src/birdApi.ts:78-91` treats typed unavailable photos as valid when `species_name` is either null or exactly the containing scientific identity, while still requiring every active-media field to be null. `app/src/BirdPages.test.tsx:582-607` covers a 706-row mixed catalog with an exact-identity placeholder and an available iNaturalist photo. My fresh read-only aggregate run reconstructed all 706 persisted rows, returned `/api/birds`, placeholder profile `baitea`, `/api/map-snapshot`, a saved plan, and `/birds` with HTTP 200, and observed exactly 622 available photos plus 84 placeholders with the DuckDB SHA-256 unchanged.

- **Catalog and profile expose coherent available, unavailable, and load-failure states.** `app/src/BirdPages.tsx:96-130` gives available images meaningful bird-identity alt text, renders unavailable images as a Rufous placeholder with an accessible `role="img"` name, announces a later image failure through `role="status"`, and leaves creator, iNaturalist source, and license links in the figcaption after failure. The profile uses the same component at `app/src/BirdPages.tsx:394-400`. Rendering and load-failure behavior are exercised at `app/src/BirdPages.test.tsx:350-365,367-388`.

- **Field Map now satisfies the prior source/license and announcement gaps.** `app/src/FieldMap.tsx:77-96` renders bird-name alt text for available thumbnails, hides Rufous placeholder artwork from assistive technology, exposes a restrained status after image failure, and preserves plain-text attribution plus native iNaturalist source and Creative Commons license links. Encounter selection remains a native button with persistent `aria-pressed`; source/license destinations remain separate native links (`app/src/FieldMap.tsx:304-317`). `app/src/FieldMap.test.tsx:180-199` verifies attribution, both destinations, placeholder replacement, and status text after failure. Focus and hover previews remain independent (`app/src/FieldMap.test.tsx:156-178`).

- **New and saved Trip Planner results share the same validated and accessible presentation.** Both `createPlan` and `getPlan` pass responses through `validatePlanDetail` (`app/src/api.ts:73-94`), and both render through `PlanView`/`PhotoArea` (`app/src/App.tsx:138-181,325-387,472-538`). Available images use common plus scientific name where present; unavailable and failed images show the Rufous artwork decoratively with explicit species-specific text; later failures use `role="status"`. Creator, license, and iNaturalist source remain visible after load failure. `app/src/App.test.tsx:160-213,442-457` verifies these states, attribution, alt text, decorative placeholder text alternative, and links.

- **Response validation fails closed before partial rendering.** The shared validator binds status, exact scientific identity, creator, selection reason, provider, dimensions, canonical license code/text/URL, exact photo ID, approved hosts, large-variant path, and URL hygiene (`app/src/curatedPhotoValidation.ts:1-72`). Catalog/profile and Field Map reuse it through `validateCatalogPhoto` (`app/src/birdApi.ts:53-91`; `app/src/mapApi.ts:68-104`). Planner validation requires exact fields and linked iNaturalist evidence (`app/src/tripPlanValidation.ts:179-189,340-359`). Adversarial coverage rejects legacy providers, wrong hosts/IDs/variants, ports, credentials, query/fragment data, unsupported or mismatched licenses, undersized dimensions, and extra fields (`app/src/curatedPhotoValidation.test.ts:15-37`; `app/src/BirdPages.test.tsx:624-665`; `app/src/tripPlanValidation.test.ts:63-84`; `app/src/App.test.tsx:459-475`).

- **Keyboard/focus and native-control semantics remain intact.** The catalog is a focusable ARIA listbox with synchronized `aria-activedescendant`/`aria-selected` and Arrow/Page/Home/End handling (`app/src/BirdPages.tsx:301-305,348-360`), covered at `app/src/BirdPages.test.tsx:167-185`. Field Map encounters are native buttons, while photo source/license destinations are native anchors. Planner controls remain labeled native inputs, selects, and buttons (`app/src/App.tsx:493-533`). No representative-photo change replaced a native control with a pointer-only element.

- **The implementation remains bounded to the active iNaturalist-only contract.** The inspected active spec excludes alternate representative-photo sources and requires placeholders rather than unsafe fallback. Current frontend validation and labels activate only `inaturalist`; the fresh aggregate inspection found zero Wikimedia/GBIF representative rows and eight of eight saved recommendation photos valid and available from iNaturalist.

### Fixed

- **Resolved prior significant finding:** Trip Planner unavailable photos now render the Rufous placeholder (`app/src/App.tsx:158-165`).
- **Resolved prior significant finding:** the superseded Wikimedia validation path is gone; one shared strict iNaturalist validator governs catalog/map/planner activation (`app/src/curatedPhotoValidation.ts:1-72`).
- **Resolved prior significant finding:** Field Map now exposes and retains canonical photo source and license destinations (`app/src/FieldMap.tsx:89-96,317`).
- **Resolved prior minor finding:** planner and Field Map asynchronous image failures now expose restrained status semantics (`app/src/App.tsx:162-164`; `app/src/FieldMap.tsx:83-85`).

### Blocker

- None found.

### Note

- The requested repository-root `plan.md` and `progress.md` do not exist; direct reads returned `ENOENT`. This review therefore used the active specification, parent/aggregate and done child tickets, aggregate/child evidence, prior UX review, current frontend source/tests, and working diff.
- The relevant frontend diff is coherent but sits inside a much larger unstaged working tree. This rereview assessed the requested representative-photo UX/accessibility surface and did not claim that unrelated changes were reviewed.

## Verification

- Fresh strict TypeScript and five focused frontend suites passed: 5 files and 145 tests (13 curated validator, 38 planner validation, 7 Field Map, 58 App, 29 BirdPages).
- Fresh read-only aggregate validation found 706/706 valid catalog photo singletons (622 iNaturalist available, 84 typed placeholders), eight/eight valid saved-plan iNaturalist photos, zero legacy representative rows, zero planner dry-run targets/lookups, HTTP 200 for catalog/placeholder profile/map/saved plan/browser routes, and unchanged database SHA-256.
- `git diff --check` passed and the staged file list was empty.

## Verdict

**Pass.** No critical, significant, or minor closure-blocking UX/accessibility finding remains. The prior `invalid unavailable photo`, planner placeholder, strict-provider-validation, Field Map source/license, and load-failure announcement findings are resolved, and the current 622/84 mixed catalog loads successfully without weakening fail-closed response handling.

## Residual risks and test limits

- jsdom establishes DOM roles, names, alt attributes, native elements, state changes, links, keyboard handlers, and validator outcomes. It does not establish actual screen-reader announcement timing or whether nested/broad polite live regions produce duplicate speech in a specific browser/AT pairing.
- No physical-browser or assistive-technology session was performed. Catalog listbox behavior should still be sampled with NVDA/JAWS/VoiceOver for active-descendant speech and scroll synchronization; planner and Field Map failure announcements should be sampled for restraint and non-duplication.
- No physical narrow-screen, browser zoom, forced-colors, or real rasterized contrast/layout pass was performed. CSS and jsdom assertions cannot prove long attribution/link wrapping or map/card layout at 320 px.
- Real remote-image loading, visual crop/subject suitability, and future provider URL/content availability remain unproven. This is an intentional metadata-only design with no binary cache.

```acceptance-report
{
  "criteriaSatisfied": [
    {
      "id": "criterion-1",
      "status": "satisfied",
      "evidence": "The independent rereview stayed within the requested iNaturalist-only representative-photo UX/accessibility surface and made no repository edits; current source and diff align with the active spec without introducing another provider or UI feature."
    },
    {
      "id": "criterion-2",
      "status": "satisfied",
      "evidence": "The review cites current source/tests and records fresh focused test output plus a fresh read-only 706-row aggregate validation, exact 622/84 counts, HTTP statuses, unchanged database hash, diff check, and residual physical-browser/AT limits."
    }
  ],
  "changedFiles": [
    "app/src/App.tsx",
    "app/src/BirdPages.tsx",
    "app/src/FieldMap.tsx",
    "app/src/birdApi.ts",
    "app/src/curatedPhotoValidation.ts",
    "app/src/styles.css",
    "app/src/tripPlanValidation.ts",
    "app/src/types.ts"
  ],
  "testsAddedOrUpdated": [
    "app/src/App.test.tsx",
    "app/src/BirdPages.test.tsx",
    "app/src/FieldMap.test.tsx",
    "app/src/curatedPhotoValidation.test.ts",
    "app/src/tripPlanValidation.test.ts"
  ],
  "commandsRun": [
    {
      "command": "cd app && npm run typecheck && npm test -- --run src/curatedPhotoValidation.test.ts src/BirdPages.test.tsx src/FieldMap.test.tsx src/tripPlanValidation.test.ts src/App.test.tsx",
      "result": "passed",
      "summary": "Strict TypeScript passed; 5 focused test files and all 145 tests passed."
    },
    {
      "command": "PYTHONDONTWRITEBYTECODE=1 .venv/bin/python /tmp/inat_aggregate_validate.py",
      "result": "passed",
      "summary": "Read-only reconstruction validated 706 catalog and 8 planner photo singletons; mixed GETs returned 200 and the database SHA-256 remained unchanged."
    },
    {
      "command": "git diff --check && test -z \"$(git diff --cached --name-only)\" && echo NO_STAGED_FILES",
      "result": "passed",
      "summary": "No whitespace errors and no staged files."
    },
    {
      "command": "git status --short && git diff --stat && git diff --name-only && git diff --cached --name-only",
      "result": "passed",
      "summary": "Inspected the complete unstaged working-tree scope and confirmed an empty staged diff."
    }
  ],
  "validationOutput": [
    "Focused frontend: 5 test files passed; 145 tests passed.",
    "Catalog reconstruction: 706 valid singletons = 622 inaturalist:available + 84 curated_photo:unavailable.",
    "Planner reconstruction: 8 valid iNaturalist available singletons; dry-run targets=0 and lookups=0.",
    "GET statuses: catalog=200, placeholder profile baitea=200, map=200, saved plan=200, browser=200.",
    "Legacy Wikimedia/GBIF representative rows=0; database SHA-256 unchanged.",
    "git diff --check passed; NO_STAGED_FILES."
  ],
  "residualRisks": [
    "No physical-browser responsive, zoom, forced-colors, or real-image-loading session was performed.",
    "No NVDA, JAWS, VoiceOver, or other assistive-technology session was performed; jsdom cannot prove announcement timing or absence of duplicate speech.",
    "Provider-hosted image availability/content and visual subject quality can change because image binaries are intentionally not stored."
  ],
  "noStagedFiles": true,
  "diffSummary": "Reviewed the iNaturalist-only frontend contract and presentation changes across catalog/profile, Field Map, and new/saved Trip Planner: shared strict validation, typed-unavailable handling, Rufous placeholders, retained attribution/source/license, and load-failure status semantics. No repository files were edited by this reviewer.",
  "reviewFindings": [
    "no blockers",
    "no significant findings",
    "no minor findings",
    "note: repository-root plan.md and progress.md were absent",
    "residual: physical-browser and assistive-technology behavior remains unverified"
  ],
  "manualNotes": "Verdict: pass. The requested invalid-unavailable failure is independently resolved against the current 622-available/84-placeholder database state."
}
```
