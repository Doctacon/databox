from __future__ import annotations

import json
import re
from pathlib import Path

import pytest
from databox.config.sources import by_name
from databox.orchestration.definitions import defs
from databox.orchestration.domains import avonet
from databox.orchestration.parallel_refresh import execute_parallel_refresh
from databox.quality.platform_health_codegen import render as render_platform_health
from databox_sources.avonet import source


def test_avonet_is_independent_unscheduled_and_iceberg_authoritative() -> None:
    registered = by_name("avonet")
    assert registered is not None
    assert registered.raw_tables == ("species_traits",)
    assert registered.scheduled is False
    assert registered.parallel_refresh is False
    assert registered.iceberg_authoritative is True
    assert registered.analytics_raw_catalog == "polaris_aws.raw_avonet"
    assert avonet.ingest_job.name == "avonet_ingest"
    assert not hasattr(avonet, "schedule")
    assert not hasattr(avonet, "daily_pipeline")
    assert defs.get_job_def("avonet_ingest").name == "avonet_ingest"
    with pytest.raises(ValueError, match="Unknown sources: avonet"):
        execute_parallel_refresh(["avonet"])
    rendered = render_platform_health([registered])
    assert "polaris_aws.raw_avonet._dlt_load_status" in rendered
    assert "SELECT load_id, rows_loaded AS rows" in rendered


def test_avonet_resource_uses_iceberg_replacement_with_lineage_columns() -> None:
    resource = source.avonet_source().resources["species_traits"]
    schema = resource.compute_table_schema()
    assert resource.table_format == "iceberg"
    assert resource.write_disposition == "replace"
    assert schema["columns"]["avibase_id"]["primary_key"] is True
    assert tuple(schema["columns"]) == tuple(source._COLUMNS)


def test_avonet_schema_artifacts_match_normalized_resource_and_annotations() -> None:
    schema_dir = Path(".schema/environmental_observations")
    dbml = (schema_dir / "avonet.dbml").read_text()
    species_table = dbml.split('Table "species_traits"', maxsplit=1)[1]
    columns = re.findall(r'^  "([^"]+)" ', species_table, flags=re.MULTILINE)
    assert columns == [*source._COLUMNS, "_dlt_load_id", "_dlt_id"]
    assert "millimetres" in species_table
    assert "grams" in species_table
    assert "1 dense, 2 semi-open, 3 open" in species_table
    assert "1 sedentary, 2 partial migrant, 3 migratory" in species_table
    taxonomy = json.loads((schema_dir / "taxonomy.json").read_text())
    assert taxonomy["BirdSpeciesTraits"]["natural_key"] == "normalized_scientific_name"
    assert taxonomy["BirdSpeciesTraits"]["tables"] == [
        {"table": "species_traits", "source_pipeline": "avonet", "role": "primary"},
        {
            "table": "dim_bird_species_traits",
            "source_pipeline": "environmental_observations",
            "role": "modeled_dimension",
        },
    ]
    ontology = (schema_dir / "ontology.md").read_text()
    assert "## BirdSpeciesTraits" in ontology
    assert "global AVONET species averages" in ontology
