Status: recorded
Created: 2026-07-09
Updated: 2026-07-09
Target: .10x/tickets/done/2026-07-09-add-inline-xeno-canto-audio.md
Verdict: pass

# Xeno-canto inline audio review

## Target

Implementation and evidence for `.10x/specs/xeno-canto-inline-audio.md`.

## Findings

### Passed — native playback and attribution

The result view uses native `<audio controls preload="none">` without autoplay. Species/type/quality context, recordist attribution, readable license, source link, and runtime failure fallback remain visible. No proxy, download, cache, stored audio, custom engine, waveform, secret, or audio artifact was introduced.

### Resolved significant — inconsistent recording identifiers

Initial review found the backend could prefer a payload ID over a conflicting row ID and the frontend did not compare source/audio IDs. The repair gathers row/summary/payload identifiers, accepts only exact numeric or uppercase `XC`-numeric forms, rejects conflicts, exposes one canonical typed ID, and requires each exact URL ID to match it. React independently enforces the same canonical-ID relation.

### Resolved significant — source fallback coupling and traversal normalization

First repair coupled source/audio availability, hiding a valid source link when audio was missing, and React validated after WHATWG path normalization. Final repair validates source and audio independently against canonical identity, preserving each safe target on failure of the other. React now uses anchored raw full-string grammars before normalization, rejecting literal and percent-encoded traversal, credentials, ports, queries, fragments, subdomains, and unexpected paths.

### Passed — adversarial coverage

Independent final review directly probed conflicting IDs, equivalent `XC`/zero-padded IDs, page/audio cross-mismatch, malformed identifiers, missing/invalid audio with valid source, invalid source with valid audio, and raw/encoded traversal. All fail-closed and fallback behaviors matched the active specification.

## Verdict

Pass. No blocker remains.

## Residual risk

Playback depends on browser and Xeno-canto availability/CORS. Exact host/path allowlists intentionally fail closed if upstream changes. No audio bytes are stored.
