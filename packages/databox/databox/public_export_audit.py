"""Cost, privacy, source-boundary, and licensing audit for public Rufous."""

from __future__ import annotations

import argparse
import json
import re
from datetime import date
from pathlib import Path
from typing import Any

from databox.public_export import (
    ALLOWED_LICENSES,
    GBIF_EBIRD_EOD_DATASET_KEY,
    GBIF_EBIRD_EOD_DISCLAIMER,
    GBIF_EBIRD_EOD_PUBLISHER,
    GBIF_RUFOUS_TAXON_KEY,
    SCHEMA_VERSION,
    canonical_license,
)

MAX_FILES = 20_000
MAX_FILE_BYTES = 25 * 1024 * 1024
_FORBIDDEN_ENTRYPOINTS = frozenset(
    {
        "_worker.js",
        "worker.js",
        "worker.mjs",
        "worker.ts",
        "wrangler.toml",
        "wrangler.json",
        "wrangler.jsonc",
    }
)
_FORBIDDEN_RAW_SUFFIXES = frozenset(
    {
        ".arrow",
        ".avro",
        ".csv",
        ".db",
        ".duckdb",
        ".dump",
        ".feather",
        ".jsonl",
        ".ndjson",
        ".orc",
        ".parquet",
        ".sql",
        ".sqlite",
        ".sqlite3",
        ".tsv",
        ".wal",
    }
)
_ALLOWED_STATIC_SUFFIXES = frozenset(
    {
        ".css",
        ".gif",
        ".html",
        ".ico",
        ".jpeg",
        ".jpg",
        ".js",
        ".json",
        ".map",
        ".mjs",
        ".png",
        ".svg",
        ".txt",
        ".webmanifest",
        ".webp",
        ".woff",
        ".woff2",
        ".xml",
    }
)
_ALLOWED_EXTENSIONLESS = frozenset({"_headers", "_redirects"})
_FORBIDDEN_BINDING_PATTERNS = (
    re.compile(r"\bd1_databases\b", re.IGNORECASE),
    re.compile(r"\bkv_namespaces\b", re.IGNORECASE),
    re.compile(r"\br2_buckets\b", re.IGNORECASE),
    re.compile(r"\bdurable_objects\b", re.IGNORECASE),
    re.compile(r"\bqueue(?:s|_producers|_consumers)\b", re.IGNORECASE),
    re.compile(r"\bsend_email\b", re.IGNORECASE),
    re.compile(r"\banalytics_engine_datasets\b", re.IGNORECASE),
    re.compile(r"\bvectorize\b", re.IGNORECASE),
    re.compile(r"\bhyperdrive\b", re.IGNORECASE),
)
_FORBIDDEN_SERVICE_HOSTS = (
    "api.mapbox.com",
    "tiles.mapbox.com",
    "maps.googleapis.com",
    "maps.google.com",
    "api.maptiler.com",
    "api.openweathermap.org",
    "api.open-meteo.com",
    "geocoding-api.open-meteo.com",
    "api.positionstack.com",
    "api.mailgun.net",
    "api.sendgrid.com",
    "api.resend.com",
    "api.ebird.org",
    "api.weather.gov",
    "epqs.nationalmap.gov",
    "challenges.cloudflare.com",
    "workers.dev",
    "www.google-analytics.com",
    "region1.google-analytics.com",
    "app.posthog.com",
)
_APPROVED_PUBLIC_DATA_ORIGIN = "https://rufous-data.loughondata.com"
_APPROVED_CONNECT_SOURCES = frozenset(
    {
        "'self'",
        "https://tiles.openfreemap.org",
        _APPROVED_PUBLIC_DATA_ORIGIN,
    }
)
_FORBIDDEN_OBJECT_STORE_MARKERS = (
    ".r2.dev",
    ".r2.cloudflarestorage.com",
    "x-amz-algorithm",
    "x-amz-credential",
    "x-amz-signature",
    "aws_access_key_id",
    "aws_secret_access_key",
)
_FORBIDDEN_PUBLIC_APP_MARKERS = (
    '"/api/',
    "'/api/",
    "`/api/",
    "http://127.0.0.1:8000",
    "http://localhost:8000",
    "Local evidence-backed birding trip planner",
)
_FORBIDDEN_PUBLIC_KEYS = frozenset(
    {
        "email",
        "email_address",
        "recipient",
        "organizer",
        "user_id",
        "watch_id",
        "plan_id",
        "source_record_id",
        "source_observation_id",
        "location_id",
        "checklist_id",
        "sub_id",
        "source_id",
        "occurrence_id",
        "gbif_id",
        "gbif_key",
        "recorded_by",
        "recordedby",
        "observer",
        "locality",
        "dlt_id",
        "dlt_load_id",
        "raw_source_table",
        "is_location_private",
    }
)
_WORKFLOW_RUNNER = re.compile(r"^\s*runs-on\s*:\s*([^#\n]+)", re.MULTILINE)


