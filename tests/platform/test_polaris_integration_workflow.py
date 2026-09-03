"""Protect the manual-only real Polaris/S3 integration boundary."""

from pathlib import Path

import yaml

ROOT = Path(__file__).parents[2]
WORKFLOW = ROOT / ".github/workflows/polaris-iceberg-integration.yaml"
COMPOSE = ROOT / "compose.iceberg.yml"


def test_real_iceberg_integration_is_manual_protected_and_oidc_backed() -> None:
    workflow = yaml.load(WORKFLOW.read_text(), Loader=yaml.BaseLoader)
    assert set(workflow["on"]) == {"workflow_dispatch"}
    assert workflow["permissions"] == {"contents": "read", "id-token": "write"}

    job = workflow["jobs"]["verify"]
    assert job["environment"] == "polaris-iceberg-integration"
    assert "inputs" not in workflow["on"]["workflow_dispatch"]
    provider_names = (
        "EBIRD" + "_API_" + "TOKEN",
        "NOAA" + "_API_" + "TOKEN",
        "XENO" + "_CANTO_" + "API_" + "KEY",
    )
    assert job["env"]["DATABOX_AWS_S3_BUCKET"] == "${{ secrets.DATABOX_AWS_S3_BUCKET }}"
    assert job["env"]["DATABOX_AWS_REGION"] == "us-west-1"
    assert {key for key in job["env"] if key.startswith(("EBIRD", "NOAA", "XENO"))} == set(
        provider_names
    )
    for provider_name in provider_names:
        assert job["env"][provider_name] == f"${{{{ secrets.{provider_name} }}}}"

    steps = job["steps"]
    credentials_step = next(
        step
        for step in steps
        if step.get("uses", "").startswith("aws-actions/configure-aws-credentials@")
    )
    assert credentials_step["with"] == {
        "role-to-assume": "${{ secrets.DATABOX_AWS_ROLE_ARN }}",
        "role-session-name": "databox-polaris-integration",
        "aws-region": "us-west-1",
    }
    assert credentials_step["uses"] != "aws-actions/configure-aws-credentials@v5.1.1"

    generation_step = next(
        step for step in steps if step.get("name") == "Generate disposable Polaris credentials"
    )
    assert "openssl rand" in generation_step["run"]
    assert "$GITHUB_ENV" in generation_step["run"]
    for credential in ("postgres_password", "client_id", "client_secret"):
        assert f"printf '::add-mask::%s\\n' \"${credential}\"" in generation_step["run"]
    assert "DATABOX_AWS_ACCESS_KEY_ID=${AWS_ACCESS_KEY_ID}" in generation_step["run"]
    assert "DATABOX_AWS_SECRET_ACCESS_KEY=${AWS_SECRET_ACCESS_KEY}" in generation_step["run"]
    assert "DATABOX_AWS_SESSION_TOKEN=${AWS_SESSION_TOKEN}" in generation_step["run"]
    assert "DATABOX_AWS_REGION=${AWS_REGION}" in generation_step["run"]
    assert "${DATABOX_AWS_SESSION_TOKEN:?set DATABOX_AWS_SESSION_TOKEN}" in COMPOSE.read_text()
    assert "secrets.DATABOX_AWS_ACCESS_KEY_ID" not in WORKFLOW.read_text()
    assert "secrets.DATABOX_AWS_SECRET_ACCESS_KEY" not in WORKFLOW.read_text()
    assert "secrets.DATABOX_POLARIS_" not in WORKFLOW.read_text()
    task_setup_index = next(
        index
        for index, step in enumerate(steps)
        if step.get("uses") == "go-task/setup-task@a00fbb05ce67b35648be3c78cbc9fd85354c757e"
    )
    verify_index = next(
        index for index, step in enumerate(steps) if step.get("run") == "task verify"
    )
    assert task_setup_index < verify_index

    cleanup_step = next(
        step for step in steps if step.get("name") == "Stop disposable Polaris catalog"
    )
    assert cleanup_step["if"] == "always()"
    assert "cleanup_variable()" in cleanup_step["run"]
    assert '"${!name:-cleanup}"' in cleanup_step["run"]
    for credential in (
        "DATABOX_POLARIS_POSTGRES_PASSWORD",
        "DATABOX_POLARIS_CLIENT_ID",
        "DATABOX_POLARIS_CLIENT_SECRET",
    ):
        assert f"$(cleanup_variable {credential})" in cleanup_step["run"]
