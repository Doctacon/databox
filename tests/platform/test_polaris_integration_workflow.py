"""Protect the manual-only real Polaris/S3 integration boundary."""

from pathlib import Path

import yaml

WORKFLOW = Path(__file__).parents[2] / ".github/workflows/polaris-iceberg-integration.yaml"


def test_real_iceberg_integration_is_manual_and_protected() -> None:
    workflow = yaml.load(WORKFLOW.read_text(), Loader=yaml.BaseLoader)
    assert set(workflow["on"]) == {"workflow_dispatch"}
    job = workflow["jobs"]["verify"]
    assert job["environment"] == "polaris-iceberg-integration"
    assert "inputs" not in workflow["on"]["workflow_dispatch"]
    assert "task verify" in [step["run"] for step in job["steps"] if "run" in step]
