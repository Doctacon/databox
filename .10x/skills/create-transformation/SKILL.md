---
name: create-transformation
description: "Use after generate-cdm to write dlthub transformation functions that map annotated source tables to CDM entities."
argument-hint: "[pipeline-name]"
metadata:
  created: 2026-07-07
  updated: 2026-07-07
---

# Create transformation

Write `@dlt.hub.transformation` functions that map annotated source tables to CDM entities, using SQL-first with optional ibis.

Requires:

- `.schema/<cdm-name>/taxonomy.json` — confirmed table-to-concept mappings and natural keys; read `_name` from this file to determine `<cdm-name>`
- `.schema/<cdm-name>/<pipeline_name>.dbml` — annotated source schemas
- `.schema/<cdm-name>/CDM.dbml` — target CDM schema

If any are missing, run the preceding skills first: `annotate-sources`, `create-ontology`, then `generate-cdm`.

The `_name` value from `taxonomy.json` is also the target `dataset_name` for the transformation pipeline. Do not re-derive it.

This skill does **not** require a dlt MCP server. Prefer local dlt pipeline state, `dlt.attach(...)`, relation schemas, and destination SQL/preview queries for validation.

## Invocation arguments

Parse the appended user text as:

- `pipeline-name`: the dlt pipeline to transform from, e.g. `hubspot_crm_pipeline`

If omitted, read `taxonomy.json` for contributing pipelines and ask the user which source pipeline to target. If the CDM requires multiple source pipelines, explain that the transformation is cross-source and ask whether to generate one cross-source script or one script per source pipeline.

## Determine the CDM folder

If the user provides a CDM folder name, use `.schema/<cdm-name>/taxonomy.json`.

If not provided:

1. Search for `.schema/*/taxonomy.json`.
2. If exactly one exists, read it and use its `_name` as `<cdm-name>`.
3. If multiple exist, ask the user which CDM to use.
4. If none exist, stop and run the preceding skills first.

## Steps

### 1. Confirm destination and dependencies

Determine destination. If the destination is not already known from prior context or project config, ask the user which destination they are using before proceeding.

Prefer the existing project environment and dependencies. Do not run dependency-install commands unless the user confirms.

Install or add the matching ibis backend only if ibis is needed:

| Destination | Command |
|---|---|
| DuckDB | `uv add "ibis-framework[duckdb]"` |
| PostgreSQL | `uv add "ibis-framework[postgres]"` |
| Snowflake | `uv add "ibis-framework[snowflake]"` |
| BigQuery | `uv add "ibis-framework[bigquery]"` |
| Other backend | `uv add "ibis-framework[<backend>]"` |

Install dlt hub support if missing and the user confirms:

```bash
uv add "dlt[hub]"
```

### 2. Read inputs

Read in parallel:

- `.schema/<cdm-name>/taxonomy.json` — table mappings and natural keys
- `.schema/<cdm-name>/<pipeline_name>.dbml` — source columns and concept mappings
- `.schema/<cdm-name>/CDM.dbml` — CDM entity definitions and column specs
- `.schema/<cdm-name>/ontology.ison` and `.schema/<cdm-name>/ontology.md` when relationship context is needed

### 3. Get actual source schema

Prefer relation schema from dlt dataset objects for actual column types. Do not rely on MCP schema tools.

```python
import dlt

pipeline = dlt.attach(pipeline_name="<pipeline_name>")
dataset = pipeline.dataset()
relation = dataset.<table_name>
schema = relation.schema()  # authoritative materialized column list
```

Cross-check the annotated columns in `.schema/<cdm-name>/<pipeline_name>.dbml` against `relation.schema()`. Note discrepancies before writing SQL.

### 4. Plan transformation order

Always run dimensions before facts because facts join on dimension surrogate keys.

Build an execution order:

1. All conformed/shared dimensions
2. Non-conformed dimensions
3. Fact tables after all their dimension FKs exist

**Do not self-reference transformation outputs while building facts by default.** Fact SQL must be derived from source-side tables/logic or explicit stage resources, not newly produced `dim_*` output tables. This avoids cyclic or destination-incompatible behavior across runs.

Allowed exception:

- If the user explicitly requests output-to-output dependencies and the destination semantics are confirmed to support that pattern, document it in the plan before writing SQL.

**Define a key type contract before writing any SQL.** Pick one key type for this pipeline, `text` or `bigint`, and apply it consistently to:

