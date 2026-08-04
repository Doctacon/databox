"""Public-release safety invariant tests."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from databox.public_export import export_public_data
from databox.public_export_audit import (
    MAX_FILE_BYTES,
    audit_deploy_context,
    audit_public_site,
    audit_workflow_runners,
)

_REVIEWED_CSP = (
    "/*\n"
    "  Content-Security-Policy: default-src 'self'; "
    "img-src 'self' data: blob: https://rufous-data.loughondata.com; "
    "media-src 'self' https://rufous-data.loughondata.com; "
    "connect-src 'self' https://tiles.openfreemap.org "
    "https://rufous-data.loughondata.com; "
    "frame-ancestors https://loughondata.com https://www.loughondata.com\n"
)
_REVIEWED_SPA_REDIRECTS = (
    "/birds / 200\n"
    "/credits / 200\n"
    "/map / 200\n"
    "/my-birds / 200\n"
    "/birds/:species/find / 200\n"
    "/birds/:species / 200\n"
    "/target-plans/:plan / 200\n"
)


def _synthetic_site(tmp_path: Path) -> Path:
    site = tmp_path / "site"
    export_public_data(mode="synthetic", output_dir=site)
    return site


def _attach_synthetic_usfws_media(site: Path, **overrides: object) -> None:
    manifest_path = site / "data/manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    summary = manifest["species"][0]
    profile_path = site / str(summary["profile_path"]).removeprefix("/")
    profile = json.loads(profile_path.read_text(encoding="utf-8"))
    digest = "d" * 64
    media: dict[str, object] = {
        "kind": "photo",
        "provider": "usfws",
        "media_id": "usfws-" + "a" * 24,
        "url": (
            "https://rufous-data.loughondata.com/rufous-media/v1/objects/"
            f"{digest[:2]}/{digest}.webp"
        ),
        "source_url": "https://www.fws.gov/media/annas-hummingbird",
        "creator": "Jane Birder/USFWS",
        "license": "Public Domain",
        "license_url": "https://www.fws.gov/notices",
        "attribution_id": "usfws-attribution-" + "b" * 24,
        "scientific_name": profile["scientific_name"],
        "title": "Anna's Hummingbird at flowers",
        "caption": "An adult hummingbird feeds at desert flowers.",
        "alt_text": "An Anna's Hummingbird feeding at red flowers.",
        "width": 650,
        "height": 433,
        "mime_type": "image/webp",
        "sha256": digest,
    }
    media.update(overrides)
    profile["media"] = [media]
    summary["hero_photo"] = media
    summary["photo_count"] = 1
    manifest["counts"]["media_items"] = 1
    manifest["counts"]["species_with_media"] = 1
    manifest["source_policy"]["media_source"] = "usfws"
    manifest["source_policy"]["media_delivery"] = "immutable_r2"
    profile_path.write_text(json.dumps(profile), encoding="utf-8")
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")


def test_synthetic_contract_passes_cost_privacy_audit(tmp_path: Path) -> None:
    site = _synthetic_site(tmp_path)
    workflows = tmp_path / "workflows"
    workflows.mkdir()
    (workflows / "public.yml").write_text(
        "jobs:\n  build:\n    runs-on: ubuntu-latest\n", encoding="utf-8"
    )
    assert audit_public_site(site, workflows) == []


def test_audit_accepts_ordinary_usfws_bird_media(tmp_path: Path) -> None:
    site = _synthetic_site(tmp_path)
    _attach_synthetic_usfws_media(site)

    assert audit_public_site(site) == []


def test_audit_accepts_ordinary_names_dates_dimensions_and_public_source_url(
    tmp_path: Path,
) -> None:
    site = _synthetic_site(tmp_path)
    _attach_synthetic_usfws_media(
        site,
        creator="Dr. Jane Q. Birder / USFWS",
        title="Twelve hummingbirds near Desert Road",
        caption="About 7,000 feathers; photographed 08/03/2026 at 650 x 433 pixels.",
        alt_text="Bird image from the public USFWS media catalog.",
        source_url="https://www.fws.gov/media/2026-08-03-hummingbird-photo",
    )

    assert audit_public_site(site) == []


@pytest.mark.parametrize(
    ("override", "field", "reason"),
    [
        ({"creator": "Jane Birder <jane@example.org>"}, "creator", "email_address"),
        ({"caption": "Call (602) 555-0199 for access."}, "caption", "phone_number"),
        ({"title": "Nest behind 123 Example Street"}, "title", "postal_address"),
        ({"caption": "Mail permit to P.O. Box 1234"}, "caption", "postal_address"),
        ({"alt_text": "Private nest at 33.4484, -112.0740"}, "alt_text", "precise_coordinates"),
        ({"caption": "GPS: 33.4, -112.1"}, "caption", "precise_coordinates"),
        ({"title": "Nest at 33° 26.5' N"}, "title", "precise_coordinates"),
    ],
)
def test_audit_rejects_obvious_contact_pii_and_private_locations_in_usfws_text(
    tmp_path: Path,
    override: dict[str, object],
    field: str,
    reason: str,
) -> None:
    site = _synthetic_site(tmp_path)
    _attach_synthetic_usfws_media(site, **override)

    findings = audit_public_site(site)

    assert any(f"USFWS {field} exposes {reason}" in finding for finding in findings)


def test_audit_rejects_usfws_media_page_with_trailing_hyphen(tmp_path: Path) -> None:
    site = _synthetic_site(tmp_path)
    _attach_synthetic_usfws_media(
        site,
        source_url="https://www.fws.gov/media/annas-hummingbird-",
    )

    assert any(
        "source_url is not an official media page" in finding for finding in audit_public_site(site)
    )


@pytest.mark.parametrize(
    ("override", "reason"),
    [
        ({"title": "U.S. Fish & Wildlife Service word-mark"}, "service_or_agency"),
        ({"caption": "2026 Federal Duck Stamp artwork"}, "federal_or_junior"),
        (
            {"alt_text": "Federal Aid in Sport Fish Restoration symbol"},
            "federal_aid_restoration",
        ),
        (
            {"source_url": "https://www.fws.gov/media/blue-goose-refuge-mark"},
            "blue_goose_refuge",
        ),
    ],
)
def test_audit_rejects_normalized_restricted_usfws_marks(
    tmp_path: Path,
    override: dict[str, object],
    reason: str,
) -> None:
    site = _synthetic_site(tmp_path)
    _attach_synthetic_usfws_media(site, **override)

    findings = audit_public_site(site)

    assert any("restricted mark" in finding and reason in finding for finding in findings)


def test_audit_rejects_unreviewed_r2_endpoints_and_broad_connect_policy(
    tmp_path: Path,
) -> None:
    site = _synthetic_site(tmp_path)
    (site / "index.html").write_text("<!doctype html>", encoding="utf-8")
    (site / "assets").mkdir()
    (site / "assets/client.js").write_text(
        "fetch('https://rufous.example.r2.dev/manifest.json?X-Amz-Signature=secret')",
        encoding="utf-8",
    )
    (site / "_headers").write_text(
        "/*\n"
        "  Content-Security-Policy: default-src 'self'; "
        "connect-src 'self' https:; frame-ancestors *\n"
        "/data/*\n"
        "  Cache-Control: no-cache, max-age=0, must-revalidate\n",
        encoding="utf-8",
    )

    findings = audit_public_site(site)

    assert any(".r2.dev" in item for item in findings)
    assert any("x-amz-signature" in item.casefold() for item in findings)
    assert any("connect-src" in item for item in findings)
    assert any("frame-ancestors" in item for item in findings)


def test_audit_rejects_broad_or_duplicate_image_and_media_csp_sources(
    tmp_path: Path,
) -> None:
    site = _synthetic_site(tmp_path)
    (site / "index.html").write_text("<!doctype html>", encoding="utf-8")
    (site / "_headers").write_text(
        "/*\n"
        "  Content-Security-Policy: default-src 'self'; "
        "img-src 'self' data: blob: https:; img-src 'self' https:; "
        "media-src https:; "
        "connect-src 'self' https://tiles.openfreemap.org "
        "https://rufous-data.loughondata.com; "
        "frame-ancestors https://loughondata.com https://www.loughondata.com\n"
        "/data/*\n  Cache-Control: no-cache, max-age=0, must-revalidate\n",
        encoding="utf-8",
    )

    findings = audit_public_site(site)

    assert any("must not repeat directives" in item for item in findings)
    assert any("img-src" in item for item in findings)
    assert any("media-src" in item for item in findings)


def test_audit_rejects_local_human_review_bundle_marker(tmp_path: Path) -> None:
    site = _synthetic_site(tmp_path)
    (site / "index.html").write_text(
        "<!doctype html>RUF_LOCAL_MEDIA_REVIEW_ONLY_DO_NOT_DEPLOY",
        encoding="utf-8",
    )
    (site / "_headers").write_text(
        _REVIEWED_CSP + "/data/*\n  Cache-Control: no-cache, max-age=0, must-revalidate\n",
        encoding="utf-8",
    )

    findings = audit_public_site(site)

    assert any("local-only application marker" in item for item in findings)


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
        _REVIEWED_CSP
        + "/data/*\n  Cache-Control: public, max-age=3600, stale-while-revalidate=86400\n"
        "/data/manifest.json\n  Cache-Control: no-cache, max-age=0, must-revalidate\n",
        encoding="utf-8",
    )

    findings = audit_public_site(site)

    assert any("manifest and shards cannot mix releases" in item for item in findings)

    headers.write_text(
        _REVIEWED_CSP + "/data/*\n  Cache-Control: no-cache, max-age=0, must-revalidate\n"
        "/data/cells/*\n  Cache-Control: public, max-age=3600\n",
        encoding="utf-8",
    )
    assert any(
        "manifest and shards cannot mix releases" in item for item in audit_public_site(site)
    )

    headers.write_text(
        _REVIEWED_CSP + "/data/*\n  Cache-Control: no-cache, max-age=0, must-revalidate\n"
        "/data/cells/*\n  Cache-Control: no-cache, max-age=0, must-revalidate\n",
        encoding="utf-8",
    )
    (site / "404.html").write_text("<!doctype html><title>Not found</title>", encoding="utf-8")
    (site / "_redirects").write_text(_REVIEWED_SPA_REDIRECTS, encoding="utf-8")
    assert audit_public_site(site) == []


def test_audit_rejects_html_fallback_and_custom_caching_for_static_assets(
    tmp_path: Path,
) -> None:
    site = _synthetic_site(tmp_path)
    (site / "index.html").write_text("<!doctype html>", encoding="utf-8")
    (site / "_redirects").write_text("/* /index.html 200\n", encoding="utf-8")
    (site / "_headers").write_text(
        _REVIEWED_CSP + "/data/*\n  Cache-Control: no-cache, max-age=0, must-revalidate\n"
        "/assets/*\n  Cache-Control: public, max-age=31536000, immutable\n",
        encoding="utf-8",
    )

    findings = audit_public_site(site)

    assert any("top-level 404.html" in finding for finding in findings)
    assert any("reviewed client-side routes" in finding for finding in findings)
    assert any("default caching outside /data" in finding for finding in findings)

    (site / "404.html").write_text("<!doctype html><title>Not found</title>", encoding="utf-8")
    (site / "_redirects").write_text(_REVIEWED_SPA_REDIRECTS, encoding="utf-8")
    (site / "_headers").write_text(
        _REVIEWED_CSP + "  Cache-Control: public, max-age=31536000, immutable\n"
        "/data/*\n  Cache-Control: no-cache, max-age=0, must-revalidate\n",
        encoding="utf-8",
    )
    assert any("default caching outside /data" in finding for finding in audit_public_site(site))

    (site / "assets").mkdir()
    (site / "assets/legacy.js").write_text("export {};", encoding="utf-8")
    (site / "_headers").write_text(
        _REVIEWED_CSP + "/data/*\n  Cache-Control: no-cache, max-age=0, must-revalidate\n",
        encoding="utf-8",
    )
    assert any("cache-recovery generation" in finding for finding in audit_public_site(site))

    (site / "assets/legacy.js").rename(site / "assets/client-g2-current.js")

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


def test_workflow_audit_requires_committed_human_gate_on_each_media_publisher(
    tmp_path: Path,
) -> None:
    workflows = tmp_path / "workflows"
    workflows.mkdir()
    (workflows / "unsafe.yaml").write_text(
        "jobs:\n  deploy:\n    runs-on: ubuntu-latest\n"
        "    steps:\n"
        "      - run: >-\n"
        "          python scripts/publish_rufous_media.py\n"
        "          --source build/rufous-media\n"
        "          --r2\n"
        "      - run: python scripts/verify_rufous_media_approvals.py\n",
        encoding="utf-8",
    )

    findings = audit_workflow_runners(workflows)

    assert any("--media-approvals" in item for item in findings)
    assert any("publisher omits" in item for item in findings)
    assert any("before cloud publishers" in item for item in findings)
