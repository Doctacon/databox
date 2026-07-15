#!/usr/bin/env python3
"""Validate that every registered dlt source completes the modeling workflow."""

from __future__ import annotations

import argparse
import json
import re
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from databox.config.sources import SOURCES, Source
from sqlglot import exp
from sqlglot.errors import ParseError
from sqlmesh.core.dialect import Model, parse

PROJECT_ROOT = Path(__file__).resolve().parent.parent
_TABLE_PATTERN = re.compile(
    r"^Table\s+\"?([^\"\s\[]+)\"?\s*(?:\[note:\s*'([^']*)'\])?\s*\{",
    re.MULTILINE,
)
_NOTE_PART_PATTERN = re.compile(r"(?:^|[;|])\s*([a-z_]+)\s*:\s*([^;|]*)")


@dataclass(frozen=True)
class SourceDbml:
    path: Path
    tables: dict[str, str]


@dataclass(frozen=True)
class SqlModel:
    path: Path
    output: tuple[str, str]
    raw_dependencies: frozenset[tuple[str, str]]


@dataclass(frozen=True)
class ModelingPaths:
    project_root: Path

    @property
    def schema_root(self) -> Path:
        return self.project_root / ".schema"

    @property
    def models_root(self) -> Path:
        return self.project_root / "transforms/main/models"


def _note_fields(note: str) -> dict[str, list[str]]:
    fields: dict[str, list[str]] = {}
    for key, value in _NOTE_PART_PATTERN.findall(note):
        fields.setdefault(key, []).append(value.strip())
    return fields


def _source_dbmls(schema_root: Path) -> list[SourceDbml]:
    artifacts: list[SourceDbml] = []
    for path in sorted(schema_root.glob("*/*.dbml")):
        if path.name == "CDM.dbml":
            continue
        tables = {name: note or "" for name, note in _TABLE_PATTERN.findall(path.read_text())}
        artifacts.append(SourceDbml(path=path, tables=tables))
    return artifacts


def _dbml_classification(note: str) -> tuple[set[str], bool]:
    fields = _note_fields(note)
    concepts = {
        value for key in ("concept", "also_concept") for value in fields.get(key, []) if value
    }
    return concepts, "excluded" in fields


def _taxonomy_classifications(
    taxonomy: dict[str, Any], pipeline: str
) -> tuple[dict[str, set[str]], dict[str, list[dict[str, Any]]]]:
    modeled: dict[str, set[str]] = {}
    for concept, details in taxonomy.items():
        if concept.startswith("_") or not isinstance(details, dict):
            continue
        for table in details.get("tables", []):
            if not isinstance(table, dict) or table.get("source_pipeline") != pipeline:
                continue
            table_name = table.get("table")
            if isinstance(table_name, str):
                modeled.setdefault(table_name, set()).add(concept)

    excluded: dict[str, list[dict[str, Any]]] = {}
    for item in taxonomy.get("_excluded", []):
        if not isinstance(item, dict) or item.get("source_pipeline") != pipeline:
            continue
        table_name = item.get("table")
        if isinstance(table_name, str):
            excluded.setdefault(table_name, []).append(item)
    return modeled, excluded


def _ontology_entities(text: str) -> set[str]:
    entities: set[str] = set()
    in_entities = False
    for line in text.splitlines():
        if line == "nodes.Entity":
            in_entities = True
            continue
        if line.startswith("nodes."):
            in_entities = False
        if not in_entities or not line or line.startswith("id\t"):
            continue
        entities.add(line.split("\t", 1)[0])
    return entities


def _cdm_tables(text: str, default_schema: str) -> dict[tuple[str, str], set[str]]:
    tables: dict[tuple[str, str], set[str]] = {}
    for table, note in _TABLE_PATTERN.findall(text):
        fields = _note_fields(note)
        schema = next(iter(fields.get("schema", [])), default_schema)
        tables[(schema.lower(), table.lower())] = {
            value for value in fields.get("source_entity", []) if value
        }
    return tables


def _model_output(model: Model) -> tuple[str, str] | None:
    for property_expression in model.expressions:
        if not isinstance(property_expression, exp.Property) or property_expression.name != "name":
            continue
        value = property_expression.args.get("value")
        if isinstance(value, exp.Table):
            return value.db.lower(), value.name.lower()
    return None


def _sql_models(models_root: Path) -> tuple[list[SqlModel], list[str]]:
    models: list[SqlModel] = []
    errors: list[str] = []
    for path in sorted(models_root.rglob("*.sql")):
        try:
            expressions = parse(path.read_text())
        except ParseError as exc:
            errors.append(f"SQLMesh parse failed for {path}: {exc}")
            continue
        model_expressions = [
            expression for expression in expressions if isinstance(expression, Model)
        ]
        if len(model_expressions) != 1:
            errors.append(
                f"SQLMesh model declaration missing or ambiguous in {path}; "
                f"expected exactly one MODEL, found {len(model_expressions)}"
            )
            continue
        output = _model_output(model_expressions[0])
        if output is None:
            errors.append(f"SQLMesh MODEL name missing or invalid in {path}")
            continue
        dependencies: set[tuple[str, str]] = set()
        for expression in expressions:
            if isinstance(expression, Model):
                continue
            clauses = [
                *expression.find_all(exp.From),
                *expression.find_all(exp.Join),
            ]
            for clause in clauses:
                for table in clause.find_all(exp.Table):
                    schema = table.db.lower()
                    if schema.startswith("raw_"):
                        dependencies.add((schema.removeprefix("raw_"), table.name.lower()))
        models.append(SqlModel(path=path, output=output, raw_dependencies=frozenset(dependencies)))
    return models, errors


