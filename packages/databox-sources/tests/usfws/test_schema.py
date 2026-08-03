"""Schema contract for bounded USFWS image metadata."""

from __future__ import annotations


def test_usfws_schema_contains_auditable_rights_fields(
    memory_duckdb_pipeline_factory,
    usfws_source_factory,
) -> None:
    pipeline = memory_duckdb_pipeline_factory(pipeline_name="usfws_schema_test")
    info = pipeline.run(usfws_source_factory())
    assert not info.has_failed_jobs
    columns = pipeline.default_schema.tables["image_records"]["columns"]
    assert {
        "run_id",
        "species_code",
        "target_scientific_name",
        "source_page_url",
        "source_license",
        "source_creator",
        "source_image_medium_url",
        "scientific_name_tags_json",
        "_loaded_at",
    } <= set(columns)
    assert pipeline.default_schema.tables["image_records"]["write_disposition"] == "merge"
    assert pipeline.default_schema.tables["image_search_runs"]["write_disposition"] == "merge"
