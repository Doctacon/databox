Status: recorded
Created: 2026-07-09
Updated: 2026-07-09
Target: .10x/tickets/done/2026-07-09-improve-species-and-weather-presentation.md
Verdict: pass

# Species and weather presentation review

## Target

Implementation and evidence for `.10x/specs/trip-plan-result-presentation.md`.

## Findings

### Passed — taxonomy conformance and cardinality

The SQLMesh planner view strips authority text to a binomial key, prefers one eBird-first dimension row, preserves source identifiers, and prevents dimension duplicates from multiplying occurrences. SQLMesh fixtures cover Western Bluebird, Gila Woodpecker, Northern Saw-whet Owl, parenthesized/unparenthesized authorities, and a duplicate dimension candidate. Recommendation aggregation collapses repeated occurrences by species.

### Resolved significant — raw GBIF name dropped at planner boundary

Initial review found `source_scientific_name` existed in the SQLMesh view but was omitted from the planner projection, contradicting source-provenance requirements. The repair selects it, stores source/accepted/conformed names in persisted evidence summary/payload, and reloads them unchanged through the API while recommendations continue displaying conformed common/scientific names. A POST → actual planner query → persistence → GET regression proves all three name forms.

### Passed — deterministic weather presentation

Weather uses only persisted `forecast_summary` and elevation data. Bounded WMO labels and deterministic conversions correctly render Fahrenheit/Celsius, mph/km/h, inches/mm, and feet/meters. Full and partial/null states are tested; status and caveats remain visible but secondary. No browser forecast fetch or model-derived weather path exists.

## Verdict

Pass. No blocker remains.

## Residual risk

Authority-free matching intentionally targets binomial species names and excludes broader hybrid/subgenus taxonomy. WMO labels remain a bounded deterministic set. These are explicit specification limits.
