"""Release-policy tests for the isolated Workers AI Free deployment."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import yaml
from databox.public_export_audit import audit_deploy_context, audit_workflow_runners

ROOT = Path(__file__).parent.parent
WORKFLOW_ROOT = ROOT / ".github/workflows"
WORKFLOW = WORKFLOW_ROOT / "rufous-ai-worker.yaml"
PAGES_WORKFLOW = WORKFLOW_ROOT / "rufous-public.yaml"


def _workflow(path: Path) -> dict[str, Any]:
    return yaml.load(path.read_text(encoding="utf-8"), Loader=yaml.BaseLoader)


def test_ai_worker_workflow_is_main_only_and_credential_isolated() -> None:
    workflow = _workflow(WORKFLOW)
    text = WORKFLOW.read_text(encoding="utf-8")
    test_job = workflow["jobs"]["test"]
    deploy = workflow["jobs"]["deploy"]

    assert workflow["permissions"] == {"contents": "read"}
    assert test_job["runs-on"] == "ubuntu-latest"
    assert deploy["runs-on"] == "ubuntu-latest"
    assert "github.ref == 'refs/heads/main'" in deploy["if"]
    assert "github.event_name == 'pull_request'" not in deploy["if"]
    assert deploy["env"] == {
        "RUF_AI_RELEASE_ENABLED": "${{ vars.RUF_AI_RELEASE_ENABLED }}",
        "RUF_AI_WORKERS_PLAN": "${{ vars.RUF_AI_WORKERS_PLAN }}",
        "RUF_AI_ACCOUNT_ID": "${{ vars.RUF_AI_ACCOUNT_ID }}",
    }
    assert "secrets." not in json.dumps(test_job)
    assert set(re.findall(r"secrets\.([A-Za-z][A-Za-z0-9_]*)", text)) == {"RUF_AI_WORKER_API_TOKEN"}

    commands = "\n".join(step.get("run", "") for step in deploy["steps"] if isinstance(step, dict))
    assert "npm exec wrangler deploy -- --config wrangler.jsonc" in commands
    assert "RUF_AI_RELEASE_ENABLED" in commands
    assert '[[ "$RUF_AI_WORKERS_PLAN" != "free" ]]' in commands
    for forbidden in (
        "pages deploy",
        "RUF_R2_ACCESS_KEY_ID",
        "RUF_R2_SECRET_ACCESS_KEY",
        "publish_rufous_public",
        "publish_rufous_media",
    ):
        assert forbidden not in text

    token_steps = [
        step
        for step in deploy["steps"]
        if isinstance(step, dict) and "secrets.RUF_AI_WORKER_API_TOKEN" in json.dumps(step)
    ]
    assert len(token_steps) == 1
    assert token_steps[0]["name"] == "Deploy only the reviewed AI Worker"
    assert token_steps[0]["env"] == {
        "CLOUDFLARE_ACCOUNT_ID": "${{ vars.RUF_AI_ACCOUNT_ID }}",
        "CLOUDFLARE_API_TOKEN": (
            "${{ secrets.RUF_AI_WORKER_API_TOKEN }}"  # secret-scan: allow
        ),
    }


def test_pages_build_uses_only_the_exact_reviewed_ai_origin() -> None:
    workflow = _workflow(PAGES_WORKFLOW)
    assert workflow["env"]["RUFOUS_AI_URL"] == "https://rufous-ai.loughondata.com"

    for job_name in ("pages", "media_delta", "production"):
        build = next(
            step
            for step in workflow["jobs"][job_name]["steps"]
            if step.get("name") == "Build static public app"
        )
        assert build["env"]["VITE_RUFOUS_AI_URL"] == "${{ env.RUFOUS_AI_URL }}"
        assert build["env"]["VITE_RUFOUS_TURNSTILE_SITE_KEY"] == (
            "${{ vars.RUF_AI_TURNSTILE_SITE_KEY }}"
        )

    synthetic_build = next(
        step
        for step in workflow["jobs"]["synthetic"]["steps"]
        if step.get("name") == "Build static public app"
    )
    assert "env" not in synthetic_build


def test_repository_workflow_audit_accepts_the_isolated_worker_release() -> None:
    assert audit_workflow_runners(WORKFLOW_ROOT) == []
    assert audit_deploy_context(ROOT) == []
