#!/usr/bin/env python3
"""Check for sensitive environment variables and secrets in code."""

import re
import sys
from pathlib import Path

# Patterns that indicate sensitive information
SENSITIVE_PATTERNS = [
    # Environment variable assignments
    (
        r'(?:export\s+)?([A-Z_]+(?:KEY|TOKEN|SECRET|PASSWORD|PASS|PWD|AUTH|CREDENTIAL|API|PRIVATE)(?:[A-Z_]*)?)\s*=\s*["\']?([^"\'\s]+)',
        "Environment variable with sensitive name",
    ),
    # Direct API keys/tokens
    (
        r'(?:api[_-]?key|token|secret|password|auth[_-]?token)\s*[:=]\s*["\']([a-zA-Z0-9\-_]{20,})["\']',
        "Hardcoded API key/token",
    ),
    # AWS credentials
    (r"(?:AKIA|ASIA|ABIA|ACCA)[A-Z0-9]{16}", "AWS Access Key ID"),
    (
        r'(?:aws[_-]?secret[_-]?access[_-]?key)\s*[:=]\s*["\']([a-zA-Z0-9/+=]{40})["\']',
        "AWS Secret Access Key",
    ),
    # Database URLs with credentials
    (
        r"(?:postgresql|postgres|mysql|mongodb|redis)://[^:]+:[^@]+@[^/]+",
        "Database URL with credentials",
    ),
    # Bearer tokens
    (r"Bearer\s+[a-zA-Z0-9\-_\.]{20,}", "Bearer token"),
    # Private keys
    (r"-----BEGIN\s+(?:RSA\s+)?PRIVATE\s+KEY-----", "Private key"),
    # Generic secrets
    (r'(?:secret|password|passwd|pwd)\s*[:=]\s*["\'](.{8,})["\']', "Hardcoded password/secret"),
]

# File patterns to check
INCLUDE_PATTERNS = [
    "*.py",
    "*.js",
    "*.ts",
    "*.jsx",
    "*.tsx",
    "*.java",
    "*.go",
    "*.rs",
    "*.yml",
    "*.yaml",
    "*.json",
    "*.toml",
    "*.ini",
    "*.conf",
    "*.config",
    "*.sh",
    "*.bash",
    "*.zsh",
    "*.fish",
    "Dockerfile",
    ".dockerignore",
    "Makefile",
]

# Files/directories to exclude
EXCLUDE_PATTERNS = [
    ".git",
    ".dlt",
    ".sqlmesh",
    "__pycache__",
    "node_modules",
    ".venv",
    "venv",
    "*.pyc",
    "*.pyo",
    "*.pyd",
    ".DS_Store",
    "*.log",
    ".env",
    ".env.*",
    "config/settings.py",  # These are expected to have env vars
]

# Allowed false positives (add specific strings that are known to be safe)
ALLOWED_VALUES = {
    "your_api_key_here",
    "your_token_here",
    "your_secret_here",
    "example_key",
    "test_token",
    "dummy_secret",
    "placeholder",
    "<your-api-key>",
    "${API_KEY}",
    "${TOKEN}",
    "os.environ.get",
    "os.getenv",
    "settings.",
    "config.",
}


def should_check_file(file_path: Path) -> bool:
    """Check if file should be scanned."""
    # Check excludes
    for pattern in EXCLUDE_PATTERNS:
        if pattern in str(file_path):
            return False

    # Check includes
    for pattern in INCLUDE_PATTERNS:
        if file_path.match(pattern):
            return True

    return False


def is_allowed_value(value: str) -> bool:
    """Check if the value is in allowed list or is a reference."""
    value_lower = value.lower()

    # Check if it's a known safe value
    for allowed in ALLOWED_VALUES:
        if allowed.lower() in value_lower:
            return True

    # Check if it's an environment variable reference
    if value.startswith("$") or value.startswith("${"):
        return True

    # Check if it's a function call or attribute access
    if "(" in value or "." in value:
        return True

    return False


def scan_file(file_path: Path) -> list[tuple[int, str, str]]:
    """Scan a file for secrets. Returns list of (line_number, issue, match)."""
    issues = []

    try:
        with open(file_path, encoding="utf-8") as f:
            content = f.read()
            content.splitlines()

        for pattern, description in SENSITIVE_PATTERNS:
            for match in re.finditer(pattern, content, re.IGNORECASE | re.MULTILINE):
                # Get line number
                line_num = content[: match.start()].count("\n") + 1
                matched_text = match.group(0)

                # Check if it's an allowed value
                if is_allowed_value(matched_text):
                    continue

                # For environment variable patterns, check the value
                if match.groups():
                    value = match.groups()[-1] if len(match.groups()) > 1 else match.group(1)
                    if is_allowed_value(value):
                        continue

                issues.append((line_num, description, matched_text))

    except Exception as e:
        print(f"Error reading {file_path}: {e}")

    return issues


def main():
    """Main function to check files passed as arguments."""
    if len(sys.argv) < 2:
        print("No files to check")
        return 0

    all_issues = []

    for file_arg in sys.argv[1:]:
        file_path = Path(file_arg)

        if not file_path.exists():
            continue

        if not should_check_file(file_path):
            continue

        issues = scan_file(file_path)
        if issues:
            all_issues.append((file_path, issues))

    if all_issues:
        print("\n❌ SECURITY CHECK FAILED: Potential secrets detected!\n")

        for file_path, issues in all_issues:
            print(f"📄 {file_path}")
            for line_num, description, match in issues:
                # Truncate match for display
                display_match = match[:50] + "..." if len(match) > 50 else match
                print(f"  Line {line_num}: {description}")
                print(f"    Found: {display_match}")
            print()

        print("🔒 Security Tips:")
        print("  - Use environment variables for sensitive values")
        print("  - Add sensitive files to .gitignore")
        print("  - Use .env files for local development")
        print("  - Never commit real API keys, tokens, or passwords")
        print("\nIf these are false positives, you can:")
        print("  1. Add the value to ALLOWED_VALUES in scripts/check_secrets.py")
        print("  2. Use environment variable references like ${API_KEY}")
        print("  3. Move sensitive config to .env files")

        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
