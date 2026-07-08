---
name: create-ontology
description: "Use after annotate-sources to build a business entity graph ontology from annotated DBML sources and taxonomy before Kimball CDM generation."
metadata:
  created: 2026-07-07
  updated: 2026-07-07
---

# Create ontology

Build a formal business entity graph from the confirmed source annotations and taxonomy, ready for Kimball CDM design.

Requires outputs from `annotate-sources`:

- `.schema/<cdm-name>/<pipeline_name>.dbml` — one annotated DBML file per pipeline
- `.schema/<cdm-name>/taxonomy.json`

If either is missing, run `annotate-sources` first.

## Determine the CDM folder

If the user provides a CDM folder name, use `.schema/<cdm-name>/taxonomy.json`.

If not provided:

1. Search for `.schema/*/taxonomy.json`.
2. If exactly one exists, read it and use its `_name` as `<cdm-name>`.
3. If multiple exist, ask the user which CDM to use.
4. If none exist, stop and run `annotate-sources` first.

All files written by this skill live under `.schema/<cdm-name>/`.

## Key concept: natural key

A **natural key** is a column whose value is derived from the real-world domain and is therefore consistent across multiple source systems. For example, `email` appearing in both `contacts` and `event_guests` means a single person can be matched and merged across both sources.

When a concept has a natural key, rows from different source tables that share the same natural key value are treated as the **same entity** — they become one row in the CDM, not two. This determines:

- Which source wins for each attribute when both have a value: the **master source**
- Whether rows that exist in only one source are still included: **union vs. intersection**

## Steps

### 1. Build entity list

Read `.schema/<cdm-name>/taxonomy.json`. For each top-level key that is not prefixed with `_`, e.g. not `_version`, `_name`, or `_excluded`:

- Create one ontology entity per canonical concept
- Name = concept key in PascalCase
- Mark as `inferred: false` because it is grounded in confirmed source mappings

### 2. Confirm natural key handling

Before deriving attributes, inspect every concept with a non-null `natural_key` in `taxonomy.json`.

If no concept has a natural key, record that no cross-source stitching strategy is needed and continue.

For every concept that has a `natural_key`, explicitly ask the user how they want conflicts resolved. Do **not** assume a strategy.

Present the concept with its natural key, contributing sources, and these options:

```text
Person appears in HubSpot (contacts) and Luma (event_guests), linked by email.

When the same person appears in both and their data conflicts, which should we trust?

  A) Prefer whichever source has a value — fall back to the other if blank
     → "Use HubSpot if available, fall back to Luma"
  B) Always use one source, ignore the other entirely
     → "Always use HubSpot, even if a field is blank"
  C) Decide field by field
     → "Use HubSpot for name/phone, Luma for registration date"

Also: what about people who only exist in one source?
  1) Include everyone (recommended)
  2) Only include people present in both sources

Which combination (A/B/C) and (1/2)?
```

Wait for explicit confirmation. Record the chosen strategy in the ontology `assumption` field before proceeding to attribute derivation.

### 3. Derive attributes per entity

**SCOPE CONSTRAINT — no inference beyond source data:** Only include attributes that correspond to actual columns in the annotated DBML/source schemas. Do **not** add computed fields, business metrics, or domain concepts such as `roi`, `is_icp`, `lead_score`, or `lifetime_value` unless a column with that data already exists in one of the source tables. If a useful attribute is missing from the data, record it as a semantic gap in step 5, not as an attribute.

For each entity, collect all columns from **all source tables mapped to that concept** in `taxonomy[concept].tables`.

For each column, include:

- column name
- dlt type from DBML
- source table
- source pipeline
- notes from DBML attributes, e.g. `primary_key`, `not null`, `unique`, `row_key`, `natural_key`

Apply the confirmed natural key strategy from step 2 to flag the **master source** per attribute.

Where the same logical attribute appears in multiple sources under different names, e.g. `phone` in contacts and `phone_number` in guests:

1. Propose a canonical attribute name.
2. Present conflicts to the user and confirm:

```text
Both sources have a phone field for Person, but named differently:
  HubSpot (contacts): phone
  Luma (guests): phone_number

Suggested unified name: phone  |  Primary source: HubSpot (contacts)
OK?
```

Wait for confirmation before proceeding.

