Status: recorded
Created: 2026-09-09
Updated: 2026-09-09

# Failed-drill marker reconciliation hardening

The `cleanup-marker` path now accepts only exact generated marker names matching `^databox_recovery_drill_[a-z0-9]{12,16}$`. Before mutation it queries PostgreSQL system catalogs and requires exactly one relation with namespace `public`, ordinary-table relkind `r`, and owner `polaris`. Missing, duplicate, wrong-namespace, wrong-type, and wrong-owner results refuse cleanup. The accepted path issues only the exact quoted `DROP TABLE public."<marker>";` without `IF EXISTS`, followed by the existing synchronous fresh-session cleanup WAL archive.

Focused tests cover short, long, and underscore-containing suffix refusal; absent and malformed relation identity; exact quoted DROP; and absence of broader deletion. No live cleanup or other live operation occurred in this repair. `uv.lock` remained unstaged and untouched by this work.