- all surrogate/foreign key casts in SQL or ibis
- every corresponding `columns=` schema hint

Do not mix key representations, e.g. `INT64` vs `STRING`, for related keys across dimensions/facts. If source systems disagree on key type, normalize to the chosen contract in staging/CTEs first.

### 5. Write transformation functions

Write one `@dlt.hub.transformation` function per CDM entity. Wrap all transformations in a `@dlt.source`.

**Dataset binding is required when yielding from `@dlt.source`.** When a transformation resource is returned/yielded from a source, pass the dataset argument explicitly. Not binding datasets can raise `IncompatibleDatasetsException`.

```python
import dlt

@dlt.source
def hubspot_activity_schema(source_dataset: dlt.Dataset):
    # Correct: dataset is explicitly bound
    yield dim_company(source_dataset)
    yield fact_activity(source_dataset)

@dlt.hub.transformation
def dim_company(dataset: dlt.Dataset):
    yield dataset("SELECT company_id, name FROM hubspot__companies")
```

#### Default to SQL transformation logic

Pass a SQL string directly to `dataset()`. SQL is easier for users to review, generally more reliable for LLM generation, and dlthub can transpile dialect differences when needed.

```python
@dlt.hub.transformation
def dim_person(dataset: dlt.Dataset):
    yield dataset("SELECT email, first_name, last_name FROM hubspot__contacts ORDER BY email")
```

If a relation variable is already available, treat it as a callable dataset relation and pass SQL directly:

```python
@dlt.hub.transformation
def dim_users(dataset: dlt.Dataset):
    yield dataset("SELECT user_id, email, created_at FROM users")
```

#### SQL style

Write all transformation SQL in ANSI-standard SQL. dlthub uses SQLGlot to transpile queries, but transpilation works best when the input SQL uses portable constructs.

Use:

- `CAST(x AS type)`, not `x::type`
- `COALESCE(a, b)`, not `IFNULL(a, b)`
- standard type names: `VARCHAR`, `BIGINT`, `BOOLEAN`, `TIMESTAMP`
- `CASE WHEN` for conditional logic
- standard aggregates: `SUM`, `AVG`, `COUNT`, `MIN`, `MAX`

When a transformation genuinely requires a dialect-specific function with no ANSI equivalent, e.g. `EPOCH_MS`, `STRFTIME`, arrays, pass `query_dialect` to `dataset()` so dlthub knows how to transpile it.

#### Cross-dataset SQL

Cross-dataset SQL must use fully qualified source references. When writing into `<target_dataset>` from a different source dataset, unqualified table names may resolve against the target dataset and fail with `table not found`.

For BigQuery, always use backtick-qualified `project.dataset.table` source-side refs:

```python
@dlt.hub.transformation
def fact_activity(dataset: dlt.Dataset):
    yield dataset(
        """
        SELECT a.id, a.activity_type, a.created_at
        FROM `my_project.source_dataset_name.activities` AS a
        """
    )
```

#### Association key check

Association key checks are mandatory before FK logic for nested association tables.

For nested association tables, verify join lineage first:

- association table `_dlt_parent_id` joins to parent row `_dlt_id`
- not to parent business keys like `id`

Do this verification before writing any JOIN used to derive foreign keys.

#### ibis option

ibis remains supported when SQL becomes too verbose for a specific step, e.g. complex programmatic expression building, reusable expression fragments, or an existing ibis-heavy codebase. If ibis is chosen, keep everything lazy and never fall back to pandas.

Minimal ibis example:

```python
@dlt.hub.transformation
def dim_person(dataset: dlt.Dataset):
    contacts = dataset.table("hubspot__contacts").to_ibis()
    yield contacts.select("email", "first_name", "last_name").order_by("email").limit(1000)
```

ibis requires a SQL-capable destination. If the user requests DuckDB as destination, check whether ibis can connect to it in the current context; if not, keep SQL-first transformations or switch to a destination that supports the desired ibis workflow.

#### Decorator default

```python
@dlt.hub.transformation(
    write_disposition="replace",
)
def dim_person(dataset: dlt.Dataset):
    ...
```

For scheduled or high-volume pipelines, switch `replace` to an incremental strategy only after the user asks for incremental behavior and the incremental grain is confirmed.

#### `columns=` hints

`columns=` hints are required for any column that may be NULL on the first run, and for any computed or derived column.

