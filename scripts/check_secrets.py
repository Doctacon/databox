#!/usr/bin/env python3
"""Scan tracked text files for credentials without printing secret material."""

from __future__ import annotations

import re
import subprocess
import sys
from collections.abc import Iterable
from pathlib import Path

ALLOW_DIRECTIVE = "secret-scan: allow"

TEXT_SUFFIXES = {
    ".bash",
    ".conf",
    ".config",
    ".css",
    ".env",
    ".fish",
    ".go",
    ".hcl",
    ".htm",
    ".html",
    ".ini",
    ".java",
    ".js",
    ".json",
    ".jsx",
    ".key",
    ".lock",
    ".md",
    ".mjs",
    ".pem",
    ".properties",
    ".py",
    ".rs",
    ".sh",
    ".sql",
    ".toml",
    ".ts",
    ".tsx",
    ".tf",
    ".txt",
    ".xml",
    ".yaml",
    ".yml",
    ".zsh",
}
TEXT_FILENAMES = {
    ".env",
    ".env.example",
    ".env.sample",
    ".env.template",
    ".netrc",
    ".npmrc",
    ".pypirc",
    "Dockerfile",
    "Makefile",
    "Taskfile",
}
EXCLUDED_DIRECTORIES = {
    ".cache",
    ".dagster",
    ".dlt",
    ".git",
    ".logs",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".sqlmesh",
    ".task",
    ".venv",
    "__pycache__",
    "build",
    "dist",
    "htmlcov",
    "logs",
    "node_modules",
    "site",
    "venv",
}
EXCLUDED_FILENAMES = {".DS_Store"}

# These are exact non-credential values used by tests or documentation. Real
# provider-shaped tokens are checked first and cannot be bypassed by this list.
SYNTHETIC_VALUES = {
    "ABCDEFGHIJKLMNOP/20260710/eu-west-1/s3/aws4_request",
    "bridge-secret",
    "configured-bridge-secret",
    "configured-secret",
    "marquez",
    "private-value",
    "secret-fixture-key",
    "secret-never-rendered",
    "synthetic-password",
    "test-key",
    "test-secret-that-must-not-appear",
    "your_ebird_api_token_here",
    "your_noaa_api_token_here",
    "your_xeno_canto_api_key_here",
}
SYNTHETIC_HIGH_CONFIDENCE_VALUES = {"-----BEGIN PRIVATE KEY----- hidden"}
PLACEHOLDER_VALUE = re.compile(
    r"(?:test|fake|dummy|synthetic|example|placeholder|redacted|changeme)"
    r"(?:[-_][a-z0-9]+)*",
    re.IGNORECASE,
)
REFERENCE_PREFIXES = ("op://", "vault://", "aws-secrets://", "doppler://")
ENVIRONMENT_REFERENCE = re.compile(r"\$(?:[A-Za-z_][A-Za-z0-9_]*|\{[A-Za-z_][A-Za-z0-9_]*\})")
CODE_REFERENCE = re.compile(
    r"(?:config|settings)(?:\.[A-Za-z_][A-Za-z0-9_]*)+"
    r"|os\.(?:environ|getenv)(?:\.[A-Za-z_][A-Za-z0-9_]*)*",
    re.IGNORECASE,
)
CODE_SUFFIXES = {".go", ".java", ".js", ".jsx", ".mjs", ".py", ".rs", ".ts", ".tsx"}
CODE_IDENTIFIER_REFERENCE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)*")
ENVIRONMENT_ACCESS = re.compile(
    r"os\.(?:getenv|environ\.get)\(\s*[\"'][A-Za-z_][A-Za-z0-9_]*[\"']\s*\)"
)
WRAPPED_LITERAL = re.compile(
    r"[A-Za-z_][A-Za-z0-9_.]*\(\s*(?P<literal>\"[^\"\r\n]*\"|'[^'\r\n]*')\s*\)"
)