def audit_public_site(
    site_dir: Path,
    workflow_root: Path | None = None,
    repository_root: Path | None = None,
) -> list[str]:
    """Return stable human-readable findings; an empty list is release-ready."""
    findings: list[str] = []
    if not site_dir.is_dir():
        return [f"public site directory is missing: {site_dir}"]
    files = sorted(path for path in site_dir.rglob("*") if path.is_file())
    if len(files) > MAX_FILES:
        findings.append(f"static site has {len(files)} files; limit is {MAX_FILES}")
    for path in files:
        relative = path.relative_to(site_dir)
        suffix = path.suffix.casefold()
        if path.stat().st_size > MAX_FILE_BYTES:
            findings.append(f"{relative} exceeds 25 MiB")
        if suffix in _FORBIDDEN_RAW_SUFFIXES:
            findings.append(f"{relative} is a forbidden raw/database artifact")
        if (suffix and suffix not in _ALLOWED_STATIC_SUFFIXES) or (
            not suffix and path.name not in _ALLOWED_EXTENSIONLESS
        ):
            findings.append(f"{relative} has an unapproved static file type")
        if suffix == ".json" and (not relative.parts or relative.parts[0] != "data"):
            findings.append(f"{relative} is JSON outside the public data contract")
        if _has_database_signature(path):
            findings.append(f"{relative} contains a database/storage file signature")
        if relative.parts and relative.parts[0].casefold() == "functions":
            findings.append(f"{relative} is a Pages Functions entry")
        if path.name.casefold() in _FORBIDDEN_ENTRYPOINTS:
            findings.append(f"{relative} is a Worker/Pages Functions entrypoint")
        if (
            len(relative.parts) >= 2
            and relative.parts[0].casefold() == "src"
            and relative.parts[1].casefold() in _FORBIDDEN_ENTRYPOINTS
        ):
            findings.append(f"{relative} is a Worker source entrypoint")
    findings.extend(_audit_deployed_text(site_dir, files))
    findings.extend(_audit_cache_coherence(site_dir))
    findings.extend(_audit_browser_security_policy(site_dir))
    findings.extend(_audit_all_json_privacy(site_dir, files))
    findings.extend(_audit_static_contract(site_dir))
    if workflow_root is not None:
        findings.extend(audit_workflow_runners(workflow_root))
    if repository_root is not None:
        findings.extend(audit_deploy_context(repository_root))
    return sorted(set(findings))


def _has_database_signature(path: Path) -> bool:
    try:
        with path.open("rb") as stream:
            header = stream.read(16)
    except OSError:
        return True
    return bool(
        header.startswith((b"SQLite format 3\x00", b"PAR1", b"ARROW1", b"Obj\x01"))
        or header[8:12] == b"DUCK"
    )


