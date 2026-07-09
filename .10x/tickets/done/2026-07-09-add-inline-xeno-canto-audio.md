Status: done
Created: 2026-07-09
Updated: 2026-07-09
Parent: .10x/tickets/done/2026-07-09-improve-trip-planner-location-and-results.md
Depends-On: .10x/tickets/done/2026-07-09-improve-species-and-weather-presentation.md

# Add inline Xeno-canto audio

## Scope

Implement `.10x/specs/xeno-canto-inline-audio.md` in the persisted API contract and React result view.

Required work:

- expose the already-persisted `audio_file_url` through the stable typed media response,
- validate source-page and audio URLs independently against HTTPS Xeno-canto hosts and expected download paths,
- render native `<audio controls preload="none">` players for valid available evidence,
- retain a separate safe recording source-page link,
- render readable recordist and license attribution,
- preserve a safe fallback when audio is missing or fails,
- add tests proving no autoplay/eager preload, unsafe URL rejection, unavailable sentinel handling, attribution, and source-link preservation,
- audit the browser bundle and repository for secrets and accidental audio artifacts.

## Explicit exclusions

- No audio download, storage, caching, proxying, waveform generation, or transcoding.
- No custom JavaScript audio engine.
- No autoplay.
- No unapproved media hosts.
- No removal of source attribution or licenses.

## Acceptance criteria

- A valid persisted Xeno-canto `/download` MP3 can play inside the app through native controls.
- Opening a plan does not eagerly fetch or store every audio file.
- Each playable item retains species/recording context, recordist, readable license, and source-page link.
- Unsafe schemes/hosts never become player or link targets.
- Missing/failed playback remains user-safe and does not hide attribution.
- Frontend typecheck/tests/build, API contract tests, bundle/audio-artifact audits, CI, docs, and independent review pass.

## Evidence expectations

Record safe HTTP content-type/CORS evidence, rendered native-control assertions, URL-safety tests, no-audio-storage audit, exact commands/results, and independent review.

## Progress and notes

- 2026-07-09: Execution started after the location and species/weather child tickets completed.
- 2026-07-09: Added a stable typed media response that independently validates persisted source/audio URLs against exact HTTPS Xeno-canto hosts, numeric recording IDs, expected paths, and no credentials/ports/query/fragment. Safe Creative Commons license links are normalized to readable labels; unsafe links fail closed.
- 2026-07-09: Added native accessible React audio controls with `preload="none"`, no autoplay, species/recording/quality context, recordist/license attribution, separate source links, and missing/failed playback fallbacks.
- 2026-07-09: Added API and React regressions for safe URLs, source/audio independence, credentials, ports, subdomains, paths, malformed/sentinel/missing-ID/mismatched-ID values, unsafe licenses, player attributes, fallback, and attribution retention.
- 2026-07-09: Live header-only evidence confirmed `https://xeno-canto.org/145961/download` returns HTTP 200, `audio/mpeg`, and permissive CORS. No audio body was stored.
- 2026-07-09: Final validation passed: 15 API tests; strict TypeScript, 20 React tests, build and bundle audit; full CI with 212 tests at 82.77% coverage; strict docs; pre-commit; diff check; no tracked or relevant untracked audio artifacts; no staged files.
- 2026-07-09: Evidence recorded in `.10x/evidence/2026-07-09-xeno-canto-inline-audio.md`.
- 2026-07-09: Independent review found two significant fail-closed gaps: the backend preferred one persisted recording identifier instead of rejecting conflicts, and the frontend validated source/audio path shapes without comparing their IDs to each other or a canonical typed identifier.
- 2026-07-09: Backend repair now collects row, summary, and payload `source_record_id`/`recording_id` values; accepts only exact numeric or uppercase `XC`-numeric forms; normalizes them to one canonical numeric ID; and returns `recording_id: null` when any supplied identifier is malformed or conflicts. Source/audio URLs are both null unless both exact path IDs equal that canonical ID.
- 2026-07-09: Frontend repair validates canonical typed `recording_id` as an exact canonical numeric string, extracts exact IDs from both safe URLs, and activates neither link/player unless page ID, download ID, and typed ID all agree. Attribution remains visible for malformed typed responses.
- 2026-07-09: Added API adversarial coverage for `XC1` versus payload `2`, consistent numeric/`XC` forms, page/audio cross-mismatch, malformed row/summary/payload/non-string identifiers, duplicate persisted identifier fields, and canonical typed output. Added React coverage for page `1`/audio `2`, URL-versus-typed mismatch, and malformed typed IDs.
- 2026-07-09: Repair validation passed Ruff, format, MyPy, all 16 API tests, strict TypeScript, 23 React/weather tests, production build, bundle audit, diff check, and no-staged-files check.
- 2026-07-09: Independent re-review found two remaining closure blockers: the first repair incorrectly coupled source/audio availability, and frontend validation used WHATWG-normalized paths rather than rejecting raw/encoded traversal first.
- 2026-07-09: Backend now validates source and audio independently against the preserved canonical persisted recording ID. Valid source fallback survives missing/invalid/unavailable/mismatched audio; valid canonical audio survives independently invalid source. Canonical identifier conflicts still disable both.
- 2026-07-09: Frontend now uses an anchored raw full-string Xeno-canto grammar before any URL normalization, rejects raw `/1/../2` and encoded `/1/%2e%2e/2`, and compares each extracted exact ID independently to typed canonical `recording_id`.
- 2026-07-09: Added API independent-output regressions and React cases for raw/encoded traversal, missing audio with valid source, invalid/mismatched audio with valid source, and invalid source with valid audio. Final focused validation passed Ruff, format, MyPy, 16 API tests, strict TypeScript, 27 React/weather tests, build, bundle audit, pre-commit, diff check, and no-staged-files check.
- 2026-07-09: Independent final review passed canonical identity, independent source/audio fallback, raw URL grammar, native-control accessibility, attribution, and no-storage constraints. Review: `.10x/reviews/2026-07-09-xeno-canto-inline-audio-review.md`.
- 2026-07-09: Retrospective: URL shape validation is insufficient without cross-field identity consistency, and safe fallback targets must remain independent. Canonical-ID and raw-grammar adversarial tests preserve both lessons; no separate knowledge or skill record is needed.

## Blockers

None.