# Provider formats are intentionally independent from the generic assignment
# heuristic. This keeps a real-looking key detectable even in a test fixture.
HIGH_CONFIDENCE_PATTERNS = (
    (re.compile(r"\b(?:AKIA|ASIA|ABIA|ACCA)[A-Z0-9]{16}\b"), "AWS access key ID"),
    (re.compile(r"\bgh[opusr]_[A-Za-z0-9]{36,255}\b"), "GitHub token"),
    (re.compile(r"\bglpat-[A-Za-z0-9_-]{20,}\b"), "GitLab token"),
    (re.compile(r"\bnpm_[A-Za-z0-9]{36}\b"), "npm token"),
    (re.compile(r"\bsk-(?:proj-)?[A-Za-z0-9_-]{20,}\b"), "OpenAI-style API key"),
    (re.compile(r"\bsk_live_[A-Za-z0-9]{16,}\b"), "Stripe live secret key"),
    (re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{10,}\b"), "Slack token"),
    (re.compile(r"\bAIza[0-9A-Za-z_-]{35}\b"), "Google API key"),
    (
        re.compile(r"-----BEGIN (?:RSA |EC |DSA |OPENSSH |ENCRYPTED )?PRIVATE KEY-----"),
        "private key",
    ),
    (
        re.compile(
            r"\b(?:postgres(?:ql)?|mysql|mongodb(?:\+srv)?|redis)://"
            r"[^\s:/]+:[^\s/@]+@[^\s/]+",
            re.IGNORECASE,
        ),
        "database URL with credentials",
    ),
    (
        re.compile(r"\bBearer\s+([A-Za-z0-9._~+/=-]{20,})", re.IGNORECASE),
        "bearer token",
    ),
)

ASSIGNMENT = re.compile(
    r"(?:"
    r"(?P<quote>[\"'])(?P<quoted_name>[A-Za-z_][A-Za-z0-9_-]*)(?P=quote)"
    r"|(?<![\"'A-Za-z0-9_-])(?P<bare_name>[A-Za-z_][A-Za-z0-9_-]*)"
    r")\s*[:=]\s*"
    r"(?P<value>"
    r"[A-Za-z_][A-Za-z0-9_.]*\(\s*(?:\"[^\"\r\n]{8,}\"|'[^'\r\n]{8,}')\s*\)"
    r"|\"[^\"\r\n]{8,}\"|'[^'\r\n]{8,}'"
    r"|[A-Za-z0-9][A-Za-z0-9_./+@:$=-]{7,}"
    r")"
)


def _is_sensitive_name(name: str) -> bool:
    separated = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", name)
    parts = {part for part in re.split(r"[_-]+", separated.lower()) if part}
    if parts & {
        "auth",
        "credential",
        "credentials",
        "password",
        "passwd",
        "pwd",
        "secret",
        "token",
    }:
        return True

    compact = "".join(parts)
    if compact.endswith(
        (
            "apikey",
            "apitoken",
            "accesstoken",
            "authtoken",
            "bearertoken",
            "claimtoken",
            "clientsecret",
            "privatekey",
            "refreshtoken",
        )
    ):
        return True

    key_qualifiers = {
        "access",
        "api",
        "auth",
        "client",
        "credential",
        "encryption",
        "private",
        "secret",
        "signing",
        "ssh",
    }
    return "key" in parts and bool(parts & key_qualifiers)


def _literal_value(raw_value: str) -> tuple[str, bool]:
    wrapper = WRAPPED_LITERAL.fullmatch(raw_value)
    if wrapper is not None:
        raw_value = wrapper.group("literal")
    quoted = len(raw_value) >= 2 and raw_value[0] == raw_value[-1] and raw_value[0] in "\"'"
    return (raw_value[1:-1] if quoted else raw_value).strip(), quoted


def _is_safe_assignment_value(raw_value: str, *, name: str, path: Path) -> bool:
    if ENVIRONMENT_ACCESS.fullmatch(raw_value):
        return True
    value, quoted = _literal_value(raw_value)
    lowered = value.lower()
    if value in SYNTHETIC_VALUES or PLACEHOLDER_VALUE.fullmatch(value):
        return True
    if lowered.startswith(REFERENCE_PREFIXES):
        return True
    if ENVIRONMENT_REFERENCE.fullmatch(value):
        return True
    if lowered in {"none", "null", "true", "false", "disabled"}:
        return True
    if value.casefold() == name.casefold():
        return True
    if CODE_REFERENCE.fullmatch(value):
        return True
    if path.suffix.lower() in CODE_SUFFIXES:
        if not quoted and CODE_IDENTIFIER_REFERENCE.fullmatch(value):
            return True
        if quoted and re.fullmatch(r"(?:\{[^{}\r\n]+\})+", value):
            return True
    return False


def _is_exact_synthetic_high_confidence_match(line: str, *, column: int) -> bool:
    for value in SYNTHETIC_HIGH_CONFIDENCE_VALUES:
        if column == 0 or line[column : column + len(value)] != value:
            continue
        quote = line[column - 1]
        if quote in "\"'" and line[column + len(value) : column + len(value) + 1] == quote:
            return True
    return False


def _path_is_excluded(path: Path, *, root: Path) -> bool:
    try:
        relative = path.absolute().relative_to(root.absolute())
    except ValueError:
        relative = Path(path.name)
    return path.name in EXCLUDED_FILENAMES or any(
        part in EXCLUDED_DIRECTORIES for part in relative.parts
    )


def should_check_file(path: Path, *, root: Path) -> bool:
    """Return whether *path* is an eligible, non-excluded text file."""
    if _path_is_excluded(path, root=root) or not path.is_file():
        return False
    return (
        path.suffix.lower() in TEXT_SUFFIXES
        or path.name in TEXT_FILENAMES
        or path.name.startswith(".env.")
    )


def _git_files(directory: Path) -> tuple[Path, list[Path]] | None:
    """Return tracked files below *directory*, or None when it is not in Git."""
    probe = subprocess.run(
        ["git", "-C", str(directory), "rev-parse", "--show-toplevel"],
        check=False,
        capture_output=True,
        text=True,
    )
    if probe.returncode != 0:
        return None
    root = Path(probe.stdout.strip()).resolve()
    try:
        relative = directory.resolve().relative_to(root)
    except ValueError:
        return None
    result = subprocess.run(
        ["git", "-C", str(root), "ls-files", "-z", "--", relative.as_posix() or "."],
        check=False,
        capture_output=True,
    )
    if result.returncode != 0:
        return None
    return root, [root / item.decode() for item in result.stdout.split(b"\0") if item]


def iter_files(arguments: Iterable[str]) -> list[Path]:
    """Expand files and directories, preferring Git's tracked-file inventory."""
    files: dict[Path, Path] = {}
    for argument in arguments:
        path = Path(argument)
        if path.is_file():
            inventory = _git_files(path.parent)
            root = inventory[0] if inventory is not None else path.parent
            files[path] = root
            continue
        if not path.is_dir():
            continue
        inventory = _git_files(path)
        if inventory is None:
            root = path.resolve()
            candidates = [candidate for candidate in path.rglob("*") if candidate.is_file()]
        else:
            root, candidates = inventory
        files.update((candidate, root) for candidate in candidates)
    return sorted(
        (path for path, root in files.items() if should_check_file(path, root=root)),
        key=lambda item: str(item),
    )


def scan_file(path: Path) -> list[tuple[int, str]]:
    """Return redacted ``(line number, description)`` findings for one file."""
    content = path.read_text(encoding="utf-8")
    lines = content.splitlines()
    findings: list[tuple[int, str]] = []

    for pattern, description in HIGH_CONFIDENCE_PATTERNS:
        for match in pattern.finditer(content):
            line_number = content.count("\n", 0, match.start()) + 1
            line = lines[line_number - 1] if line_number <= len(lines) else ""
            line_start = content.rfind("\n", 0, match.start()) + 1
            if _is_exact_synthetic_high_confidence_match(line, column=match.start() - line_start):
                continue
            findings.append((line_number, description))

    for line_number, line in enumerate(lines, start=1):
        if ALLOW_DIRECTIVE in line:
            continue
        for match in ASSIGNMENT.finditer(line):
            name = match.group("quoted_name") or match.group("bare_name")
            if not _is_sensitive_name(name):
                continue
            if _is_safe_assignment_value(match.group("value"), name=name, path=path):
                continue
            findings.append((line_number, "credential-like literal assignment"))

    return sorted(set(findings))


def main(arguments: list[str] | None = None) -> int:
    """Scan explicit paths, defaulting to the current repository directory."""
    requested_paths = arguments or ["."]
    directory_scan = any(Path(argument).is_dir() for argument in requested_paths)
    paths = iter_files(requested_paths)
    if directory_scan and not paths:
        print("Secret scan failed: no eligible files found for directory scan.", file=sys.stderr)
        return 2
    findings: list[tuple[Path, list[tuple[int, str]]]] = []
    read_errors: list[tuple[Path, str]] = []
    for path in paths:
        try:
            issues = scan_file(path)
        except (OSError, UnicodeError) as exc:
            read_errors.append((path, str(exc)))
            continue
        if issues:
            findings.append((path, issues))

    if read_errors:
        print("Secret scan could not read eligible files:", file=sys.stderr)
        for path, error in read_errors:
            print(f"  {path}: {error}", file=sys.stderr)
        return 2

    if findings:
        print("Secret scan failed: potential credentials detected.", file=sys.stderr)
        for path, issues in findings:
            for line_number, description in issues:
                print(f"  {path}:{line_number}: {description}", file=sys.stderr)
        print(
            f"Use '{ALLOW_DIRECTIVE}' only for a reviewed synthetic fixture.",
            file=sys.stderr,
        )
        return 1

    print(f"Secret scan passed: {len(paths)} eligible files checked.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
