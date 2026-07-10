Status: recorded
Created: 2026-07-09
Updated: 2026-07-09
Relates-To: .10x/tickets/done/2026-07-09-integrate-media-into-recommendation-cards.md, .10x/specs/recommendation-card-media-layout.md

# Recommendation card media layout evidence

## What was observed

The React result view now renders persisted recommendation-centric `photo` and `call` objects inside the owning recommendation card. The legacy top-level media list is not consulted and the standalone Call and Media Examples section is absent.

After the hero and optional caveat notice, panel headings are exactly:

1. Field Plan
2. Weather and Elevation
3. High-likelihood Species
4. Uncommon but Plausible Targets
5. Evidence and Provenance

Evidence remains visible in the final section. Agent Workflow is a native `<details><summary>` disclosure inside that same final section.

## Media behavior exercised

`app/src/App.test.tsx` verifies:

- available and unavailable photo/call areas coexist without removing or reordering recommendations,
- nested photo/call values are treated as untrusted: null, missing, primitive, array, wrong-field, and malformed-caveat inputs fail only that medium to a placeholder without throwing or hiding the other medium/card,
- media species identity must match the owning recommendation's authority-free binomial; when scientific identity is absent, only an exact common-name match is accepted,
- a different-species photo renders only its unavailable placeholder and one generic photo mismatch caveat; creator, rights holder, publisher, license, source link, original caveats, and species-derived media labels are absent while the owning card remains,
- Xeno calls require canonical numeric/XC `source_record_id`, typed recording ID, source URL ID, and audio URL ID to agree,
- a different-species or cross-ID call renders only its unavailable placeholder and one generic call mismatch caveat; scope, type, quality, recordist, license, source link, original caveats, and audio labels are absent while the owning card remains,
- media is read only from each recommendation object and remains attached by `recommendation_id`, even when the obsolete top-level media list contains conflicting data,
- photo URLs require the exact GBIF 500x500 cache grammar and occurrence-ID relation,
- photo source URLs require the exact GBIF occurrence path,
- images use `loading="lazy"`, accurate common/scientific alt text, the responsive class/frame, and no fixed width/height attributes,
- creator, rights holder, publisher, license, and source remain visible after image load failure,
- malformed photo URLs fail to the visible photo placeholder without affecting the call,
- native audio has controls, `preload="none"`, no autoplay, and canonical recording-ID/source/audio relationships,
- `Arizona recording` and `Global example` labels render from the persisted call scope,
- type, quality, recordist, license, and source remain visible after playback failure,
- malformed call URLs fail to the visible call placeholder without affecting the photo,
- active media requires a nonempty license label exactly matching the code/version derived from the finite safe license URL; missing/mismatched labels fail closed, CC0 is covered, and readable attribution remains,
- Creative Commons links use a finite browser-side allowlist, with ND variants permitted only for unchanged audio,
- the standalone media section is absent,
- the exact final section order and native workflow disclosure semantics are present,
- evidence rows remain visible before the workflow disclosure is opened.

The responsive implementation uses a bounded 4:3 `.photo-frame`, width/height 100% `.responsive-bird-photo` with `object-fit: cover`, full-width native audio, wrapping card grids, and the existing mobile breakpoints without fixed media dimensions. Grid, card, photo, call, and metadata children explicitly use `min-width: 0`; metadata/link children use `overflow-wrap: anywhere` and `word-break: break-word`. A long unbroken attribution fixture asserts the applied DOM classes and computed rules.

## Commands and results

```text
cd app && npm run typecheck && npm test -- --run && npm run build
TypeScript passed; 50 tests passed; 30-module production build passed.

task app:audit-bundle
3 configuration names and 3 configured values absent.

task ci
242 tests passed; 83.90% coverage; Ruff, formatting, MyPy, secret, generated-staging, and platform-health checks passed.

task docs:build
Strict documentation build passed.

uv run --no-sync pre-commit run --all-files
All configured hooks passed.
```

## What this supports

- Every rendered recommendation card has one independent photo area and one independent call area.
- Available media retains complete attribution; load failures do not erase attribution.
- Malformed browser-facing media fails closed without changing recommendation facts.
- Identity-mismatched media cannot visually attach semantic metadata or attribution from another species/recording; identity-consistent media retains attribution after simulated binary load failure.
- Recommendation-centric attachment replaces the obsolete standalone display.
- Result order, evidence visibility, and workflow accessibility match the active specification.
- Browser assets remain free of Cloudflare and discovery credentials/configuration.

## Limits

- Browser tests simulate image/audio error events; they do not download remote media bytes.
- CSS responsiveness is verified through bounded classes/attributes and existing breakpoint rules rather than screenshot-based visual regression.
- The stable API still includes the legacy top-level `media` field for compatibility, so its TypeScript type remains even though this UI no longer renders it.
