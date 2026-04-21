"""Run every Soda contract against the SQLMesh `__dev` virtual environment.

Soda contracts hard-code dataset paths like `databox/ebird/fct_x`. SQLMesh's
dev env materializes the same table at `ebird__dev.fct_x`. This script
rewrites `databox/<schema>/<table>` to `databox/<schema>__dev/<table>` in
each contract YAML (in memory, committed files untouched) and pipes the
rewritten contract into Soda's ContractVerificationSession.

Exit: 0 if every contract passes, 1 on any failure, 2 on invocation error.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

from databox.config.settings import settings

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CONTRACTS_DIR = PROJECT_ROOT / "soda" / "contracts"

# Matches `dataset: <db>/<schema>/<table>` (first-line or indented). Captures
# the schema so we can append `__dev`. Excludes already-suffixed datasets.
DATASET_RE = re.compile(
    r"^(\s*dataset:\s*[^/\s]+/)([^/\s_]+(?:_[^/\s_]+)*?)(/[^/\s]+\s*)$",
    re.MULTILINE,
)


def rewrite_for_dev(contract_yaml: str) -> str:
    def _sub(match: re.Match[str]) -> str:
        prefix, schema, tail = match.group(1), match.group(2), match.group(3)
        if schema.endswith("__dev"):
            return match.group(0)
        return f"{prefix}{schema}__dev{tail}"

    return DATASET_RE.sub(_sub, contract_yaml)


def main() -> int:
    from soda_core.common.yaml import ContractYamlSource, DataSourceYamlSource
    from soda_core.contracts.contract_verification import ContractVerificationSession

    contracts = sorted(CONTRACTS_DIR.rglob("*.yaml")) + sorted(CONTRACTS_DIR.rglob("*.yml"))
    if not contracts:
        print("no Soda contracts found", file=sys.stderr)
        return 2

    datasource_yaml = settings.soda_datasource_yaml
    failures: list[tuple[Path, str]] = []

    for contract in contracts:
        original = contract.read_text()
        rewritten = rewrite_for_dev(original)
        result = ContractVerificationSession.execute(
            contract_yaml_sources=[ContractYamlSource.from_str(rewritten)],
            data_source_yaml_sources=[DataSourceYamlSource.from_str(datasource_yaml)],
        )
        if result.is_failed:
            failures.append((contract, result.get_errors_str()))
            print(f"FAIL {contract.relative_to(PROJECT_ROOT)}")
        else:
            print(f"ok   {contract.relative_to(PROJECT_ROOT)}")

    if failures:
        print(f"\n{len(failures)} contract(s) failed against __dev schema:", file=sys.stderr)
        for path, errors in failures:
            print(f"\n--- {path.relative_to(PROJECT_ROOT)} ---\n{errors}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
