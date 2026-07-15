"""Registry-derived annotate → taxonomy → ontology → CDM → SQLMesh guard."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from databox.config.sources import SOURCES, Source

from scripts.check_source_modeling import validate_modeling_contract


def _source(*tables: str) -> Source:
    return Source(name="example", raw_tables=tables or ("records",))


def _write_complete_contract(
    root: Path,
    *,
    source: Source | None = None,
    pipeline: str = "example_api",
) -> Path:
    source = source or _source()
    domain = root / ".schema/domain"
    domain.mkdir(parents=True)
    table_blocks = "\n\n".join(
        f'Table "{table}" [note: \'concept: Record | role: primary\'] {{\n  "id" text\n}}'
        for table in source.raw_tables
    )
    dbml = domain / f"{pipeline}.dbml"
    dbml.write_text(table_blocks + "\n")
    taxonomy = {
        "_version": "1.0",
        "_name": "domain",
        "Record": {
            "description": "Example records",
            "tables": [
                {"table": table, "source_pipeline": pipeline, "role": "primary"}
                for table in source.raw_tables
            ],
        },
        "_excluded": [],
    }
    (domain / "taxonomy.json").write_text(json.dumps(taxonomy))
    (domain / "ontology.ison").write_text(
        "nodes.Entity\nid\tlabel\tinferred\tassumption\n"
        "Record\tRecord\tfalse\tSource-backed\n\n"
        "nodes.Attribute\nentity\tname\ttype\n"
    )
    (domain / "CDM.dbml").write_text(
        "Table fact_record [note: 'table_type:fact; source_entity:Record'] {\n  \"id\" text\n}\n"
    )
    models = root / "transforms/main/models/domain"
    models.mkdir(parents=True)
    dependencies = "\nUNION ALL\n".join(
        f"SELECT * FROM {source.raw_catalog}.{table}" for table in source.raw_tables
    )
    (models / "fact_record.sql").write_text(
        "MODEL (name domain.fact_record, kind FULL);\n\n" + dependencies + "\n"
    )
    return dbml


def _errors(root: Path, source: Source | None = None) -> list[str]:
    return validate_modeling_contract([source or _source()], project_root=root)


def test_current_registry_sources_complete_modeling_workflow() -> None:
    errors = validate_modeling_contract(SOURCES)
    assert not errors, "\n".join(errors)


def test_complete_contract_passes(tmp_path: Path) -> None:
    _write_complete_contract(tmp_path)
    assert _errors(tmp_path) == []


def test_documented_exclusion_does_not_require_downstream_modeling(tmp_path: Path) -> None:
    source = _source("records", "metadata")
    dbml = _write_complete_contract(tmp_path, source=source)
    dbml.write_text(
        dbml.read_text().replace(
            'concept: Record | role: primary\'] {\n  "id" text\n}',
            'excluded: source metadata\'] {\n  "id" text\n}',
            1,
        )
    )
    taxonomy_path = dbml.parent / "taxonomy.json"
    taxonomy = json.loads(taxonomy_path.read_text())
    taxonomy["Record"]["tables"] = [
        item for item in taxonomy["Record"]["tables"] if item["table"] != "records"
    ]
    taxonomy["_excluded"] = [
        {
            "table": "records",
            "source_pipeline": "example_api",
            "reason": "Source metadata only",
        }
    ]
    taxonomy_path.write_text(json.dumps(taxonomy))
    assert _errors(tmp_path, source) == []


def test_missing_annotation_owner_fails_with_inventory(tmp_path: Path) -> None:
    _write_complete_contract(tmp_path).unlink()
    errors = _errors(tmp_path)
    assert errors == [
        "example: annotation ownership missing; no source DBML contains registered tables "
        "['records']"
    ]


def test_ambiguous_annotation_ownership_names_candidates(tmp_path: Path) -> None:
    dbml = _write_complete_contract(tmp_path)
    (dbml.parent / "duplicate.dbml").write_text(dbml.read_text())
    errors = _errors(tmp_path)
    assert len(errors) == 1
    assert "annotation ownership ambiguous" in errors[0]
    assert "duplicate.dbml" in errors[0]
    assert "example_api.dbml" in errors[0]


def test_missing_table_annotation_fails_with_table(tmp_path: Path) -> None:
    dbml = _write_complete_contract(tmp_path)
    dbml.write_text(dbml.read_text().replace(" [note: 'concept: Record | role: primary']", ""))
    errors = _errors(tmp_path)
    assert any("example.records: DBML/taxonomy concept mismatch" in error for error in errors)


@pytest.mark.parametrize(
    ("dbml_note", "taxonomy_concepts"),
    [
        ("unconcept: Record | role: primary", {"Record"}),
        ("concept: Other | role: primary", {"Record"}),
        ("concept: Record | also_concept: Extra", {"Record"}),
        ("concept: Record", {"Record", "Extra"}),
    ],
)
def test_dbml_concepts_must_exactly_match_taxonomy(
    tmp_path: Path, dbml_note: str, taxonomy_concepts: set[str]
) -> None:
    dbml = _write_complete_contract(tmp_path)
    dbml.write_text(dbml.read_text().replace("concept: Record | role: primary", dbml_note))
    taxonomy_path = dbml.parent / "taxonomy.json"
    taxonomy = json.loads(taxonomy_path.read_text())
    if "Extra" in taxonomy_concepts:
        taxonomy["Extra"] = {
            "description": "Extra concept",
            "tables": [
                {
                    "table": "records",
                    "source_pipeline": "example_api",
                    "role": "secondary",
                }
            ],
        }
    taxonomy_path.write_text(json.dumps(taxonomy))
    errors = _errors(tmp_path)
    assert any("example.records: DBML/taxonomy concept mismatch" in error for error in errors)


@pytest.mark.parametrize("taxonomy_excluded", [False, True])
def test_dbml_exclusion_must_exactly_match_taxonomy(
    tmp_path: Path, taxonomy_excluded: bool
) -> None:
    dbml = _write_complete_contract(tmp_path)
    taxonomy_path = dbml.parent / "taxonomy.json"
    taxonomy = json.loads(taxonomy_path.read_text())
    if taxonomy_excluded:
        taxonomy["Record"]["tables"] = []
        taxonomy["_excluded"] = [
            {
                "table": "records",
                "source_pipeline": "example_api",
                "reason": "Metadata",
            }
        ]
    else:
        dbml.write_text(
            dbml.read_text().replace(
                "concept: Record | role: primary",
                "concept: Record | excluded: Metadata",
            )
        )
    taxonomy_path.write_text(json.dumps(taxonomy))
    errors = _errors(tmp_path)
    assert any("example.records: DBML/taxonomy exclusion mismatch" in error for error in errors)


def test_missing_taxonomy_classification_fails_with_pipeline(tmp_path: Path) -> None:
    dbml = _write_complete_contract(tmp_path)
    taxonomy_path = dbml.parent / "taxonomy.json"
    taxonomy = json.loads(taxonomy_path.read_text())
    taxonomy["Record"]["tables"] = []
    taxonomy_path.write_text(json.dumps(taxonomy))
    errors = _errors(tmp_path)
    assert any(
        "example.records: taxonomy classification missing for pipeline 'example_api'" == error
        for error in errors
    )
    assert not any("every registered raw table is excluded" in error for error in errors)


def test_modeled_and_excluded_table_fails_as_conflict(tmp_path: Path) -> None:
    dbml = _write_complete_contract(tmp_path)
    taxonomy_path = dbml.parent / "taxonomy.json"
    taxonomy = json.loads(taxonomy_path.read_text())
    taxonomy["_excluded"] = [
        {
            "table": "records",
            "source_pipeline": "example_api",
            "reason": "Contradictory exclusion",
        }
    ]
    taxonomy_path.write_text(json.dumps(taxonomy))
    errors = _errors(tmp_path)
    assert any("example.records: taxonomy conflict" in error for error in errors)


def test_exclusion_without_reason_fails(tmp_path: Path) -> None:
    dbml = _write_complete_contract(tmp_path)
    dbml.write_text(
        dbml.read_text().replace("concept: Record | role: primary", "excluded: metadata")
    )
    taxonomy_path = dbml.parent / "taxonomy.json"
    taxonomy = json.loads(taxonomy_path.read_text())
    taxonomy["Record"]["tables"] = []
    taxonomy["_excluded"] = [{"table": "records", "source_pipeline": "example_api", "reason": ""}]
    taxonomy_path.write_text(json.dumps(taxonomy))
    errors = _errors(tmp_path)
    assert any("taxonomy exclusion must include a reason" in error for error in errors)


def test_missing_ontology_entity_fails_with_concept(tmp_path: Path) -> None:
    dbml = _write_complete_contract(tmp_path)
    ontology = dbml.parent / "ontology.ison"
    ontology.write_text(ontology.read_text().replace("Record\tRecord\tfalse\tSource-backed\n", ""))
    errors = _errors(tmp_path)
    assert "example: ontology entity missing for modeled concept 'Record'" in errors


def test_missing_cdm_entity_fails_with_concept(tmp_path: Path) -> None:
    dbml = _write_complete_contract(tmp_path)
    cdm = dbml.parent / "CDM.dbml"
    cdm.write_text(cdm.read_text().replace("source_entity:Record", "source_entity:Other"))
    errors = _errors(tmp_path)
    assert "example: CDM source_entity missing for concept 'Record'" in errors


def test_sql_comments_and_strings_do_not_count_as_transformations(tmp_path: Path) -> None:
    _write_complete_contract(tmp_path)
    model = tmp_path / "transforms/main/models/domain/fact_record.sql"
    model.write_text(
        "MODEL (name domain.fact_record, kind FULL);\n\n"
        "-- FROM raw_example.records\n"
        "SELECT 'JOIN raw_example.records' AS fake_dependency\n"
    )
    errors = _errors(tmp_path)
    assert any(
        "example.records: semantic SQLMesh transformation missing" in error for error in errors
    )
    assert "example: no modeled table has a semantic SQLMesh transformation" in errors


@pytest.mark.parametrize(
    "statement",
    [
        "INSERT INTO raw_example.records SELECT 1",
        "UPDATE raw_example.records SET id = 1",
        "DELETE FROM raw_example.records WHERE id = 1",
    ],
    ids=["insert-target", "update-target", "delete-target"],
)
def test_raw_write_targets_do_not_count_as_dependencies(tmp_path: Path, statement: str) -> None:
    _write_complete_contract(tmp_path)
    model = tmp_path / "transforms/main/models/domain/fact_record.sql"
    model.write_text("MODEL (name domain.fact_record, kind FULL);\n\n" + statement + ";\n")
    errors = _errors(tmp_path)
    assert any("semantic SQLMesh transformation missing" in error for error in errors)


def test_quoted_dependency_with_comments_is_detected_by_sql_ast(tmp_path: Path) -> None:
    _write_complete_contract(tmp_path)
    model = tmp_path / "transforms/main/models/domain/fact_record.sql"
    model.write_text(
        'MODEL (name "domain"."fact_record", kind FULL);\n\n'
        'SELECT * FROM /* not lexical */ "raw_example"."records"\n'
    )
    assert _errors(tmp_path) == []


def test_genuine_join_dependency_is_detected_by_sql_ast(tmp_path: Path) -> None:
    _write_complete_contract(tmp_path)
    model = tmp_path / "transforms/main/models/domain/fact_record.sql"
    model.write_text(
        "MODEL (name domain.fact_record, kind FULL);\n\n"
        "SELECT records.* FROM (SELECT 1 AS id) AS seed\n"
        "JOIN raw_example.records AS records ON records.id = seed.id\n"
    )
    assert _errors(tmp_path) == []


def test_operational_model_dependency_does_not_count(tmp_path: Path) -> None:
    _write_complete_contract(tmp_path)
    model = tmp_path / "transforms/main/models/domain/fact_record.sql"
    model.write_text(
        "MODEL (name analytics.platform_health, kind FULL);\n\nSELECT * FROM raw_example.records\n"
    )
    errors = _errors(tmp_path)
    assert any("semantic SQLMesh transformation missing" in error for error in errors)


def test_cdm_model_requires_intersecting_source_entity(tmp_path: Path) -> None:
    dbml = _write_complete_contract(tmp_path)
    cdm = dbml.parent / "CDM.dbml"
    cdm.write_text(
        cdm.read_text() + "\nTable fact_other [note: 'table_type:fact; source_entity:Other'] {\n"
        '  "id" text\n}\n'
    )
    model = tmp_path / "transforms/main/models/domain/fact_record.sql"
    model.write_text(
        "MODEL (name domain.fact_other, kind FULL);\n\nSELECT * FROM raw_example.records\n"
    )
    errors = _errors(tmp_path)
    assert any("semantic SQLMesh transformation missing" in error for error in errors)


def test_fully_excluded_source_fails(tmp_path: Path) -> None:
    dbml = _write_complete_contract(tmp_path)
    dbml.write_text(
        dbml.read_text().replace("concept: Record | role: primary", "excluded: metadata")
    )
    taxonomy_path = dbml.parent / "taxonomy.json"
    taxonomy = json.loads(taxonomy_path.read_text())
    taxonomy["Record"]["tables"] = []
    taxonomy["_excluded"] = [
        {
            "table": "records",
            "source_pipeline": "example_api",
            "reason": "Metadata only",
        }
    ]
    taxonomy_path.write_text(json.dumps(taxonomy))
    errors = _errors(tmp_path)
    expected = (
        "example: every registered raw table is excluded; "
        "at least one modeled business table is required"
    )
    assert expected in errors


@pytest.mark.parametrize("stage", ["taxonomy.json", "ontology.ison", "CDM.dbml"])
def test_missing_required_stage_fails_with_stage(tmp_path: Path, stage: str) -> None:
    dbml = _write_complete_contract(tmp_path)
    (dbml.parent / stage).unlink()
    errors = _errors(tmp_path)
    assert any(
        "missing modeling artifacts" in error and stage.split(".")[0] in error for error in errors
    )
