# Source typing with Pydantic

dlt sources yield records as plain dicts by default — convenient for
bootstrap, but there's no contract between what the upstream API sends and
what lands in DuckDB. When an API renames a field or flips a type, the drift
only surfaces downstream when a SQLMesh test or Soda contract fails, hours
or days after the bad record loads.

The fix is a Pydantic model at the `@dlt.resource` boundary. The resource
validates each record through the model before yielding. Upstream drift
raises `pydantic.ValidationError` at extract time, before dlt writes
anything.

## Pilot: eBird `RecentObservation`

The canonical example is `packages/databox-sources/databox_sources/ebird/models.py`,
which defines `RecentObservation` for the eBird recent/notable endpoints.
Key shape decisions:

- **`AliasChoices` for input, explicit wire names for output.** The API
  sends `subId`, `howMany`, etc.; the legacy dlt resource yielded the same
  camelCase keys so dlt's normalizer could lowercase and snake_case them
  on write. The model accepts either form on input (camelCase or
  snake_case) via `validation_alias=AliasChoices(...)`, and emits the
  legacy wire shape via `to_record()`. This keeps the DuckDB schema
  bit-for-bit identical during the migration.
- **`extra="ignore"`.** Upstream adding a field (e.g. a new `hasRichMedia`)
  must not break the extract. The model silently drops unknown keys.
- **`populate_by_name=True`.** Lets tests pass either API names or Python
  names.
- **Defaults on optional fields.** `how_many` is genuinely absent when an
  observer reports an "X" count; making it `int | None` with `default=None`
  reflects that. Similarly for `obs_valid` and friends.

## How a resource uses the model

Inside `source.py`, the `process_observation` helper validates each record
and returns a dict-shaped payload keyed by the legacy wire names:

```python
def process_observation(obs, region, is_notable=False):
    enriched = dict(obs)
    enriched["_region_code"] = region
    enriched["_loaded_at"] = pendulum.now().isoformat()
    enriched["_observation_date"] = obs.get("obsDt")
    enriched["_is_notable"] = is_notable
    return RecentObservation.model_validate(enriched).to_record()
```

The resource keeps its explicit `columns={...}` hint (the model's Python
field names don't round-trip 1:1 to the legacy underscore-prefixed metadata
columns, so `columns=RecentObservation` is deferred). Validation is still
the primary drift-detection mechanism; `columns=` is just a type pin for
three numeric fields dlt can't infer safely.

## When to add a model

Reach for a model when:

- the resource hits an external API you don't control
- the resource yields records with more than ~5 meaningful fields
- downstream consumers (staging views, Soda contracts) would silently
  accept a renamed or re-typed field

Skip the model when:

- the resource reads local files you fully control
- the yielded shape is a trivial `{key, value}` pair
- the upstream schema is already typed via an SDK

## Relationship to Soda contracts

Pydantic at the source is the first line of defense: it catches type and
required-field drift before the record lands. Soda contracts on the staging
view are the second line: they catch semantic drift (row counts, freshness
windows, value ranges) on what dlt *did* write.

Both are valuable. Pydantic fails closed earlier; Soda catches the things
types alone can't express.

## Next steps

This is a pilot. Follow-up work (not yet ticketed):

1. Extend to the other eBird resources (`species_list`, `hotspots`,
   `taxonomy`, `region_stats`).
2. Add models for the NOAA, USGS, and USGS earthquakes sources.
3. Revisit `columns=ModelClass` once we settle on a shared convention for
   dlt load-metadata fields (the `_region_code` / `_loaded_at` pattern).