def _audit_all_json_privacy(site_dir: Path, files: list[Path]) -> list[str]:
    findings: list[str] = []
    for path in files:
        if path.suffix.casefold() != ".json" or path.stat().st_size > MAX_FILE_BYTES:
            continue
        relative = path.relative_to(site_dir)
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            findings.append(f"{relative} is not valid UTF-8 JSON")
            continue
        findings.extend(_audit_forbidden_keys(value, relative))
    return findings


def _audit_deployed_text(site_dir: Path, files: list[Path]) -> list[str]:
    findings: list[str] = []
    text_suffixes = {".html", ".js", ".mjs", ".css", ".json", ".jsonc", ".toml", ".yaml", ".yml"}
    config_suffixes = {".jsonc", ".toml", ".yaml", ".yml"}
    for path in files:
        if path.suffix.casefold() not in text_suffixes or path.stat().st_size > MAX_FILE_BYTES:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        relative = path.relative_to(site_dir)
        lower = text.casefold()
        for host in _FORBIDDEN_SERVICE_HOSTS:
            if host in lower:
                findings.append(f"{relative} depends on forbidden metered service {host}")
        for marker in _FORBIDDEN_OBJECT_STORE_MARKERS:
            if marker in lower:
                findings.append(
                    f"{relative} exposes a forbidden object-store endpoint or credential marker "
                    f"{marker!r}"
                )
        if "open_meteo" in lower or "open-meteo" in lower:
            findings.append(f"{relative} contains forbidden Open-Meteo provenance")
        for marker in _FORBIDDEN_PUBLIC_APP_MARKERS:
            if marker.casefold() in lower:
                findings.append(f"{relative} contains local-only application marker {marker!r}")
        if path.suffix.casefold() in config_suffixes or path.name.casefold().startswith("wrangler"):
            for pattern in _FORBIDDEN_BINDING_PATTERNS:
                if pattern.search(text):
                    findings.append(
                        f"{relative} contains a metered Cloudflare binding ({pattern.pattern})"
                    )
    return findings


def _audit_cache_coherence(site_dir: Path) -> list[str]:
    """Ensure a manifest refresh cannot be combined with stale data shards."""
    if not (site_dir / "index.html").is_file():
        return []
    headers_path = site_dir / "_headers"
    if not headers_path.is_file():
        return ["static application is missing its _headers cache policy"]
    try:
        text = headers_path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return ["static application _headers cache policy is unreadable"]
    policies_by_route: dict[str, list[str]] = {}
    route: str | None = None
    for raw_line in text.splitlines():
        stripped = raw_line.strip()
        if stripped and not raw_line.startswith((" ", "\t")):
            route = stripped
            continue
        if (
            route is not None
            and route.startswith("/data")
            and stripped.casefold().startswith("cache-control:")
        ):
            policies_by_route.setdefault(route, []).append(stripped.casefold())
    expected = "cache-control: no-cache, max-age=0, must-revalidate"
    if policies_by_route.get("/data/*") != [expected] or any(
        policy != expected
        for route_policies in policies_by_route.values()
        for policy in route_policies
    ):
        return ["all /data/* assets must revalidate so manifest and shards cannot mix releases"]
    return []


def _audit_browser_security_policy(site_dir: Path) -> list[str]:
    """Require the public browser to contact only the reviewed data and map origins."""
    if not (site_dir / "index.html").is_file():
        return []
    headers_path = site_dir / "_headers"
    if not headers_path.is_file():
        return []
    try:
        text = headers_path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return []
    csp_lines = [
        line.strip()
        for line in text.splitlines()
        if line.strip().casefold().startswith("content-security-policy:")
    ]
    if len(csp_lines) != 1:
        return ["static application must declare exactly one Content-Security-Policy"]
    _, policy = csp_lines[0].split(":", 1)
    directives: dict[str, list[str]] = {}
    for raw_directive in policy.split(";"):
        tokens = raw_directive.strip().split()
        if tokens:
            directives[tokens[0].casefold()] = tokens[1:]
    connect_sources = frozenset(directives.get("connect-src", []))
    findings: list[str] = []
    if connect_sources != _APPROVED_CONNECT_SOURCES:
        findings.append(
            "Content-Security-Policy connect-src must contain only self, OpenFreeMap, "
            "and the reviewed Rufous R2 custom domain"
        )
    frame_ancestors = frozenset(directives.get("frame-ancestors", []))
    if frame_ancestors != {
        "https://loughondata.com",
        "https://www.loughondata.com",
    }:
        findings.append(
            "Content-Security-Policy frame-ancestors must allow only the two loughondata.com "
            "site origins"
        )
    return findings


