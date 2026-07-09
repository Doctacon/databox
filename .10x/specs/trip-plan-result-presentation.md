Status: active
Created: 2026-07-09
Updated: 2026-07-09

# Trip Plan Result Presentation

## Purpose and scope

This specification governs species naming and weather/elevation presentation in the local Birding Trip Copilot result view.

## Species names

- Recommendation cards MUST show a common English name as the primary heading when the conformed taxonomy contains one.
- The scientific name MUST appear directly below the common name in smaller secondary styling.
- Scientific-name-only display is permitted only when no common name exists in the conformed species dimension.
- GBIF-only uncommon recommendations MUST use authority-free scientific-name conformance to recover the eBird common name and species code where available.
- Taxonomic authorities such as `Swainson, 1832` or `(J.F.Gmelin, 1788)` MUST NOT prevent a match to an authority-free eBird scientific name.
- The implementation MUST avoid duplicate conformance joins and MUST retain source evidence/provenance.

## Weather and elevation

- Source status MUST be a secondary health indicator, not the primary weather result.
- For the selected trip window, the app MUST show available:
  - minimum and maximum temperature,
  - average humidity,
  - maximum precipitation probability and precipitation total,
  - maximum sustained wind and gust speed,
  - a human-readable condition summary derived from persisted WMO weather codes,
  - elevation.
- The UI MUST display both US customary and metric units:
  - Fahrenheit and Celsius,
  - miles per hour and kilometers per hour,
  - inches and millimeters where precipitation is nonzero or relevant,
  - feet and meters.
- Conversions MUST be deterministic application code over the persisted Open-Meteo values; the model MUST NOT invent or convert measurements.
- Values MUST be rounded for field use while preserving the original persisted payload unchanged.
- Partial or unavailable fields MUST be labeled individually; one missing field MUST NOT hide available weather context.
- Weather caveats MUST remain visible.

## Acceptance scenarios

### Conformed uncommon species

Given a GBIF occurrence for `Sialia mexicana Swainson, 1832` and eBird taxonomy for `Sialia mexicana`, when recommendations are presented, then the card heading is `Western Bluebird` and `Sialia mexicana` appears below in smaller scientific styling.

Equivalent authority-free matching MUST support examples such as `Melanerpes uropygialis` → `Gila Woodpecker` and `Aegolius acadicus` → `Northern Saw-whet Owl` when present in the conformed taxonomy.

### Useful weather summary

Given persisted forecast values, when the result loads, then the user sees actual condition, temperature, humidity, precipitation, wind/gust, and elevation values in both unit systems rather than only `status: available`.

### Partial weather

Given elevation is available but forecast rows are unavailable, when the result loads, then elevation is shown, forecast fields are marked unavailable, and the source caveat remains visible.

## Explicit exclusions

- No model-generated weather prose or measurements.
- No replacement of persisted source evidence with transient browser data.
- No user preference/account system for units in this version.
- No global taxonomy expansion beyond available conformed sources.
