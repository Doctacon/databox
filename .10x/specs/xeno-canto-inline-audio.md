Status: active
Created: 2026-07-09
Updated: 2026-07-09

# Xeno-canto Inline Audio Playback

## Purpose and scope

This specification governs in-app playback of Xeno-canto call examples without downloading or storing audio in Databox.

## Playback behavior

- Each available Xeno-canto media example SHOULD render an accessible native HTML audio player with play/pause, seek, and volume controls.
- Audio MUST stream from the persisted Xeno-canto `audio_file_url`; Databox MUST NOT copy, cache, bulk-download, or persist audio bytes.
- Players MUST use `preload="none"` so opening a plan does not fetch every recording.
- The source recording page MUST remain available as a separate safe link.
- The recording's common name, recording type, quality, recordist attribution, and license MUST remain visible.
- Raw license URLs SHOULD be rendered as readable safe links rather than unformatted text.

## URL safety

- Playback and source links MUST allow only HTTPS Xeno-canto hosts or explicitly ratified Xeno-canto-controlled media hosts.
- The direct Xeno-canto `/{recording_id}/download` URL is currently evidenced to return `audio/mpeg` with permissive CORS and MAY be streamed directly.
- Unsafe schemes, unexpected hosts, malformed URLs, unavailable evidence sentinels, and missing audio URLs MUST never become active player sources.
- When direct playback is unavailable, the UI MUST show a clear unavailable message and retain the safe source-page link when present.

## Accessibility

- Native controls MUST remain keyboard focusable and expose browser-provided accessible names/semantics.
- Each player MUST have nearby text identifying the species and recording type.
- Playback MUST not autoplay.
- A failed audio load MUST not remove attribution or license information.

## Acceptance scenarios

### Play in app

Given an available evidence row with source page `https://xeno-canto.org/145961` and audio URL `https://xeno-canto.org/145961/download`, when the plan is shown, then a native non-autoplaying audio player can stream the MP3 inside the app and a separate source link remains available.

### No eager downloads

Given multiple media examples, when the plan page opens and the user has not pressed play, then each player uses `preload="none"` and Databox stores no audio bytes.

### Unsafe media URL

Given a `javascript:` URL or unexpected host in persisted evidence, when the plan is rendered, then no active audio source or unsafe link is created.

## Explicit exclusions

- No local audio storage, offline audio cache, waveform generation, transcoding, or bulk download.
- No custom JavaScript audio engine when native controls satisfy the requirement.
- No autoplay.
- No removal of source attribution or licensing.