def audit_workflow_runners(workflow_root: Path) -> list[str]:
    findings: list[str] = []
    if not workflow_root.is_dir():
        return [f"workflow directory is missing: {workflow_root}"]
    for path in sorted([*workflow_root.glob("*.yml"), *workflow_root.glob("*.yaml")]):
        text = path.read_text(encoding="utf-8")
        runners = [match.group(1).strip().strip("'\"") for match in _WORKFLOW_RUNNER.finditer(text)]
        if not runners:
            findings.append(f"{path.name} does not declare a runner")
        for runner in runners:
            if runner != "ubuntu-latest":
                findings.append(f"{path.name} uses non-free/nonstandard runner {runner!r}")
        if "workflow_run:" in text and "secrets." in text:
            trust_markers = (
                "github.event.workflow_run.event == 'push'",
                "github.event.workflow_run.head_repository.full_name == github.repository",
                "github.event.workflow_run.head_branch == 'main'",
                "github.event.workflow_run.conclusion == 'success'",
                "github.event.workflow_run.head_sha == github.sha",
            )
            for marker in trust_markers:
                if marker not in text:
                    findings.append(
                        f"{path.name} exposes secrets after workflow_run without trust guard "
                        f"{marker!r}"
                    )
        pages_deploy = "pages deploy" in text.casefold()
        if "workflow_dispatch:" in text and pages_deploy:
            if "github.ref == 'refs/heads/main'" not in text:
                findings.append(f"{path.name} permits a manual Pages deployment outside main")
        if "data_version" in text and pages_deploy:
            if 'if [[ "$GITHUB_EVENT_NAME" != "schedule" ]]' not in text:
                findings.append(
                    f"{path.name} may skip application releases when only the data version "
                    "is unchanged"
                )
        if pages_deploy and "working-directory: ${{ runner.temp }}" not in text:
            findings.append(
                f"{path.name} must run Wrangler from the isolated runner temp directory"
            )
        if pages_deploy:
            for deployment_hazard in (
                ".github/workflows/**",
                "functions/**",
                "worker.js",
                "worker.mjs",
                "worker.ts",
                "_worker.js",
                "wrangler.toml",
                "wrangler.json",
                "wrangler.jsonc",
                ".wrangler/deploy/**",
            ):
                if text.count(deployment_hazard) < 2:
                    findings.append(
                        f"{path.name} must trigger push and pull-request audits for "
                        f"deployment hazard path {deployment_hazard!r}"
                    )
    return findings


def audit_deploy_context(repository_root: Path) -> list[str]:
    """Reject files Wrangler or Pages could treat as a runtime entrypoint."""
    if not repository_root.is_dir():
        return [f"repository directory is missing: {repository_root}"]
    findings: list[str] = []
    for root in (repository_root, repository_root / "app"):
        label = root.relative_to(repository_root) if root != repository_root else Path(".")
        for name in _FORBIDDEN_ENTRYPOINTS:
            candidate = root / name
            if candidate.exists():
                findings.append(f"{label / name} is forbidden in the Pages deployment context")
        functions = root / "functions"
        if functions.exists():
            findings.append(f"{label / 'functions'} is a forbidden Pages Functions directory")
    if (repository_root / ".wrangler" / "deploy").exists():
        findings.append(".wrangler/deploy is forbidden in the Pages deployment context")
    return findings


