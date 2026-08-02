"""Hard-zero-cost static-site invariant tests."""

from __future__ import annotations

import json
from pathlib import Path

from databox.public_export import export_public_data
from databox.public_export_audit import (
    MAX_FILE_BYTES,
    audit_deploy_context,
    audit_public_site,
    audit_workflow_runners,
)


def _synthetic_site(tmp_path: Path) -> Path:
    site = tmp_path / "site"
    export_public_data(mode="synthetic", output_dir=site)
    return site


def test_synthetic_contract_passes_cost_privacy_audit(tmp_path: Path) -> None:
    site = _synthetic_site(tmp_path)
    workflows = tmp_path / "workflows"
    workflows.mkdir()
    (workflows / "public.yml").write_text(
        "jobs:\n  build:\n    runs-on: ubuntu-latest\n", encoding="utf-8"
    )
    assert audit_public_site(site, workflows) == []


def test_audit_rejects_functions_bindings_metered_services_and_oversized_files(
    tmp_path: Path,
) -> None:
    site = _synthetic_site(tmp_path)
    functions = site / "functions"
    functions.mkdir()
    (functions / "api.js").write_text("fetch('https://api.mapbox.com')", encoding="utf-8")
    assets = site / "assets"
    assets.mkdir()
    (assets / "local-client.js").write_text(
        "fetch('/api/targets'); fetch('https://rufous.example.workers.dev')",
        encoding="utf-8",
    )
    (site / "wrangler.toml").write_text("[[d1_databases]]\nbinding='DB'", encoding="utf-8")
    oversized = site / "large.bin"
    with oversized.open("wb") as stream:
        stream.truncate(MAX_FILE_BYTES + 1)

    findings = audit_public_site(site)
    assert any("Pages Functions" in item for item in findings)
    assert any("Worker/Pages Functions entrypoint" in item for item in findings)
    assert any("metered Cloudflare binding" in item for item in findings)
    assert any("exceeds 25 MiB" in item for item in findings)
    assert any("api.mapbox.com" in item for item in findings)
    assert any("workers.dev" in item for item in findings)
    assert any("local-only application marker" in item for item in findings)


def test_audit_rejects_runtime_files_in_repository_deploy_context(tmp_path: Path) -> None:
    repository = tmp_path / "repository"
    (repository / "functions").mkdir(parents=True)
    (repository / "app").mkdir()
    (repository / "app/wrangler.toml").write_text("name='dynamic'", encoding="utf-8")
    (repository / ".wrangler/deploy").mkdir(parents=True)

    findings = audit_deploy_context(repository)

    assert any("functions" in item for item in findings)
    assert any("app/wrangler.toml" in item for item in findings)
    assert any(".wrangler/deploy" in item for item in findings)


def test_audit_requires_one_coherent_revalidation_policy_for_all_data(tmp_path: Path) -> None:
    site = _synthetic_site(tmp_path)
    (site / "index.html").write_text("<!doctype html>", encoding="utf-8")
    headers = site / "_headers"
    headers.write_text(
        "/data/*\n  Cache-Control: public, max-age=3600, stale-while-revalidate=86400\n"
        "/data/manifest.json\n  Cache-Control: no-cache, max-age=0, must-revalidate\n",
        encoding="utf-8",
    )

    findings = audit_public_site(site)

    assert any("manifest and shards cannot mix releases" in item for item in findings)

    headers.write_text(
        "/data/*\n  Cache-Control: no-cache, max-age=0, must-revalidate\n"
        "/data/cells/*\n  Cache-Control: public, max-age=3600\n",
        encoding="utf-8",
    )
    assert any(
        "manifest and shards cannot mix releases" in item for item in audit_public_site(site)
    )

    headers.write_text(
        "/data/*\n  Cache-Control: no-cache, max-age=0, must-revalidate\n"
        "/data/cells/*\n  Cache-Control: no-cache, max-age=0, must-revalidate\n",
        encoding="utf-8",
    )
    assert audit_public_site(site) == []