def validate_modeling_contract(
    sources: Sequence[Source] = SOURCES,
    *,
    project_root: Path = PROJECT_ROOT,
) -> list[str]:
    """Return actionable contract errors without reading data or contacting providers."""
    paths = ModelingPaths(project_root)
    dbmls = _source_dbmls(paths.schema_root)
    sql_models, errors = _sql_models(paths.models_root)

    for source in sources:
        raw_tables = set(source.raw_tables)
        owners = [artifact for artifact in dbmls if raw_tables <= set(artifact.tables)]
        if not owners:
            errors.append(
                f"{source.name}: annotation ownership missing; no source DBML contains "
                f"registered tables {sorted(raw_tables)}"
            )
            continue
        if len(owners) > 1:
            owner_paths = [str(owner.path.relative_to(project_root)) for owner in owners]
            errors.append(
                f"{source.name}: annotation ownership ambiguous for registered tables "
                f"{sorted(raw_tables)}; candidates={owner_paths}"
            )
            continue

        owner = owners[0]
        pipeline = owner.path.stem
        domain_dir = owner.path.parent
        taxonomy_path = domain_dir / "taxonomy.json"
        ontology_path = domain_dir / "ontology.ison"
        cdm_path = domain_dir / "CDM.dbml"
        required = {
            "taxonomy": taxonomy_path,
            "ontology": ontology_path,
            "CDM": cdm_path,
        }
        missing_artifacts = [stage for stage, path in required.items() if not path.exists()]
        if missing_artifacts:
            errors.append(
                f"{source.name}: missing modeling artifacts {missing_artifacts} in "
                f"{domain_dir.relative_to(project_root)}"
            )
            continue

        try:
            taxonomy = json.loads(taxonomy_path.read_text())
        except json.JSONDecodeError as exc:
            errors.append(f"{source.name}: invalid taxonomy JSON in {taxonomy_path}: {exc}")
            continue
        if not isinstance(taxonomy, dict):
            errors.append(f"{source.name}: taxonomy root must be an object in {taxonomy_path}")
            continue

        modeled, excluded = _taxonomy_classifications(taxonomy, pipeline)
        modeled_tables: set[str] = set()
        excluded_tables: set[str] = set()
        modeled_concepts: set[str] = set()
        table_concepts: dict[str, set[str]] = {}
        for table in sorted(raw_tables):
            taxonomy_concepts = modeled.get(table, set())
            exclusions = excluded.get(table, [])
            dbml_concepts, dbml_excluded = _dbml_classification(owner.tables[table])
            taxonomy_excluded = bool(exclusions)
            if dbml_concepts != taxonomy_concepts:
                errors.append(
                    f"{source.name}.{table}: DBML/taxonomy concept mismatch; "
                    f"DBML={sorted(dbml_concepts)}, taxonomy={sorted(taxonomy_concepts)}"
                )
            if dbml_excluded != taxonomy_excluded:
                errors.append(
                    f"{source.name}.{table}: DBML/taxonomy exclusion mismatch; "
                    f"DBML excluded={dbml_excluded}, taxonomy excluded={taxonomy_excluded}"
                )
            if taxonomy_concepts and exclusions:
                errors.append(
                    f"{source.name}.{table}: taxonomy conflict; modeled as "
                    f"{sorted(taxonomy_concepts)} and explicitly excluded"
                )
                continue
            if not taxonomy_concepts and not exclusions:
                errors.append(
                    f"{source.name}.{table}: taxonomy classification missing for "
                    f"pipeline {pipeline!r}"
                )
                continue
            if exclusions:
                excluded_tables.add(table)
                if any(not str(item.get("reason", "")).strip() for item in exclusions):
                    errors.append(
                        f"{source.name}.{table}: taxonomy exclusion must include a reason"
                    )
                continue
            modeled_tables.add(table)
            modeled_concepts.update(taxonomy_concepts)
            table_concepts[table] = taxonomy_concepts

        default_schema = str(taxonomy.get("_name", "")).strip()
        if not default_schema:
            errors.append(f"{source.name}: taxonomy _name is required in {taxonomy_path}")
            continue
        ontology_entities = _ontology_entities(ontology_path.read_text())
        cdm_tables = _cdm_tables(cdm_path.read_text(), default_schema)
        cdm_entities = {concept for concepts in cdm_tables.values() for concept in concepts}
        for concept in sorted(modeled_concepts):
            if concept not in ontology_entities:
                errors.append(
                    f"{source.name}: ontology entity missing for modeled concept {concept!r}"
                )
            if concept not in cdm_entities:
                errors.append(f"{source.name}: CDM source_entity missing for concept {concept!r}")

        transformed_tables: set[str] = set()
        for table in sorted(modeled_tables):
            raw_dependency = (source.name, table)
            eligible_models = [
                model
                for model in sql_models
                if raw_dependency in model.raw_dependencies
                and model.output in cdm_tables
                and bool(cdm_tables[model.output] & table_concepts[table])
            ]
            if not eligible_models:
                errors.append(
                    f"{source.name}.{table}: semantic SQLMesh transformation missing; expected "
                    f"a real FROM or JOIN dependency on {source.raw_catalog}.{table} in a MODEL "
                    "declared by CDM.dbml with an intersecting source_entity"
                )
            else:
                transformed_tables.add(table)
        if excluded_tables == raw_tables:
            errors.append(
                f"{source.name}: every registered raw table is excluded; at least one modeled "
                "business table is required"
            )
        elif modeled_tables and not transformed_tables:
            errors.append(f"{source.name}: no modeled table has a semantic SQLMesh transformation")

    return errors


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args(argv)
    errors = validate_modeling_contract()
    if errors:
        for error in errors:
            print(f"  ✗ {error}")
        return 1
    print(f"✓ {len(SOURCES)} registered sources complete the modeling workflow")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