def _audit_static_contract(site_dir: Path) -> list[str]:
    data_dir = site_dir / "data"
    if not data_dir.is_dir() and (site_dir / "manifest.json").is_file():
        data_dir = site_dir
    manifest_path = data_dir / "manifest.json"
    attribution_path = data_dir / "attribution.json"
    if not manifest_path.is_file() or not attribution_path.is_file():
        return ["static data contract requires data/manifest.json and data/attribution.json"]
    findings: list[str] = []
    manifest = _read_object(manifest_path, findings)
    attribution = _read_object(attribution_path, findings)
    if not manifest or not attribution:
        return findings
    if manifest.get("schema_version") != SCHEMA_VERSION:
        findings.append("manifest schema_version is unsupported")
    if manifest.get("mode") != "public":
        findings.append("manifest mode must be public")
    mode = manifest.get("release_mode")
    source_policy = manifest.get("source_policy")
    if not isinstance(source_policy, dict):
        findings.append("manifest source_policy metadata is missing")
    else:
        if source_policy.get("direct_ebird") != "excluded":
            findings.append("manifest must exclude direct eBird data")
        if mode == "production":
            if source_policy.get("occurrence_source") != "gbif":
                findings.append("production occurrence source must be GBIF")
            if source_policy.get("gbif_dataset_key") != GBIF_EBIRD_EOD_DATASET_KEY:
                findings.append("production GBIF source must be the allowlisted eBird EOD dataset")
            if source_policy.get("coverage") != "bounded_sample":
                findings.append("production GBIF source must disclose bounded sample coverage")
            if source_policy.get("required_taxon_key") != GBIF_RUFOUS_TAXON_KEY:
                findings.append("production GBIF source must reserve the Rufous taxon")
        elif mode == "synthetic":
            if source_policy.get("occurrence_source") != "synthetic":
                findings.append("synthetic occurrence source marker is missing")
            if source_policy.get("gbif_dataset_key") is not None:
                findings.append("synthetic manifest must not claim a GBIF dataset")
            if source_policy.get("coverage") != "fictional_fixture":
                findings.append("synthetic manifest must disclose fixture coverage")
            if source_policy.get("required_taxon_key") is not None:
                findings.append("synthetic manifest must not claim a required GBIF taxon")
    if mode not in {"production", "synthetic"}:
        findings.append("manifest release_mode must be synthetic or production")

    policy = manifest.get("license_policy")
    if not isinstance(policy, dict) or policy.get("version") != 1:
        findings.append("manifest license policy metadata is missing")
    elif policy.get("allowed") != {
        provider: sorted(values) for provider, values in ALLOWED_LICENSES.items()
    }:
        findings.append("manifest license policy does not match the fail-closed allowlist")
    if mode == "production":
        sources = attribution.get("sources")
        providers = (
            {
                item.get("provider")
                for item in sources
                if isinstance(sources, list) and isinstance(item, dict)
            }
            if isinstance(sources, list)
            else set()
        )
        for required in ("gbif_ebird_eod", "usgs_gnis", "us_census_tigerweb"):
            if required not in providers:
                findings.append(f"production attribution is missing {required}")
        if "ebird" in providers:
            findings.append("production attribution includes forbidden direct eBird data")
        eod_sources = (
            [
                item
                for item in sources
                if isinstance(item, dict) and item.get("provider") == "gbif_ebird_eod"
            ]
            if isinstance(sources, list)
            else []
        )
        if len(eod_sources) != 1:
            findings.append("production attribution must contain one GBIF eBird EOD source")
        else:
            eod = eod_sources[0]
            if eod.get("dataset_key") != GBIF_EBIRD_EOD_DATASET_KEY:
                findings.append("production attribution names the wrong GBIF dataset")
            if canonical_license("gbif", eod.get("license")) is None:
                findings.append("production GBIF eBird EOD source license is not allowed")
            modifications = eod.get("modifications")
            if not isinstance(modifications, str) or not all(
                marker in modifications.casefold()
                for marker in ("selected arizona", "removed observer", "rounded coordinates")
            ):
                findings.append(
                    "production GBIF attribution must visibly identify Rufous modifications"
                )
            if eod.get("disclaimer") != GBIF_EBIRD_EOD_DISCLAIMER:
                findings.append(
                    "production GBIF attribution must retain the dataset accuracy notice"
                )

    referenced: set[Path] = {manifest_path, attribution_path}
    attribution_items = attribution.get("items")
    if not isinstance(attribution_items, list):
        attribution_items = []
    attribution_ids = {
        str(item.get("attribution_id"))
        for item in attribution_items
        if isinstance(item, dict) and isinstance(item.get("attribution_id"), str)
    }
    species = manifest.get("species")
    cells = manifest.get("cells")
    prefixes = manifest.get("place_prefixes")
    production_has_rufous = False
    if not isinstance(species, list) or not species:
        findings.append("manifest species index is empty or malformed")
    else:
        for item in species:
            if not isinstance(item, dict):
                findings.append("manifest species summary is malformed")
                continue
            path = _contract_path(site_dir, data_dir, item.get("profile_path"))
            if path is None or not path.is_file():
                findings.append(f"missing species profile {item.get('profile_path')!r}")
                continue
            referenced.add(path)
            profile = _read_object(path, findings)
            scientific_name = profile.get("scientific_name")
            if (
                mode == "production"
                and isinstance(scientific_name, str)
                and scientific_name.casefold().startswith("selasphorus rufus")
            ):
                production_has_rufous = True
            findings.extend(_audit_species_profile(profile, path.relative_to(site_dir)))
    if mode == "production" and not production_has_rufous:
        findings.append("production species index is missing Rufous Hummingbird")
    for name, rows, path_field in (("cell", cells, "path"), ("place", prefixes, "path")):
        if not isinstance(rows, list):
            findings.append(f"manifest {name} index is malformed")
            continue
        for item in rows:
            path = _contract_path(
                site_dir, data_dir, item.get(path_field) if isinstance(item, dict) else None
            )
            if path is None or not path.is_file():
                findings.append(f"missing {name} shard {item!r}")
                continue
            referenced.add(path)
            payload = _read_object(path, findings)
            findings.extend(_audit_forbidden_keys(payload, path.relative_to(site_dir)))
            if name == "cell":
                findings.extend(
                    _audit_observation_shard(
                        payload,
                        path.relative_to(site_dir),
                        attribution_ids,
                        mode,
                    )
                )
            else:
                findings.extend(_audit_place_shard(payload, path.relative_to(site_dir), mode))
    findings.extend(_audit_attribution_items(attribution, attribution_path.relative_to(site_dir)))
    findings.extend(_audit_forbidden_keys(manifest, manifest_path.relative_to(site_dir)))
    findings.extend(_audit_forbidden_keys(attribution, attribution_path.relative_to(site_dir)))

    contract_json = set(data_dir.rglob("*.json"))
    for unreferenced in sorted(contract_json - referenced):
        findings.append(f"unreferenced public JSON asset {unreferenced.relative_to(site_dir)}")
    return findings