If there is no cross-source duplication for an entity, preserve source column names as canonical attribute names unless the user asks for renaming.

### 4. Define relationships

Use two sources of relationships.

#### From natural keys

From `taxonomy.json` → `concept.natural_key`:

- Each natural key defines a union/stitching relationship between source tables of the same concept.
- Record as a `STITCHED_BY` edge with the key column.

#### From structural relationships in annotated DBML

Read `.schema/<cdm-name>/<pipeline_name>.dbml` and look for explicit DBML `Ref` statements, foreign-key notes, and strong structural FK columns, e.g. `company_id` on contacts pointing to a mapped Company entity.

Map inter-entity relationships with UPPER_SNAKE_CASE edge labels, e.g.:

- `BELONGS_TO`
- `ATTENDED`
- `PLACED_BY`
- `LOCATED_AT`
- `OBSERVED_AT`

Do not invent relationships that are not supported by source columns or user confirmation. If a relationship is plausible but not structurally explicit, present it to the user before writing it, and mark `inferred: true` only if the user accepts it as an inferred relationship.

### 5. Flag semantic gaps

Compare the entity list against the user's stated use cases from `taxonomy.json` → `concept.use_cases`.

If a use case requires a concept that has **no contributing source table**:

- Flag it as a semantic gap.
- Record it as an assumption/gap, e.g. `{"gap": "Contract entity needed for billing use case, no source table found"}`.
- Suggest where this data might come from: new pipeline, manual input, or derivation from existing tables if supported by columns.

Present gaps to the user before writing output.

If no semantic gaps are found, record that no gaps were identified from the stated use cases and confirmed taxonomy.

### 6. Write ontology

Write `.schema/<cdm-name>/ontology.ison` in Graph ISON format (https://graph.ison.dev/) — tabular DSV sections, **not JSON**.

Use tab-separated columns and a blank line between sections.

Example:

```ison
nodes.Entity
id	label	inferred	assumption
Person	Person	false	Collapses hubspot contact + luma guest. Natural key: email.
Company	Company	false	Master source: hubspot__companies.

nodes.Attribute
entity	name	type	master_source	also_in	note
:Entity:Person	email	text	hubspot__contacts	luma__guests	natural_key
:Entity:Person	first_name	text	hubspot__contacts

edges.BELONGS_TO
from	to	via	inferred
:Entity:Person	:Entity:Company	hubspot__contacts.associated_company_id	false

edges.STITCHED_BY
from	to	via	inferred
:Entity:Person	:Entity:Person	email	false
```

Rules:

- One `nodes.<Type>` section per entity type.
- One `edges.<LABEL>` section per relationship label.
- Node references use `:Type:id` syntax, e.g. `:Entity:Person`.
- Attributes are a separate `nodes.Attribute` section with an `entity` reference column.
- Keep section columns stable across rows.
- Prefer empty fields over placeholder text when optional values are absent.
- Sanitize tabs/newlines from values before writing tabular output.

If semantic gaps were found, append:

```ison
nodes.SemanticGap
concept	use_case	note
Contract	track subscription billing	no source table found
```

### 7. Write human-readable ontology summary

Write `.schema/<cdm-name>/ontology.md`.

Required structure:

- Title with CDM name
- Source artifacts read
- One section per entity containing:
  - short description from taxonomy
  - mapped source tables
  - attribute table: `name | type | source | notes`
  - relationships table: `relationship | target | via | inferred`
  - natural-key/master-source assumption, if applicable
- Final `Assumptions & Exclusions` section containing:
  - natural-key conflict strategies
  - semantic gaps, if any
  - excluded tables from `taxonomy.json` → `_excluded`

### 8. Ask the user to review

After writing both files, explicitly ask the user to open and review `.schema/<cdm-name>/ontology.md` before continuing:

```text
Please review `.schema/<cdm-name>/ontology.md` — it summarises every entity, its attributes, and the relationships between them.

Let me know if anything looks wrong or needs changing before we move on.
```

Wait for explicit confirmation before handing over to `generate-cdm` skill.

## Output

- `.schema/<cdm-name>/ontology.ison` — entity graph with attributes, relationships, and gaps
- `.schema/<cdm-name>/ontology.md` — human-readable summary

After review confirmation, hand over to the `generate-cdm` skill if available; otherwise tell the user the ontology artifacts are ready for CDM generation.
