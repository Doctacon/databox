"""Regression contract for Rufous's Pages-only release path."""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).parents[2]
WORKFLOW = ROOT / ".github" / "workflows" / "rufous-public.yaml"


def _workflow() -> dict[str, Any]:
    return yaml.load(WORKFLOW.read_text(encoding="utf-8"), Loader=yaml.BaseLoader)


def _route_script(workflow: dict[str, Any]) -> str:
    steps = workflow["jobs"]["route"]["steps"]
    return next(step["run"] for step in steps if step.get("id") == "route")


def _git(repository: Path, *arguments: str) -> str:
    result = subprocess.run(
        ["git", *arguments],
        cwd=repository,
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def _commit(repository: Path, changes: dict[str, str], message: str) -> str:
    for relative_path, content in changes.items():
        path = repository / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    _git(repository, "add", "--all")
    _git(
        repository,
        "-c",
        "user.name=Rufous Test",
        "-c",
        "user.email=rufous-test@example.invalid",
        "commit",
        "-m",
        message,
    )
    return _git(repository, "rev-parse", "HEAD")


def _route_push(repository: Path, script: str, before: str, head: str) -> str:
    return _run_route(
        repository,
        script,
        before=before,
        dispatch_mode="",
        event_name="push",
        head=head,
        release_ref="refs/heads/main",
    )


def _route_dispatch(repository: Path, script: str, dispatch_mode: str) -> str:
    return _run_route(
        repository,
        script,
        before="",
        dispatch_mode=dispatch_mode,
        event_name="workflow_dispatch",
        head="",
        release_ref="refs/heads/main",
    )


def _run_route(
    repository: Path,
    script: str,
    *,
    before: str,
    dispatch_mode: str,
    event_name: str,
    head: str,
    release_ref: str,
) -> str:
    output = repository / "github-output"
    output.unlink(missing_ok=True)
    environment = {
        **os.environ,
        "BEFORE_SHA": before,
        "DISPATCH_MODE": dispatch_mode,
        "EVENT_NAME": event_name,
        "GITHUB_OUTPUT": str(output),
        "HEAD_SHA": head,
        "RELEASE_REF": release_ref,
    }
    subprocess.run(
        ["bash", "-c", script],
        cwd=repository,
        env=environment,
        check=True,
        capture_output=True,
        text=True,
    )
    entries = dict(
        line.split("=", maxsplit=1) for line in output.read_text(encoding="utf-8").splitlines()
    )
    return entries["release_mode"]


def test_main_push_routes_only_app_changes_to_pages(tmp_path: Path) -> None:
    workflow = _workflow()
    script = _route_script(workflow)
    _git(tmp_path, "init", "--quiet")

    initial = _commit(
        tmp_path,
        {"app/src/main.ts": "initial\n", "README.md": "initial\n"},
        "initial",
    )
    app_only = _commit(
        tmp_path,
        {"app/src/main.ts": "browser-only change\n"},
        "app only",
    )
    mixed = _commit(
        tmp_path,
        {"app/src/main.ts": "mixed change\n", "README.md": "changed too\n"},
        "mixed",
    )
    _git(tmp_path, "mv", "README.md", "app/renamed-readme.md")
    _git(
        tmp_path,
        "-c",
        "user.name=Rufous Test",
        "-c",
        "user.email=rufous-test@example.invalid",
        "commit",
        "-m",
        "outside file moved into app",
    )
    moved_into_app = _git(tmp_path, "rev-parse", "HEAD")
    worker_only = _commit(
        tmp_path,
        {"workers/rufous-ai/src/index.ts": "worker-only change\n"},
        "isolated AI worker",
    )

    assert _route_push(tmp_path, script, initial, app_only) == "pages"
    assert _route_push(tmp_path, script, app_only, mixed) == "full"
    assert _route_push(tmp_path, script, mixed, moved_into_app) == "full"
    assert _route_push(tmp_path, script, moved_into_app, worker_only) == "none"


def test_media_refresh_is_manual_only_and_pushes_never_route_to_it(tmp_path: Path) -> None:
    workflow = _workflow()
    script = _route_script(workflow)
    _git(tmp_path, "init", "--quiet")

    initial = _commit(
        tmp_path,
        {
            "packages/databox/databox/public_media_delta.py": "initial\n",
            "tests/rufous_media/test_public_media_delta.py": "initial\n",
            "config/rufous-pinned-public-media.json": "initial\n",
            "config/rufous-wikimedia-public-media.json": "initial\n",
            "README.md": "initial\n",
        },
        "initial",
    )
    safe_delta = _commit(
        tmp_path,
        {
            "packages/databox/databox/public_media_delta.py": "delta implementation\n",
            "tests/rufous_media/test_public_media_delta.py": "delta tests\n",
        },
        "safe media delta",
    )
    pinned_media = _commit(
        tmp_path,
        {"config/rufous-pinned-public-media.json": "reviewed media pin\n"},
        "pin reviewed media",
    )
    curated_wikimedia = _commit(
        tmp_path,
        {"config/rufous-wikimedia-public-media.json": "curated candidates\n"},
        "curate Wikimedia candidates",
    )
    mixed = _commit(
        tmp_path,
        {
            "packages/databox/databox/public_media_delta.py": "another delta\n",
            "README.md": "unrelated change\n",
        },
        "mixed media delta",
    )
    app_mixed = _commit(
        tmp_path,
        {
            "packages/databox/databox/public_media_delta.py": "third delta\n",
            "app/src/main.ts": "browser change\n",
        },
        "app and media delta",
    )

    assert _route_dispatch(tmp_path, script, "media-refresh") == "media"
    assert _route_dispatch(tmp_path, script, "pages-only") == "pages"
    assert _route_dispatch(tmp_path, script, "full") == "full"
    assert _route_push(tmp_path, script, initial, safe_delta) == "full"
    assert _route_push(tmp_path, script, safe_delta, pinned_media) == "none"
    assert _route_push(tmp_path, script, pinned_media, curated_wikimedia) == "none"
    assert _route_push(tmp_path, script, curated_wikimedia, mixed) == "full"
    assert _route_push(tmp_path, script, mixed, app_mixed) == "full"


def test_audio_refresh_is_manual_and_any_audio_pin_change_does_not_deploy(
    tmp_path: Path,
) -> None:
    workflow = _workflow()
    script = _route_script(workflow)
    _git(tmp_path, "init", "--quiet")

    initial = _commit(
        tmp_path,
        {
            "config/rufous-public-audio-selection.json": "initial\n",
            "config/rufous-pinned-public-audio.json": "initial\n",
            "packages/databox/databox/public_audio_release.py": "initial\n",
        },
        "initial",
    )
    selection_only = _commit(
        tmp_path,
        {"config/rufous-public-audio-selection.json": "reviewed selection\n"},
        "review audio selection",
    )
    pin_only = _commit(
        tmp_path,
        {"config/rufous-pinned-public-audio.json": "reviewed pin\n"},
        "pin reviewed audio",
    )
    implementation = _commit(
        tmp_path,
        {"packages/databox/databox/public_audio_release.py": "implementation\n"},
        "implement audio release",
    )
    tests_only = _commit(
        tmp_path,
        {"tests/rufous_media/test_public_audio_release.py": "tests\n"},
        "test audio release",
    )

    assert _route_dispatch(tmp_path, script, "audio-refresh") == "audio"
    assert _route_push(tmp_path, script, initial, selection_only) == "none"
    assert _route_push(tmp_path, script, selection_only, pin_only) == "none"
    assert _route_push(tmp_path, script, pin_only, implementation) == "none"
    assert _route_push(tmp_path, script, implementation, tests_only) == "none"


def test_pages_job_cannot_publish_or_rebuild_r2_data() -> None:
    workflow = _workflow()
    pages = workflow["jobs"]["pages"]
    pages_readiness = workflow["jobs"]["readiness"]
    production_readiness = workflow["jobs"]["production_readiness"]
    serialized = json.dumps(pages)
    pages_configuration = json.dumps(pages_readiness)
    commands = "\n".join(step.get("run", "") for step in pages["steps"])

    assert "needs.route.outputs.release_mode == 'pages'" in pages["if"]
    assert "rm -rf app/dist/data" in commands
    assert "scripts/rufous_media/hydrate_rufous_public.py" not in commands
    assert "--shell-only" in commands
    assert "scripts/rufous_media/audit_rufous_public.py app/dist" in commands
    assert 'wrangler" pages deploy' in commands

    forbidden = (
        "RUFOUS_R2_BUCKET",
        "RUFOUS_R2_ACCOUNT_ID",
        "RUFOUS_R2_ACCESS_KEY_ID",
        "RUFOUS_R2_SECRET_ACCESS_KEY",
        "RUF_R2_ACCESS_KEY_ID",
        "RUF_R2_SECRET_ACCESS_KEY",
        "R2_ACCESS_KEY_ID",
        "R2_SECRET_ACCESS_KEY",
        "publish_rufous_public.py",
        "publish_rufous_media.py",
        "export_rufous_public.py",
        "hydrate_rufous_public.py",
        "load_dlt_quack.py",
        "load_rufous_usfws_media.py",
        "prepare_rufous_media.py",
        "sqlmesh_plan_rufous",
        "--r2",
    )
    assert not [token for token in forbidden if token in serialized]
    assert not [token for token in forbidden if token in pages_configuration]
    assert "needs.route.outputs.release_mode == 'full'" in production_readiness["if"]
    assert "needs.route.outputs.release_mode == 'media'" in production_readiness["if"]
    assert "needs.route.outputs.release_mode == 'audio'" in production_readiness["if"]


def test_explicit_media_refresh_targets_only_one_selected_provider() -> None:
    workflow = _workflow()
    dispatch_options = workflow["on"]["workflow_dispatch"]["inputs"]["release_mode"]["options"]
    provider_options = workflow["on"]["workflow_dispatch"]["inputs"]["media_provider"]["options"]
    media = workflow["jobs"]["media_delta"]
    steps = media["steps"]
    step_names = [step.get("name", "") for step in steps]
    commands = "\n".join(step.get("run", "") for step in steps)

    assert "media-refresh" in dispatch_options
    assert provider_options == ["inaturalist", "wikimedia"]
    assert "needs.route.outputs.release_mode == 'media'" in media["if"]
    assert "github.event_name == 'workflow_dispatch'" in media["if"]
    assert "github.event_name == 'push'" not in media["if"]
    assert "inputs.release_mode == 'media-refresh'" in media["if"]
    assert media["env"]["RUFOUS_MEDIA_PROVIDER"] == "${{ inputs.media_provider }}"
    assert "scripts/rufous_media/hydrate_rufous_public.py app/dist" in commands
    assert "load_pending_public_media_selections" in commands
    assert 'provider=os.environ["RUFOUS_MEDIA_PROVIDER"]' in commands
    assert "scripts/rufous_media/load_rufous_wikimedia_media.py" in commands
    assert "--input config/rufous-wikimedia-public-media.json" in commands
    assert "--targets-from-public-output app/dist" in commands
    assert "mkdir -p data" in commands
    assert 'duckdb.connect("data/databox.duckdb").close()' in commands
    assert "scripts/rufous_media/sqlmesh_plan_rufous_inaturalist_media.sh" in commands
    assert "scripts/rufous_media/prepare_rufous_media.py" in commands
    assert '--provider "$RUFOUS_MEDIA_PROVIDER"' in commands
    prepare_step = steps[step_names.index("Prepare only approved provider WebP candidates")]
    assert prepare_step["run"].splitlines()[0].endswith(" \\")
    assert "--approvals config/rufous-media-visual-approvals.json" in prepare_step["run"]
    assert "scripts/rufous_media/verify_rufous_media_approvals.py" in commands
    assert "scripts/rufous_media/compose_rufous_media_pin.py" in commands
    assert "--verify-pinned config/rufous-pinned-public-media.json" in commands
    assert "scripts/rufous_media/apply_rufous_media_delta.py" in commands
    assert "--active-root app/dist" in commands
    assert "--prepared-media-dir build/rufous-selected-media" in commands
    assert "--output-root build/rufous-public-data" in commands
    assert "scripts/rufous_media/audit_app_bundle.py" in commands
    assert "scripts/rufous_media/audit_rufous_public.py app/dist" in commands
    assert commands.count("python scripts/rufous_media/publish_rufous_media.py") == 2
    assert commands.count('--provider "$RUFOUS_MEDIA_PROVIDER"') >= 5
    assert commands.count("python scripts/rufous_media/publish_rufous_public.py") == 2

    pending_index = step_names.index("Identify only newly approved unpictured provider species")
    no_op_index = step_names.index("Stop cleanly when every approved image is already live")
    inaturalist_index = step_names.index("Refresh only newly committed iNaturalist selections")
    warehouse_index = step_names.index("Initialize the isolated Wikimedia media warehouse")
    wikimedia_index = step_names.index("Load only the committed offline Wikimedia metadata")
    prepare_index = step_names.index("Prepare only approved provider WebP candidates")
    assert (
        pending_index
        < no_op_index
        < inaturalist_index
        < warehouse_index
        < wikimedia_index
        < prepare_index
    )
    assert steps[no_op_index]["if"] == "steps.pending-media.outputs.pending_count == '0'"
    assert "env.RUFOUS_MEDIA_PROVIDER == 'inaturalist'" in steps[inaturalist_index]["if"]
    assert "env.RUFOUS_MEDIA_PROVIDER == 'wikimedia'" in steps[warehouse_index]["if"]
    assert "env.RUFOUS_MEDIA_PROVIDER == 'wikimedia'" in steps[wikimedia_index]["if"]
    for step in steps[prepare_index:]:
        assert step.get("if") == "steps.pending-media.outputs.pending_count != '0'"

    preflight_data = step_names.index("Preflight monotonic R2 activation before Pages deployment")
    preflight_media = step_names.index("Preflight only the approved provider media objects")
    publish_media = step_names.index("Publish only the approved provider media objects")
    deploy_pages = step_names.index("Deploy immutable static Pages release")
    activate_data = step_names.index("Publish and activate the audited immutable R2 delta release")
    assert preflight_data < publish_media
    assert preflight_media < publish_media < deploy_pages < activate_data

    forbidden = (
        "load_rufous_usfws_media.py",
        "--source gbif",
        "scripts/rufous_media/sqlmesh_plan_rufous_public.sh",
        "scripts/rufous_media/sqlmesh_plan_rufous_media.sh",
        "RUF_GNIS_URL",
        "gnis-arizona",
        "DomesticNames_AZ.txt",
        "scripts/rufous_media/export_rufous_public.py",
    )
    assert not [token for token in forbidden if token in commands]


def test_automatic_full_release_reuses_pinned_media_without_provider_work() -> None:
    workflow = _workflow()
    production_steps = workflow["jobs"]["production"]["steps"]
    step_names = [step.get("name", "") for step in production_steps]
    production_commands = "\n".join(step.get("run", "") for step in production_steps)

    verify_index = step_names.index("Verify the pinned immutable media catalog")
    export_index = step_names.index("Export licensed static public projection")
    assert verify_index < export_index
    assert "--manifest config/rufous-pinned-public-media.json" in production_commands
    assert "--media-manifest config/rufous-pinned-public-media.json" in production_commands
    assert "--media-approvals config/rufous-media-visual-approvals.json" in production_commands
    assert "rm -rf app/dist/data" in production_commands
    assert (
        "scripts/rufous_media/audit_rufous_public.py app/dist --shell-only" in production_commands
    )
    assert (
        "scripts/rufous_media/audit_rufous_public.py build/rufous-public-data"
        in production_commands
    )
    assert '"$RUFOUS_PUBLIC_DATA_URL/manifest.json"' in production_commands
    assert '"$RUF_PUBLIC_URL/data/manifest.json"' not in production_commands

    forbidden = (
        "load_rufous_usfws_media.py",
        "load_rufous_wikimedia_media.py",
        "databox.public_inaturalist_media_ingest",
        "scripts/rufous_media/sqlmesh_plan_rufous_media.sh",
        "scripts/rufous_media/sqlmesh_plan_rufous_inaturalist_media.sh",
        "scripts/rufous_media/prepare_rufous_media.py",
        "scripts/rufous_media/publish_rufous_media.py",
        "actions/cache/restore",
        "actions/cache/save",
        "scripts/rufous_media/hydrate_rufous_public.py",
        "commons.wikimedia.org",
        "upload.wikimedia.org",
    )
    assert not [token for token in forbidden if token in production_commands]


def test_full_release_loads_avonet_through_its_independent_job() -> None:
    workflow = _workflow()
    steps = workflow["jobs"]["production"]["steps"]
    step_names = [step.get("name", "") for step in steps]

    avonet_name = "Load the pinned AVONET trait snapshot independently"
    gbif_name = "Refresh and model the licensed GBIF publication warehouse"
    avonet_index = step_names.index(avonet_name)
    gbif_index = step_names.index(gbif_name)
    avonet_step = steps[avonet_index]
    gbif_step = steps[gbif_index]

    assert avonet_index < gbif_index
    assert avonet_step["env"] == {"PYTHONPATH": "${{ github.workspace }}"}
    assert 'mkdir -p data "$DAGSTER_HOME"' in avonet_step["run"]
    assert (
        "uv run dg launch --target-path packages/databox --job avonet_ingest" in avonet_step["run"]
    )
    assert "scripts/sources/load_dlt_quack.py" in gbif_step["run"]
    assert "--source gbif" in gbif_step["run"]
    assert "--source avonet" not in gbif_step["run"]
    assert "--database data/databox.duckdb" in gbif_step["run"]
    assert "bash scripts/rufous_media/sqlmesh_plan_rufous_public.sh" in gbif_step["run"]


def test_explicit_audio_refresh_separates_untrusted_media_from_r2_credentials() -> None:
    workflow = _workflow()
    dispatch_options = workflow["on"]["workflow_dispatch"]["inputs"]["release_mode"]["options"]
    prepare = workflow["jobs"]["audio_prepare"]
    upload = workflow["jobs"]["audio_delta"]
    prepare_steps = prepare["steps"]
    upload_steps = upload["steps"]
    prepare_names = [step.get("name", "") for step in prepare_steps]
    upload_names = [step.get("name", "") for step in upload_steps]
    prepare_commands = "\n".join(step.get("run", "") for step in prepare_steps)
    upload_commands = "\n".join(step.get("run", "") for step in upload_steps)

    assert "audio-refresh" in dispatch_options
    for job in (prepare, upload):
        assert "needs.route.outputs.release_mode == 'audio'" in job["if"]
        assert "github.event_name == 'workflow_dispatch'" in job["if"]
        assert "github.event_name == 'push'" not in job["if"]
        assert "inputs.release_mode == 'audio-refresh'" in job["if"]
    assert "needs.audio_prepare.result == 'success'" in upload["if"]
    assert "Verify this revision is still the main branch head" in prepare_names
    assert "Verify this revision is still the main branch head" in upload_names
    assert "tests/rufous_media/test_public_audio_export.py" in prepare_commands
    assert "tests/rufous_media/test_public_audio_release.py" in prepare_commands
    assert "tests/rufous_media/test_public_audio_selection.py" in prepare_commands
    assert "tests/rufous_media/test_rufous_public_workflow.py" in prepare_commands
    assert (
        "python -m databox.public_audio_release acquire "
        "--selection config/rufous-public-audio-selection.json "
        "--output build/rufous-public-audio"
    ) in " ".join(prepare_commands.split())
    toolchain_step = prepare_steps[
        prepare_names.index("Build the checksum-pinned FFmpeg sanitizer")
    ]
    assert prepare["runs-on"] == "ubuntu-24.04"
    assert "https://ffmpeg.org/releases/ffmpeg-7.1.1.tar.xz" in toolchain_step["run"]
    assert (
        "733984395e0dbbe5c046abda2dc49a5544e7e0e1e2366bba849222ae9e3a03b1"
        in (toolchain_step["run"])
    )
    assert "sha256sum --check --strict" in toolchain_step["run"]
    assert "--disable-autodetect" in toolchain_step["run"]
    assert "setup-ffmpeg" not in json.dumps(prepare_steps)
    cache_save_step = next(
        step for step in prepare_steps if "actions/cache/save@" in step.get("uses", "")
    )
    prepare_cache_restore_step = next(
        step for step in prepare_steps if "actions/cache/restore@" in step.get("uses", "")
    )
    cache_restore_step = next(
        step for step in upload_steps if "actions/cache/restore@" in step.get("uses", "")
    )
    cache_key = "rufous-public-audio-${{ hashFiles('config/rufous-pinned-public-audio.json') }}"
    assert cache_save_step["with"] == {
        "path": "build/rufous-public-audio",
        "key": cache_key,
    }
    assert prepare_cache_restore_step["with"] == {
        "path": "build/rufous-public-audio",
        "key": cache_key,
    }
    assert cache_restore_step["with"] == {
        "path": "build/rufous-public-audio",
        "key": cache_key,
        "fail-on-cache-miss": "true",
    }
    assert "restore-keys" not in cache_restore_step["with"]
    assert "restore-keys" not in prepare_cache_restore_step["with"]
    cache_miss_condition = "steps.audio_cache.outputs.cache-hit != 'true'"
    for name in (
        "Build the checksum-pinned FFmpeg sanitizer",
        "Verify the pinned audio sanitizer toolchain",
        "Test the bounded public audio release path",
        "Reproduce every reviewed object without cloud credentials",
        "Verify the complete prepared package without cloud credentials",
        "Cache the verified package for the isolated upload job",
    ):
        assert prepare_steps[prepare_names.index(name)]["if"] == cache_miss_condition
    assert "databox.public_audio_release verify-preverified" in prepare_commands
    assert "actions/upload-artifact@" not in json.dumps(prepare_steps)
    assert "actions/download-artifact@" not in json.dumps(upload_steps)
    assert "secrets." not in json.dumps(prepare_steps)

    assert "databox.public_audio_release acquire" not in upload_commands
    assert "databox.public_audio_release ensure-r2" not in upload_commands
    assert "databox.public_audio_release verify-preverified" in upload_commands
    assert (
        "python -m databox.public_audio_release publish-preverified-r2 "
        "--source build/rufous-public-audio "
        "--selection config/rufous-public-audio-selection.json"
    ) in " ".join(upload_commands.split())
    upload_step = upload_steps[
        upload_names.index("Upload pinned bytes without provider or media-parser access")
    ]
    assert upload_step["env"] == {
        "RUFOUS_R2_ACCOUNT_ID": "${{ secrets.CLOUDFLARE_ACCOUNT_ID }}",
        "RUFOUS_R2_ACCESS_KEY_ID": (
            "${{ secrets.RUF_R2_ACCESS_KEY_ID }}"  # secret-scan: allow
        ),
        "RUFOUS_R2_SECRET_ACCESS_KEY": (
            "${{ secrets.RUF_R2_SECRET_ACCESS_KEY }}"  # secret-scan: allow
        ),
    }
    assert "publish-preverified-r2" in upload_step["run"]
    assert "verify" not in upload_step["run"]

    forbidden = (
        "wrangler",
        "pages deploy",
        "publish_rufous_public.py",
        "export_rufous_public.py",
        "hydrate_rufous_public.py",
        "load_dlt_quack.py",
        "sqlmesh_plan_rufous",
        "app/dist",
    )
    combined_commands = f"{prepare_commands}\n{upload_commands}"
    assert not [token for token in forbidden if token in combined_commands]


def test_production_deployment_is_paused_fail_closed() -> None:
    workflow = _workflow()

    assert workflow["jobs"]["production"]["if"] == "${{ false }}"


def test_automatic_releases_verify_audio_without_contacting_sources() -> None:
    workflow = _workflow()
    production = workflow["jobs"]["production"]
    steps = production["steps"]
    commands = "\n".join(step.get("run", "") for step in steps)

    assert "databox.public_audio_release verify-pin" in commands
    assert "databox.public_audio_release verify-r2" in commands
    assert "config/rufous-public-audio-selection.json" in commands
    assert "config/rufous-pinned-public-audio.json" in commands
    assert "--audio-manifest config/rufous-pinned-public-audio.json" in commands
    assert "tests/rufous_media/test_public_audio_export.py" in commands
    assert "tests/rufous_media/test_public_audio_release.py" in commands
    assert "databox.public_audio_release ensure-r2" not in commands

    step_names = [step.get("name", "") for step in steps]
    verify_r2 = steps[step_names.index("Verify every pinned immutable audio object exists in R2")]
    assert verify_r2["env"] == {
        "RUFOUS_R2_ACCOUNT_ID": "${{ secrets.CLOUDFLARE_ACCOUNT_ID }}",
        "RUFOUS_R2_ACCESS_KEY_ID": (
            "${{ secrets.RUF_R2_ACCESS_KEY_ID }}"  # secret-scan: allow
        ),
        "RUFOUS_R2_SECRET_ACCESS_KEY": (
            "${{ secrets.RUF_R2_SECRET_ACCESS_KEY }}"  # secret-scan: allow
        ),
    }
    assert step_names.index(
        "Verify every pinned immutable audio object exists in R2"
    ) < step_names.index("Deploy immutable static Pages release")

    for job_name in ("synthetic", "pages", "production"):
        automatic_commands = "\n".join(
            step.get("run", "") for step in workflow["jobs"][job_name]["steps"]
        )
        assert "ensure-r2" not in automatic_commands

    workflow_paths = workflow["on"]["push"]["paths"]
    pull_request_paths = workflow["on"]["pull_request"]["paths"]
    required_paths = (
        "config/rufous-public-audio-selection.json",
        "config/rufous-pinned-public-audio.json",
        "packages/databox/databox/public_audio*.py",
        "tests/rufous_media/test_public_audio*.py",
    )
    for path in required_paths:
        assert path in workflow_paths
        assert path in pull_request_paths


def test_only_manual_media_refresh_can_contact_media_providers() -> None:
    workflow = _workflow()
    automatic_jobs = ("pages", "production")
    forbidden = (
        "load_rufous_usfws_media.py",
        "load_rufous_wikimedia_media.py",
        "databox.public_inaturalist_media_ingest",
        "prepare_rufous_media.py",
        "publish_rufous_media.py",
        "hydrate_rufous_public.py",
        "commons.wikimedia.org",
        "upload.wikimedia.org",
    )
    for job_name in automatic_jobs:
        commands = "\n".join(step.get("run", "") for step in workflow["jobs"][job_name]["steps"])
        assert not [token for token in forbidden if token in commands]

    manual_commands = "\n".join(
        step.get("run", "") for step in workflow["jobs"]["media_delta"]["steps"]
    )
    assert "databox.public_inaturalist_media_ingest" in manual_commands
    assert "prepare_rufous_media.py" in manual_commands
    assert "publish_rufous_media.py" in manual_commands