def _audit_observation_shard(
    payload: dict[str, Any],
    relative: Path,
    attribution_ids: set[str],
    mode: object,
) -> list[str]:
    observations = payload.get("observations")
    if not isinstance(observations, list):
        return [f"{relative} observations must be an array"]
    findings: list[str] = []
    for index, observation in enumerate(observations):
        label = f"{relative} observations[{index}]"
        if not isinstance(observation, dict):
            findings.append(f"{label} is malformed")
            continue
        source = observation.get("source")
        attribution_id = observation.get("attribution_id")
        expected_source = "synthetic" if mode == "synthetic" else "gbif"
        if source != expected_source:
            findings.append(f"{label} source must be {expected_source}")
        if not isinstance(attribution_id, str) or not attribution_id:
            findings.append(f"{label} is missing attribution_id")
        elif source == "gbif" and attribution_id not in attribution_ids:
            findings.append(f"{label} lacks matching GBIF item attribution")
        location = observation.get("location")
        findings.extend(_audit_timezone(location, label))
        if mode == "production":
            public_id = observation.get("public_id")
            if not isinstance(public_id, str) or re.fullmatch(r"[a-f0-9]{24}", public_id) is None:
                findings.append(f"{label} has an invalid generalized public_id")
            observed_at = observation.get("observed_at")
            try:
                parsed_date = (
                    date.fromisoformat(observed_at) if isinstance(observed_at, str) else None
                )
            except ValueError:
                parsed_date = None
            if parsed_date is None or observed_at != parsed_date.isoformat():
                findings.append(f"{label} must expose only a day-level observation date")
            if (
                observation.get("count") is not None
                or observation.get("count_display") != "occurrence"
            ):
                findings.append(f"{label} must not expose a source occurrence count")
            if observation.get("is_notable") is not False:
                findings.append(f"{label} must not expose source notability")
            if not isinstance(location, dict):
                continue
            if (
                location.get("name") != "Generalized Arizona occurrence"
                or location.get("kind") != "generalized"
            ):
                findings.append(f"{label} must use the generalized production location label")
            for coordinate in ("latitude", "longitude"):
                value = location.get(coordinate)
                if (
                    isinstance(value, bool)
                    or not isinstance(value, int | float)
                    or round(float(value), 2) != float(value)
                ):
                    findings.append(f"{label} {coordinate} must be rounded to 0.01 degrees")
    return findings


