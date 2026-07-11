Status: active
Created: 2026-07-11
Updated: 2026-07-11

# Trip Planner eBird evidence eligibility

## Context

Aggregate privacy review found that the preserved Trip Planner's eBird evidence view admitted private, invalid, and unreviewed observations. Forty private and twenty-six invalid or unreviewed eBird evidence rows were already persisted in saved plans. Recommendations were ranked from those rows, so row-only redaction would leave misleading derived artifacts.

## Decision

- Trip Planner eBird evidence MUST be valid, reviewed, and non-private before ranking, model grounding, persistence, or API exposure.
- Defense in depth MUST enforce eligibility in the modeled planner view and the Python lookup boundary.
- Any saved plan containing an ineligible eBird evidence source record is tainted. The complete plan aggregate MUST be deleted atomically, including recommendations, evidence, media metadata, traces, and plan row.
- Remediation MUST be explicit, idempotent, offline, single-writer, and fail closed. It MUST identify rows by authoritative modeled source record identity, not by parsing arbitrary payload text.
- No plan is rebuilt automatically; rebuilding would require new model/media network side effects and would not preserve the original artifact.

## Alternatives considered

- Public-only filtering was rejected because invalid/unreviewed evidence is unsuitable for grounded planning.
- Deleting only evidence was rejected because derived recommendations could remain influenced by prohibited rows.
- Automatic rebuild was rejected because it introduces unrequested live model/media calls and a semantically new artifact.

## Consequences

Current affected saved plans will be permanently removed. Future planner results use a smaller, stronger evidence set. Production SQLMesh and runtime remediation require explicit verification and evidence before aggregate closure.