```python
@dlt.hub.transformation(
    write_disposition="replace",
    columns={
        "company_sk":   {"data_type": "text", "nullable": False},
        "email_hash":   {"data_type": "text", "nullable": True},
        "month_bucket": {"data_type": "text", "nullable": True},
        "event_count":  {"data_type": "bigint", "nullable": True},
    },
)
def dim_person(dataset: dlt.Dataset):
    ...
```

`columns=` `data_type` values for keys must match the key type contract selected in step 4.

Add `columns=` for:

- any computed or derived column: every hash, date bucket, `TRY_CAST`, `CASE WHEN`, aggregate alias, function chain
- any column from a LEFT JOIN
- any cast from string to typed value where source may be empty
- any column that was NULL-only in a prior run

Omitting `columns=` can cause silent data loss: dlthub may strip a column from the outer SELECT if its schema entry has no `data_type`.

Do **not** use `execute_sql_query` for cloud destinations. Use dlthub transformations with SQL-first, or ibis when explicitly selected.

### 6. Write the script

Output file:

```text
transformations/<dataset_name>_to_cdm.py
```

Structure:

```python
import dlt

@dlt.source
def <dataset_name>_to_cdm(dataset: dlt.Dataset):
    # dimensions first
    yield dim_person(dataset)
    yield dim_company(dataset)
    yield dim_event(dataset)
    # facts after
    yield fact_event_attendance(dataset)

@dlt.hub.transformation(write_disposition="replace")
def dim_person(dataset: dlt.Dataset):
    ...

# ... remaining functions

if __name__ == "__main__":
    source_pipeline = dlt.attach(pipeline_name="<source_pipeline_name>")
    source_dataset = source_pipeline.dataset()

    load_info = source_pipeline.run(<dataset_name>_to_cdm(source_dataset))
    print(load_info)
```

Run from the project root so dlt state resolves correctly. If needed, enforce root CWD in the entrypoint:

```python
from pathlib import Path
import os

os.chdir(Path(__file__).resolve().parents[1])
```

Naming convention: `pipeline_name` and `dataset_name` should reflect the business domain and central fact, not the source systems. Here, `<dataset_name>` comes from `taxonomy.json` `_name`.

### 7. Get feedback before running

Show a summary of:

- output tables being created
- source tables used per output table
- key type contract
- any `columns=` hints and why they are required
- any source columns skipped and why
- any relationship/FK assumptions

Ask the user to confirm before running the transformation.

### 8. Run

Run the script from the project root.

If the run fails, read the error before deciding where to go. Do not proceed to validation.

- SQL syntax error, unsupported function, dialect error → debug the transformation SQL.
- Pipeline state error, stale packages, schema drift, connection error → debug dlt pipeline state and destination connection.

### 9. Validate output without MCP

After a successful run, verify the transformation produced the expected result using local/destination-native checks, not MCP.

Preferred validation methods:

1. Attach the output pipeline and use dlt dataset relations.
2. Use destination SQL through the project-native client, e.g. DuckDB connection for local DuckDB/Quack after no writer is active.
3. Use `relation.schema()` for column names/types.
4. Use `SELECT COUNT(*)`, duplicate checks by grain, FK anti-joins, and small previews.

Example validation skeleton:

```python
import dlt

pipeline = dlt.attach(pipeline_name="<source_pipeline_name>")
dataset = pipeline.dataset()

for table_name in ["dim_person", "fact_event_attendance"]:
    relation = dataset.table(table_name)
    print(table_name, relation.schema())
    print(dataset(f"SELECT COUNT(*) AS row_count FROM {table_name}"))
    print(dataset(f"SELECT * FROM {table_name} LIMIT 10"))
```

What to check:

- all expected CDM tables exist; no silent skip due to empty resource
- row counts are non-zero and plausible relative to source table sizes
- surrogate key columns are populated, not all NULL
- foreign keys in fact tables resolve to values present in dimension tables
- no unexpected duplicate rows, i.e. grain violation
- computed columns are present and non-NULL where expected
- column names and types match `.schema/<cdm-name>/CDM.dbml`

If any check fails, debug the transformation before presenting success.

If all checks pass, ask the user what they want next:

```text
Transformation validated successfully. What would you like to do next?
1. Deploy and schedule this transformation.
2. Explore and visualise the CDM output.
```

## Output

- `transformations/<dataset_name>_to_cdm.py` — dlthub transformation script
