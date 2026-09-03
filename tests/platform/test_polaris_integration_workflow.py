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
    assert job["name"] == "Real Polaris/S3 source verification (${{ matrix.source }})"
    assert job["environment"] == "polaris-iceberg-integration"
    assert job["strategy"] == {
        "fail-fast": "false",
        "matrix": {
            "source": [
                "ebird",
                "gbif",
                "xeno_canto",
                "noaa",
                "usgs",
                "usgs_earthquakes",
            ]
        },
    }
    assert "inputs" not in workflow["on"]["workflow_dispatch"]
    provider_names = (
        "EBIRD" + "_API_" + "TOKEN",
        "NOAA" + "_API_" + "TOKEN",
        "XENO" + "_CANTO_" + "API_" + "KEY",
    )
    assert job["env"]["DATABOX_AWS_S3_BUCKET"] == "${{ secrets.DATABOX_AWS_S3_BUCKET }}"
    assert job["env"]["DATABOX_ICEBERG_WAREHOUSE_PREFIX"] == (
        "integration/${{ github.run_id }}/${{ github.run_attempt }}/${{ matrix.source }}/warehouse"
    )
    assert job["env"]["DATABOX_ICEBERG_WAREHOUSE_PREFIX"] != "warehouse"
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
    start_index = next(
        index
        for index, step in enumerate(steps)
        if step.get("name") == "Start disposable Polaris catalog"
    )
    provision_index = next(
        index
        for index, step in enumerate(steps)
        if step.get("name") == "Provision isolated databox_lake catalog"
    )
    provision_step = steps[provision_index]
    assert provision_step["env"] == {"DATABOX_AWS_ROLE_ARN": "${{ secrets.DATABOX_AWS_ROLE_ARN }}"}
    assert 'name: "databox_lake"' in provision_step["run"]
    assert (
        'warehouse="s3://${DATABOX_AWS_S3_BUCKET}/${DATABOX_ICEBERG_WAREHOUSE_PREFIX}"'
        in (provision_step["run"])
    )
    assert "allowedLocations: [$warehouse]" in provision_step["run"]
    assert "roleArn: $role_arn" in provision_step["run"]
    assert "::add-mask::%s" in provision_step["run"]
    provision_script = provision_step["run"]
    create_catalog_role = provision_script.index(
        '"${management_url}/catalogs/databox_lake/catalog-roles"'
    )
    grant_content = provision_script.index(
        '"${management_url}/catalogs/databox_lake/catalog-roles/integration_writer/grants"'
    )
    assign_to_service_admin = provision_script.index(
        '"${management_url}/principal-roles/service_admin/catalog-roles/databox_lake"'
    )
    assert create_catalog_role < grant_content < assign_to_service_admin
    assert '{"catalogRole":{"name":"integration_writer","properties":{}}}' in provision_script
    assert '{"type":"catalog","privilege":"CATALOG_MANAGE_CONTENT"}' in provision_script
    assert '{"catalogRole":{"name":"integration_writer"}}' in provision_script
    assert not any(step.get("uses", "").startswith("go-task/setup-task@") for step in steps)
    verify_index = next(
        index
        for index, step in enumerate(steps)
        if step.get("name") == "Verify real Polaris/S3 source publication"
    )
    assert steps[verify_index]["run"] == (
        ".venv/bin/python scripts/sources/load_dlt_iceberg.py "
        '--source "${{ matrix.source }}" --skip-sqlmesh'
    )
    assert start_index < provision_index < verify_index

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


def test_s3_preflight_is_read_only_scoped_and_runs_before_source_verification() -> None:
    workflow = yaml.load(WORKFLOW.read_text(), Loader=yaml.BaseLoader)
    steps = workflow["jobs"]["verify"]["steps"]

    provision_index = next(
        index
        for index, step in enumerate(steps)
        if step.get("name") == "Provision isolated databox_lake catalog"
    )
    preflight_index = next(
        index
        for index, step in enumerate(steps)
        if step.get("name") == "Preflight AWS identity and isolated S3 prefix"
    )
    verify_index = next(
        index
        for index, step in enumerate(steps)
        if step.get("name") == "Verify real Polaris/S3 source publication"
    )
    preflight_step = steps[preflight_index]

    assert provision_index < preflight_index < verify_index
    assert preflight_step["shell"] == "bash"
    assert preflight_step["run"].splitlines() == [
        "set -euo pipefail",
        "aws sts get-caller-identity",
        "aws s3api list-objects-v2 \\",
        '  --bucket "${DATABOX_AWS_S3_BUCKET}" \\',
        '  --prefix "${DATABOX_ICEBERG_WAREHOUSE_PREFIX}" \\',
        "  --max-items 1",
    ]
