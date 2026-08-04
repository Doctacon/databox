"""Cost, privacy, source-boundary, and licensing audit for public Rufous."""

from __future__ import annotations

import argparse
import json
import re
from collections.abc import Mapping
from datetime import date
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlsplit

from databox.public_export import (
    ALLOWED_LICENSES,
    GBIF_EBIRD_EOD_DATASET_KEY,
    GBIF_EBIRD_EOD_DISCLAIMER,
    GBIF_EBIRD_EOD_PUBLISHER,
    GBIF_RUFOUS_TAXON_KEY,
    SCHEMA_VERSION,
    canonical_license,
    public_provider_attribution_sources,
    valid_public_audio_call,
)
from databox.public_restricted_marks import restricted_usfws_mark_reason

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
_PUBLIC_ASSET_GENERATION_MARKER = "-g2-"
_REVIEWED_SPA_REDIRECTS = (
    "/birds / 200",
    "/credits / 200",
    "/map / 200",
    "/my-birds / 200",
    "/birds/:species/find / 200",
    "/birds/:species / 200",
    "/target-plans/:plan / 200",
)
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
_APPROVED_IMAGE_SOURCES = frozenset(
    {
        "'self'",
        "data:",
        "blob:",
        _APPROVED_PUBLIC_DATA_ORIGIN,
    }
)
_APPROVED_MEDIA_SOURCES = frozenset({"'self'", _APPROVED_PUBLIC_DATA_ORIGIN})
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
    "RUF_LOCAL_MEDIA_REVIEW_ONLY_DO_NOT_DEPLOY",
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
_SHA256 = re.compile(r"^[a-f0-9]{64}$")
_MEDIA_ID = re.compile(r"^usfws-[a-f0-9]{24}$")
_MEDIA_ATTRIBUTION_ID = re.compile(r"^usfws-attribution-[a-f0-9]{24}$")
_INATURALIST_MEDIA_ID = re.compile(r"^inaturalist-(?P<photo_id>[1-9][0-9]*)$")
_INATURALIST_ATTRIBUTION_ID = re.compile(r"^inaturalist-attribution-(?P<photo_id>[1-9][0-9]*)$")
_WIKIMEDIA_MEDIA_ID = re.compile(r"^wikimedia-[a-f0-9]{24}$")
_WIKIMEDIA_ATTRIBUTION_ID = re.compile(r"^wikimedia-attribution-[a-f0-9]{24}$")
_USFWS_MEDIA_PAGE = re.compile(
    r"^https://www\.fws\.gov/media/[a-z0-9](?:[a-z0-9-]{0,238}[a-z0-9])?$"
)
_INATURALIST_PHOTO_PAGE = re.compile(
    r"^https://www\.inaturalist\.org/photos/(?P<photo_id>[1-9][0-9]*)$"
)
_WIKIMEDIA_FILE_PAGE = re.compile(
    r"^https://commons\.wikimedia\.org/wiki/File:[^/?#\x00-\x20\x7f]+$"
)
_MEDIA_PROVIDER_LABELS = {
    "usfws": "USFWS",
    "inaturalist": "iNaturalist",
    "wikimedia": "Wikimedia Commons",
}
_MEDIA_ID_PATTERNS = {
    "usfws": _MEDIA_ID,
    "inaturalist": _INATURALIST_MEDIA_ID,
    "wikimedia": _WIKIMEDIA_MEDIA_ID,
}
_MEDIA_ATTRIBUTION_ID_PATTERNS = {
    "usfws": _MEDIA_ATTRIBUTION_ID,
    "inaturalist": _INATURALIST_ATTRIBUTION_ID,
    "wikimedia": _WIKIMEDIA_ATTRIBUTION_ID,
}
_MEDIA_SOURCE_PAGE_PATTERNS = {
    "usfws": _USFWS_MEDIA_PAGE,
    "inaturalist": _INATURALIST_PHOTO_PAGE,
    "wikimedia": _WIKIMEDIA_FILE_PAGE,
}