def _audit_place_shard(payload: dict[str, Any], relative: Path, mode: object) -> list[str]:
    places = payload.get("places")
    if not isinstance(places, list):
        return [f"{relative} places must be an array"]
    findings: list[str] = []
    for index, place in enumerate(places):
        label = f"{relative} places[{index}]"
        findings.extend(_audit_timezone(place, label))
        if isinstance(place, dict):
            source = place.get("source")
            if mode == "production" and source != "usgs_gnis":
                findings.append(f"{label} has a forbidden place source")
            elif mode == "synthetic" and source not in {"synthetic", "usgs_gnis"}:
                findings.append(f"{label} has a forbidden place source")
            if mode == "production" and place.get("kind") != "place":
                findings.append(f"{label} must be a GNIS place")
    return findings


def _audit_timezone(value: object, label: str) -> list[str]:
    if not isinstance(value, dict):
        return [f"{label} location is malformed"]
    findings: list[str] = []
    if value.get("timezone") not in {None, "America/Phoenix", "America/Denver"}:
        findings.append(f"{label} has unsupported timezone")
    if not isinstance(value.get("timezone_source"), str) or not value["timezone_source"]:
        findings.append(f"{label} is missing timezone_source")
    return findings


def _contract_path(site_dir: Path, data_dir: Path, value: object) -> Path | None:
    if not isinstance(value, str) or not value.startswith("/") or ".." in Path(value).parts:
        return None
    relative = value.removeprefix("/")
    candidate = site_dir / relative
    if candidate.is_file() or candidate.parent.exists():
        return candidate
    # Supports auditing the dedicated exporter artifact before it is copied into
    # a complete Pages output directory.
    if relative.startswith("data/"):
        return data_dir / relative.removeprefix("data/")
    return candidate


def _read_object(path: Path, findings: list[str]) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        findings.append(f"{path.name} is not valid UTF-8 JSON")
        return {}
    if not isinstance(value, dict):
        findings.append(f"{path.name} must contain a JSON object")
        return {}
    return value


