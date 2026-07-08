Status: active
Created: 2026-07-07
Updated: 2026-07-07

# Databox 10x Records

This directory is the durable project-memory home for Databox.

Use focused records under:

- `decisions/` — active architectural decisions; superseded decisions move to `decisions/superseded/`.
- `research/` — investigations and source material; bulky/source artifacts go in `research/.storage/`.
- `specs/` — active behavioral contracts; superseded specs move to `specs/superseded/`.
- `tickets/` — active work; completed work moves to `tickets/done/`, cancelled work to `tickets/cancelled/`.
- `evidence/` — reproducible observations and verification notes; bulky artifacts go in `evidence/.storage/`.
- `reviews/` — adversarial reviews of changes or records.
- `knowledge/` — reusable project conventions and vocabulary.
- `skills/` — source 10x skills as `.10x/skills/<skill-slug>/SKILL.md`.

Existing `docs/adr/`, logs, and external artifacts may remain canonical, but durable 10x-relevant state should be indexed here when it becomes active project memory.