def _valid_wikimedia_file_page(value: str) -> bool:
    if len(value) > 2_000 or _WIKIMEDIA_FILE_PAGE.fullmatch(value) is None:
        return False
    try:
        parsed = urlsplit(value)
        port = parsed.port
        encoded_name = parsed.path.removeprefix("/wiki/File:")
        if re.search(r"%(?![0-9A-Fa-f]{2})", encoded_name):
            return False
        name = unquote(encoded_name, errors="strict")
    except (UnicodeError, ValueError):
        return False
    return bool(
        parsed.scheme == "https"
        and parsed.hostname == "commons.wikimedia.org"
        and parsed.username is None
        and parsed.password is None
        and port is None
        and not parsed.query
        and not parsed.fragment
        and 0 < len(name) <= 500
        and name.strip() == name
        and name not in {".", ".."}
        and not any(character in name for character in ("/", "\\"))
        and not any(ord(character) < 32 or ord(character) == 127 for character in name)
    )


_PUBLIC_MEDIA_URL = re.compile(
    r"^https://rufous-data\.loughondata\.com/rufous-media/v1/objects/"
    r"(?P<shard>[a-f0-9]{2})/(?P<sha>[a-f0-9]{64})\.webp$"
)
_MEDIA_SOURCE_PROVIDERS = {
    "none": frozenset(),
    "usfws": frozenset({"usfws"}),
    "inaturalist": frozenset({"inaturalist"}),
    "wikimedia": frozenset({"wikimedia"}),
    "usfws+inaturalist": frozenset({"usfws", "inaturalist"}),
    "usfws+wikimedia": frozenset({"usfws", "wikimedia"}),
    "inaturalist+wikimedia": frozenset({"inaturalist", "wikimedia"}),
    "usfws+inaturalist+wikimedia": frozenset({"usfws", "inaturalist", "wikimedia"}),
}
_AUDIO_PROVIDER_ORDER = ("xeno_canto", "inaturalist", "wikimedia", "usfws")
_PUBLIC_MEDIA_EMAIL = re.compile(
    r"(?<![A-Za-z0-9.!#$%&'*+/=?^_`{|}~-])"
    r"[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]{1,64}@"
    r"(?:[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?\.)+[A-Za-z]{2,63}\b"
)
_PUBLIC_MEDIA_PHONE = re.compile(
    r"(?<!\d)(?:\+?1[ .-]?)?(?:\(\d{3}\)|\d{3})[ .-]\d{3}[ .-]\d{4}(?!\d)"
)
_PUBLIC_MEDIA_PO_BOX = re.compile(
    r"\bP(?:ost)?\.?\s*O(?:ffice)?\.?\s+Box\s+\d{1,10}\b",
    re.IGNORECASE,
)
_PUBLIC_MEDIA_STREET_ADDRESS = re.compile(
    r"\b\d{2,6}\s+(?:[A-Za-z0-9][A-Za-z0-9.'-]*\s+){0,4}"
    r"(?:Street|St|Avenue|Ave|Road|Rd|Drive|Dr|Lane|Ln|Court|Ct|"
    r"Boulevard|Blvd|Terrace|Way)\b",
    re.IGNORECASE,
)
_PUBLIC_MEDIA_LABELED_COORDINATE = re.compile(
    r"\b(?:GPS|coordinates?|lat(?:itude)?|lon(?:gitude)?)\b\s*[:=]?\s*"
    r"[-+]?\d{1,3}(?:\.\d+)?",
    re.IGNORECASE,
)
_PUBLIC_MEDIA_COORDINATE_PAIR = re.compile(
    r"(?<![\d.])(?P<latitude>[-+]?\d{1,2}\.\d{3,})\s*[,;]\s*"
    r"(?P<longitude>[-+]?\d{1,3}\.\d{3,})(?![\d.])"
)
_PUBLIC_MEDIA_DMS_COORDINATE = re.compile(
    r"\b\d{1,3}\s*[°º]\s*\d{1,2}(?:\.\d+)?\s*['′]",
    re.IGNORECASE,
)


