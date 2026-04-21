---
id: ticket:ebird-observations-submission-id-contract
kind: ticket
status: closed
created_at: 2026-04-21T00:00:00Z
updated_at: 2026-04-21T16:15:00Z
scope:
  kind: workspace
links:
  initiative: initiative:scaffold-polish
---

# Goal

Remove the `No duplicate values` check on `submission_id` in `soda/contracts/ebird_staging/stg_ebird_observations.yaml`. The column is an eBird checklist ID — one checklist contains many species observations — so it is not unique at the observation grain.

# Why

Full-refresh log shows 103 duplicate submission_ids in a 4483-row dataset (2.29%). This is expected eBird semantics, not a data quality bug. The contract encodes the wrong invariant.

A correct observation-grain uniqueness check would be on the tuple `(submission_id, species_code)` — one species per observation per checklist. That is not currently expressible in Soda Core's single-column `duplicate` check. Drop the bad check; optionally add a dataset-level composite-key check in a follow-up if Soda supports it.

# In Scope

- Edit `soda/contracts/ebird_staging/stg_ebird_observations.yaml`: remove `duplicate: { must_be: 0 }` from the `submission_id` column.
- Keep `missing: { must_be: 0 }` on `submission_id`.
- No changes to staging SQL or dlt source.

# Out of Scope

- Adding composite-key uniqueness. If Soda Core supports it cleanly, open a separate ticket.
- Auditing other contracts for similar ID-vs-grain confusion.

# Acceptance

- Contract edit lands.
- `task verify` / `task full-refresh` log shows zero `submission_id No duplicate values … FAILED` lines.

# Close Notes — 2026-04-21

Removed `duplicate: { must_be: 0 }` from `submission_id` column in `soda/contracts/ebird_staging/stg_ebird_observations.yaml`. Kept `missing: { must_be: 0 }`.

Verified: `.logs/verify-20260421-161451.log` — no `submission_id` FAILED lines. Zero Soda contract failures overall.

Composite-key check `(submission_id, species_code)` not added — Soda Core single-column `duplicate` does not support it directly. If a composite check is needed later, revisit via Soda `checks:` custom SQL expression or a dataset-level assertion.