def _audit_species_profile(profile: dict[str, Any], relative: Path) -> list[str]:
    findings = _audit_forbidden_keys(profile, relative)
    for field in ("species_code", "common_name", "scientific_name"):
        if not isinstance(profile.get(field), str) or not profile[field].strip():
            findings.append(f"{relative} is missing {field}")
    media = profile.get("media")
    if not isinstance(media, list):
        findings.append(f"{relative} media must be an array")
        return findings
    for item in media:
        if not isinstance(item, dict):
            findings.append(f"{relative} contains malformed media")
            continue
        provider = item.get("provider")
        required = ("creator", "source_url", "license", "license_url", "attribution_id", "url")
        if not isinstance(provider, str) or provider not in ALLOWED_LICENSES:
            findings.append(f"{relative} media provider is not allowed")
        elif canonical_license(provider, item.get("license")) is None:
            findings.append(f"{relative} media license is not allowed for {provider}")
        for field in required:
            if not isinstance(item.get(field), str) or not item[field].strip():
                findings.append(f"{relative} media is missing {field}")
    return findings


def _audit_attribution_items(attribution: dict[str, Any], relative: Path) -> list[str]:
    findings: list[str] = []
    items = attribution.get("items")
    if not isinstance(items, list):
        return [f"{relative} items must be an array"]
    identifiers: set[str] = set()
    for item in items:
        if not isinstance(item, dict):
            findings.append(f"{relative} contains malformed item attribution")
            continue
        provider = item.get("provider")
        identifier = item.get("attribution_id")
        for field in (
            "attribution_id",
            "provider",
            "creator",
            "source_url",
            "license",
            "license_url",
        ):
            if not isinstance(item.get(field), str) or not item[field].strip():
                findings.append(f"{relative} item attribution is missing {field}")
        if isinstance(identifier, str):
            if identifier in identifiers:
                findings.append(f"{relative} has duplicate attribution_id {identifier}")
            identifiers.add(identifier)
        if (
            not isinstance(provider, str)
            or canonical_license(provider, item.get("license")) is None
        ):
            findings.append(f"{relative} has forbidden or malformed {provider!r} license")
        if provider == "gbif":
            for field in (
                "dataset_title",
                "dataset_key",
                "publisher",
                "dataset_citation",
                "dataset_doi",
            ):
                if not isinstance(item.get(field), str) or not item[field].strip():
                    findings.append(f"{relative} GBIF attribution is missing {field}")
            if item.get("dataset_key") != GBIF_EBIRD_EOD_DATASET_KEY:
                findings.append(f"{relative} GBIF attribution is not the allowlisted EOD dataset")
            if item.get("creator") != item.get("publisher"):
                findings.append(f"{relative} GBIF attribution exposes a non-dataset creator")
            if item.get("publisher") != GBIF_EBIRD_EOD_PUBLISHER:
                findings.append(f"{relative} GBIF attribution has an unexpected publisher")
            source_url = item.get("source_url")
            if isinstance(source_url, str) and (
                "/occurrence/" in source_url.casefold()
                or "ebird.org/checklist/" in source_url.casefold()
            ):
                findings.append(f"{relative} GBIF attribution exposes a record-level URL")
    return findings


def _audit_forbidden_keys(value: object, relative: Path, prefix: str = "") -> list[str]:
    findings: list[str] = []
    if isinstance(value, dict):
        for key, item in value.items():
            location = f"{prefix}.{key}" if prefix else key
            if key.casefold() in _FORBIDDEN_PUBLIC_KEYS:
                findings.append(f"{relative} exposes forbidden field {location}")
            findings.extend(_audit_forbidden_keys(item, relative, location))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            findings.extend(_audit_forbidden_keys(item, relative, f"{prefix}[{index}]"))
    return findings


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("site", type=Path)
    parser.add_argument("--workflows", type=Path)
    parser.add_argument("--repository-root", type=Path)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    findings = audit_public_site(args.site, args.workflows, args.repository_root)
    if findings:
        print("Rufous public release safety audit failed:")
        for finding in findings:
            print(f"- {finding}")
        return 1
    print("Rufous public release safety audit passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
