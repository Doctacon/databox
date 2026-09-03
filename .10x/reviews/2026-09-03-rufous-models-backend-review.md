Status: recorded
Created: 2026-09-03
Updated: 2026-09-03
Target: .10x/tickets/done/2026-09-03-migrate-rufous-models-and-backend.md
Verdict: pass

# Rufous models and backend review

## Findings

No unresolved in-scope finding remains. Rufous pins the public `databox-sources` package through the GitHub repository at immutable revision `572ca6191f598e323161cdadeec3898f10913d31`. Read-only artifact input, writable application state, and SQLMesh state use separate paths. Product SQL reads the v1 artifact contract; only Rufous-owned iNaturalist state remains local. No private `databox.*` import remains.

The USFWS job is manual and unscheduled and retains modeled targets, request bounds, current-run filtering, and fail-closed verification. Eleven product-owned SQLMesh tests are the complete moved set; seven environmental/analytics tests remain correctly owned by Databox.

Five unchanged public-workflow tests remain failing because they assert Databox paths and workflow names. They are within the explicit web/deployment exclusion and are durably owned by `.10x/tickets/done/2026-09-03-migrate-rufous-web-public-deployment.md`; they were not skipped or weakened.

## Residual risk

Full destination aggregate remains red only for those five owned workflow assertions until the next ticket executes. Production remains disabled.

## Verdict

Pass for this bounded model/backend slice.
