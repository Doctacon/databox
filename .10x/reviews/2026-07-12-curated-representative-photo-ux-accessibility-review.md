Status: recorded
Created: 2026-07-12
Updated: 2026-07-12
Target: `.10x/tickets/done/2026-07-11-verify-curated-representative-photos.md`, frontend curated representative-photo implementation and tests
Verdict: fail

# Curated representative-photo UX and accessibility review

## Review

### Correct

- **Catalog and profile curated-or-placeholder behavior is coherent.** `app/src/BirdPages.tsx:100-136` renders a lazy curated image when the already-strict `birdApi` contract succeeds, otherwise renders the Rufous placeholder with an accessible “No licensed photo available for …” name. A later image error swaps to the same placeholder, exposes a `role="status"` error, and retains creator, provider source, license, selection reason, and lookup metadata. Tests exercise available, unavailable, and load-failure states in `app/src/BirdPages.test.tsx:298-312,348-381`.
- **Catalog malformed data fails closed before rendering.** `app/src/birdApi.ts:55-137` uses exact keys and validates provider, source-record identity, provider hosts/path grammar, Creative Commons code/URL agreement, creator, original dimensions, and species identity. `app/src/BirdPages.test.tsx:597-636` challenges wrong identity, host, query, record ID, provider, dimensions, license, type, date, and extra fields.
- **Field Map reuses the validated catalog photo contract.** `app/src/mapApi.ts:76-116` validates each map photo with `validateCatalogPhoto`, enforces exact encounter-species cardinality, and rejects unrelated, duplicate, or malformed media. `app/src/FieldMap.tsx:78-90` gives available thumbnails bird-name alt text and hides decorative Rufous artwork from assistive technology. Hover and focus previews are independent, and encounter rows remain native buttons (`app/src/FieldMap.tsx:114-169,305-306`; `app/src/FieldMap.test.tsx:153-187`).
- **Trip Planner uses one presentation path for newly created and saved plans.** Both `createPlan` and `getPlan` results pass through the plan-detail validator before `PhotoArea` renders them, so new and migrated saved plans receive the same lazy image, alt text, attribution, loading-failure, and unavailable treatment (`app/src/App.tsx:162-213,329-358,615-663`). Available iNaturalist rendering and image failure retention are covered in `app/src/App.test.tsx:174-212,442-478`.
- **Alt text is meaningful and placeholders are not exposed as duplicate artwork.** Catalog/profile/planner images identify common and scientific names where both exist; Field Map thumbnails identify the visible bird name. Rufous artwork in catalog and map placeholders is decorative (`alt=""`, `aria-hidden="true"`), while catalog placeholder state itself receives an accessible name.
- **Loading and top-level error states are generally semantic.** Catalog, profile, Field Map, and planner use `role="status"`, `role="alert"`, and/or `aria-busy` for fetch and validation states (`app/src/BirdPages.tsx:331-337,517-520`; `app/src/FieldMap.tsx:292-296`; `app/src/App.tsx:655-660`). Strict-response rejection prevents partial catalog/profile/map/planner rendering for many malformed cases.
- **Keyboard foundations are preserved.** The catalog wheel is a focusable listbox with `aria-activedescendant`, selected options, Arrow/Page/Home/End handling, and reduced-motion scrolling (`app/src/BirdPages.tsx:279-321,338-344`). Field Map rows are native buttons and expose persistent selection through `aria-pressed`. Source and license destinations elsewhere are native links.

### Significant findings — closure blocking

1. **Trip Planner does not show the required Rufous placeholder for unavailable curated photos.** The active spec says source exhaustion “MUST show the Rufous placeholder.” `PhotoArea` renders only a patterned text `<div>` containing “No licensed photo is available” (`app/src/App.tsx:183-190`), for both new and saved plans. The existing test explicitly asserts that weaker state (`app/src/App.test.tsx:191-194`), so the test currently codifies the spec drift rather than detecting it. Catalog/profile and Field Map do use Rufous, demonstrating the intended reusable behavior. This blocks the active-spec curated-or-placeholder acceptance scenario.

2. **Trip Planner’s browser validator can accept and activate mismatched Wikimedia metadata.** `curatedPhotoMatches` only checks that the display pathname contains `/wikipedia/commons/thumb/` and that the source pathname starts with `/wiki/File:`; it does not bind either file path to the `Q…|File:…` source record, validate the canonical thumbnail width, or apply the stronger file-title grammar used by the catalog validator (`app/src/tripPlanValidation.ts:276-299`, compared with `app/src/birdApi.ts:91-114`). `safeCuratedPhotoUrls` repeats the same loose conditions at presentation time (`app/src/App.tsx:122-148`). Consequently, an approved-host response whose source record names one file while both URLs name another can pass validation and become active. This violates the active spec’s requirement that planner GET/browser contracts reject provider/URL/identity mismatches. Frontend fixtures and malformed-photo tests cover only iNaturalist (`app/src/App.test.tsx:19-27,460-478`), leaving this path untested.

3. **Field Map omits canonical source and license destinations from its visible attribution.** `EncounterThumbnail` displays creator, license code, and provider as plain text, before and after failure, but never renders `photo.source_url` or `photo.license_url` (`app/src/FieldMap.tsx:78-90`). The shared curated-photo spec requires provider attribution, source, and license to remain visible when browser image loading fails. Catalog/profile/planner expose source and license as links; the map is the lone surface where a user cannot inspect either canonical destination. `app/src/FieldMap.test.tsx:180-187` verifies only the plain-text creator/code/provider string, so it cannot establish the aggregate evidence claim that safe links/source attribution are retained across all surfaces.

### Minor finding

