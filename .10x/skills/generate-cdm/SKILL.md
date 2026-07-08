---
name: generate-cdm
description: "Use after create-ontology to generate a Kimball-style Canonical Data Model in DBML from ontology artifacts before writing transformations."
metadata:
  created: 2026-07-07
  updated: 2026-07-07
---

# Generate CDM

Translate the ontology into an implementation-ready Canonical Data Model using Kimball dimensional modeling.

Requires outputs from `create-ontology`:

- `.schema/<cdm-name>/ontology.ison`
- `.schema/<cdm-name>/ontology.md`
- `.schema/<cdm-name>/taxonomy.json`

If `ontology.ison` is missing, run `create-ontology` first.

Read `_name` from `.schema/<cdm-name>/taxonomy.json` to determine `<cdm-name>`. All files in this skill are under that folder.

Reference: DBML format — https://dbml.dbdiagram.io/

## Determine the CDM folder

If the user provides a CDM folder name, use `.schema/<cdm-name>/taxonomy.json`.

If not provided:

1. Search for `.schema/*/taxonomy.json`.
2. If exactly one exists, read it and use its `_name` as `<cdm-name>`.
3. If multiple exist, ask the user which CDM to use.
4. If none exist, stop and run `annotate-sources` and `create-ontology` first.

## Steps

### 1. Classify entities as fact or reference tables

Read `.schema/<cdm-name>/ontology.ison`. For each entity, apply Kimball classification:

| Signals | Classification |
|---|---|
| Describes a business event, measurement, observation, or transaction, e.g. EventAttendance, Order, PageView, WeatherObservation | **Fact table** |
| Describes a stable business object, reference object, actor, location, product, or classification, e.g. Person, Company, Product, Station, Species | **Reference table** |
| A reference table shared across multiple fact tables | **Shared reference table** |

Use `dim_` prefixes for reference tables and `fact_` prefixes for fact tables.

Present the classification to the user and confirm before proceeding:

```text
Here's how I'd structure your data model:

  Reference tables (who/what your data is about):
    dim_person — Person (shared across all facts)
    dim_company — Company (shared across all facts)
    dim_event — Event

  Fact tables (the events/transactions):
    fact_event_attendance — one row per person per event attended

Does this look right?
```

Agree on **shared reference tables** early; they must be consistent across all fact tables.

### 2. Define grain for every fact table

For each fact table, write an explicit grain statement:

> One row per **[unit]** per **[unit]**

Example: `One row per person per event attended.`

The grain drives:

- Which columns go in the fact table vs. a dimension
- The grain key: column combination used to detect duplicates
- The surrogate key definition

Never proceed without a confirmed grain. Ask the user to confirm all fact grains before writing the CDM.

### 3. Design dimension/reference tables

For each dimension/reference entity:

- Add a **surrogate key**: `<entity_name>_sk`, `bigint` or stable string hash.
- Assign **SCD type**:
  - **Type 1** (default): overwrite on change; use when history does not matter.
  - **Type 2**: track history; adds `valid_from` (`timestamp`), `valid_to` (`timestamp`, nullable), `is_current` (`bool`).
  - Use Type 2 for status, tier, segment, role, or anything an analyst might want `as of` a date.
- Include `source_id` and `source_pipeline` for lineage when the ontology/source schema has a natural/source key.
- Apply null semantics with sentinel rows: `UNKNOWN`, `NOT_APPLICABLE`; **never use NULL as a foreign key** (Kimball Rule #6).

### 4. Design fact tables

For each fact table:

- Reference dimension surrogate keys as FKs. Do not use natural keys as dimension references in facts.
- Add a degenerate dimension for the natural transaction/event key if useful, e.g. `event_id`, `sub_id`, `load_id`.
- Include additive measures, amounts, counts, and event metrics.
- Clearly label semi-additive measures.
- Do not include descriptive attributes; push those to dimensions.

### 5. Review entity equivalence

Check for aliases that only become visible at the dimensional modeling stage, e.g. two ontology entities that would produce identical dimension tables.

Do **not** re-open concept collapses already confirmed in `taxonomy.json`; those are settled.

If a new collapse is warranted, confirm with the user before merging tables.

### 6. Write CDM

Write `.schema/<cdm-name>/CDM.dbml` using DBML syntax.

Encode metadata in `Table` notes:

```dbml
Table dim_person [note: 'table_type:dimension; surrogate_key:person_sk; scd_type:1; conformed:true'] {
  person_sk bigint [pk, note: 'surrogate key']
  source_id varchar [note: 'source key — original ID from the upstream system, stored for lineage']
  source_pipeline varchar
  email varchar
  first_name varchar
  last_name varchar
  company_sk bigint [ref: > dim_company.company_sk]
}

Table fact_event_attendance [note: 'table_type:fact; grain:one row per person per event attended'] {
  attendance_sk bigint [pk]
  person_sk bigint [ref: > dim_person.person_sk]
  event_sk bigint [ref: > dim_event.event_sk]
  registered_at timestamp
  attended bool
}
```

Required `note` fields per table type:

- **Dimension/reference**: `table_type`, `surrogate_key`, `scd_type`, `conformed`
- **Fact**: `table_type`, `grain`

Use DBML `Ref` or inline `[ref: > ...]` declarations for fact-to-dimension relationships.

### 7. Ask the user to review

After writing the file, explicitly ask the user to open and review `.schema/<cdm-name>/CDM.dbml` before continuing:

```text
Please review `.schema/<cdm-name>/CDM.dbml` — it contains the full data model with all tables, columns, and relationships.

Let me know if anything looks wrong or needs changing before we move on.
```

Wait for explicit confirmation before handing over to `create-transformation`.

## Output

- `.schema/<cdm-name>/CDM.dbml` — implementation-ready CDM schema

After review confirmation, hand over to the `create-transformation` skill if available; otherwise tell the user the CDM is ready for transformation implementation.
