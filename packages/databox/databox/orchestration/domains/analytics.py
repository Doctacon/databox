"""Cross-domain SQLMesh assets and Soda checks.

The SQLMesh project is the modeled-asset authority. Every resolved model must
have exactly one identity-matched Soda contract before Definitions can load.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable
from pathlib import Path

import dagster as dg
import yaml

from databox.orchestration._factories import SODA_DIR, soda_check, sqlmesh_project


def modeled_soda_contracts(
    specs: Iterable[dg.AssetSpec],
    contracts_dir: Path,
) -> list[tuple[dg.AssetKey, Path]]:
    """Return deterministic model/contract pairs or fail on inventory drift."""
    keys = [spec.key for spec in specs]
    key_counts = Counter(tuple(key.path) for key in keys)
    duplicate_keys = sorted(path for path, count in key_counts.items() if count > 1)
    errors = [f"duplicate SQLMesh asset key: {'/'.join(path)}" for path in duplicate_keys]

    expected: dict[tuple[str, str], dg.AssetKey] = {}
    for key in keys:
        path = key.path
        if len(path) != 3 or path[0] != "sqlmesh":
            errors.append(
                "invalid SQLMesh modeled asset key; expected sqlmesh/<schema>/<model>, "
                f"got {key.to_user_string()}"
            )
            continue
        identity = (path[1], path[2])
        expected.setdefault(identity, key)

    contract_files: dict[tuple[str, str], Path] = {}
    datasets: dict[str, list[Path]] = {}
    candidates = sorted([*contracts_dir.rglob("*.yaml"), *contracts_dir.rglob("*.yml")])
    for contract_path in candidates:
        relative = contract_path.relative_to(contracts_dir)
        if relative.parts[0].startswith("raw_"):
            continue
        if len(relative.parts) != 2 or contract_path.suffix != ".yaml":
            errors.append(
                f"modeled Soda contract must use contracts/<schema>/<model>.yaml: {contract_path}"
            )
            continue
        schema = relative.parts[0]
        identity = (schema, contract_path.stem)
        previous = contract_files.setdefault(identity, contract_path)
        if previous != contract_path:
            errors.append(
                f"duplicate modeled Soda contract files for {schema}.{contract_path.stem}: "
                f"{previous}, {contract_path}"
            )
        try:
            document = yaml.safe_load(contract_path.read_text()) or {}
        except yaml.YAMLError as exc:
            errors.append(f"invalid modeled Soda contract YAML {contract_path}: {exc}")
            continue
        dataset = document.get("dataset") if isinstance(document, dict) else None
        expected_dataset = f"databox/{schema}/{contract_path.stem}"
        if dataset != expected_dataset:
            errors.append(
                f"modeled Soda contract identity mismatch in {contract_path}: "
                f"expected {expected_dataset!r}, got {dataset!r}"
            )
        if isinstance(dataset, str):
            datasets.setdefault(dataset, []).append(contract_path)

    for dataset, paths in sorted(datasets.items()):
        if len(paths) > 1:
            errors.append(
                f"duplicate modeled Soda contract dataset {dataset!r}: "
                + ", ".join(str(path) for path in paths)
            )

    missing = sorted(set(expected) - set(contract_files))
    extra = sorted(set(contract_files) - set(expected))
    errors.extend(
        f"missing modeled Soda contract: {contracts_dir / schema / f'{model}.yaml'}"
        for schema, model in missing
    )
    errors.extend(
        f"extra modeled Soda contract without SQLMesh asset: {contract_files[(schema, model)]}"
        for schema, model in extra
    )

    if errors:
        raise ValueError("modeled SQLMesh/Soda contract parity failed:\n- " + "\n- ".join(errors))

    return [(expected[identity], contract_files[identity]) for identity in sorted(expected)]


_MODELED_CONTRACTS = modeled_soda_contracts(
    sqlmesh_project.specs,
    SODA_DIR / "contracts",
)

sqlmesh_asset_keys = [key for key, _ in _MODELED_CONTRACTS]
asset_checks: list[dg.AssetChecksDefinition] = [
    soda_check(key, contract_path) for key, contract_path in _MODELED_CONTRACTS
]