- **Planner and Field Map image-load failures are not explicitly announced.** Catalog uses `role="status"` for “Photo could not be loaded,” but the planner swaps ordinary text inside `.media-placeholder` and Field Map mutates ordinary `<small>` text (`app/src/App.tsx:183-190`; `app/src/FieldMap.tsx:84-89`). A focused screen reader is not guaranteed to announce either asynchronous update. Preserve the existing visible state while exposing the failure through a restrained status announcement; do not make persistent attribution a noisy live region.

### Notes and residual risks

- The requested repository-root `plan.md` and `progress.md` do not exist; direct reads returned `ENOENT`, and a repository search found neither file. This review therefore used the active specification, parent/verification tickets, three done child tickets, aggregate evidence, child evidence/reviews, frontend source/tests, and the working diff.
- The aggregate evidence reports 769 Python tests, 273 frontend tests, strict TypeScript, production build, static checks, and an empty cached diff. This reviewer inspected those records and relevant tests/diff but did not independently rerun the suites.
- jsdom proves DOM structure, labels, attributes, event handlers, and validator outcomes; it does **not** prove real image loading, visual crop/subject quality, rendered attribution wrapping, contrast over actual browser rasterization, scroll centering, or announcement behavior.
- CSS-string assertions are not a physical 320 px viewport test. A browser pass should inspect catalog wheel/profile, dense Field Map rows, and planner cards with long creator/file/license text at narrow and zoomed layouts.
- The listbox/`aria-activedescendant` wheel needs physical keyboard plus NVDA/JAWS/VoiceOver verification for option announcements and scroll synchronization. Field Map needs keyboard, forced-colors, and screen-reader testing with real MapLibre controls. The image-failure status behavior should be verified with assistive technology after repair.
- Provider-hosted images can disappear after metadata validation. The UI deliberately retains metadata rather than binaries; visual subject suitability remains provider-curation quality, not something automated tests establish.

## Verdict

**Fail.** No critical security blocker was found, but the three significant findings are direct active-spec or strict-contract gaps and block aggregate closure. The change should be repaired and the focused frontend tests plus full frontend gates rerun before this review can pass.

```acceptance-report
{
  "criteriaSatisfied": [
    {
      "id": "criterion-1",
      "status": "satisfied",
      "evidence": "Review-only task stayed within the curated representative-photo frontend UX/accessibility surface; no repository files were edited."
    },
    {
      "id": "criterion-2",
      "status": "satisfied",
      "evidence": "Record-ready review cites the active spec, aggregate/child evidence, implementation and test line ranges, three closure-blocking findings, one minor finding, verdict, and jsdom/manual residual risks."
    }
  ],
  "changedFiles": [
    "app/src/App.tsx",
    "app/src/BirdPages.tsx",
    "app/src/FieldMap.tsx",
    "app/src/birdApi.ts",
    "app/src/mapApi.ts",
    "app/src/tripPlanValidation.ts",
    "app/src/types.ts"
  ],
  "testsAddedOrUpdated": [
    "app/src/App.test.tsx",
    "app/src/BirdPages.test.tsx",
    "app/src/FieldMap.test.tsx",
    "app/src/tripPlanValidation.test.ts"
  ],
  "commandsRun": [
    {
      "command": "git status --short && git diff --stat && git diff --cached --stat",
      "result": "passed",
      "summary": "Inspected working-tree scope; cached diff was empty."
    },
    {
      "command": "git diff -- app/src/BirdPages.tsx app/src/BirdPages.test.tsx app/src/FieldMap.tsx app/src/FieldMap.test.tsx app/src/App.tsx app/src/App.test.tsx app/src/tripPlanValidation.ts app/src/tripPlanValidation.test.ts app/src/types.ts app/src/birdApi.ts",
      "result": "passed",
      "summary": "Inspected the relevant frontend implementation and test diff."
    }
  ],
  "validationOutput": [
    "Independent static review found Trip Planner lacks the required Rufous unavailable placeholder.",
    "Independent static review found Trip Planner Wikimedia URL/file identity validation weaker than the active strict contract.",
    "Independent static review found Field Map omits canonical source and license destinations.",
    "Aggregate evidence inspected: 769 Python tests and 273 frontend tests reported passing, but suites were not independently rerun by this reviewer."
  ],
  "residualRisks": [
    "No physical-browser visual or responsive-device run was performed.",
    "No NVDA, JAWS, VoiceOver, or other assistive-technology session was performed.",
    "jsdom cannot establish image availability, visual crop quality, layout wrapping, real scroll behavior, contrast rasterization, or live-region announcements.",
    "Provider-hosted image availability and provider-curated subject quality can change after persistence."
  ],
  "noStagedFiles": true,
  "diffSummary": "Reviewed curated provider/type validation and presentation changes across catalog/profile, Field Map, and Trip Planner plus associated frontend tests; reviewer made no repository edits.",
  "reviewFindings": [
    "significant: app/src/App.tsx:183-190 - unavailable new/saved Trip Planner photos render text only instead of the required Rufous placeholder",
    "significant: app/src/tripPlanValidation.ts:276-299 and app/src/App.tsx:122-148 - mismatched Wikimedia file/source metadata can pass browser validation and activate",
    "significant: app/src/FieldMap.tsx:78-90 - Field Map omits canonical source and license destinations, including after load failure",
    "minor: app/src/App.tsx:183-190 and app/src/FieldMap.tsx:84-89 - asynchronous image failures lack an explicit restrained status announcement"
  ],
  "manualNotes": "Verdict: fail. Root plan.md and progress.md were absent. Aggregate test results were inspected from evidence rather than rerun."
}
```