def _public_media_privacy_reason(value: str) -> str | None:
    """Identify only high-confidence contact or precise-location disclosures."""
    if _PUBLIC_MEDIA_EMAIL.search(value):
        return "email_address"
    if _PUBLIC_MEDIA_PHONE.search(value):
        return "phone_number"
    if _PUBLIC_MEDIA_PO_BOX.search(value) or _PUBLIC_MEDIA_STREET_ADDRESS.search(value):
        return "postal_address"
    if _PUBLIC_MEDIA_LABELED_COORDINATE.search(value) or _PUBLIC_MEDIA_DMS_COORDINATE.search(value):
        return "precise_coordinates"
    for match in _PUBLIC_MEDIA_COORDINATE_PAIR.finditer(value):
        latitude = float(match.group("latitude"))
        longitude = float(match.group("longitude"))
        if -90 <= latitude <= 90 and -180 <= longitude <= 180:
            return "precise_coordinates"
    return None


def audit_public_site(
    site_dir: Path,
    workflow_root: Path | None = None,
    repository_root: Path | None = None,
    *,
    shell_only: bool = False,
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
    findings.extend(_audit_static_routing(site_dir))
    findings.extend(_audit_browser_security_policy(site_dir))
    findings.extend(_audit_all_json_privacy(site_dir, files))
    if shell_only:
        findings.extend(_audit_shell_only_contract(site_dir))
    else:
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


def _audit_static_routing(site_dir: Path) -> list[str]:
    """Keep SPA navigation from turning missing executable assets into cached HTML."""
    if not (site_dir / "index.html").is_file():
        return []

    findings: list[str] = []
    if not (site_dir / "404.html").is_file():
        findings.append(
            "static application must include a top-level 404.html to disable implicit SPA fallback"
        )

    redirects_path = site_dir / "_redirects"
    try:
        redirect_lines = tuple(
            line.strip()
            for line in redirects_path.read_text(encoding="utf-8").splitlines()
            if line.strip() and not line.lstrip().startswith("#")
        )
    except (OSError, UnicodeDecodeError):
        redirect_lines = ()
    if redirect_lines != _REVIEWED_SPA_REDIRECTS:
        findings.append(
            "static application _redirects must proxy only the reviewed client-side routes"
        )

    headers_path = site_dir / "_headers"
    try:
        header_lines = headers_path.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeDecodeError):
        return findings
    route: str | None = None
    for raw_line in header_lines:
        stripped = raw_line.strip()
        if stripped and not raw_line.startswith((" ", "\t")):
            route = stripped
            continue
        if (
            route is not None
            and route != "/data"
            and not route.startswith("/data/")
            and stripped.casefold().startswith("cache-control:")
        ):
            findings.append("static application must use Pages' default caching outside /data")
            break

    assets_dir = site_dir / "assets"
    if assets_dir.is_dir() and any(
        _PUBLIC_ASSET_GENERATION_MARKER not in path.name
        for path in assets_dir.rglob("*")
        if path.is_file()
    ):
        findings.append("static application assets must use the reviewed cache-recovery generation")
    return findings


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
    duplicate_directives: set[str] = set()
    for raw_directive in policy.split(";"):
        tokens = raw_directive.strip().split()
        if tokens:
            name = tokens[0].casefold()
            if name in directives:
                duplicate_directives.add(name)
            directives[name] = tokens[1:]
    connect_sources = frozenset(directives.get("connect-src", []))
    findings: list[str] = []
    if duplicate_directives:
        findings.append("Content-Security-Policy must not repeat directives")
    if connect_sources != _APPROVED_CONNECT_SOURCES:
        findings.append(
            "Content-Security-Policy connect-src must contain only self, OpenFreeMap, "
            "and the reviewed Rufous R2 custom domain"
        )
    image_sources = frozenset(directives.get("img-src", []))
    if image_sources != _APPROVED_IMAGE_SOURCES:
        findings.append(
            "Content-Security-Policy img-src must contain only self, data, blob, "
            "and the reviewed Rufous media origin"
        )
    media_sources = frozenset(directives.get("media-src", []))
    if media_sources != _APPROVED_MEDIA_SOURCES:
        findings.append(
            "Content-Security-Policy media-src must contain only self and the reviewed "
            "Rufous media origin"
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
            if runner not in {"ubuntu-latest", "ubuntu-24.04"}:
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
        media_publishers = _workflow_media_publisher_commands(text)
        if media_publishers:
            required_markers = (
                "config/rufous-media-visual-approvals.json",
                "python scripts/verify_rufous_media_approvals.py",
                "--media-approvals config/rufous-media-visual-approvals.json",
            )
            for marker in required_markers:
                if marker not in text:
                    findings.append(
                        f"{path.name} media publication is missing human approval gate "
                        f"marker {marker!r}"
                    )
            for line_number, arguments in media_publishers:
                if "--approvals config/rufous-media-visual-approvals.json" not in arguments:
                    findings.append(
                        f"{path.name}:{line_number} media publisher omits the committed "
                        "human approval ledger"
                    )
            gate_position = text.find("python scripts/verify_rufous_media_approvals.py")
            first_publisher = text.find("python scripts/publish_rufous_media.py")
            if gate_position < 0 or gate_position > first_publisher:
                findings.append(
                    f"{path.name} must run the human media approval gate before cloud publishers"
                )
    return findings


def _workflow_media_publisher_commands(text: str) -> list[tuple[int, str]]:
    lines = text.splitlines()
    commands: list[tuple[int, str]] = []
    for index, line in enumerate(lines):
        if line.strip() != "python scripts/publish_rufous_media.py":
            continue
        arguments: list[str] = []
        for following in lines[index + 1 :]:
            stripped = following.strip()
            if not stripped.startswith("--"):
                break
            arguments.append(stripped)
        commands.append((index + 1, " ".join(arguments)))
    return commands


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


def _audit_media_attribution_sources(
    sources: object,
    *,
    advertised_photo_providers: frozenset[str],
    advertised_audio_providers: frozenset[str],
) -> list[str]:
    if not isinstance(sources, list):
        return ["public attribution sources must be an array"]
    findings: list[str] = []
    advertised_providers = advertised_photo_providers | advertised_audio_providers
    expected_sources = [
        source
        for provider in _AUDIO_PROVIDER_ORDER
        if provider in advertised_providers
        for source in public_provider_attribution_sources(
            provider,
            includes_photos=provider in advertised_photo_providers,
            includes_audio=provider in advertised_audio_providers,
        )
    ]
    expected_by_provider = {str(source["provider"]): source for source in expected_sources}
    known_provider_ids = {
        provider_id
        for provider in _AUDIO_PROVIDER_ORDER
        for provider_id in (provider, f"{provider}_audio")
    }
    for provider, contract in expected_by_provider.items():
        matches = [
            item for item in sources if isinstance(item, dict) and item.get("provider") == provider
        ]
        if len(matches) != 1:
            findings.append(
                f"public attribution must contain one {provider} media source when advertised"
            )
            continue
        source = matches[0]
        if source != contract:
            findings.append(f"public {provider} media attribution does not match its contract")
    for source in sources:
        source_provider = source.get("provider") if isinstance(source, dict) else None
        if source_provider in known_provider_ids and source_provider not in expected_by_provider:
            findings.append(
                f"public attribution contains unadvertised {source_provider} media source"
            )
    return findings


def _audit_shell_only_contract(site_dir: Path) -> list[str]:
    """Require a built application shell with no bundled public-data snapshot."""
    findings: list[str] = []
    index = site_dir / "index.html"
    if index.is_symlink() or not index.is_file():
        findings.append("shell-only release requires a built static application index.html")
    data = site_dir / "data"
    if data.exists() or data.is_symlink():
        findings.append("shell-only release must not contain a data/ path")
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
    advertised_media_providers: frozenset[str] = frozenset()
    advertised_audio_providers: frozenset[str] = frozenset()
    if not isinstance(source_policy, dict):
        findings.append("manifest source_policy metadata is missing")
    else:
        media_source = source_policy.get("media_source")
        if isinstance(media_source, str) and media_source in _MEDIA_SOURCE_PROVIDERS:
            advertised_media_providers = _MEDIA_SOURCE_PROVIDERS[media_source]
        else:
            findings.append("manifest media source marker is invalid")
        expected_delivery = "none" if media_source == "none" else "immutable_r2"
        if source_policy.get("media_delivery") != expected_delivery:
            findings.append("manifest media delivery marker is invalid")
        audio_source = source_policy.get("audio_source")
        if audio_source == "none":
            advertised_audio_providers = frozenset()
        elif isinstance(audio_source, str):
            audio_parts = audio_source.split("+")
            advertised_audio_providers = frozenset(audio_parts)
            expected_audio_parts = [
                provider
                for provider in _AUDIO_PROVIDER_ORDER
                if provider in advertised_audio_providers
            ]
            if audio_parts != expected_audio_parts or len(audio_parts) != len(
                advertised_audio_providers
            ):
                findings.append("manifest audio source marker is invalid")
                advertised_audio_providers = frozenset()
        else:
            findings.append("manifest audio source marker is invalid")
        expected_audio_delivery = "none" if audio_source == "none" else "immutable_r2"
        if source_policy.get("audio_delivery") != expected_audio_delivery:
            findings.append("manifest audio delivery marker is invalid")
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
            if not advertised_media_providers:
                findings.append("production media source must identify a reviewed provider")
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
    sources = attribution.get("sources")
    if mode == "production":
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
    findings.extend(
        _audit_media_attribution_sources(
            sources,
            advertised_photo_providers=advertised_media_providers,
            advertised_audio_providers=advertised_audio_providers,
        )
    )

    referenced: set[Path] = {manifest_path, attribution_path}
    attribution_items = attribution.get("items")
    if not isinstance(attribution_items, list):
        attribution_items = []
    attribution_by_id = {
        str(item.get("attribution_id")): item
        for item in attribution_items
        if isinstance(item, dict) and isinstance(item.get("attribution_id"), str)
    }
    attribution_ids = set(attribution_by_id)
    species = manifest.get("species")
    cells = manifest.get("cells")
    prefixes = manifest.get("place_prefixes")
    production_has_rufous = False
    production_rufous_has_media = False
    observed_media_providers: set[str] = set()
    media_item_count = 0
    species_with_media = 0
    audio_item_count = 0
    species_with_audio = 0
    observed_audio_providers: set[str] = set()
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
            for field in ("species_code", "common_name", "scientific_name"):
                if item.get(field) != profile.get(field):
                    findings.append(f"species summary disagrees with profile field {field}")
            if "call" not in item or "call" not in profile:
                findings.append("species summary and profile must declare an optional call")
            media = profile.get("media")
            profile_media = media if isinstance(media, list) else []
            observed_media_providers.update(
                str(media_item.get("provider"))
                for media_item in profile_media
                if isinstance(media_item, dict)
                and media_item.get("provider") in {"usfws", "inaturalist", "wikimedia"}
            )
            summary_count = item.get("photo_count")
            if type(summary_count) is not int or summary_count != len(profile_media):
                findings.append("species summary photo_count disagrees with its profile")
            expected_hero = profile_media[0] if profile_media else None
            if item.get("hero_photo") != expected_hero:
                findings.append("species summary hero_photo disagrees with its profile")
            profile_call = profile.get("call")
            if item.get("call") != profile_call:
                findings.append("species summary call disagrees with its profile")
            if profile_call is not None:
                audio_item_count += 1
                species_with_audio += 1
                if isinstance(profile_call, dict) and isinstance(profile_call.get("provider"), str):
                    observed_audio_providers.add(profile_call["provider"])
            media_item_count += len(profile_media)
            if profile_media:
                species_with_media += 1
            if (
                mode == "production"
                and isinstance(scientific_name, str)
                and scientific_name.casefold() == "selasphorus rufus"
            ):
                production_has_rufous = True
                production_rufous_has_media = bool(profile_media)
            findings.extend(
                _audit_species_profile(
                    profile,
                    path.relative_to(site_dir),
                    mode=mode,
                    attribution_by_id=attribution_by_id,
                )
            )
    if mode == "production" and not production_has_rufous:
        findings.append("production species index is missing Rufous Hummingbird")
    elif mode == "production" and not production_rufous_has_media:
        findings.append("production Rufous Hummingbird profile is missing reviewed public media")
    if frozenset(observed_media_providers) != advertised_media_providers:
        findings.append("manifest media source marker does not match species profiles")
    if frozenset(observed_audio_providers) != advertised_audio_providers:
        findings.append("manifest audio source marker does not match species profiles")
    counts = manifest.get("counts")
    if not isinstance(counts, dict):
        findings.append("manifest counts are missing")
    else:
        if counts.get("media_items") != media_item_count:
            findings.append("manifest media_items count does not match profiles")
        if counts.get("species_with_media") != species_with_media:
            findings.append("manifest species_with_media count does not match profiles")
        if counts.get("audio_items") != audio_item_count:
            findings.append("manifest audio_items count does not match profiles")
        if counts.get("species_with_audio") != species_with_audio:
            findings.append("manifest species_with_audio count does not match profiles")
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


def _audit_species_profile(
    profile: dict[str, Any],
    relative: Path,
    *,
    mode: object,
    attribution_by_id: Mapping[str, dict[str, Any]],
) -> list[str]:
    findings = _audit_forbidden_keys(profile, relative)
    for field in ("species_code", "common_name", "scientific_name"):
        if not isinstance(profile.get(field), str) or not profile[field].strip():
            findings.append(f"{relative} is missing {field}")
    media = profile.get("media")
    if not isinstance(media, list):
        findings.append(f"{relative} media must be an array")
        return findings
    if "call" not in profile:
        findings.append(f"{relative} must declare an optional audio call")
    seen_media_ids: set[str] = set()
    seen_source_urls: set[str] = set()
    for item in media:
        if not isinstance(item, dict):
            findings.append(f"{relative} contains malformed media")
            continue
        provider = item.get("provider")
        required = (
            "media_id",
            "creator",
            "source_url",
            "license",
            "license_url",
            "attribution_id",
            "url",
            "scientific_name",
            "title",
            "alt_text",
            "sha256",
            "mime_type",
        )
        if not isinstance(provider, str) or provider not in _MEDIA_PROVIDER_LABELS:
            findings.append(f"{relative} media provider is not allowed")
        elif canonical_license(provider, item.get("license")) is None:
            findings.append(f"{relative} media license is not allowed for {provider}")
        for field in required:
            if not isinstance(item.get(field), str) or not item[field].strip():
                findings.append(f"{relative} media is missing {field}")
        if not isinstance(provider, str) or provider not in _MEDIA_PROVIDER_LABELS:
            continue
        provider_label = _MEDIA_PROVIDER_LABELS[provider]
        media_id = item.get("media_id")
        attribution_id = item.get("attribution_id")
        source_url = item.get("source_url")
        asset_url = item.get("url")
        sha256 = item.get("sha256")
        license_pair = canonical_license(provider, item.get("license"))
        match = _PUBLIC_MEDIA_URL.fullmatch(asset_url) if isinstance(asset_url, str) else None
        media_id_match = (
            _MEDIA_ID_PATTERNS[provider].fullmatch(media_id) if isinstance(media_id, str) else None
        )
        attribution_id_match = (
            _MEDIA_ATTRIBUTION_ID_PATTERNS[provider].fullmatch(attribution_id)
            if isinstance(attribution_id, str)
            else None
        )
        source_url_match = (
            _MEDIA_SOURCE_PAGE_PATTERNS[provider].fullmatch(source_url)
            if isinstance(source_url, str)
            else None
        )
        if (
            provider == "wikimedia"
            and isinstance(source_url, str)
            and not _valid_wikimedia_file_page(source_url)
        ):
            source_url_match = None
        if media_id_match is None:
            findings.append(f"{relative} {provider_label} media_id is invalid")
        elif media_id in seen_media_ids:
            findings.append(f"{relative} repeats {provider_label} media_id {media_id}")
        else:
            assert isinstance(media_id, str)
            seen_media_ids.add(media_id)
        if attribution_id_match is None:
            findings.append(f"{relative} {provider_label} attribution_id is invalid")
        if source_url_match is None:
            findings.append(f"{relative} {provider_label} source_url is not an official media page")
        elif source_url in seen_source_urls:
            findings.append(f"{relative} repeats a {provider_label} source page")
        else:
            assert isinstance(source_url, str)
            seen_source_urls.add(source_url)
        if (
            provider == "inaturalist"
            and media_id_match is not None
            and attribution_id_match is not None
            and source_url_match is not None
            and (
                media_id_match.group("photo_id") != source_url_match.group("photo_id")
                or attribution_id_match.group("photo_id") != source_url_match.group("photo_id")
            )
        ):
            findings.append(f"{relative} iNaturalist identifiers do not match its photo page")
        if (
            not isinstance(sha256, str)
            or not _SHA256.fullmatch(sha256)
            or match is None
            or match.group("sha") != sha256
            or match.group("shard") != sha256[:2]
        ):
            findings.append(f"{relative} {provider_label} asset URL is not content-addressed")
        if license_pair is None or item.get("license_url") != license_pair[1]:
            findings.append(f"{relative} {provider_label} license URL is invalid")
        if item.get("scientific_name") != profile.get("scientific_name"):
            findings.append(
                f"{relative} {provider_label} scientific identity does not match the profile"
            )
        if item.get("kind") != "photo" or item.get("mime_type") != "image/webp":
            findings.append(f"{relative} {provider_label} media must be a WebP photo")
        for dimension in ("width", "height"):
            value = item.get(dimension)
            if type(value) is not int or not 1 <= value <= 650:
                findings.append(f"{relative} {provider_label} media has invalid {dimension}")
        creator = item.get("creator")
        title = item.get("title")
        alt_text = item.get("alt_text")
        identity_values = {
            str(value).strip().casefold()
            for value in (profile.get("common_name"), profile.get("scientific_name"), title)
            if isinstance(value, str) and value.strip()
        }
        if not isinstance(creator, str) or creator.strip().casefold() in identity_values:
            findings.append(f"{relative} {provider_label} creator credit is not credible")
        for field in ("creator", "title", "caption", "alt_text"):
            value = item.get(field)
            reason = _public_media_privacy_reason(value) if isinstance(value, str) else None
            if reason is not None:
                findings.append(f"{relative} {provider_label} {field} exposes {reason}")
        if provider != "usfws" or not isinstance(title, str) or not isinstance(alt_text, str):
            continue
        restricted_mark = restricted_usfws_mark_reason(
            (
                title,
                item.get("caption") if isinstance(item.get("caption"), str) else None,
                alt_text,
                source_url if isinstance(source_url, str) else None,
                asset_url if isinstance(asset_url, str) else None,
            )
        )
        if restricted_mark is not None:
            findings.append(f"{relative} USFWS item identifies restricted mark {restricted_mark}")
    call = profile.get("call")
    if call is None:
        return findings
    if not valid_public_audio_call(
        call,
        species_code=(
            profile.get("species_code") if isinstance(profile.get("species_code"), str) else None
        ),
        common_name=(
            profile.get("common_name") if isinstance(profile.get("common_name"), str) else None
        ),
        scientific_name=(
            profile.get("scientific_name")
            if isinstance(profile.get("scientific_name"), str)
            else None
        ),
    ):
        findings.append(f"{relative} audio call fails the public contract")
        return findings
    assert isinstance(call, dict)
    attribution_id = str(call["attribution_id"])
    attribution = attribution_by_id.get(attribution_id)
    expected_attribution = {
        "attribution_id": attribution_id,
        "kind": "audio",
        "provider": call["provider"],
        "provider_id": call["provider_id"],
        "common_name": profile["common_name"],
        "scientific_name": profile["scientific_name"],
        "creator": call["creator"],
        "source_url": call["source_url"],
        "license": call["license"],
        "license_url": call["license_url"],
        "recording_type": call["recording_type"],
        "modifications": call["modifications"],
    }
    if attribution != expected_attribution:
        findings.append(f"{relative} audio call lacks exact item attribution")
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
    parser.add_argument(
        "--shell-only",
        action="store_true",
        help="require a built static application with no bundled data/ snapshot",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    findings = audit_public_site(
        args.site,
        args.workflows,
        args.repository_root,
        shell_only=args.shell_only,
    )
    if findings:
        print("Rufous public release safety audit failed:")
        for finding in findings:
            print(f"- {finding}")
        return 1
    print("Rufous public release safety audit passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
