Status: active
Created: 2026-07-11
Updated: 2026-07-11

# Structured personal observation locations

## Purpose

Extend private observation events with optional explicit place selection while preserving legacy/free-text logging.

## Storage

Keep existing trimmed nullable `location` display/free-text field. Add nullable:

- `location_source`: `ebird_hotspot` or `open_meteo`;
- `location_source_id` bounded nonblank text;
- `location_latitude`, `location_longitude` finite governed Arizona coordinates;
- `location_timezone`: exactly `America/Phoenix`;
- `location_region_code`: exactly `US-AZ`.

Structured fields are all-or-none. When present, `location` MUST equal the selected canonical display name. When absent, `location` remains optional private free text. Migration is idempotent, preserves every current row, and adds no inferred values.

## API and browser

Observation create/edit accepts either:

- `location_selection` with the exact strict suggestion object and matching `location`; or
- free-text `location` with no selection.

Editing selected text in the combobox clears selection and saves free text unless another suggestion is selected. Existing structured observations initialize the combobox selection; legacy rows initialize free text. Observation reads return structured fields only through private observation/life-list-related collection surfaces; they MUST NOT enter catalog, Field Map, public evidence, logs, traces, fixtures, or model prompts.

Deletion and derived life-list behavior are unchanged. No save-time/background geocoding, reverse geocoding, remote sync, or automatic location correction.

## Acceptance scenarios

- Selecting Watson Lake stores its exact hotspot ID/name/coordinates/timezone/region.
- Typing `Back yard` without selection stores only free text.
- Editing selected text clears structured identity atomically.
- Partial/mismatched/out-of-bounds/source-invalid structured inputs rollback.
- Legacy observation migration preserves its original location and null structured fields.
