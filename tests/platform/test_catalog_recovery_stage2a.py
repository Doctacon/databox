import json
import os
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).parents[2]
SCRIPT = ROOT / "scripts/platform/catalog-recovery-stage2a"


def test_stage2a_script_is_valid_local_posix_only() -> None:
    subprocess.run(["bash", "-n", str(SCRIPT)], check=True)
    text = SCRIPT.read_text()

    assert "repo1-type=posix" in text
    assert "--type=name" in text
    assert "stage2a_target_" in text
    assert 'targetBracket":"A-not-B' in text
    assert "http://localhost:8182/q/health/ready" in text
    assert "src=$repo,dst=/repo" in text
    assert "src=$config,dst=/etc/pgbackrest/pgbackrest.conf,readonly" in text
    assert "src=$dst,dst=/var/lib/postgresql/data" in text
    assert "pg_is_in_recovery()" in text
    assert 'containersAbsent":true' in text

    for forbidden in (
        "aws ",
        "s3://",
        "databox-polaris-catalog-backup",
        "databox-iceberg-postgres-1",
        "databox-iceberg-polaris-1",
        "docker volume rm",
        "docker network rm",
    ):
        assert forbidden not in text


@pytest.mark.parametrize(
    ("inspect_mode", "expected_containment", "expected_absent"),
    [("not-found", "passed", True), ("api-error", "unknown", False)],
)
def test_failure_receipt_distinguishes_absence_from_unknown_docker_state(
    tmp_path: Path,
    inspect_mode: str,
    expected_containment: str,
    expected_absent: bool,
) -> None:
    docker = tmp_path / "docker"
    docker.write_text(
        "#!/bin/sh\n"
        'if [ "${1:-}" = inspect ]; then\n'
        '  if [ "${STUB_MODE}" = not-found ]; then\n'
        "    echo 'Error: No such object: generated' >&2\n"
        "    exit 1\n"
        "  fi\n"
        "  echo 'Cannot connect to the Docker daemon' >&2\n"
        "  exit 2\n"
        "fi\n"
        "exit 2\n"
    )
    docker.chmod(0o700)
    evidence = tmp_path / "evidence"
    env = os.environ.copy()
    env.update(
        {
            "DATABOX_STAGE2A_EVIDENCE_ROOT": str(evidence),
            "PATH": f"{tmp_path}:{env['PATH']}",
            "STUB_MODE": inspect_mode,
        }
    )

    result = subprocess.run([str(SCRIPT)], env=env, check=False)

    assert result.returncode != 0
    receipts = list(evidence.glob("*/result.json"))
    assert len(receipts) == 1
    receipt = json.loads(receipts[0].read_text())
    assert receipt["containment"] == expected_containment
    assert receipt["containersAbsent"] is expected_absent