def test_audit_rejects_forbidden_personal_field_and_license(tmp_path: Path) -> None:
    site = _synthetic_site(tmp_path)
    manifest = json.loads((site / "data/manifest.json").read_text())
    profile_path = site / str(manifest["species"][0]["profile_path"]).removeprefix("/")
    profile = json.loads(profile_path.read_text())
    profile["email"] = "visitor@example.com"
    profile["media"] = [
        {
            "kind": "photo",
            "provider": "inaturalist",
            "url": "https://example.com/photo.jpg",
            "source_url": "https://example.com/item",
            "creator": "Creator",
            "license": "CC BY-NC 4.0",
            "license_url": "https://creativecommons.org/licenses/by-nc/4.0/",
            "attribution_id": "bad",
        }
    ]
    profile_path.write_text(json.dumps(profile), encoding="utf-8")
    findings = audit_public_site(site)
    assert any("forbidden field email" in item for item in findings)
    assert any("media license is not allowed" in item for item in findings)


def test_audit_rejects_hitchhiking_raw_data_and_unreferenced_personal_json(
    tmp_path: Path,
) -> None:
    site = _synthetic_site(tmp_path)
    (site / "warehouse.duckdb").write_bytes(b"\x00" * 8 + b"DUCK" + b"\x00" * 4)
    (site / "observations.csv").write_text("email\nvisitor@example.com\n", encoding="utf-8")
    (site / "private.json").write_text(
        json.dumps({"nested": {"email": "visitor@example.com"}}),
        encoding="utf-8",
    )

    findings = audit_public_site(site)

    assert any("warehouse.duckdb is a forbidden raw/database artifact" in item for item in findings)
    assert any(
        "warehouse.duckdb contains a database/storage file signature" in item for item in findings
    )
    assert any("observations.csv is a forbidden raw/database artifact" in item for item in findings)
    assert any("private.json is JSON outside the public data contract" in item for item in findings)
    assert any("private.json exposes forbidden field nested.email" in item for item in findings)


def test_audit_rejects_production_with_direct_ebird_or_wrong_gbif_dataset(
    tmp_path: Path,
) -> None:
    site = _synthetic_site(tmp_path)
    manifest_path = site / "data/manifest.json"
    manifest = json.loads(manifest_path.read_text())
    manifest["release_mode"] = "production"
    manifest["source_policy"] = {
        "direct_ebird": "included",
        "occurrence_source": "ebird",
        "gbif_dataset_key": "wrong",
        "coverage": "unknown",
        "required_taxon_key": None,
    }
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    findings = audit_public_site(site)
    assert any("exclude direct eBird" in item for item in findings)


def test_workflow_audit_rejects_paid_and_dynamic_runners(tmp_path: Path) -> None:
    workflows = tmp_path / "workflows"
    workflows.mkdir()
    (workflows / "bad.yaml").write_text(
        "jobs:\n"
        "  paid:\n    runs-on: ubuntu-latest-16-cores\n"
        "  dynamic:\n    runs-on: ${{ matrix.runner }}\n",
        encoding="utf-8",
    )
    findings = audit_workflow_runners(workflows)
    assert len(findings) == 2
    assert all("non-free/nonstandard" in item for item in findings)


def test_workflow_audit_rejects_untrusted_privileged_workflow_run(tmp_path: Path) -> None:
    workflows = tmp_path / "workflows"
    workflows.mkdir()
    (workflows / "unsafe.yaml").write_text(
        "on:\n  workflow_run:\n    workflows: [CI]\n  workflow_dispatch:\n"
        "jobs:\n  deploy:\n    runs-on: ubuntu-latest\n"
        "    env:\n      TOKEN: ${{ secrets.DEPLOY_TOKEN }}\n"
        "    steps:\n      - run: npx wrangler pages deploy app/dist\n",
        encoding="utf-8",
    )

    findings = audit_workflow_runners(workflows)

    assert sum("without trust guard" in item for item in findings) == 5
    assert any("outside main" in item for item in findings)
    assert any("isolated runner temp" in item for item in findings)
    assert any("deployment hazard path '.github/workflows/**'" in item for item in findings)


def test_workflow_audit_rejects_data_only_skip_for_application_release(tmp_path: Path) -> None:
    workflows = tmp_path / "workflows"
    workflows.mkdir()
    (workflows / "unsafe.yaml").write_text(
        "on:\n  schedule:\n    - cron: '0 */6 * * *'\n"
        "jobs:\n  deploy:\n    runs-on: ubuntu-latest\n"
        "    steps:\n      - run: new_version=data_version\n"
        "      - run: npx wrangler pages deploy app/dist\n",
        encoding="utf-8",
    )

    findings = audit_workflow_runners(workflows)

    assert any("may skip application releases" in item for item in findings)
