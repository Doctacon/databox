#!/usr/bin/env python3
"""Run one tightly fenced, disposable Iceberg warehouse recovery drill."""

from __future__ import annotations

import argparse
import base64
import hashlib
import hmac
import importlib.metadata
import json
import os
import re
import secrets
import stat
import subprocess
import sys
import tempfile
import time
from collections.abc import Callable, Mapping, MutableMapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, Protocol
from urllib.parse import quote, urlencode, urlparse
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener

from dotenv import dotenv_values


class DrillError(RuntimeError):
    """The recovery drill refused an unsafe or inconsistent operation."""


class AwsCliOperationError(DrillError):
    """An AWS CLI operation failed with one sanitized error category."""

    def __init__(self, error_kind: str) -> None:
        if not re.fullmatch(r"[a-z][a-z0-9-]{0,63}", error_kind):
            raise ValueError("AWS CLI error category is invalid")
        self.error_kind = error_kind
        super().__init__("AWS CLI operation failed")


class SeedStageError(DrillError):
    """A Seed-A operation failed at one sanitized execution stage."""

    def __init__(self, stage: str, *, error_kind: str = "unclassified") -> None:
        if not re.fullmatch(r"[a-z][a-z0-9-]{0,63}", stage):
            raise ValueError("Seed-A error stage is invalid")
        if not re.fullmatch(r"[a-z][a-z0-9-]{0,63}", error_kind):
            raise ValueError("Seed-A error category is invalid")
        self.stage = stage
        self.error_kind = error_kind
        super().__init__("isolated Seed-A execution stage failed")


class RecoveryStageError(DrillError):
    """A Recovery-A operation failed at one sanitized execution stage."""

    def __init__(
        self,
        stage: str,
        *,
        error_kind: str = "unclassified",
        containment_error_kind: str | None = None,
    ) -> None:
        if not re.fullmatch(r"[a-z][a-z0-9-]{0,63}", stage):
            raise ValueError("Recovery-A error stage is invalid")
        if not re.fullmatch(r"[a-z][a-z0-9-]{0,63}", error_kind):
            raise ValueError("Recovery-A error category is invalid")
        if containment_error_kind is not None and not re.fullmatch(
            r"[a-z][a-z0-9-]{0,63}", containment_error_kind
        ):
            raise ValueError("Recovery-A containment error category is invalid")
        self.stage = stage
        self.error_kind = error_kind
        self.containment_error_kind = containment_error_kind
        super().__init__("isolated Recovery-A execution stage failed")


def _exception_error_kind(error: Exception) -> str:
    if isinstance(error, AwsCliOperationError):
        return error.error_kind
    error_type = type(error)
    if error_type.__module__.startswith("pyiceberg.") and re.fullmatch(
        r"[A-Za-z][A-Za-z0-9]{0,63}", error_type.__name__
    ):
        normalized = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", "-", error_type.__name__).lower()
        candidate = f"pyiceberg-{normalized}"
        if len(candidate) > 64:
            return "unclassified"
        if error.args and isinstance(error.args[0], str):
            match = re.match(r"^([A-Za-z][A-Za-z0-9_.-]{0,63}):(?:\s|$)", error.args[0])
            if match is not None:
                server_type = match.group(1).rsplit(".", 1)[-1]
                if server_type.endswith(("Error", "Exception")):
                    server_type = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", "-", server_type)
                    server_type = re.sub(r"[^A-Za-z0-9]+", "-", server_type).strip("-")
                    detailed = f"{candidate}-{server_type.lower()}"
                    if len(detailed) <= 64:
                        return detailed
        return candidate
    return "unclassified"


def _seed_stage(stage: str, operation: Callable[[], Any]) -> Any:
    try:
        return operation()
    except SeedStageError:
        raise
    except Exception as exc:
        raise SeedStageError(stage, error_kind=_exception_error_kind(exc)) from exc


def _recovery_stage(stage: str, operation: Callable[[], Any]) -> Any:
    try:
        return operation()
    except RecoveryStageError:
        raise
    except Exception as exc:
        raise RecoveryStageError(stage, error_kind=_exception_error_kind(exc)) from exc


def _aws_cli_error_kind(stderr: str) -> str:
    lowered = stderr.lower()
    if "error parsing parameter" in lowered:
        return "aws-parameter-parse"
    match = re.search(r"An error occurred \(([A-Za-z0-9.]+)\) when calling", stderr)
    if match is not None:
        return f"aws-{match.group(1).lower()}"
    if "could not connect to the endpoint" in lowered:
        return "aws-endpoint-unavailable"
    if "ssl validation failed" in lowered:
        return "aws-tls-failure"
    if "unable to locate credentials" in lowered:
        return "aws-credentials-unavailable"
    return "aws-cli-error"


@dataclass(frozen=True)
class DrillScope:
    """Generated names that fence one disposable recovery drill."""

    run_id: str
    prefix: str
    catalog: str
    namespace: str
    table: str


@dataclass(frozen=True)
class GraphNode:
    """One exact versioned object required by the synthetic Iceberg table."""

    key: str
    kind: str
    source_version_id: str
    etag: str
    size: int
    sha256: str
    depth: int


@dataclass(frozen=True)
class TableCapture:
    """Private point-in-time contract returned by the live preparation adapter."""

    bucket: str
    table_uuid: str
    metadata_location: str
    snapshot_id: int
    schema_sha256: str
    row_count: int
    rows_sha256: str
    nodes: tuple[GraphNode, ...]


@dataclass(frozen=True)
class ObjectState:
    """Observed latest state of one exact graph key."""

    exists: bool
    delete_marker: bool
    version_id: str | None = None
    size: int | None = None
    sha256: str | None = None


@dataclass(frozen=True)
class DeleteResult:
    """Result of an ordinary delete in a versioned bucket."""

    delete_marker: bool
    version_id: str


@dataclass(frozen=True)
class ValidationResult:
    """Fresh catalog, graph, and row validation after restoration."""

    table_uuid: str
    metadata_location: str
    snapshot_id: int
    logical_graph_sha256: str
    row_count: int
    rows_sha256: str


@dataclass(frozen=True)
class VersionEntry:
    """One exact object version or delete marker from a complete key timeline."""

    key: str
    version_id: str
    latest: bool
    delete_marker: bool
    etag: str | None = None
    size: int | None = None


@dataclass(frozen=True)
class GraphObject:
    """One external file reached from the constrained Iceberg point-A metadata."""

    location: str
    kind: str
    depth: int


@dataclass(frozen=True)
class RuntimeBinding:
    """Non-secret fingerprints that bind a live manifest to its reviewed runtime."""

    source_revision: str
    script_sha256: str
    python_version: str
    pyiceberg_version: str
    pyarrow_version: str
    configuration_sha256: str

    def as_manifest(self) -> dict[str, str]:
        return {
            "sourceRevision": self.source_revision,
            "scriptSha256": self.script_sha256,
            "pythonVersion": self.python_version,
            "pyicebergVersion": self.pyiceberg_version,
            "pyarrowVersion": self.pyarrow_version,
            "configurationSha256": self.configuration_sha256,
        }


@dataclass(frozen=True, repr=False)
class RecoverySettings:
    """Private host settings used to generate and execute isolated plans."""

    bucket: str
    region: str
    storage_role_arn: str
    profile: str
    identity_sha256: str
    run_secret: str

    @classmethod
    def load(cls) -> RecoverySettings:
        values = {
            key: value
            for key, value in dotenv_values(_ROOT / ".env").items()
            if isinstance(value, str) and value
        }
        values.update(os.environ)
        names = {
            "bucket": "DATABOX_AWS_S3_BUCKET",
            "region": "DATABOX_AWS_REGION",
            "storage_role_arn": "DATABOX_RECOVERY_STORAGE_ROLE_ARN",
            "profile": "DATABOX_RECOVERY_PROFILE",
            "identity_sha256": "DATABOX_RECOVERY_IDENTITY_SHA256",
            "run_secret": "DATABOX_RECOVERY_RUN_SECRET",  # secret-scan: allow
        }
        if any(not values.get(environment_name) for environment_name in names.values()):
            raise DrillError("required private recovery settings are missing")
        settings = cls(
            **{
                field_name: values[environment_name]
                for field_name, environment_name in names.items()
            }
        )
        if not re.fullmatch(r"[a-z0-9][a-z0-9.-]{1,61}[a-z0-9]", settings.bucket):
            raise DrillError("warehouse bucket setting is invalid")
        if not re.fullmatch(r"[a-z]{2}(?:-gov)?-[a-z]+-\d", settings.region):
            raise DrillError("warehouse region setting is invalid")
        if not re.fullmatch(
            r"arn:(?:aws|aws-us-gov):iam::[0-9]{12}:role/[A-Za-z0-9+=,.@_/-]+",
            settings.storage_role_arn,
        ):
            raise DrillError("Polaris storage role setting is invalid")
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.@+-]{0,127}", settings.profile):
            raise DrillError("AWS CLI profile name is invalid")
        if not _SHA256.fullmatch(settings.identity_sha256):
            raise DrillError("expected AWS identity digest is invalid")
        if not 32 <= len(settings.run_secret) <= 4096:
            raise DrillError("private recovery run secret is outside the safe length")
        return settings


@dataclass(frozen=True)
class ImagePin:
    """Read-only Docker image identity and launch contract pinned in Seed-A."""

    reference: str
    image_id: str
    entrypoint: tuple[str, ...]
    command: tuple[str, ...]
    environment: tuple[str, ...] = ()
    user: str = ""
    working_directory: str = ""

    def as_manifest(self) -> dict[str, object]:
        return {
            "reference": self.reference,
            "imageId": self.image_id,
            "entrypoint": list(self.entrypoint),
            "command": list(self.command),
            "environment": list(self.environment),
            "user": self.user,
            "workingDirectory": self.working_directory,
        }


@dataclass(frozen=True, repr=False)
class RunCredentials:
    postgres_password: str
    polaris_client_id: str
    polaris_client_secret: str


@dataclass(frozen=True, repr=False)
class AwsCredentials:
    access_key_id: str
    secret_access_key: str
    session_token: str


@dataclass(frozen=True, repr=False)
class VerifiedAwsContext:
    environment: Mapping[str, str]
    identity: CallerIdentity
    credentials: AwsCredentials
    store: Any


CommandRunner = Callable[..., subprocess.CompletedProcess[str]]


def _isolate_parent_aws_environment(environment: MutableMapping[str, str], *, region: str) -> None:
    """Disable ambient SDK providers and proxies before PyIceberg is constructed."""
    if not re.fullmatch(r"[a-z]{2}(?:-gov)?-[a-z]+-\d", region):
        raise DrillError("AWS region is invalid")
    for name in tuple(environment):
        if name.startswith("AWS_") or name.upper() in {
            "BOTO_CONFIG",
            "HTTP_PROXY",
            "HTTPS_PROXY",
            "ALL_PROXY",
        }:
            environment.pop(name, None)
    environment.update(
        {
            "AWS_CONFIG_FILE": os.devnull,
            "AWS_SHARED_CREDENTIALS_FILE": os.devnull,
            "AWS_EC2_METADATA_DISABLED": "true",
            "BOTO_CONFIG": os.devnull,
            "AWS_REGION": region,
            "AWS_DEFAULT_REGION": region,
            "NO_PROXY": "127.0.0.1,localhost,::1",
            "no_proxy": "127.0.0.1,localhost,::1",
        }
    )


def _profile_environment(base: Mapping[str, str], *, profile: str, region: str) -> dict[str, str]:
    """Build one explicit AWS CLI profile context without inherited providers."""
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.@+-]{0,127}", profile):
        raise DrillError("AWS CLI profile name is invalid")
    if not re.fullmatch(r"[a-z]{2}(?:-gov)?-[a-z]+-\d", region):
        raise DrillError("AWS region is invalid")
    retained = {
        name: base[name]
        for name in (
            "HOME",
            "PATH",
            "LANG",
            "LC_ALL",
            "LC_CTYPE",
            "TMPDIR",
            "SSL_CERT_FILE",
            "SSL_CERT_DIR",
        )
        if base.get(name)
    }
    retained.update(
        {
            "AWS_PROFILE": profile,
            "AWS_REGION": region,
            "AWS_DEFAULT_REGION": region,
            "AWS_EC2_METADATA_DISABLED": "true",
        }
    )
    return retained


def _credential_environment(
    base: Mapping[str, str],
    *,
    credentials: AwsCredentials,
    region: str,
) -> dict[str, str]:
    """Pin one exported credential set without retaining its mutable profile."""
    if (
        not re.fullmatch(r"[A-Z0-9]{16,128}", credentials.access_key_id)
        or not 32 <= len(credentials.secret_access_key) <= 256
        or not 16 <= len(credentials.session_token) <= 8192
    ):
        raise DrillError("exported AWS credentials are invalid")
    environment = _profile_environment(base, profile="pinned", region=region)
    environment.pop("AWS_PROFILE")
    environment.update(
        {
            "AWS_ACCESS_KEY_ID": credentials.access_key_id,
            "AWS_SECRET_ACCESS_KEY": credentials.secret_access_key,
            "AWS_SESSION_TOKEN": credentials.session_token,
        }
    )
    return environment


class AwsCliVersionStore:
    """Strict, prefix-fenced S3 version operations through the installed AWS CLI."""

    def __init__(
        self,
        *,
        bucket: str,
        prefix: str,
        region: str,
        environ: Mapping[str, str],
        expected_owner: str | None = None,
        temp_root: Path | None = None,
        runner: CommandRunner = subprocess.run,
    ) -> None:
        if expected_owner is not None and not re.fullmatch(r"[0-9]{12}", expected_owner):
            raise DrillError("expected S3 bucket owner is invalid")
        self.bucket = bucket
        self.prefix = prefix.rstrip("/")
        self.region = region
        self.environ = dict(environ)
        self.expected_owner = expected_owner
        self.temp_root = temp_root
        self.runner = runner

    def _key(self, key: str) -> str:
        if not key.startswith(self.prefix + "/"):
            raise DrillError("S3 key is outside the generated drill prefix")
        return key

    def _run_json(self, command: Sequence[str]) -> dict[str, object]:
        completed = self.runner(
            list(command),
            env=self.environ,
            text=True,
            capture_output=True,
            check=False,
        )
        if completed.returncode != 0:
            raise AwsCliOperationError(_aws_cli_error_kind(completed.stderr or ""))
        try:
            value = json.loads(completed.stdout)
        except json.JSONDecodeError as exc:
            raise DrillError("AWS CLI S3 operation returned invalid JSON") from exc
        if not isinstance(value, dict):
            raise DrillError("AWS CLI S3 operation returned an unexpected shape")
        return value

    def list_versions(self, key: str) -> tuple[VersionEntry, ...]:
        """Return the complete exact-key version and delete-marker timeline."""
        key = self._key(key)
        entries: list[VersionEntry] = []
        marker: tuple[str, str] | None = None
        seen: set[tuple[str, bool]] = set()
        for _page in range(100):
            command = [
                "aws",
                "s3api",
                "list-object-versions",
                "--bucket",
                self.bucket,
                "--prefix",
                key,
                "--max-keys",
                "1000",
                "--no-paginate",
            ]
            if marker is not None:
                command.extend(
                    [
                        "--key-marker",
                        marker[0],
                        "--version-id-marker",
                        marker[1],
                    ]
                )
            command.extend(["--region", self.region, "--output", "json", "--no-cli-pager"])
            if self.expected_owner is not None:
                command.extend(["--expected-bucket-owner", self.expected_owner])
            response = self._run_json(command)
            for field, delete_marker in (("Versions", False), ("DeleteMarkers", True)):
                raw_items = response.get(field, [])
                if not isinstance(raw_items, list):
                    raise DrillError("AWS version listing contains an invalid collection")
                for item in raw_items:
                    if not isinstance(item, dict) or item.get("Key") != key:
                        continue
                    version_id = item.get("VersionId")
                    latest = item.get("IsLatest")
                    if not isinstance(version_id, str) or not isinstance(latest, bool):
                        raise DrillError("AWS version listing contains an invalid entry")
                    identity = (version_id, delete_marker)
                    if identity in seen:
                        raise DrillError("AWS version listing contains a duplicate entry")
                    seen.add(identity)
                    if delete_marker:
                        entries.append(
                            VersionEntry(
                                key=key,
                                version_id=version_id,
                                latest=latest,
                                delete_marker=True,
                            )
                        )
                    else:
                        etag = item.get("ETag")
                        size = item.get("Size")
                        if (
                            not isinstance(etag, str)
                            or isinstance(size, bool)
                            or not isinstance(size, int)
                            or size < 0
                        ):
                            raise DrillError("AWS version listing contains invalid object metadata")
                        entries.append(
                            VersionEntry(
                                key=key,
                                version_id=version_id,
                                latest=latest,
                                delete_marker=False,
                                etag=etag,
                                size=size,
                            )
                        )
                    if len(entries) > 16:
                        raise DrillError("AWS version listing exceeds the per-key safety limit")

            truncated = response.get("IsTruncated")
            if truncated is False:
                latest_count = sum(entry.latest for entry in entries)
                if entries and latest_count != 1:
                    raise DrillError("AWS version listing has an ambiguous latest entry")
                return tuple(entries)
            if truncated is not True:
                raise DrillError("AWS version listing has an invalid truncation status")
            next_key = response.get("NextKeyMarker")
            next_version = response.get("NextVersionIdMarker")
            if not isinstance(next_key, str) or not isinstance(next_version, str):
                raise DrillError("AWS version listing omitted pagination markers")
            next_marker = (next_key, next_version)
            if next_marker == marker:
                raise DrillError("AWS version listing pagination did not advance")
            marker = next_marker
        raise DrillError("AWS version listing exceeded the pagination safety limit")

    def verify_bucket_protection(self, *, root_arn: str) -> None:
        """Require the approved location, versioning, retention, and two-Deny policy."""
        if not re.fullmatch(r"arn:(?:aws|aws-us-gov):iam::[0-9]{12}:root", root_arn):
            raise DrillError("approved account-root policy exception is invalid")
        location = self._run_json(self._command("get-bucket-location", "--bucket", self.bucket))
        if location.get("LocationConstraint") != self.region:
            raise DrillError("warehouse bucket region does not match the approved runtime")
        versioning = self._run_json(self._command("get-bucket-versioning", "--bucket", self.bucket))
        if versioning.get("Status") != "Enabled" or versioning.get("MFADelete") not in {
            None,
            "Disabled",
        }:
            raise DrillError("warehouse bucket versioning is not in the approved state")
        lifecycle = self._run_json(
            self._command("get-bucket-lifecycle-configuration", "--bucket", self.bucket)
        )
        rules = lifecycle.get("Rules")
        if not isinstance(rules, list) or len(rules) != 1:
            raise DrillError("warehouse lifecycle is not the approved single-rule shape")
        rule = rules[0]
        if not isinstance(rule, dict):
            raise DrillError("warehouse lifecycle rule is invalid")
        expiration = rule.get("NoncurrentVersionExpiration")
        bucket_wide = rule.get("Filter") == {"Prefix": ""} or rule.get("Prefix") == ""
        forbidden = {
            "Expiration",
            "Transitions",
            "NoncurrentVersionTransitions",
            "AbortIncompleteMultipartUpload",
        }
        if (
            rule.get("ID") != "expire-noncurrent-object-versions-after-30-days"
            or rule.get("Status") != "Enabled"
            or not bucket_wide
            or expiration != {"NoncurrentDays": 30}
            or forbidden.intersection(rule)
        ):
            raise DrillError("warehouse lifecycle rule is not the approved retention contract")

        policy_response = self._run_json(
            self._command("get-bucket-policy", "--bucket", self.bucket)
        )
        policy_text = policy_response.get("Policy")
        try:
            policy = json.loads(policy_text) if isinstance(policy_text, str) else None
        except json.JSONDecodeError as exc:
            raise DrillError("warehouse bucket policy is invalid") from exc
        if not isinstance(policy, dict) or set(policy) != {"Version", "Statement"}:
            raise DrillError("warehouse bucket policy is not the approved exact shape")
        statements = policy.get("Statement")
        if policy.get("Version") != "2012-10-17" or not isinstance(statements, list):
            raise DrillError("warehouse bucket policy is not the approved exact shape")
        if len(statements) != 2 or not all(isinstance(item, dict) for item in statements):
            raise DrillError("warehouse bucket policy is not the approved two-Deny shape")
        by_sid = {item.get("Sid"): item for item in statements}
        if len(by_sid) != 2:
            raise DrillError("warehouse bucket policy statement identities are invalid")
        partition = root_arn.split(":", 2)[1]
        bucket_arn = f"arn:{partition}:s3:::{self.bucket}"
        expected = {
            "DenyNonRootVersionDeletion": (
                {"s3:DeleteObjectVersion"},
                {f"{bucket_arn}/*"},
            ),
            "DenyNonRootProtectionChanges": (
                {
                    "s3:PutBucketVersioning",
                    "s3:PutLifecycleConfiguration",
                    "s3:PutBucketPolicy",
                    "s3:DeleteBucketPolicy",
                },
                {bucket_arn},
            ),
        }

        def strings(value: object) -> set[str] | None:
            if isinstance(value, str):
                return {value}
            if isinstance(value, list) and all(isinstance(item, str) for item in value):
                return set(value)
            return None

        for sid, (actions, resources) in expected.items():
            statement = by_sid.get(sid)
            if not isinstance(statement, dict):
                raise DrillError("warehouse bucket policy omitted an approved Deny")
            principal = statement.get("Principal")
            if (
                set(statement) != {"Sid", "Effect", "Principal", "Action", "Resource", "Condition"}
                or statement.get("Effect") != "Deny"
                or principal not in ("*", {"AWS": "*"})
                or strings(statement.get("Action")) != actions
                or strings(statement.get("Resource")) != resources
                or statement.get("Condition") != {"ArnNotEquals": {"aws:PrincipalArn": root_arn}}
            ):
                raise DrillError("warehouse bucket policy differs from the approved Denies")

    def verify_empty_prefix(self) -> None:
        """Require no current, historical, or marker entry below this generated run prefix."""
        response = self._run_json(
            [
                "aws",
                "s3api",
                "list-object-versions",
                "--bucket",
                self.bucket,
                "--prefix",
                self.prefix + "/",
                "--max-keys",
                "1",
                "--no-paginate",
                "--region",
                self.region,
                "--output",
                "json",
                "--no-cli-pager",
                *(
                    ["--expected-bucket-owner", self.expected_owner]
                    if self.expected_owner is not None
                    else []
                ),
            ]
        )
        if response.get("Versions") or response.get("DeleteMarkers"):
            raise DrillError("generated recovery prefix is not empty")
        if response.get("IsTruncated") is True:
            raise DrillError("generated recovery prefix emptiness check was truncated")

    def prefix_keys(self) -> frozenset[str]:
        """List the complete bounded key set below the generated run prefix."""
        response = self._run_json(
            [
                "aws",
                "s3api",
                "list-object-versions",
                "--bucket",
                self.bucket,
                "--prefix",
                self.prefix + "/",
                "--max-keys",
                "1000",
                "--no-paginate",
                "--region",
                self.region,
                "--output",
                "json",
                "--no-cli-pager",
                *(
                    ["--expected-bucket-owner", self.expected_owner]
                    if self.expected_owner is not None
                    else []
                ),
            ]
        )
        versions = response.get("Versions", [])
        markers = response.get("DeleteMarkers", [])
        if (
            response.get("IsTruncated") is not False
            or not isinstance(versions, list)
            or not isinstance(markers, list)
        ):
            raise DrillError("generated prefix inventory is incomplete")
        keys: set[str] = set()
        for item in [*versions, *markers]:
            key = item.get("Key") if isinstance(item, dict) else None
            if not isinstance(key, str) or not key.startswith(self.prefix + "/"):
                raise DrillError("generated prefix inventory contains an invalid key")
            keys.add(key)
            if len(keys) > _MAX_STAGE1_OBJECTS:
                raise DrillError("generated prefix exceeds the object-count safety limit")
        return frozenset(keys)

    def verify_only_key(self, key: str) -> None:
        """Require the generated prefix to contain only one exact canary timeline."""
        key = self._key(key)
        keys = self.prefix_keys()
        if keys != {key}:
            raise DrillError("generated prefix contains an unexpected key or canary history")
        timeline = self.list_versions(key)
        if (
            len(timeline) != 3
            or sum(entry.delete_marker for entry in timeline) != 1
            or sum(not entry.delete_marker for entry in timeline) != 2
        ):
            raise DrillError("generated prefix contains an unexpected key or canary history")

    def _command(self, operation: str, *arguments: str) -> list[str]:
        command = [
            "aws",
            "s3api",
            operation,
            *arguments,
            "--region",
            self.region,
            "--output",
            "json",
            "--no-cli-pager",
        ]
        if self.expected_owner is not None:
            command.extend(["--expected-bucket-owner", self.expected_owner])
        return command

    def _version_state(self, entry: VersionEntry) -> ObjectState:
        if entry.delete_marker:
            return ObjectState(
                exists=False,
                delete_marker=True,
                version_id=entry.version_id,
            )
        head = self._run_json(
            self._command(
                "head-object",
                "--bucket",
                self.bucket,
                "--key",
                entry.key,
                "--version-id",
                entry.version_id,
            )
        )
        size = head.get("ContentLength")
        etag = head.get("ETag")
        response_version = head.get("VersionId")
        if (
            isinstance(size, bool)
            or not isinstance(size, int)
            or not 0 <= size <= _MAX_GRAPH_BYTES
            or not isinstance(etag, str)
            or etag != entry.etag
            or size != entry.size
            or response_version != entry.version_id
        ):
            raise DrillError("version-specific object metadata is invalid or exceeds limits")

        if self.temp_root is not None:
            self.temp_root.mkdir(parents=True, exist_ok=True, mode=0o700)
            self.temp_root.chmod(0o700)
        descriptor, filename = tempfile.mkstemp(
            prefix=".iceberg-recovery-object-",
            dir=self.temp_root,
        )
        os.close(descriptor)
        path = Path(filename)
        path.chmod(0o600)
        try:
            response = self._run_json(
                [
                    *self._command(
                        "get-object",
                        "--bucket",
                        self.bucket,
                        "--key",
                        entry.key,
                        "--version-id",
                        entry.version_id,
                    ),
                    str(path),
                ]
            )
            if response.get("VersionId") != entry.version_id:
                raise DrillError("version-specific object read returned the wrong version")
            payload = path.read_bytes()
            if len(payload) != size:
                raise DrillError("version-specific object size changed during read")
            digest = hashlib.sha256(payload).hexdigest()
        finally:
            path.unlink(missing_ok=True)
        return ObjectState(
            exists=True,
            delete_marker=False,
            version_id=entry.version_id,
            size=size,
            sha256=digest,
        )

    def current_state(self, node: GraphNode) -> ObjectState:
        """Read and hash the exact latest state for one approved graph key."""
        timeline = self.list_versions(node.key)
        latest = [entry for entry in timeline if entry.latest]
        if not latest:
            return ObjectState(exists=False, delete_marker=False)
        if len(latest) != 1:
            raise DrillError("object version timeline has an ambiguous latest entry")
        return self._version_state(latest[0])

    def exact_source_state(self, node: GraphNode) -> ObjectState:
        """Read and hash the approved noncurrent source version without promoting it."""
        source = [
            entry
            for entry in self.list_versions(node.key)
            if entry.version_id == node.source_version_id and not entry.delete_marker
        ]
        if len(source) != 1 or source[0].etag != node.etag or source[0].size != node.size:
            raise DrillError("approved historical source version is missing or changed")
        state = self._version_state(source[0])
        if not _matches_content(node, state) or state.version_id != node.source_version_id:
            raise DrillError("approved historical source version bytes changed")
        return state

    def put_canary(self, key: str, payload: bytes) -> GraphNode:
        """Create and verify one bounded disposable capability-canary version."""
        key = self._key(key)
        if not payload or len(payload) > 1024:
            raise DrillError("capability canary payload is outside the safety limit")
        if self.temp_root is not None:
            self.temp_root.mkdir(parents=True, exist_ok=True, mode=0o700)
            self.temp_root.chmod(0o700)
        descriptor, filename = tempfile.mkstemp(
            prefix=".iceberg-recovery-canary-",
            dir=self.temp_root,
        )
        path = Path(filename)
        try:
            with os.fdopen(descriptor, "wb") as handle:
                handle.write(payload)
                handle.flush()
                os.fsync(handle.fileno())
            path.chmod(0o600)
            response = self._run_json(
                self._command(
                    "put-object",
                    "--bucket",
                    self.bucket,
                    "--key",
                    key,
                    "--body",
                    str(path),
                )
            )
        finally:
            path.unlink(missing_ok=True)
        version_id = response.get("VersionId")
        etag = response.get("ETag")
        if (
            not isinstance(version_id, str)
            or not version_id
            or version_id == "null"
            or not isinstance(etag, str)
        ):
            raise DrillError("capability canary put did not create a versioned object")
        node = GraphNode(
            key=key,
            kind="capability-canary",
            source_version_id=version_id,
            etag=etag,
            size=len(payload),
            sha256=hashlib.sha256(payload).hexdigest(),
            depth=0,
        )
        state = self.current_state(node)
        if not _matches_content(node, state) or state.version_id != version_id:
            raise DrillError("capability canary current bytes could not be verified")
        return node

    def delete_current(self, node: GraphNode) -> DeleteResult:
        """Ordinary-delete one approved current key, creating a delete marker."""
        key = self._key(node.key)
        response = self._run_json(
            self._command(
                "delete-object",
                "--bucket",
                self.bucket,
                "--key",
                key,
            )
        )
        marker = response.get("DeleteMarker")
        version_id = response.get("VersionId")
        if marker is not True or not isinstance(version_id, str) or not version_id:
            raise DrillError("ordinary delete did not return a versioned delete marker")
        return DeleteResult(delete_marker=True, version_id=version_id)

    def restore(self, node: GraphNode) -> ObjectState:
        """Promote the node's exact source version and verify its new current bytes."""
        key = self._key(node.key)
        source = [
            entry
            for entry in self.list_versions(key)
            if entry.version_id == node.source_version_id and not entry.delete_marker
        ]
        if len(source) != 1 or source[0].etag != node.etag or source[0].size != node.size:
            raise DrillError("approved historical source version is missing or changed")
        copy_source = (
            f"{quote(self.bucket, safe='')}/{quote(key, safe='/')}"
            f"?versionId={quote(node.source_version_id, safe='')}"
        )
        response = self._run_json(
            self._command(
                "copy-object",
                "--bucket",
                self.bucket,
                "--key",
                key,
                "--copy-source",
                copy_source,
                "--copy-source-if-match",
                node.etag,
                *(
                    ["--expected-source-bucket-owner", self.expected_owner]
                    if self.expected_owner is not None
                    else []
                ),
            )
        )
        new_version = response.get("VersionId")
        copy_result = response.get("CopyObjectResult")
        copied_etag = copy_result.get("ETag") if isinstance(copy_result, dict) else None
        if (
            not isinstance(new_version, str)
            or not new_version
            or new_version == node.source_version_id
            or not isinstance(copied_etag, str)
        ):
            raise DrillError("historical version promotion returned an invalid result")
        state = self.current_state(node)
        if state.version_id != new_version:
            raise DrillError("promoted version is not the new current version")
        return state


def capture_iceberg_graph(
    table: Any,
    *,
    location_validator: Callable[[str], object] | None = None,
    expected_snapshot_count: int = 1,
) -> tuple[GraphObject, ...]:
    """Traverse a complete supported Iceberg graph with an exact snapshot count."""
    if (
        isinstance(expected_snapshot_count, bool)
        or not isinstance(expected_snapshot_count, int)
        or expected_snapshot_count < 1
        or expected_snapshot_count > 16
    ):
        raise DrillError("expected Iceberg snapshot count is invalid")
    metadata = table.metadata
    snapshot = table.current_snapshot()
    if metadata.format_version != 2 or snapshot is None:
        raise DrillError("captured table must have a current Iceberg v2 snapshot")
    if (
        len(metadata.snapshots) != expected_snapshot_count
        or snapshot.snapshot_id != metadata.current_snapshot_id
    ):
        raise DrillError("captured table has an unexpected snapshot count")
    if set(metadata.refs) != {"main"} or metadata.refs["main"].snapshot_id != snapshot.snapshot_id:
        raise DrillError("point-A table must contain only its current main reference")

    found: dict[str, GraphObject] = {}

    def add(location: object, kind: str, depth: int) -> None:
        if not isinstance(location, str) or not location:
            raise DrillError("Iceberg graph contains an invalid external location")
        if location_validator is not None:
            location_validator(location)
        candidate = GraphObject(location=location, kind=kind, depth=depth)
        existing = found.get(location)
        if existing is not None and existing != candidate:
            raise DrillError("Iceberg graph assigns conflicting roles to one location")
        found[location] = candidate
        if len(found) > _MAX_GRAPH_OBJECTS:
            raise DrillError("Iceberg graph exceeds the object-count safety limit")

    add(table.metadata_location, "metadata", 0)
    for entry in metadata.metadata_log:
        add(entry.metadata_file, "metadata-ancestor", 1)
    add(snapshot.manifest_list, "manifest-list", 1)

    manifests = snapshot.manifests(table.io)
    for manifest in manifests:
        if getattr(manifest.content, "name", "") != "DATA":
            raise DrillError("point-A table contains an unsupported delete manifest")
        add(manifest.manifest_path, "manifest", 2)
        for entry in manifest.fetch_manifest_entry(table.io, discard_deleted=False):
            if getattr(entry.status, "name", "") != "ADDED":
                raise DrillError("point-A table contains a non-added manifest entry")
            data_file = entry.data_file
            content_name = getattr(data_file.content, "name", "")
            kind = {
                "DATA": "data",
                "POSITION_DELETES": "position-delete",
                "EQUALITY_DELETES": "equality-delete",
            }.get(content_name)
            if kind is None:
                raise DrillError("Iceberg graph contains an unsupported data-file content type")
            add(data_file.file_path, kind, 3)

    for statistics_file in metadata.statistics:
        add(statistics_file.statistics_path, "statistics", 1)
    for statistics_file in metadata.partition_statistics:
        add(statistics_file.statistics_path, "partition-statistics", 1)

    return tuple(sorted(found.values(), key=lambda item: (item.depth, item.location)))


class WarehouseDrillOperations(Protocol):
    """Effects required by the narrow preparation and execution functions."""

    def prepare(
        self,
        scope: DrillScope,
        rows: Sequence[Mapping[str, object]],
        *,
        capability_canary: GraphNode | None = None,
    ) -> TableCapture: ...

    def current_state(self, node: GraphNode) -> ObjectState: ...

    def delete_current(self, node: GraphNode) -> DeleteResult: ...

    def assert_table_unreadable(self, manifest: Mapping[str, object]) -> None: ...

    def restore(self, node: GraphNode) -> ObjectState: ...

    def validate(self, manifest: Mapping[str, object]) -> ValidationResult: ...


TokenFactory = Callable[[], str]

_DETERMINISTIC_ROWS: tuple[Mapping[str, object], ...] = (
    {"event_id": 1, "generation": "point-a", "value": 10},
    {"event_id": 2, "generation": "point-a", "value": 20},
    {"event_id": 3, "generation": "point-a", "value": 30},
)
_RUN_ID = re.compile(r"[0-9a-f]{16}")
_SHA256 = re.compile(r"[0-9a-f]{64}")
_MAX_STAGE1_OBJECTS = 64
_MAX_GRAPH_OBJECTS = _MAX_STAGE1_OBJECTS - 1
_MAX_GRAPH_BYTES = 32 * 1024 * 1024
_MAX_PREPARE_VERSIONS_PER_KEY = 12
_MAX_PRIVATE_RESPONSE_BYTES = 1024 * 1024
_POLARIS_REQUEST_TIMEOUT_SECONDS = 15
_SEED_PLAN_LIFETIME = timedelta(hours=6)
_POSTGRES_IMAGE = "postgres:17.6-bookworm"
_POLARIS_ADMIN_IMAGE = "apache/polaris-admin-tool:1.7.0"
_POLARIS_IMAGE = "apache/polaris:1.7.0"
_VENDED_S3_CREDENTIAL_PROPERTIES = (
    "s3.access-key-id",
    "s3.secret-access-key",
    "s3.session-token",
)
_ROOT = Path(__file__).resolve().parents[2]
_LIVE_EVIDENCE_ROOT = _ROOT / ".recovery" / "iceberg"


def _absolute_path(path: Path) -> Path:
    return Path(os.path.abspath(path))


def _require_live_evidence_root(path: Path) -> Path:
    candidate = _absolute_path(path)
    if candidate != _LIVE_EVIDENCE_ROOT:
        raise DrillError("live evidence must use the fixed private repository directory")
    current = _ROOT
    for part in candidate.relative_to(_ROOT).parts:
        current /= part
        if current.exists() and current.is_symlink():
            raise DrillError("live evidence directory must not contain symlinks")
    return candidate


def _require_live_plan_path(path: Path) -> Path:
    candidate = _absolute_path(path)
    evidence_root = _require_live_evidence_root(candidate.parent.parent)
    if (
        candidate.name not in {"seed-a.plan.json", "manifest.json"}
        or candidate.parent.parent != evidence_root
    ):
        raise DrillError("live plan is outside the fixed private evidence directory")
    for component in (candidate.parent, candidate):
        try:
            details = component.lstat()
        except OSError as exc:
            raise DrillError("live plan path is unavailable") from exc
        if stat.S_ISLNK(details.st_mode):
            raise DrillError("live plan path must not contain symlinks")
    if not stat.S_ISDIR(candidate.parent.lstat().st_mode):
        raise DrillError("live plan run directory is invalid")
    if stat.S_IMODE(candidate.parent.lstat().st_mode) != 0o700:
        raise DrillError("live plan run directory is not mode 0700")
    return candidate


def _new_run_id() -> str:
    return secrets.token_hex(8)


def _scope(run_id: str) -> DrillScope:
    if not _RUN_ID.fullmatch(run_id):
        raise DrillError("generated run ID is invalid")
    return DrillScope(
        run_id=run_id,
        prefix=f"integration/recovery/{run_id}/stage1/warehouse",
        catalog=f"recovery_{run_id}",
        namespace=f"drill_{run_id}",
        table=f"events_{run_id}",
    )


def _canonical_json(value: object) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode()


def _identity_sha256(account: str, authorization_principal: str) -> str:
    return hashlib.sha256(
        _canonical_json({"account": account, "arn": authorization_principal})
    ).hexdigest()


@dataclass(frozen=True)
class CallerIdentity:
    account: str
    arn: str
    digest: str

    @property
    def root_arn(self) -> str:
        partition = self.arn.split(":", 2)[1]
        return f"arn:{partition}:iam::{self.account}:root"

    @property
    def role_arn(self) -> str | None:
        partition, service, resource = (
            self.arn.split(":", 5)[1],
            self.arn.split(":", 5)[2],
            self.arn.split(":", 5)[5],
        )
        if service != "sts" or not resource.startswith("assumed-role/"):
            return None
        role_and_session = resource.removeprefix("assumed-role/").rsplit("/", 1)
        if len(role_and_session) != 2 or not all(role_and_session):
            return None
        return f"arn:{partition}:iam::{self.account}:role/{role_and_session[0]}"

    @property
    def authorization_principal(self) -> str:
        return self.role_arn or self.arn


@dataclass(frozen=True, repr=False)
class RuntimeConfig:
    """Private local settings required by the real, explicitly invoked drill."""

    bucket: str
    region: str
    polaris_url: str
    polaris_client_id: str
    polaris_client_secret: str
    storage_role_arn: str

    @classmethod
    def isolated(
        cls,
        *,
        settings: RecoverySettings,
        polaris_url: str,
        credentials: RunCredentials,
    ) -> RuntimeConfig:
        return cls(
            bucket=settings.bucket,
            region=settings.region,
            polaris_url=polaris_url,
            polaris_client_id=credentials.polaris_client_id,
            polaris_client_secret=credentials.polaris_client_secret,
            storage_role_arn=settings.storage_role_arn,
        )


def _source_runtime_binding(configuration: Mapping[str, object]) -> RuntimeBinding:
    completed = subprocess.run(
        ["git", "rev-parse", "--verify", "HEAD"],
        cwd=_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    revision = completed.stdout.strip()
    if completed.returncode != 0 or not re.fullmatch(r"[0-9a-f]{40,64}", revision):
        raise DrillError("source revision could not be pinned")
    try:
        script_sha256 = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
        pyiceberg_version = importlib.metadata.version("pyiceberg")
        pyarrow_version = importlib.metadata.version("pyarrow")
    except (OSError, importlib.metadata.PackageNotFoundError) as exc:
        raise DrillError("runtime dependency versions could not be pinned") from exc
    return RuntimeBinding(
        source_revision=revision,
        script_sha256=script_sha256,
        python_version=f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
        pyiceberg_version=pyiceberg_version,
        pyarrow_version=pyarrow_version,
        configuration_sha256=hashlib.sha256(_canonical_json(configuration)).hexdigest(),
    )


def _runtime_binding_from_manifest(value: object) -> RuntimeBinding:
    if not isinstance(value, dict) or set(value) != {
        "sourceRevision",
        "scriptSha256",
        "pythonVersion",
        "pyicebergVersion",
        "pyarrowVersion",
        "configurationSha256",
    }:
        raise DrillError("private drill runtime binding has an unexpected shape")
    fields = tuple(value.values())
    if not all(isinstance(item, str) for item in fields):
        raise DrillError("private drill runtime binding values are invalid")
    binding = RuntimeBinding(
        source_revision=value["sourceRevision"],
        script_sha256=value["scriptSha256"],
        python_version=value["pythonVersion"],
        pyiceberg_version=value["pyicebergVersion"],
        pyarrow_version=value["pyarrowVersion"],
        configuration_sha256=value["configurationSha256"],
    )
    if (
        not re.fullmatch(r"[0-9a-f]{40,64}", binding.source_revision)
        or not _SHA256.fullmatch(binding.script_sha256)
        or not re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+", binding.python_version)
        or not re.fullmatch(r"[0-9A-Za-z][0-9A-Za-z.+-]{0,63}", binding.pyiceberg_version)
        or not re.fullmatch(r"[0-9A-Za-z][0-9A-Za-z.+-]{0,63}", binding.pyarrow_version)
        or not _SHA256.fullmatch(binding.configuration_sha256)
    ):
        raise DrillError("private drill runtime binding values are invalid")
    return binding


def _require_identity_relationship(
    *,
    identity: CallerIdentity,
    storage_role_arn: str,
) -> str:
    """Bind the one approved non-root operator to the Polaris storage account."""
    role_account = storage_role_arn.split(":", 5)[4]
    if identity.account != role_account:
        raise DrillError("operator and Polaris storage identities do not align")
    return identity.root_arn


def _run_cli_json(
    command: Sequence[str],
    *,
    environ: Mapping[str, str],
    runner: CommandRunner = subprocess.run,
) -> dict[str, object]:
    completed = runner(
        list(command),
        env=dict(environ),
        text=True,
        capture_output=True,
        check=False,
    )
    if completed.returncode != 0:
        raise DrillError("AWS CLI identity operation failed")
    try:
        value = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise DrillError("AWS CLI identity operation returned invalid JSON") from exc
    if not isinstance(value, dict):
        raise DrillError("AWS CLI identity operation returned an unexpected shape")
    return value


def _verify_non_root_identity(
    *,
    environ: Mapping[str, str],
    expected_sha256: str,
    region: str,
    runner: CommandRunner = subprocess.run,
) -> CallerIdentity:
    response = _run_cli_json(
        (
            "aws",
            "sts",
            "get-caller-identity",
            "--region",
            region,
            "--output",
            "json",
            "--no-cli-pager",
        ),
        environ=environ,
        runner=runner,
    )
    account = response.get("Account")
    arn = response.get("Arn")
    if (
        not isinstance(account, str)
        or not re.fullmatch(r"[0-9]{12}", account)
        or not isinstance(arn, str)
        or not re.fullmatch(
            rf"arn:(?:aws|aws-us-gov):(?:iam|sts)::{account}:"
            r"(?:user|role|assumed-role)/[A-Za-z0-9+=,.@_/-]+",
            arn,
        )
    ):
        raise DrillError("AWS caller is invalid or is account root")
    candidate = CallerIdentity(account=account, arn=arn, digest="")
    digest = _identity_sha256(account, candidate.authorization_principal)
    if not hmac.compare_digest(digest, expected_sha256):
        raise DrillError("AWS caller does not match the approved identity digest")
    return CallerIdentity(account=account, arn=arn, digest=digest)


class _NoRedirectHandler(HTTPRedirectHandler):
    def redirect_request(
        self,
        request: Any,
        file_pointer: Any,
        code: int,
        message: str,
        headers: Any,
        new_url: str,
    ) -> None:
        del request, file_pointer, code, message, headers, new_url
        return None


class PolarisGateway:
    """Provision and open one generated catalog through loopback Polaris only."""

    def __init__(self, *, config: RuntimeConfig, opener: Any | None = None) -> None:
        self.config = config
        self.base_url = config.polaris_url.rstrip("/")
        self._opener = opener or build_opener(ProxyHandler({}), _NoRedirectHandler())

    def _bounded_json(self, request: Request) -> dict[str, object]:
        try:
            with self._opener.open(request, timeout=_POLARIS_REQUEST_TIMEOUT_SECONDS) as response:
                if not 200 <= response.status < 300:
                    message = (
                        "loopback Polaris redirect refused"
                        if 300 <= response.status < 400
                        else "loopback Polaris request failed"
                    )
                    raise DrillError(message)
                payload = response.read(_MAX_PRIVATE_RESPONSE_BYTES + 1)
        except DrillError:
            raise
        except Exception as exc:
            raise DrillError("loopback Polaris request failed") from exc
        if len(payload) > _MAX_PRIVATE_RESPONSE_BYTES:
            raise DrillError("loopback Polaris response exceeded the safety limit")
        if not payload:
            return {}
        try:
            value = json.loads(payload)
        except json.JSONDecodeError as exc:
            raise DrillError("loopback Polaris returned invalid JSON") from exc
        if not isinstance(value, dict):
            raise DrillError("loopback Polaris returned an unexpected response")
        return value

    def _token(self) -> str:
        basic = base64.b64encode(
            f"{self.config.polaris_client_id}:{self.config.polaris_client_secret}".encode()
        ).decode()
        request = Request(
            f"{self.base_url}/api/catalog/v1/oauth/tokens",
            data=urlencode(
                {"grant_type": "client_credentials", "scope": "PRINCIPAL_ROLE:ALL"}
            ).encode(),
            headers={
                "Authorization": f"Basic {basic}",
                "Content-Type": "application/x-www-form-urlencoded",
                "Polaris-Realm": "POLARIS",
            },
            method="POST",
        )
        value = self._bounded_json(request).get("access_token")
        if not isinstance(value, str) or not value:
            raise DrillError("loopback Polaris did not return an access token")
        return value

    def _management(
        self,
        *,
        token: str,
        method: str,
        path: str,
        payload: Mapping[str, object] | None = None,
    ) -> dict[str, object]:
        request = Request(
            f"{self.base_url}/api/management/v1{path}",
            data=_canonical_json(payload) if payload is not None else None,
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": "application/json",
                "Content-Type": "application/json",
                "Polaris-Realm": "POLARIS",
            },
            method=method,
        )
        return self._bounded_json(request)

    @staticmethod
    def _catalog_request(
        request: Callable[..., Any], method: str, url: str, **kwargs: object
    ) -> Any:
        kwargs["allow_redirects"] = False
        kwargs["timeout"] = _POLARIS_REQUEST_TIMEOUT_SECONDS
        response = request(method=method, url=url, **kwargs)
        if 300 <= response.status_code < 400:
            response.close()
            raise DrillError("loopback Polaris redirect refused")
        return response

    def open(self, scope: DrillScope) -> Any:
        from pyiceberg.catalog.rest import RestCatalog

        gateway = self

        class NoRedirectRestCatalog(RestCatalog):
            def _create_session(self) -> Any:
                session = super()._create_session()
                session.trust_env = False
                request = session.request

                def request_without_redirect(method: str, url: str, **kwargs: object) -> Any:
                    return gateway._catalog_request(request, method, url, **kwargs)

                session.request = request_without_redirect
                return session

        return NoRedirectRestCatalog(
            name=f"iceberg_recovery_{scope.run_id}",
            uri=f"{self.base_url}/api/catalog",
            warehouse=scope.catalog,
            credential=(f"{self.config.polaris_client_id}:{self.config.polaris_client_secret}"),
            scope="PRINCIPAL_ROLE:ALL",
            **{
                "oauth2-server-uri": f"{self.base_url}/api/catalog/v1/oauth/tokens",
                "header.X-Iceberg-Access-Delegation": "vended-credentials",
            },
        )

    def provision(self, scope: DrillScope) -> Any:
        token = self._token()
        catalog = quote(scope.catalog, safe="")
        role = "recovery_writer"
        warehouse = f"s3://{self.config.bucket}/{scope.prefix}"
        self._management(
            token=token,
            method="POST",
            path="/catalogs",
            payload={
                "catalog": {
                    "name": scope.catalog,
                    "type": "INTERNAL",
                    "readOnly": False,
                    "properties": {"default-base-location": warehouse},
                    "storageConfigInfo": {
                        "storageType": "S3",
                        "allowedLocations": [warehouse],
                        "roleArn": self.config.storage_role_arn,
                    },
                }
            },
        )
        self._management(
            token=token,
            method="POST",
            path=f"/catalogs/{catalog}/catalog-roles",
            payload={"catalogRole": {"name": role, "properties": {}}},
        )
        self._management(
            token=token,
            method="PUT",
            path=f"/catalogs/{catalog}/catalog-roles/{role}/grants",
            payload={"type": "catalog", "privilege": "CATALOG_MANAGE_CONTENT"},
        )
        self._management(
            token=token,
            method="PUT",
            path=f"/principal-roles/service_admin/catalog-roles/{catalog}",
            payload={"catalogRole": {"name": role}},
        )
        return self.open(scope)

    def catalog_fingerprint(self, scope: DrillScope) -> str:
        token = self._token()
        value = self._management(
            token=token,
            method="GET",
            path=f"/catalogs/{quote(scope.catalog, safe='')}",
        )
        catalog = value
        properties = catalog.get("properties")
        storage = catalog.get("storageConfigInfo")
        if not isinstance(properties, dict) or not isinstance(storage, dict):
            raise DrillError("isolated Polaris catalog configuration is incomplete")
        warehouse = f"s3://{self.config.bucket}/{scope.prefix}"
        role_sha256 = hashlib.sha256(self.config.storage_role_arn.encode()).hexdigest()
        projection = {
            "name": catalog.get("name"),
            "type": catalog.get("type"),
            "propertiesSha256": hashlib.sha256(_canonical_json(properties)).hexdigest(),
            "defaultBaseLocation": properties.get("default-base-location"),
            "storageType": storage.get("storageType"),
            "allowedLocations": storage.get("allowedLocations"),
            "storageRoleSha256": role_sha256,
        }
        if (
            catalog.get("name") != scope.catalog
            or catalog.get("type") != "INTERNAL"
            or properties.get("default-base-location") != warehouse
            or storage.get("storageType") != "S3"
            or storage.get("allowedLocations") != [warehouse]
            or storage.get("roleArn") != self.config.storage_role_arn
        ):
            raise DrillError("isolated Polaris catalog configuration differs from Seed-A")
        return hashlib.sha256(_canonical_json(projection)).hexdigest()


class IsolatedStage1Stack:
    """Run transient secret-bearing processes in exact run-owned Docker resources."""

    def __init__(
        self,
        *,
        scope: DrillScope,
        resources: Mapping[str, str],
        images: Mapping[str, ImagePin],
        seed_plan_sha256: str,
        execution_plan_sha256: str,
        runner: CommandRunner = subprocess.run,
        popen_factory: Callable[..., Any] = subprocess.Popen,
        sleeper_seconds: int = 21600,
    ) -> None:
        if dict(resources) != _stack_resources(scope):
            raise DrillError("isolated stack resources do not match the generated scope")
        self.scope = scope
        self.resources = dict(resources)
        self.images = dict(images)
        self.seed_plan_sha256 = seed_plan_sha256
        self.execution_plan_sha256 = execution_plan_sha256
        self.runner = runner
        self.popen_factory = popen_factory
        self.sleeper_seconds = sleeper_seconds
        self._children: list[Any] = []
        self._created_containers: set[str] = set()

    def _capture(self, command: Sequence[str]) -> subprocess.CompletedProcess[str]:
        completed = self.runner(
            list(command),
            text=True,
            capture_output=True,
            check=False,
        )
        if len((completed.stdout or "").encode()) > _MAX_PRIVATE_RESPONSE_BYTES:
            raise DrillError("Docker response exceeded the safety limit")
        return completed

    def _run(self, command: Sequence[str], *, input_text: str | None = None) -> None:
        completed = self.runner(
            list(command),
            input=input_text,
            text=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )
        if completed.returncode != 0:
            raise DrillError("isolated Docker operation failed")

    def _label_map(self, *, phase: str | None = None) -> dict[str, str]:
        labels = {
            "com.databox.owner": "iceberg-recovery",
            "com.databox.run": self.scope.run_id,
            "com.databox.stage": "stage1",
            "com.databox.seed-plan": self.seed_plan_sha256,
        }
        if phase is not None:
            labels["com.databox.phase"] = phase
            labels["com.databox.approved-plan"] = self.execution_plan_sha256
        return labels

    def _labels(self, *, phase: str | None = None) -> list[str]:
        arguments: list[str] = []
        for name, value in sorted(self._label_map(phase=phase).items()):
            arguments.extend(["--label", f"{name}={value}"])
        return arguments

    def _listed_names(self, resource: str, name: str) -> tuple[str, ...]:
        command = ["docker", resource, "ls"]
        if resource == "container":
            command.append("--all")
        format_field = "{{.Names}}" if resource == "container" else "{{.Name}}"
        command.extend(["--filter", f"name=^{name}$", "--format", format_field])
        completed = self._capture(command)
        if completed.returncode != 0:
            raise DrillError("Docker resource inventory failed")
        return tuple(line for line in completed.stdout.splitlines() if line)

    def _require_containers_absent(self) -> None:
        for key in ("postgresContainer", "bootstrapContainer", "polarisContainer"):
            name = self.resources[key]
            if self._listed_names("container", name):
                raise DrillError("generated Docker container name is already present")

    def _volume_consumers(self) -> dict[str, str]:
        completed = self._capture(
            (
                "docker",
                "container",
                "ls",
                "--all",
                "--filter",
                f"volume={self.resources['postgresVolume']}",
                "--format",
                "{{.ID}}\t{{.Names}}",
            )
        )
        if completed.returncode != 0:
            raise DrillError("Docker volume consumer inventory failed")
        consumers: dict[str, str] = {}
        for line in completed.stdout.splitlines():
            if not line:
                continue
            parts = line.split("\t")
            if (
                len(parts) != 2
                or not re.fullmatch(r"[0-9a-f]{12,64}", parts[0])
                or not parts[1]
                or parts[1] in consumers
            ):
                raise DrillError("Docker volume consumer inventory is ambiguous")
            consumers[parts[1]] = parts[0]
        return consumers

    def _resource_inspect(self, resource: str, name: str) -> dict[str, object]:
        completed = self._capture(("docker", resource, "inspect", name))
        if completed.returncode != 0:
            raise DrillError("required generated Docker resource is unavailable")
        try:
            value = json.loads(completed.stdout)
        except json.JSONDecodeError as exc:
            raise DrillError("Docker resource inspection returned invalid JSON") from exc
        if not isinstance(value, list) or len(value) != 1 or not isinstance(value[0], dict):
            raise DrillError("Docker resource inspection returned an unexpected shape")
        return value[0]

    def _retained_resource_state(
        self,
    ) -> tuple[dict[str, object], dict[str, object], str]:
        expected_labels = self._label_map()
        network = self._resource_inspect("network", self.resources["network"])
        volume = self._resource_inspect("volume", self.resources["postgresVolume"])
        if (
            network.get("Name") != self.resources["network"]
            or network.get("Labels") != expected_labels
            or network.get("Driver") != "bridge"
            or network.get("Scope") != "local"
            or network.get("Internal") is not False
            or network.get("Attachable") is not False
            or network.get("Ingress") is not False
            or not isinstance(network.get("Containers"), dict)
            or volume.get("Name") != self.resources["postgresVolume"]
            or volume.get("Labels") != expected_labels
            or volume.get("Driver") != "local"
            or volume.get("Scope") != "local"
        ):
            raise DrillError("generated Docker resources do not match Seed-A")
        network_projection = dict(network)
        network_projection.pop("Containers", None)
        fingerprint = hashlib.sha256(
            _canonical_json(
                {
                    "network": network_projection,
                    "volume": volume,
                }
            )
        ).hexdigest()
        return network, volume, fingerprint

    def _require_retained_resources(self, *, require_containers_absent: bool = True) -> str:
        network, _volume, fingerprint = self._retained_resource_state()
        if require_containers_absent:
            if network["Containers"]:
                raise DrillError("generated Docker network has unexpected attachments")
            self._require_containers_absent()
            if self._volume_consumers():
                raise DrillError("generated Docker volume has unexpected consumers")
        return fingerprint

    def retained_resources_sha256(self) -> str:
        """Fingerprint detached run-owned resources after secret containment."""
        return self._require_retained_resources()

    def create_seed_resources(self) -> None:
        self._require_containers_absent()
        for resource, name in (
            ("network", self.resources["network"]),
            ("volume", self.resources["postgresVolume"]),
        ):
            if self._listed_names(resource, name):
                raise DrillError("generated Docker resource name is already present")
        self._run(
            (
                "docker",
                "network",
                "create",
                "--driver",
                "bridge",
                *self._labels(),
                self.resources["network"],
            )
        )
        self._run(
            (
                "docker",
                "volume",
                "create",
                *self._labels(),
                self.resources["postgresVolume"],
            )
        )
        self._require_retained_resources()

    def _validate_recovery_remnant(
        self,
        *,
        key: str,
        container: Mapping[str, object],
        network_id: str,
        attachment_id: str,
    ) -> None:
        image_key = "postgres" if key == "postgresContainer" else "polaris"
        pin = self.images[image_key]
        name = self.resources[key]
        alias = "postgres" if key == "postgresContainer" else "polaris"
        expected_labels = self._label_map(phase="recovery")
        config = container.get("Config")
        host = container.get("HostConfig")
        network_settings = container.get("NetworkSettings")
        network_map = (
            network_settings.get("Networks") if isinstance(network_settings, dict) else None
        )
        network_details = (
            network_map.get(self.resources["network"]) if isinstance(network_map, dict) else None
        )
        container_id = container.get("Id")
        if (
            not isinstance(container_id, str)
            or container_id != attachment_id
            or container.get("Name") != f"/{name}"
            or container.get("Image") != pin.image_id
            or container.get("Path") != "/bin/sh"
            or container.get("Args")
            != [
                "-ceu",
                f"exec sleep {self.sleeper_seconds}",
            ]
            or not isinstance(config, dict)
            or config.get("Image") != pin.image_id
            or config.get("Entrypoint") != ["/bin/sh"]
            or config.get("Cmd")
            != [
                "-ceu",
                f"exec sleep {self.sleeper_seconds}",
            ]
            or config.get("Env") != list(pin.environment)
            or (config.get("User") or "") != pin.user
            or (config.get("WorkingDir") or "") != pin.working_directory
            or config.get("Labels") != expected_labels
            or not isinstance(host, dict)
            or host.get("NetworkMode") != self.resources["network"]
            or host.get("RestartPolicy") != {"Name": "no", "MaximumRetryCount": 0}
            or host.get("AutoRemove") is not False
            or host.get("Privileged") is not False
            or host.get("ReadonlyRootfs") is not False
            or host.get("Binds") not in (None, [])
            or not isinstance(network_map, dict)
            or set(network_map) != {self.resources["network"]}
            or not isinstance(network_details, dict)
            or network_details.get("NetworkID") != network_id
            or alias not in (network_details.get("Aliases") or [])
        ):
            raise DrillError("existing recovery container is not an exact owned remnant")

        mounts = container.get("Mounts")
        port_bindings = host.get("PortBindings")
        if key == "postgresContainer":
            if (
                not isinstance(mounts, list)
                or len(mounts) != 1
                or not isinstance(mounts[0], dict)
                or mounts[0].get("Type") != "volume"
                or mounts[0].get("Name") != self.resources["postgresVolume"]
                or mounts[0].get("Destination") != "/var/lib/postgresql/data"
                or mounts[0].get("RW") is not True
                or port_bindings not in (None, {})
            ):
                raise DrillError("existing recovery PostgreSQL mount is not owned")
            return
        if (
            mounts != []
            or not isinstance(port_bindings, dict)
            or set(port_bindings) != {"8181/tcp"}
        ):
            raise DrillError("existing recovery Polaris bindings are not exact")
        binding = port_bindings["8181/tcp"]
        if (
            not isinstance(binding, list)
            or len(binding) != 1
            or not isinstance(binding[0], dict)
            or binding[0].get("HostIp") != "127.0.0.1"
            or not isinstance(binding[0].get("HostPort"), str)
            or not binding[0]["HostPort"].isdigit()
            or not 1024 <= int(binding[0]["HostPort"]) <= 65535
        ):
            raise DrillError("existing recovery Polaris port is not loopback-only")

    def use_retained_resources(self, expected_sha256: str) -> None:
        if not _SHA256.fullmatch(expected_sha256):
            raise DrillError("retained Docker resource fingerprint is invalid")
        network, _volume, actual_sha256 = self._retained_resource_state()
        if not hmac.compare_digest(actual_sha256, expected_sha256):
            raise DrillError("retained Docker resources changed after Seed-A")

        present: dict[str, Mapping[str, object]] = {}
        for key in ("postgresContainer", "bootstrapContainer", "polarisContainer"):
            name = self.resources[key]
            names = self._listed_names("container", name)
            if names not in ((), (name,)):
                raise DrillError("Docker container inventory is ambiguous")
            if not names:
                continue
            if key == "bootstrapContainer":
                raise DrillError("Recovery-A cannot own a bootstrap container remnant")
            present[key] = self._resource_inspect("container", name)

        attachments = network["Containers"]
        attachment_ids: dict[str, str] = {}
        for container_id, attachment in attachments.items():
            if (
                not isinstance(container_id, str)
                or not isinstance(attachment, dict)
                or not isinstance(attachment.get("Name"), str)
                or attachment["Name"] in attachment_ids
            ):
                raise DrillError("generated Docker network attachment is invalid")
            attachment_ids[attachment["Name"]] = container_id
        expected_names = {self.resources[key] for key in present}
        if set(attachment_ids) != expected_names:
            raise DrillError("generated Docker network has unknown attachments")
        volume_consumers = self._volume_consumers()
        postgres_name = self.resources["postgresContainer"]
        expected_consumers = {postgres_name} if "postgresContainer" in present else set()
        if set(volume_consumers) != expected_consumers:
            raise DrillError("generated Docker volume has unknown consumers")
        network_id = network.get("Id")
        if not isinstance(network_id, str) or not network_id:
            raise DrillError("generated Docker network identity is invalid")
        for key, container in present.items():
            name = self.resources[key]
            self._validate_recovery_remnant(
                key=key,
                container=container,
                network_id=network_id,
                attachment_id=attachment_ids[name],
            )
            if key == "postgresContainer":
                inspected_id = container.get("Id")
                if not isinstance(inspected_id, str) or not inspected_id.startswith(
                    volume_consumers[name]
                ):
                    raise DrillError("recovery PostgreSQL volume consumer identity changed")

        for key in ("polarisContainer", "postgresContainer"):
            if key in present:
                self._run(("docker", "rm", "--force", self.resources[key]))
        self._require_containers_absent()
        if self._volume_consumers():
            raise DrillError("generated Docker volume remains in use after containment")

    def _create_sleeper(
        self,
        *,
        name: str,
        image: ImagePin,
        phase: str,
        network_alias: str,
        mount_postgres: bool = False,
        publish_api: bool = False,
    ) -> None:
        command = [
            "docker",
            "create",
            "--name",
            name,
            *self._labels(phase=phase),
            "--network",
            self.resources["network"],
            "--network-alias",
            network_alias,
            "--restart=no",
            "--stop-timeout",
            "30",
        ]
        if mount_postgres:
            command.extend(
                [
                    "--mount",
                    "type=volume,src="
                    f"{self.resources['postgresVolume']},dst=/var/lib/postgresql/data",
                ]
            )
        if publish_api:
            command.extend(["--publish", "127.0.0.1::8181"])
        command.extend(
            [
                "--entrypoint",
                "/bin/sh",
                image.image_id,
                "-ceu",
                f"exec sleep {self.sleeper_seconds}",
            ]
        )
        self._run(command)
        self._created_containers.add(name)
        self._run(("docker", "start", name))

    def _spawn(self, command: Sequence[str], payload: str) -> None:
        process = self.popen_factory(
            list(command),
            stdin=subprocess.PIPE,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            text=True,
        )
        if process.stdin is None:
            raise DrillError("isolated Docker child did not accept private input")
        process.stdin.write(payload)
        process.stdin.close()
        self._children.append(process)

    def _wait_postgres(self) -> None:
        command = (
            "docker",
            "exec",
            self.resources["postgresContainer"],
            "pg_isready",
            "-U",
            "polaris",
            "-d",
            "polaris",
        )
        for _attempt in range(120):
            completed = self._capture(command)
            if completed.returncode == 0:
                return
            time.sleep(0.25)
        raise DrillError("isolated PostgreSQL did not become ready")

    @staticmethod
    def _launch(pin: ImagePin) -> tuple[str, ...]:
        launch = pin.entrypoint + pin.command
        if not launch:
            raise DrillError("pinned Docker image launch command is empty")
        return launch

    def start(
        self,
        credentials: RunCredentials,
        aws: AwsCredentials,
        *,
        bootstrap: bool,
        region: str,
    ) -> str:
        phase = "seed" if bootstrap else "recovery"
        postgres = self.resources["postgresContainer"]
        _seed_stage(
            "postgres-container-start",
            lambda: self._create_sleeper(
                name=postgres,
                image=self.images["postgres"],
                phase=phase,
                network_alias="postgres",
                mount_postgres=True,
            ),
        )
        postgres_script = """\
IFS= read -r POSTGRES_PASSWORD
export POSTGRES_PASSWORD POSTGRES_DB=polaris POSTGRES_USER=polaris
exec \"$@\" -c archive_mode=off -c listen_addresses='*'
"""
        _seed_stage(
            "postgres-process-launch",
            lambda: self._spawn(
                (
                    "docker",
                    "exec",
                    "--interactive",
                    postgres,
                    "/bin/sh",
                    "-ceu",
                    postgres_script,
                    "launcher",
                    *self._launch(self.images["postgres"]),
                ),
                credentials.postgres_password + "\n",
            ),
        )
        _seed_stage("postgres-readiness", self._wait_postgres)

        if bootstrap:
            bootstrap_name = self.resources["bootstrapContainer"]
            admin_pin = self.images["polarisAdmin"]
            if not admin_pin.entrypoint:
                raise DrillError("Polaris admin image requires a pinned entrypoint")
            _seed_stage(
                "polaris-bootstrap-container-start",
                lambda: self._create_sleeper(
                    name=bootstrap_name,
                    image=admin_pin,
                    phase=phase,
                    network_alias="bootstrap",
                ),
            )
            bootstrap_script = """\
IFS= read -r DB_PASSWORD
IFS= read -r CLIENT_ID
IFS= read -r CLIENT_SECRET
exec env \\
  'polaris.persistence.type=relational-jdbc' \\
  'quarkus.datasource.username=polaris' \\
  \"quarkus.datasource.password=${DB_PASSWORD}\" \\
  'quarkus.datasource.jdbc.url=jdbc:postgresql://postgres:5432/polaris' \\
  \"$@\" bootstrap -r POLARIS -c \"POLARIS,${CLIENT_ID},${CLIENT_SECRET}\"
"""
            _seed_stage(
                "polaris-bootstrap",
                lambda: self._run(
                    (
                        "docker",
                        "exec",
                        "--interactive",
                        bootstrap_name,
                        "/bin/sh",
                        "-ceu",
                        bootstrap_script,
                        "launcher",
                        *admin_pin.entrypoint,
                    ),
                    input_text=(
                        f"{credentials.postgres_password}\n"
                        f"{credentials.polaris_client_id}\n"
                        f"{credentials.polaris_client_secret}\n"
                    ),
                ),
            )
            _seed_stage(
                "polaris-bootstrap-containment",
                lambda: self._run(("docker", "rm", "--force", bootstrap_name)),
            )
            self._created_containers.discard(bootstrap_name)

        polaris = self.resources["polarisContainer"]
        _seed_stage(
            "polaris-container-start",
            lambda: self._create_sleeper(
                name=polaris,
                image=self.images["polaris"],
                phase=phase,
                network_alias="polaris",
                publish_api=True,
            ),
        )
        polaris_script = """\
IFS= read -r DB_PASSWORD
IFS= read -r AWS_ACCESS_KEY_ID
IFS= read -r AWS_SECRET_ACCESS_KEY
IFS= read -r AWS_SESSION_TOKEN
IFS= read -r AWS_REGION
export POLARIS_PERSISTENCE_TYPE=relational-jdbc
export QUARKUS_DATASOURCE_USERNAME=polaris
export QUARKUS_DATASOURCE_PASSWORD=${DB_PASSWORD}
export QUARKUS_DATASOURCE_JDBC_URL=jdbc:postgresql://postgres:5432/polaris
export POLARIS_REALM_CONTEXT_REALMS=POLARIS
export POLARIS_REALM_CONTEXT_REQUIRE_HEADER=false
export AWS_ACCESS_KEY_ID AWS_SECRET_ACCESS_KEY AWS_SESSION_TOKEN AWS_REGION
export AWS_DEFAULT_REGION=${AWS_REGION}
exec \"$@\"
"""
        _seed_stage(
            "polaris-process-launch",
            lambda: self._spawn(
                (
                    "docker",
                    "exec",
                    "--interactive",
                    polaris,
                    "/bin/sh",
                    "-ceu",
                    polaris_script,
                    "launcher",
                    *self._launch(self.images["polaris"]),
                ),
                (
                    f"{credentials.postgres_password}\n"
                    f"{aws.access_key_id}\n"
                    f"{aws.secret_access_key}\n"
                    f"{aws.session_token}\n"
                    f"{region}\n"
                ),
            ),
        )
        completed = _seed_stage(
            "polaris-port-discovery",
            lambda: self._capture(("docker", "port", polaris, "8181/tcp")),
        )
        if completed.returncode != 0:
            raise SeedStageError("polaris-port-discovery")
        lines = [line for line in completed.stdout.splitlines() if line]
        if len(lines) != 1:
            raise SeedStageError("polaris-port-discovery")
        match = re.fullmatch(r"127\.0\.0\.1:([0-9]{1,5})", lines[0])
        if match is None or not 1024 <= int(match.group(1)) <= 65535:
            raise SeedStageError("polaris-port-discovery")
        return f"http://127.0.0.1:{match.group(1)}"

    def close(self) -> None:
        errors = False
        polaris = self.resources["polarisContainer"]
        bootstrap = self.resources["bootstrapContainer"]
        postgres = self.resources["postgresContainer"]
        if postgres in self._created_containers:
            completed = self._capture(
                (
                    "docker",
                    "exec",
                    "--user",
                    "postgres",
                    postgres,
                    "pg_ctl",
                    "-D",
                    "/var/lib/postgresql/data",
                    "-m",
                    "fast",
                    "-w",
                    "stop",
                )
            )
            errors = errors or completed.returncode != 0
        for name in (bootstrap, polaris, postgres):
            if name not in self._created_containers:
                continue
            completed = self._capture(("docker", "rm", "--force", name))
            errors = errors or completed.returncode != 0
            self._created_containers.discard(name)
        for process in self._children:
            try:
                process.wait(timeout=5)
            except Exception:
                errors = True
        try:
            self._require_containers_absent()
        except DrillError:
            errors = True
        if errors:
            raise DrillError("secret-bearing Docker container containment failed")


def _rows_digest(rows: Sequence[Mapping[str, object]]) -> str:
    normalized = [dict(row) for row in sorted(rows, key=lambda row: int(row["event_id"]))]
    return hashlib.sha256(_canonical_json(normalized)).hexdigest()


def _schema_digest(table: Any) -> str:
    return hashlib.sha256(
        _canonical_json(table.schema().model_dump(mode="json", by_alias=True))
    ).hexdigest()


class _PrefixFencedInputFile:
    """Bind a delegate read failure to its already validated request location."""

    def __init__(self, delegate: Any, location: str) -> None:
        self._delegate = delegate
        self._location = location

    @property
    def location(self) -> str:
        return self._location

    def __len__(self) -> int:
        return len(self._delegate)

    def exists(self) -> bool:
        return self._delegate.exists()

    def open(self, seekable: bool = True) -> Any:
        try:
            return self._delegate.open(seekable=seekable)
        except FileNotFoundError as exc:
            raise FileNotFoundError(f"validated FileIO input is absent: {self._location}") from exc


class _PrefixFencedFileIO:
    """Reject every PyIceberg file operation outside one generated S3 scope."""

    def __init__(self, delegate: Any, validator: Callable[[str], object]) -> None:
        self._delegate = delegate
        self._validator = validator
        self.properties = getattr(delegate, "properties", {})

    def new_input(self, location: str) -> Any:
        self._validator(location)
        return _PrefixFencedInputFile(self._delegate.new_input(location), location)

    def new_output(self, location: str) -> Any:
        self._validator(location)
        return self._delegate.new_output(location)

    def delete(self, location: str) -> None:
        self._validator(location)
        self._delegate.delete(location)


class LiveWarehouseDrillOperations:
    """Real Polaris, PyIceberg, and S3 effects for one generated drill scope."""

    def __init__(
        self,
        *,
        scope: DrillScope,
        bucket: str,
        gateway: PolarisGateway,
        writer_store: AwsCliVersionStore,
        recovery_store: AwsCliVersionStore,
        runtime_binding: RuntimeBinding | None = None,
    ) -> None:
        self.scope = scope
        self.bucket = bucket
        self.gateway = gateway
        self.writer_store = writer_store
        self.recovery_store = recovery_store
        self.runtime_binding = runtime_binding
        self._break_proof_table: Any | None = None
        self._break_proof_io: Any | None = None

    def _require_scope(self, scope: DrillScope) -> None:
        if scope != self.scope:
            raise DrillError("operation scope does not match the generated live scope")

    def _verify_capability_canary(self) -> GraphNode:
        key = f"{self.scope.prefix}/capability-canary.bin"
        node = _seed_stage(
            "canary-put",
            lambda: self.writer_store.put_canary(key, b"canary\n"),
        )
        deleted = _seed_stage(
            "canary-delete",
            lambda: self.writer_store.delete_current(node),
        )
        marker = _seed_stage(
            "canary-marker-read",
            lambda: self.writer_store.current_state(node),
        )
        if (
            not deleted.delete_marker
            or not deleted.version_id
            or marker.exists
            or not marker.delete_marker
            or marker.version_id != deleted.version_id
        ):
            raise SeedStageError("canary-marker-validation")
        _seed_stage(
            "canary-source-read",
            lambda: self.recovery_store.exact_source_state(node),
        )
        restored = _seed_stage(
            "canary-restore",
            lambda: self.recovery_store.restore(node),
        )
        if not _matches_content(node, restored) or restored.version_id in {
            None,
            node.source_version_id,
        }:
            raise SeedStageError("canary-restore-validation")
        _seed_stage(
            "canary-restored-source-read",
            lambda: self.recovery_store.exact_source_state(node),
        )
        return node

    def _validate_preverified_canary(self, node: GraphNode) -> None:
        expected_key = f"{self.scope.prefix}/capability-canary.bin"
        if (
            node.key != expected_key
            or node.kind != "capability-canary"
            or not node.source_version_id
            or node.source_version_id == "null"
            or not node.etag
            or node.size != len(b"canary\n")
            or node.sha256 != hashlib.sha256(b"canary\n").hexdigest()
            or node.depth != 0
        ):
            raise SeedStageError("canary-residual-validation")
        self.recovery_store.verify_only_key(node.key)
        current = self.recovery_store.current_state(node)
        if not _matches_content(node, current) or current.version_id in {
            None,
            node.source_version_id,
        }:
            raise SeedStageError("canary-residual-validation")
        self.recovery_store.exact_source_state(node)

    def _table(self) -> Any:
        table = self.gateway.open(self.scope).load_table((self.scope.namespace, self.scope.table))
        return self._fence_table(table)

    def _key(self, location: str) -> str:
        parsed = urlparse(location)
        key = parsed.path.lstrip("/")
        if (
            parsed.scheme != "s3"
            or parsed.netloc != self.bucket
            or parsed.params
            or parsed.query
            or parsed.fragment
            or not key.startswith(self.scope.prefix + "/")
        ):
            raise DrillError("Iceberg graph contains an external or malformed S3 location")
        return key

    def _fence_table(self, table: Any) -> Any:
        self._key(table.metadata_location)
        properties = getattr(table.io, "properties", None)
        if not isinstance(properties, Mapping) or any(
            not isinstance(properties.get(name), str)
            or not properties[name]
            or len(properties[name]) > 8192
            for name in _VENDED_S3_CREDENTIAL_PROPERTIES
        ):
            raise DrillError("catalog-loaded FileIO lacks vended session credentials")
        table.io = _PrefixFencedFileIO(table.io, self._key)
        return table

    def _rows(self, table: Any) -> tuple[Mapping[str, object], ...]:
        try:
            raw = table.scan().to_arrow().to_pylist()
        except Exception as exc:
            raise DrillError("fresh PyIceberg query failed") from exc
        if (
            not isinstance(raw, list)
            or len(raw) > 32
            or not all(isinstance(row, dict) for row in raw)
        ):
            raise DrillError("fresh PyIceberg query returned an invalid result")
        rows = tuple(sorted((dict(row) for row in raw), key=lambda row: int(row["event_id"])))
        if rows != tuple(dict(row) for row in _DETERMINISTIC_ROWS):
            raise DrillError("fresh PyIceberg query did not return the deterministic rows")
        return rows

    def _capture(self, table: Any) -> TableCapture:
        graph = capture_iceberg_graph(table, location_validator=self._key)
        approved: list[tuple[GraphObject, str, VersionEntry]] = []
        total_size = 0
        for item in graph:
            key = self._key(item.location)
            timeline = self.recovery_store.list_versions(key)
            if len(timeline) > _MAX_PREPARE_VERSIONS_PER_KEY:
                raise DrillError("graph key lacks safe version-count headroom")
            latest = [entry for entry in timeline if entry.latest]
            if (
                len(latest) != 1
                or latest[0].delete_marker
                or latest[0].version_id == "null"
                or latest[0].etag is None
                or latest[0].size is None
            ):
                raise DrillError("graph key has no unambiguous versioned current object")
            total_size += latest[0].size
            if total_size > _MAX_GRAPH_BYTES:
                raise DrillError("prepared graph exceeds the byte limit before object reads")
            approved.append((item, key, latest[0]))

        nodes: list[GraphNode] = []
        observed_size = 0
        for item, key, latest in approved:
            state = self.recovery_store._version_state(latest)
            if not state.exists or state.size != latest.size or state.sha256 is None:
                raise DrillError("graph key current bytes could not be captured")
            observed_size += state.size
            if observed_size > _MAX_GRAPH_BYTES:
                raise DrillError("prepared graph exceeded the byte limit during object reads")
            nodes.append(
                GraphNode(
                    key=key,
                    kind=item.kind,
                    source_version_id=latest.version_id,
                    etag=latest.etag,
                    size=latest.size,
                    sha256=state.sha256,
                    depth=item.depth,
                )
            )
        rows = self._rows(table)
        snapshot = table.current_snapshot()
        if snapshot is None:
            raise DrillError("prepared table has no current snapshot")
        return TableCapture(
            bucket=self.bucket,
            table_uuid=str(table.metadata.table_uuid),
            metadata_location=table.metadata_location,
            snapshot_id=snapshot.snapshot_id,
            schema_sha256=_schema_digest(table),
            row_count=len(rows),
            rows_sha256=_rows_digest(rows),
            nodes=tuple(nodes),
        )

    def prepare(
        self,
        scope: DrillScope,
        rows: Sequence[Mapping[str, object]],
        *,
        capability_canary: GraphNode | None = None,
    ) -> TableCapture:
        self._require_scope(scope)
        if tuple(rows) != _DETERMINISTIC_ROWS:
            raise DrillError("prepared rows do not match the deterministic contract")
        try:
            if capability_canary is None:
                _seed_stage("point-a-empty-prefix", self.recovery_store.verify_empty_prefix)
                capability_canary = _seed_stage(
                    "capability-canary",
                    self._verify_capability_canary,
                )
            _seed_stage(
                "canary-residual-validation",
                lambda: self._validate_preverified_canary(capability_canary),
            )
            catalog = _seed_stage(
                "catalog-provision",
                lambda: self.gateway.provision(scope),
            )
            namespace_location = f"s3://{self.bucket}/{scope.prefix}/{scope.namespace}"
            table_location = f"{namespace_location}/{scope.table}"
            namespace_key = self._key(namespace_location)
            table_key = self._key(table_location)
            if table_key != f"{namespace_key}/{scope.table}":
                raise DrillError("generated table location is outside its namespace")
            _seed_stage(
                "namespace-create",
                lambda: catalog.create_namespace(
                    scope.namespace,
                    {"location": namespace_location},
                ),
            )
            from pyarrow import Table as ArrowTable
            from pyiceberg.schema import Schema
            from pyiceberg.types import LongType, NestedField, StringType

            schema = _seed_stage(
                "table-schema-construction",
                lambda: Schema(
                    NestedField(1, "event_id", LongType(), required=True),
                    NestedField(2, "generation", StringType(), required=True),
                    NestedField(3, "value", LongType(), required=True),
                ),
            )
            table = _seed_stage(
                "table-create",
                lambda: catalog.create_table(
                    (scope.namespace, scope.table),
                    schema=schema,
                    location=table_location,
                    properties={"format-version": "2"},
                ),
            )
            _seed_stage("table-fileio-fence", lambda: self._fence_table(table))
            _seed_stage(
                "point-a-append",
                lambda: table.append(
                    ArrowTable.from_pylist(
                        [dict(row) for row in rows],
                        schema=schema.as_arrow(),
                    )
                ),
            )
            return _seed_stage("point-a-capture", lambda: self._capture(self._table()))
        except DrillError:
            raise
        except Exception as exc:
            raise DrillError("real synthetic Iceberg preparation failed") from exc

    def current_state(self, node: GraphNode) -> ObjectState:
        return self.recovery_store.current_state(node)

    def delete_current(self, node: GraphNode) -> DeleteResult:
        return self.writer_store.delete_current(node)

    def _verify_expected_damage(self, manifest: Mapping[str, object]) -> None:
        graph = manifest.get("graph")
        raw_nodes = graph.get("nodes") if isinstance(graph, dict) else None
        if not isinstance(raw_nodes, list) or not raw_nodes:
            raise DrillError("break proof manifest graph is invalid")
        for raw in raw_nodes:
            if not isinstance(raw, dict):
                raise DrillError("break proof manifest graph node is invalid")
            key = raw.get("key")
            source_version = raw.get("sourceVersionId")
            etag = raw.get("etag")
            size = raw.get("size")
            digest = raw.get("sha256")
            if (
                not isinstance(key, str)
                or not isinstance(source_version, str)
                or not isinstance(etag, str)
                or isinstance(size, bool)
                or not isinstance(size, int)
                or not isinstance(digest, str)
            ):
                raise DrillError("break proof manifest graph node values are invalid")
            try:
                timeline = self.recovery_store.list_versions(key)
            except Exception as exc:
                raise DrillError("historical source verification was unavailable") from exc
            latest = [entry for entry in timeline if entry.latest]
            if len(latest) != 1 or not latest[0].delete_marker:
                raise DrillError("expected current delete marker is absent during break proof")
            source = [
                entry
                for entry in timeline
                if entry.version_id == source_version and not entry.delete_marker
            ]
            if len(source) != 1 or source[0].etag != etag or source[0].size != size:
                raise DrillError("historical source version is absent during break proof")
            try:
                state = self.recovery_store._version_state(source[0])
            except Exception as exc:
                raise DrillError(
                    "historical source version was not independently readable"
                ) from exc
            if (
                not state.exists
                or state.delete_marker
                or state.version_id != source_version
                or state.size != size
                or state.sha256 != digest
            ):
                raise DrillError("historical source content differs during break proof")

    @staticmethod
    def _message_names_exact_location(message: str, location: str) -> bool:
        pattern = re.compile(
            rf"(?<![A-Za-z0-9._~%!$&'()*+,;=:@/?#-]){re.escape(location)}"
            r"(?![A-Za-z0-9._~%!$&'()*+,;=:@/?#-])"
        )
        return pattern.search(message) is not None

    def _approved_missing_location(
        self,
        error: BaseException,
        manifest: Mapping[str, object],
        *,
        expected_location: str | None = None,
    ) -> str | None:
        raw_graph = manifest.get("graph")
        raw_nodes = raw_graph.get("nodes") if isinstance(raw_graph, dict) else None
        if not isinstance(raw_nodes, list) or not raw_nodes:
            return None
        locations: set[str] = set()
        for raw in raw_nodes:
            key = raw.get("key") if isinstance(raw, dict) else None
            if not isinstance(key, str):
                return None
            location = f"s3://{self.bucket}/{key}"
            self._key(location)
            locations.add(location)
        if expected_location is not None:
            if expected_location not in locations:
                return None
            locations = {expected_location}

        current: BaseException | None = error
        seen: set[int] = set()
        matches: set[str] = set()
        for _depth in range(8):
            if current is None or id(current) in seen:
                break
            seen.add(id(current))
            if isinstance(current, FileNotFoundError):
                message = str(current)
                matches.update(
                    location
                    for location in locations
                    if self._message_names_exact_location(message, location)
                )
            current = current.__cause__ or current.__context__
        if len(matches) != 1:
            return None
        return next(iter(matches))

    def assert_table_unreadable(self, manifest: Mapping[str, object]) -> None:
        self._manifest_scope(manifest)
        try:
            catalog = self.gateway.open(self.scope)
            namespaces = catalog.list_namespaces()
        except Exception as exc:
            raise RecoveryStageError("break-proof", error_kind="catalog-health") from exc
        if (self.scope.namespace,) not in namespaces:
            raise RecoveryStageError("break-proof", error_kind="namespace-missing")
        if self._break_proof_table is None or self._break_proof_io is None:
            raise RecoveryStageError("break-proof", error_kind="fileio-unavailable")

        try:
            scan = self._break_proof_table.scan()
            list(scan.plan_files())
            scan.to_arrow()
        except Exception as exc:
            location = self._approved_missing_location(exc, manifest)
            if location is None:
                raise RecoveryStageError(
                    "break-proof", error_kind="missing-query-unexpected-error"
                ) from exc
        else:
            raise RecoveryStageError("break-proof", error_kind="table-readable")

        try:
            with self._break_proof_io.new_input(location).open() as stream:
                stream.read(1)
        except Exception as exc:
            if (
                self._approved_missing_location(
                    exc,
                    manifest,
                    expected_location=location,
                )
                != location
            ):
                raise RecoveryStageError(
                    "break-proof", error_kind="missing-proof-unexpected-error"
                ) from exc
        else:
            raise RecoveryStageError("break-proof", error_kind="approved-object-readable")
        try:
            self._verify_expected_damage(manifest)
        except DrillError as proof_exc:
            raise RecoveryStageError(
                "break-proof", error_kind="missing-proof-invalid"
            ) from proof_exc

    def restore(self, node: GraphNode) -> ObjectState:
        return self.recovery_store.restore(node)

    def _manifest_scope(self, manifest: Mapping[str, object]) -> None:
        raw = manifest.get("scope")
        if not isinstance(raw, dict) or raw.get("runId") != self.scope.run_id:
            raise DrillError("manifest does not match the live operation scope")

    def validate(self, manifest: Mapping[str, object]) -> ValidationResult:
        self._manifest_scope(manifest)
        try:
            table = self._table()
            if self._break_proof_table is None:
                self._break_proof_table = table
                self._break_proof_io = table.io
            capture = self._capture(table)
            graph, logical_sha = _validate_capture(self.scope, capture)
            expected_graph = manifest.get("graph")
            expected_table = manifest.get("table")
            if not isinstance(expected_graph, dict) or not isinstance(expected_table, dict):
                raise DrillError("manifest validation contract is invalid")
            if graph.get("logicalSha256") != expected_graph.get("logicalSha256"):
                raise DrillError("restored logical Iceberg graph does not match point A")
            original_nodes = expected_graph.get("nodes")
            if not isinstance(original_nodes, list):
                raise DrillError("manifest graph nodes are invalid")
            for raw_node in original_nodes:
                if not isinstance(raw_node, dict):
                    raise DrillError("manifest graph node is invalid")
                key = raw_node.get("key")
                source_version = raw_node.get("sourceVersionId")
                if not isinstance(key, str) or not isinstance(source_version, str):
                    raise DrillError("manifest graph source is invalid")
                source = [
                    entry
                    for entry in self.recovery_store.list_versions(key)
                    if entry.version_id == source_version and not entry.delete_marker
                ]
                if len(source) != 1:
                    raise DrillError("recorded point-A source version was not preserved")
            return ValidationResult(
                table_uuid=capture.table_uuid,
                metadata_location=capture.metadata_location,
                snapshot_id=capture.snapshot_id,
                logical_graph_sha256=logical_sha,
                row_count=capture.row_count,
                rows_sha256=capture.rows_sha256,
            )
        except DrillError:
            raise
        except Exception as exc:
            raise DrillError("fresh restored Iceberg validation failed") from exc


def _node_dict(node: GraphNode) -> dict[str, object]:
    return {
        "key": node.key,
        "kind": node.kind,
        "sourceVersionId": node.source_version_id,
        "etag": node.etag,
        "size": node.size,
        "sha256": node.sha256,
        "depth": node.depth,
    }


def _validate_capture(scope: DrillScope, capture: TableCapture) -> tuple[dict[str, object], str]:
    if not capture.bucket or not capture.table_uuid or capture.snapshot_id <= 0:
        raise DrillError("prepared table identity is invalid")
    if capture.row_count != len(_DETERMINISTIC_ROWS):
        raise DrillError("prepared row count does not match the deterministic contract")
    if not _SHA256.fullmatch(capture.schema_sha256) or not _SHA256.fullmatch(capture.rows_sha256):
        raise DrillError("prepared table digest is invalid")
    if not 0 < len(capture.nodes) <= _MAX_GRAPH_OBJECTS:
        raise DrillError("prepared graph object count is outside the safe limit")
    if sum(node.size for node in capture.nodes) > _MAX_GRAPH_BYTES:
        raise DrillError("prepared graph exceeds the byte limit")

    expected_prefix = scope.prefix + "/"
    keys: set[str] = set()
    metadata_keys: list[str] = []
    node_values: list[dict[str, object]] = []
    logical_nodes: list[dict[str, object]] = []
    for node in capture.nodes:
        if node.key in keys or not node.key.startswith(expected_prefix):
            raise DrillError("prepared graph contains a duplicate or out-of-scope key")
        if (
            not node.kind
            or not node.source_version_id
            or node.source_version_id == "null"
            or node.size < 0
            or node.depth < 0
            or not _SHA256.fullmatch(node.sha256)
        ):
            raise DrillError("prepared graph node is invalid")
        keys.add(node.key)
        if node.kind == "metadata":
            metadata_keys.append(node.key)
        node_values.append(_node_dict(node))
        logical_nodes.append(
            {
                "key": node.key,
                "kind": node.kind,
                "size": node.size,
                "sha256": node.sha256,
                "depth": node.depth,
            }
        )

    parsed = urlparse(capture.metadata_location)
    if (
        parsed.scheme != "s3"
        or parsed.netloc != capture.bucket
        or parsed.path.lstrip("/") not in metadata_keys
        or len(metadata_keys) != 1
    ):
        raise DrillError("catalog metadata location does not identify one graph root")

    logical = {
        "tableUuid": capture.table_uuid,
        "metadataLocation": capture.metadata_location,
        "snapshotId": capture.snapshot_id,
        "schemaSha256": capture.schema_sha256,
        "rowsSha256": capture.rows_sha256,
        "nodes": logical_nodes,
    }
    logical_sha = hashlib.sha256(_canonical_json(logical)).hexdigest()
    graph = {"logicalSha256": logical_sha, "nodes": node_values}
    return graph, logical_sha


def _atomic_private_write(path: Path, payload: bytes) -> None:
    """Durably publish one private receipt without replacing an existing name."""
    if len(payload) > _MAX_PRIVATE_RESPONSE_BYTES:
        raise DrillError("private drill evidence exceeds the size limit")
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    try:
        parent = path.parent.lstat()
    except OSError as exc:
        raise DrillError("private drill evidence directory is unavailable") from exc
    if not stat.S_ISDIR(parent.st_mode) or stat.S_IMODE(parent.st_mode) != 0o700:
        raise DrillError("private drill evidence directory is unsafe")
    descriptor, filename = tempfile.mkstemp(
        prefix=f".{path.name}.",
        suffix=".tmp",
        dir=path.parent,
    )
    temporary = Path(filename)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        temporary.chmod(0o600)
        try:
            os.link(temporary, path, follow_symlinks=False)
        except FileExistsError as exc:
            raise DrillError("private drill manifest already exists") from exc
        temporary.unlink()
        directory = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise


def _atomic_private_replace(path: Path, payload: bytes) -> None:
    if len(payload) > _MAX_PRIVATE_RESPONSE_BYTES:
        raise DrillError("private drill evidence exceeds the size limit")
    try:
        details = path.lstat()
    except OSError as exc:
        raise DrillError("private drill evidence cannot be replaced") from exc
    if not stat.S_ISREG(details.st_mode) or stat.S_IMODE(details.st_mode) != 0o600:
        raise DrillError("private drill evidence replacement target is unsafe")
    descriptor, filename = tempfile.mkstemp(
        prefix=f".{path.name}.",
        suffix=".tmp",
        dir=path.parent,
    )
    temporary = Path(filename)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        temporary.chmod(0o600)
        os.replace(temporary, path)
        directory = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise


def _bounded_local_json(
    command: Sequence[str], *, runner: CommandRunner = subprocess.run
) -> object:
    completed = runner(
        list(command),
        text=True,
        capture_output=True,
        check=False,
    )
    if completed.returncode != 0:
        raise DrillError("local read-only runtime inspection failed")
    if len(completed.stdout.encode()) > _MAX_PRIVATE_RESPONSE_BYTES:
        raise DrillError("local runtime inspection exceeded the response limit")
    try:
        return json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise DrillError("local runtime inspection returned invalid JSON") from exc


def _inspect_docker_image(reference: str, *, runner: CommandRunner = subprocess.run) -> ImagePin:
    value = _bounded_local_json(
        ("docker", "image", "inspect", reference),
        runner=runner,
    )
    if not isinstance(value, list) or len(value) != 1 or not isinstance(value[0], dict):
        raise DrillError("Docker image inspection returned an unexpected shape")
    image = value[0]
    image_id = image.get("Id")
    config = image.get("Config")
    if not isinstance(image_id, str) or not re.fullmatch(r"sha256:[0-9a-f]{64}", image_id):
        raise DrillError("Docker image inspection returned an invalid image ID")
    if not isinstance(config, dict):
        raise DrillError("Docker image inspection omitted image configuration")

    def command_tuple(value: object) -> tuple[str, ...]:
        if value is None:
            return ()
        if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
            raise DrillError("Docker image launch configuration is invalid")
        return tuple(value)

    entrypoint = command_tuple(config.get("Entrypoint"))
    command = command_tuple(config.get("Cmd"))
    environment = command_tuple(config.get("Env"))
    user = config.get("User") or ""
    working_directory = config.get("WorkingDir") or ""
    if not entrypoint and not command:
        raise DrillError("Docker image has no pinned launch command")
    if not isinstance(user, str) or not isinstance(working_directory, str):
        raise DrillError("Docker image execution configuration is invalid")
    return ImagePin(
        reference=reference,
        image_id=image_id,
        entrypoint=entrypoint,
        command=command,
        environment=environment,
        user=user,
        working_directory=working_directory,
    )


def _docker_runtime_fingerprint(*, runner: CommandRunner = subprocess.run) -> str:
    value = _bounded_local_json(
        ("docker", "version", "--format", "{{json .}}"),
        runner=runner,
    )
    if not isinstance(value, dict):
        raise DrillError("Docker runtime inspection returned an unexpected shape")
    client = value.get("Client")
    server = value.get("Server")
    if not isinstance(client, dict) or not isinstance(server, dict):
        raise DrillError("Docker client/server inspection is incomplete")
    projection = {
        "clientVersion": client.get("Version"),
        "clientApiVersion": client.get("ApiVersion"),
        "serverVersion": server.get("Version"),
        "serverApiVersion": server.get("ApiVersion"),
    }
    if not all(isinstance(item, str) and item for item in projection.values()):
        raise DrillError("Docker client/server version values are invalid")
    return hashlib.sha256(_canonical_json(projection)).hexdigest()


def _secret_binding(settings: RecoverySettings, run_id: str) -> str:
    return hmac.new(
        settings.run_secret.encode(),
        f"databox-iceberg-recovery:{run_id}:binding".encode(),
        hashlib.sha256,
    ).hexdigest()


def _derive_run_credentials(settings: RecoverySettings, scope: DrillScope) -> RunCredentials:
    def derive(label: str) -> str:
        return hmac.new(
            settings.run_secret.encode(),
            f"databox-iceberg-recovery:{scope.run_id}:{label}".encode(),
            hashlib.sha256,
        ).hexdigest()

    return RunCredentials(
        postgres_password=derive("postgres-password"),  # secret-scan: allow
        polaris_client_id=f"recovery-{scope.run_id}",
        polaris_client_secret=derive("polaris-client-secret"),  # secret-scan: allow
    )


def _export_aws_credentials(
    *,
    environ: Mapping[str, str],
    runner: CommandRunner = subprocess.run,
) -> AwsCredentials:
    value = _run_cli_json(
        (
            "aws",
            "configure",
            "export-credentials",
            "--format",
            "process",
            "--no-cli-pager",
        ),
        environ=environ,
        runner=runner,
    )
    access_key = value.get("AccessKeyId")  # secret-scan: allow
    secret_key = value.get("SecretAccessKey")  # secret-scan: allow
    session_token = value.get("SessionToken")  # secret-scan: allow
    if (
        not isinstance(access_key, str)
        or not re.fullmatch(r"[A-Z0-9]{16,128}", access_key)
        or not isinstance(secret_key, str)
        or not 32 <= len(secret_key) <= 256
        or not isinstance(session_token, str)
        or not 16 <= len(session_token) <= 8192
    ):
        raise DrillError("explicit operator profile did not export valid temporary credentials")
    return AwsCredentials(access_key, secret_key, session_token)


def _stack_resources(scope: DrillScope) -> dict[str, str]:
    stem = f"databox-ir-{scope.run_id}"
    return {
        "network": f"{stem}-net",
        "postgresVolume": f"{stem}-pgdata",
        "postgresContainer": f"{stem}-postgres",
        "bootstrapContainer": f"{stem}-bootstrap",
        "polarisContainer": f"{stem}-polaris",
    }


def _seed_contract() -> dict[str, object]:
    return {
        "formatVersion": 3,
        "rowsSha256": _rows_digest(_DETERMINISTIC_ROWS),
        "rowCount": len(_DETERMINISTIC_ROWS),
        "maxStage1Objects": _MAX_STAGE1_OBJECTS,
        "maxGraphObjects": _MAX_GRAPH_OBJECTS,
        "retainedCanaryObjects": 1,
        "maxGraphBytes": _MAX_GRAPH_BYTES,
        "maxVersionsPerKey": _MAX_PREPARE_VERSIONS_PER_KEY,
        "canarySha256": hashlib.sha256(b"canary\n").hexdigest(),
        "operations": [
            "operator-canary-put-ordinary-delete",
            "operator-canary-exact-version-promotion",
            "validate-canary-only-prefix",
            "create-run-network",
            "create-postgres-volume",
            "start-transient-postgres",
            "bootstrap-transient-polaris",
            "start-transient-polaris",
            "create-generated-catalog-namespace-table",
            "append-deterministic-point-a",
            "validate-complete-stage1-prefix",
            "capture-recovery-plan",
            "remove-secret-bearing-containers",
        ],
        "prohibited": [
            "active-polaris",
            "canonical-catalog-or-warehouse",
            "delete-object-version",
            "delete-marker-removal",
            "bucket-control-change",
            "network-or-volume-removal",
            "automatic-cleanup",
        ],
    }


def _recovery_contract() -> dict[str, object]:
    return {
        "operations": [
            "validate-exact-point-a",
            "operator-canary-put-ordinary-delete",
            "operator-canary-exact-version-promotion",
            "publish-damage-marker-no-replace",
            "ordinary-delete-approved-graph-leaf-to-root",
            "verify-approved-missing-object",
            "promote-exact-approved-source-versions",
            "validate-recovered-point-a",
        ],
        "resume": "restore-only",
        "prohibited": [
            "active-polaris",
            "canonical-catalog-or-warehouse",
            "delete-object-version",
            "delete-marker-removal",
            "bucket-control-change",
            "network-or-volume-removal",
            "automatic-cleanup",
        ],
    }


def prepare_seed_plan(
    *,
    settings: RecoverySettings,
    evidence_root: Path,
    token_factory: TokenFactory = _new_run_id,
    clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    image_inspector: Callable[[str], ImagePin] = _inspect_docker_image,
    docker_fingerprint: Callable[[], str] = _docker_runtime_fingerprint,
) -> dict[str, object]:
    """Generate one mutation-free, exact-hash Seed-A operation plan."""
    scope = _scope(token_factory())
    created_at = clock()
    if created_at.tzinfo is None or created_at.utcoffset() is None:
        raise DrillError("Seed-A plan clock must be timezone-aware")
    created_at = created_at.astimezone(UTC)
    images = {
        name: image_inspector(reference)
        for name, reference in (
            ("postgres", _POSTGRES_IMAGE),
            ("polarisAdmin", _POLARIS_ADMIN_IMAGE),
            ("polaris", _POLARIS_IMAGE),
        )
    }
    docker_sha256 = docker_fingerprint()
    if not _SHA256.fullmatch(docker_sha256):
        raise DrillError("Docker runtime fingerprint is invalid")
    resources = _stack_resources(scope)
    expected_owner = settings.storage_role_arn.split(":", 5)[4]
    scope_manifest = {
        "runId": scope.run_id,
        "prefix": scope.prefix,
        "catalog": scope.catalog,
        "namespace": scope.namespace,
        "table": scope.table,
        "bucket": settings.bucket,
        "region": settings.region,
        "expectedOwner": expected_owner,
    }
    identities = {
        "profile": settings.profile,
        "identitySha256": settings.identity_sha256,
        "storageRoleArn": settings.storage_role_arn,
        "separatePrincipalProof": False,
    }
    stack = {
        "resources": resources,
        "images": {name: pin.as_manifest() for name, pin in images.items()},
        "dockerRuntimeSha256": docker_sha256,
        "secretBindingSha256": _secret_binding(settings, scope.run_id),
        "realm": "POLARIS",
        "database": "polaris",
        "databaseUser": "polaris",
        "clientId": f"recovery-{scope.run_id}",
    }
    runtime = _source_runtime_binding(
        {
            "scope": scope_manifest,
            "identities": identities,
            "stack": stack,
        }
    )
    plan = {
        "schemaVersion": 2,
        "planType": "seed-a",
        "createdAt": created_at.isoformat().replace("+00:00", "Z"),
        "expiresAt": (created_at + _SEED_PLAN_LIFETIME).isoformat().replace("+00:00", "Z"),
        "scope": scope_manifest,
        "identities": identities,
        "stack": stack,
        "runtime": runtime.as_manifest(),
        "contract": _seed_contract(),
    }
    plan_path = evidence_root / scope.run_id / "seed-a.plan.json"
    payload = _canonical_json(plan)
    _atomic_private_write(plan_path, payload)
    return {
        "status": "planned",
        "planType": "seed-a",
        "runId": scope.run_id,
        "plan": str(plan_path),
        "planSha256": hashlib.sha256(payload).hexdigest(),
    }


def _read_exact_private_json(path: Path, expected_sha256: str) -> tuple[dict[str, object], str]:
    if not _SHA256.fullmatch(expected_sha256):
        raise DrillError("approved private plan SHA-256 is invalid")
    try:
        details = path.lstat()
        if (
            not stat.S_ISREG(details.st_mode)
            or stat.S_IMODE(details.st_mode) != 0o600
            or details.st_size > _MAX_PRIVATE_RESPONSE_BYTES
        ):
            raise DrillError("private plan is not a bounded mode-0600 regular file")
        payload = path.read_bytes()
    except DrillError:
        raise
    except OSError as exc:
        raise DrillError("private plan is unavailable") from exc
    actual_sha256 = hashlib.sha256(payload).hexdigest()
    if not hmac.compare_digest(actual_sha256, expected_sha256):
        raise DrillError("private plan does not match the approved SHA-256")
    try:
        value = json.loads(payload)
    except json.JSONDecodeError as exc:
        raise DrillError("private plan is invalid JSON") from exc
    if not isinstance(value, dict):
        raise DrillError("private plan has an unexpected shape")
    return value, actual_sha256


def _image_pin_from_manifest(value: object, *, reference: str) -> ImagePin:
    if not isinstance(value, dict) or set(value) != {
        "reference",
        "imageId",
        "entrypoint",
        "command",
        "environment",
        "user",
        "workingDirectory",
    }:
        raise DrillError("Seed-A image pin has an unexpected shape")
    image_id = value.get("imageId")
    entrypoint = value.get("entrypoint")
    command = value.get("command")
    environment = value.get("environment")
    user = value.get("user")
    working_directory = value.get("workingDirectory")
    if (
        value.get("reference") != reference
        or not isinstance(image_id, str)
        or not re.fullmatch(r"sha256:[0-9a-f]{64}", image_id)
        or not isinstance(entrypoint, list)
        or not all(isinstance(item, str) for item in entrypoint)
        or not isinstance(command, list)
        or not all(isinstance(item, str) for item in command)
        or not isinstance(environment, list)
        or not all(isinstance(item, str) for item in environment)
        or not isinstance(user, str)
        or not isinstance(working_directory, str)
        or not entrypoint + command
    ):
        raise DrillError("Seed-A image pin values are invalid")
    return ImagePin(
        reference,
        image_id,
        tuple(entrypoint),
        tuple(command),
        tuple(environment),
        user,
        working_directory,
    )


def _seed_plan_contract(
    path: Path,
    expected_sha256: str,
    *,
    clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    require_current: bool = True,
    require_runtime_match: bool = True,
) -> tuple[dict[str, object], DrillScope, dict[str, ImagePin], RuntimeBinding, str]:
    plan, actual_sha256 = _read_exact_private_json(path, expected_sha256)
    if (
        set(plan)
        != {
            "schemaVersion",
            "planType",
            "createdAt",
            "expiresAt",
            "scope",
            "identities",
            "stack",
            "runtime",
            "contract",
        }
        or plan.get("schemaVersion") != 2
        or plan.get("planType") != "seed-a"
    ):
        raise DrillError("private Seed-A plan has an unexpected shape")
    raw_scope = plan.get("scope")
    if not isinstance(raw_scope, dict) or set(raw_scope) != {
        "runId",
        "prefix",
        "catalog",
        "namespace",
        "table",
        "bucket",
        "region",
        "expectedOwner",
    }:
        raise DrillError("private Seed-A scope has an unexpected shape")
    run_id = raw_scope.get("runId")
    if not isinstance(run_id, str):
        raise DrillError("private Seed-A run ID is invalid")
    scope = _scope(run_id)
    expected_scope = {
        "runId": scope.run_id,
        "prefix": scope.prefix,
        "catalog": scope.catalog,
        "namespace": scope.namespace,
        "table": scope.table,
        "bucket": raw_scope.get("bucket"),
        "region": raw_scope.get("region"),
        "expectedOwner": raw_scope.get("expectedOwner"),
    }
    if raw_scope != expected_scope:
        raise DrillError("private Seed-A scope is not generated")
    bucket = raw_scope.get("bucket")
    region = raw_scope.get("region")
    owner = raw_scope.get("expectedOwner")
    if (
        not isinstance(bucket, str)
        or not re.fullmatch(r"[a-z0-9][a-z0-9.-]{1,61}[a-z0-9]", bucket)
        or not isinstance(region, str)
        or not re.fullmatch(r"[a-z]{2}(?:-gov)?-[a-z]+-\d", region)
        or not isinstance(owner, str)
        or not re.fullmatch(r"[0-9]{12}", owner)
    ):
        raise DrillError("private Seed-A target values are invalid")
    if path.parent.name != scope.run_id or path.name != "seed-a.plan.json":
        raise DrillError("private Seed-A plan path does not match its run")

    identities = plan.get("identities")
    if not isinstance(identities, dict) or set(identities) != {
        "profile",
        "identitySha256",
        "storageRoleArn",
        "separatePrincipalProof",
    }:
        raise DrillError("private Seed-A identities have an unexpected shape")
    profile = identities.get("profile")
    identity_digest = identities.get("identitySha256")
    storage_role = identities.get("storageRoleArn")
    if (
        not isinstance(profile, str)
        or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.@+-]{0,127}", profile)
        or not isinstance(identity_digest, str)
        or not _SHA256.fullmatch(identity_digest)
        or identities.get("separatePrincipalProof") is not False
        or not isinstance(storage_role, str)
        or not re.fullmatch(
            rf"arn:(?:aws|aws-us-gov):iam::{owner}:role/[A-Za-z0-9+=,.@_/-]+",
            storage_role,
        )
    ):
        raise DrillError("private Seed-A identity values are invalid")

    stack = plan.get("stack")
    if not isinstance(stack, dict) or set(stack) != {
        "resources",
        "images",
        "dockerRuntimeSha256",
        "secretBindingSha256",
        "realm",
        "database",
        "databaseUser",
        "clientId",
    }:
        raise DrillError("private Seed-A stack has an unexpected shape")
    if stack.get("resources") != _stack_resources(scope):
        raise DrillError("private Seed-A resource names are not generated")
    images = stack.get("images")
    if not isinstance(images, dict) or set(images) != {
        "postgres",
        "polarisAdmin",
        "polaris",
    }:
        raise DrillError("private Seed-A image pins are invalid")
    image_pins = {
        "postgres": _image_pin_from_manifest(images["postgres"], reference=_POSTGRES_IMAGE),
        "polarisAdmin": _image_pin_from_manifest(
            images["polarisAdmin"], reference=_POLARIS_ADMIN_IMAGE
        ),
        "polaris": _image_pin_from_manifest(images["polaris"], reference=_POLARIS_IMAGE),
    }
    if (
        not isinstance(stack.get("dockerRuntimeSha256"), str)
        or not _SHA256.fullmatch(stack["dockerRuntimeSha256"])
        or not isinstance(stack.get("secretBindingSha256"), str)
        or not _SHA256.fullmatch(stack["secretBindingSha256"])
        or stack.get("realm") != "POLARIS"
        or stack.get("database") != "polaris"
        or stack.get("databaseUser") != "polaris"
        or stack.get("clientId") != f"recovery-{scope.run_id}"
    ):
        raise DrillError("private Seed-A stack values are invalid")
    if plan.get("contract") != _seed_contract():
        raise DrillError("private Seed-A operation contract is not exact")
    runtime = _runtime_binding_from_manifest(plan.get("runtime"))
    if require_runtime_match:
        current_runtime = _source_runtime_binding(
            {"scope": raw_scope, "identities": identities, "stack": stack}
        )
        if runtime != current_runtime:
            raise DrillError("current runtime does not match the approved Seed-A plan")
    try:
        created_at = datetime.fromisoformat(str(plan.get("createdAt")).replace("Z", "+00:00"))
        expires_at = datetime.fromisoformat(str(plan.get("expiresAt")).replace("Z", "+00:00"))
    except ValueError as exc:
        raise DrillError("private Seed-A timestamps are invalid") from exc
    now = clock()
    if (
        created_at.tzinfo is None
        or expires_at.tzinfo is None
        or now.tzinfo is None
        or expires_at - created_at != _SEED_PLAN_LIFETIME
        or (require_current and not created_at <= now.astimezone(UTC) <= expires_at)
    ):
        raise DrillError("private Seed-A approval window is invalid or expired")
    return plan, scope, image_pins, runtime, actual_sha256


def _settings_match_seed_plan(
    settings: RecoverySettings,
    plan: Mapping[str, object],
    scope: DrillScope,
) -> None:
    raw_scope = plan["scope"]
    identities = plan["identities"]
    stack = plan["stack"]
    if (
        not isinstance(raw_scope, dict)
        or not isinstance(identities, dict)
        or not isinstance(stack, dict)
    ):
        raise DrillError("private Seed-A plan sections are invalid")
    if (
        raw_scope.get("bucket") != settings.bucket
        or raw_scope.get("region") != settings.region
        or raw_scope.get("expectedOwner") != settings.storage_role_arn.split(":", 5)[4]
        or identities
        != {
            "profile": settings.profile,
            "identitySha256": settings.identity_sha256,
            "storageRoleArn": settings.storage_role_arn,
            "separatePrincipalProof": False,
        }
        or stack.get("secretBindingSha256") != _secret_binding(settings, scope.run_id)
    ):
        raise DrillError("private settings do not match the approved Seed-A plan")


def _write_recovery_plan(
    *,
    scope: DrillScope,
    capture: TableCapture,
    evidence_root: Path,
    runtime_binding: RuntimeBinding | None = None,
    parent_seed_sha256: str | None = None,
    stack: Mapping[str, object] | None = None,
    catalog_fingerprint_sha256: str | None = None,
    retained_resources_sha256: str | None = None,
    clock: Callable[[], datetime] = lambda: datetime.now(UTC),
) -> dict[str, object]:
    graph, logical_sha = _validate_capture(scope, capture)
    isolated = parent_seed_sha256 is not None
    if isolated and (
        runtime_binding is None
        or stack is None
        or catalog_fingerprint_sha256 is None
        or retained_resources_sha256 is None
        or not _SHA256.fullmatch(parent_seed_sha256)
        or not _SHA256.fullmatch(catalog_fingerprint_sha256)
        or not _SHA256.fullmatch(retained_resources_sha256)
    ):
        raise DrillError("isolated recovery plan context is incomplete")
    created_at = clock().astimezone(UTC) if isolated else None
    manifest = {
        "schemaVersion": 4 if isolated else (2 if runtime_binding is not None else 1),
        "scope": {
            "runId": scope.run_id,
            "prefix": scope.prefix,
            "catalog": scope.catalog,
            "namespace": scope.namespace,
            "table": scope.table,
        },
        "table": {
            "bucket": capture.bucket,
            "tableUuid": capture.table_uuid,
            "metadataLocation": capture.metadata_location,
            "snapshotId": capture.snapshot_id,
            "schemaSha256": capture.schema_sha256,
            "rowCount": capture.row_count,
            "rowsSha256": capture.rows_sha256,
        },
        "graph": graph,
    }
    if runtime_binding is not None:
        manifest["runtime"] = runtime_binding.as_manifest()
    if isolated:
        assert created_at is not None
        manifest.update(
            {
                "planType": "recovery-a",
                "createdAt": created_at.isoformat().replace("+00:00", "Z"),
                "expiresAt": (created_at + _SEED_PLAN_LIFETIME).isoformat().replace("+00:00", "Z"),
                "parentSeedPlanSha256": parent_seed_sha256,
                "stack": dict(stack or {}),
                "catalogFingerprintSha256": catalog_fingerprint_sha256,
                "retainedResourcesSha256": retained_resources_sha256,
                "contract": _recovery_contract(),
            }
        )
    manifest_path = evidence_root / scope.run_id / "manifest.json"
    payload = _canonical_json(manifest)
    _atomic_private_write(manifest_path, payload)
    digest = hashlib.sha256(payload).hexdigest()
    if isolated:
        return {
            "status": "recovery-planned",
            "planType": "recovery-a",
            "runId": scope.run_id,
            "plan": str(manifest_path),
            "planSha256": digest,
            "logicalGraphSha256": logical_sha,
            "nodeCount": len(capture.nodes),
            "rowCount": capture.row_count,
        }
    return {
        "status": "prepared",
        "runId": scope.run_id,
        "manifest": str(manifest_path),
        "manifestSha256": digest,
        "logicalGraphSha256": logical_sha,
        "nodeCount": len(capture.nodes),
        "rowCount": capture.row_count,
    }


def _verify_pinned_docker(
    plan: Mapping[str, object],
    image_pins: Mapping[str, ImagePin],
    *,
    image_inspector: Callable[[str], ImagePin] = _inspect_docker_image,
    docker_fingerprint: Callable[[], str] = _docker_runtime_fingerprint,
) -> None:
    for pin in image_pins.values():
        if image_inspector(pin.reference) != pin:
            raise DrillError("Docker image differs from the approved Seed-A pin")
    stack = plan.get("stack")
    if not isinstance(stack, dict) or docker_fingerprint() != stack.get("dockerRuntimeSha256"):
        raise DrillError("Docker runtime differs from the approved Seed-A pin")


def _wait_for_polaris(
    config: RuntimeConfig,
    *,
    sleep: Callable[[float], None] = time.sleep,
) -> PolarisGateway:
    gateway = PolarisGateway(config=config)
    for _attempt in range(120):
        try:
            gateway._token()
        except DrillError:
            sleep(0.25)
        else:
            return gateway
    raise DrillError("isolated Polaris did not become ready")


def _run_seed_capability_canary(
    *,
    scope: DrillScope,
    bucket: str,
    store: AwsCliVersionStore,
    runtime_binding: RuntimeBinding,
) -> GraphNode:
    operations = LiveWarehouseDrillOperations(
        scope=scope,
        bucket=bucket,
        gateway=object(),
        writer_store=store,
        recovery_store=store,
        runtime_binding=runtime_binding,
    )
    return operations._verify_capability_canary()


def _validate_seed_capability_canary(
    *,
    scope: DrillScope,
    bucket: str,
    store: AwsCliVersionStore,
    runtime_binding: RuntimeBinding,
    node: GraphNode,
) -> None:
    operations = LiveWarehouseDrillOperations(
        scope=scope,
        bucket=bucket,
        gateway=object(),
        writer_store=store,
        recovery_store=store,
        runtime_binding=runtime_binding,
    )
    operations._validate_preverified_canary(node)


def _validate_stage1_prefix(
    store: AwsCliVersionStore,
    canary: GraphNode,
    capture: TableCapture,
) -> None:
    graph_keys = [node.key for node in capture.nodes]
    expected = {canary.key, *graph_keys}
    if (
        len(graph_keys) != len(set(graph_keys))
        or canary.key in graph_keys
        or len(expected) > _MAX_STAGE1_OBJECTS
    ):
        raise DrillError("completed Stage-1 prefix exceeds the object-count safety limit")
    if store.prefix_keys() != expected:
        raise DrillError("completed Stage-1 prefix does not exactly match the captured graph")


def execute_seed_plan(
    *,
    settings: RecoverySettings,
    plan_path: Path,
    expected_sha256: str,
    clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    image_inspector: Callable[[str], ImagePin] = _inspect_docker_image,
    docker_fingerprint: Callable[[], str] = _docker_runtime_fingerprint,
    live_aws_factory: Callable[..., VerifiedAwsContext] | None = None,
    capability_checker: Callable[..., GraphNode] | None = None,
    stack_factory: Callable[..., IsolatedStage1Stack] = IsolatedStage1Stack,
    operations_factory: Callable[..., LiveWarehouseDrillOperations] | None = None,
    credential_exporter: Callable[..., AwsCredentials] = _export_aws_credentials,
    gateway_waiter: Callable[[RuntimeConfig], PolarisGateway] = _wait_for_polaris,
) -> dict[str, object]:
    """Execute one exact approved Seed-A plan and emit a separate Recovery-A plan."""
    plan, scope, image_pins, runtime_binding, plan_sha256 = _seed_stage(
        "seed-plan-validation",
        lambda: _seed_plan_contract(
            plan_path,
            expected_sha256,
            clock=clock,
        ),
    )
    _seed_stage(
        "seed-settings-validation",
        lambda: _settings_match_seed_plan(settings, plan, scope),
    )
    _seed_stage(
        "docker-pin-validation",
        lambda: _verify_pinned_docker(
            plan,
            image_pins,
            image_inspector=image_inspector,
            docker_fingerprint=docker_fingerprint,
        ),
    )
    live_aws = live_aws_factory or _verify_live_aws
    aws = _seed_stage(
        "aws-preflight",
        lambda: live_aws(
            settings=settings,
            scope=scope,
            temp_root=plan_path.parent,
            credential_exporter=credential_exporter,
        ),
    )
    _seed_stage("s3-empty-prefix", aws.store.verify_empty_prefix)
    check_capability = capability_checker or _run_seed_capability_canary
    capability_canary = _seed_stage(
        "capability-canary",
        lambda: check_capability(
            scope=scope,
            bucket=settings.bucket,
            store=aws.store,
            runtime_binding=runtime_binding,
        ),
    )
    if not isinstance(capability_canary, GraphNode):
        raise SeedStageError("canary-residual-validation")
    _seed_stage(
        "canary-residual-validation",
        lambda: _validate_seed_capability_canary(
            scope=scope,
            bucket=settings.bucket,
            store=aws.store,
            runtime_binding=runtime_binding,
            node=capability_canary,
        ),
    )
    exported = aws.credentials
    credentials = _derive_run_credentials(settings, scope)
    stack_manifest = plan.get("stack")
    if not isinstance(stack_manifest, dict):
        raise DrillError("private Seed-A stack is invalid")
    resources = stack_manifest.get("resources")
    if not isinstance(resources, dict):
        raise DrillError("private Seed-A resources are invalid")
    stack = _seed_stage(
        "stack-construction",
        lambda: stack_factory(
            scope=scope,
            resources=resources,
            images=image_pins,
            seed_plan_sha256=plan_sha256,
            execution_plan_sha256=plan_sha256,
        ),
    )
    capture: TableCapture | None = None
    catalog_fingerprint: str | None = None
    retained_resources_sha256: str | None = None
    _seed_stage("seed-resource-creation", stack.create_seed_resources)
    try:
        polaris_url = _seed_stage(
            "stack-start",
            lambda: stack.start(
                credentials,
                exported,
                bootstrap=True,
                region=settings.region,
            ),
        )
        config = RuntimeConfig.isolated(
            settings=settings,
            polaris_url=polaris_url,
            credentials=credentials,
        )
        gateway = _seed_stage("polaris-readiness", lambda: gateway_waiter(config))
        make_operations = operations_factory or _isolated_operations
        operations = _seed_stage(
            "operation-construction",
            lambda: make_operations(
                scope=scope,
                config=config,
                aws=aws,
                runtime_binding=runtime_binding,
            ),
        )
        operations.gateway = gateway
        capture = _seed_stage(
            "point-a-preparation",
            lambda: operations.prepare(
                scope,
                _DETERMINISTIC_ROWS,
                capability_canary=capability_canary,
            ),
        )
        _seed_stage(
            "stage1-prefix-validation",
            lambda: _validate_stage1_prefix(aws.store, capability_canary, capture),
        )
        catalog_fingerprint = _seed_stage(
            "catalog-fingerprint",
            lambda: gateway.catalog_fingerprint(scope),
        )
    finally:
        _seed_stage("secret-container-containment", stack.close)
    retained_resources_sha256 = _seed_stage(
        "retained-resource-validation",
        stack.retained_resources_sha256,
    )
    if capture is None or catalog_fingerprint is None or retained_resources_sha256 is None:
        raise DrillError("Seed-A did not produce a complete recovery contract")
    return _seed_stage(
        "recovery-plan-publication",
        lambda: _write_recovery_plan(
            scope=scope,
            capture=capture,
            evidence_root=plan_path.parent.parent,
            runtime_binding=runtime_binding,
            parent_seed_sha256=plan_sha256,
            stack=stack_manifest,
            catalog_fingerprint_sha256=catalog_fingerprint,
            retained_resources_sha256=retained_resources_sha256,
            clock=clock,
        ),
    )


def execute_recovery_plan(
    *,
    settings: RecoverySettings,
    plan_path: Path,
    expected_sha256: str,
    clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    image_inspector: Callable[[str], ImagePin] = _inspect_docker_image,
    docker_fingerprint: Callable[[], str] = _docker_runtime_fingerprint,
    live_aws_factory: Callable[..., VerifiedAwsContext] | None = None,
    stack_factory: Callable[..., IsolatedStage1Stack] = IsolatedStage1Stack,
    operations_factory: Callable[..., LiveWarehouseDrillOperations] | None = None,
    credential_exporter: Callable[..., AwsCredentials] = _export_aws_credentials,
    gateway_waiter: Callable[[RuntimeConfig], PolarisGateway] = _wait_for_polaris,
) -> dict[str, object]:
    """Execute one exact Recovery-A plan against its retained isolated stack."""
    manifest, scope, recovery_capture, plan_sha256, runtime_binding = _manifest_contract(
        plan_path,
        expected_sha256,
        clock=clock,
        allow_expired=True,
    )
    if manifest.get("schemaVersion") != 4 or runtime_binding is None:
        raise DrillError("live recovery requires an isolated Recovery-A plan")
    parent_sha256 = manifest.get("parentSeedPlanSha256")
    if not isinstance(parent_sha256, str):
        raise DrillError("Recovery-A parent Seed-A hash is invalid")
    seed_path = plan_path.parent / "seed-a.plan.json"
    seed_plan, seed_scope, image_pins, seed_runtime, verified_parent_sha256 = _seed_plan_contract(
        seed_path,
        parent_sha256,
        clock=clock,
        require_current=False,
    )
    if (
        seed_scope != scope
        or verified_parent_sha256 != parent_sha256
        or manifest.get("stack") != seed_plan.get("stack")
        or runtime_binding != seed_runtime
    ):
        raise DrillError("Recovery-A plan does not match its approved Seed-A parent")
    _settings_match_seed_plan(settings, seed_plan, scope)
    _verify_pinned_docker(
        seed_plan,
        image_pins,
        image_inspector=image_inspector,
        docker_fingerprint=docker_fingerprint,
    )
    stack_manifest = manifest.get("stack")
    resources = stack_manifest.get("resources") if isinstance(stack_manifest, dict) else None
    if not isinstance(resources, dict):
        raise DrillError("Recovery-A retained resources are invalid")
    stack = stack_factory(
        scope=scope,
        resources=resources,
        images=image_pins,
        seed_plan_sha256=parent_sha256,
        execution_plan_sha256=plan_sha256,
    )
    # Exact owned remnants can contain expired temporary credentials. Contain
    # them before an expiry rejection or AWS/profile dependency can delay re-entry.
    retained_sha256 = manifest.get("retainedResourcesSha256")
    if not isinstance(retained_sha256, str):
        raise DrillError("Recovery-A retained resource fingerprint is invalid")
    _recovery_stage(
        "retained-resource-validation",
        lambda: stack.use_retained_resources(retained_sha256),
    )
    if _recovery_plan_expired(manifest, clock=clock):
        _read_damage_marker(
            plan_path.parent / "damage-started.json",
            scope=scope,
            manifest_sha256=plan_sha256,
            nodes=sorted(
                recovery_capture.nodes,
                key=lambda item: (-item.depth, item.key),
            ),
        )
    live_aws = live_aws_factory or _verify_live_aws
    aws = _recovery_stage(
        "aws-preflight",
        lambda: live_aws(
            settings=settings,
            scope=scope,
            temp_root=plan_path.parent,
            credential_exporter=credential_exporter,
        ),
    )
    exported = aws.credentials
    credentials = _derive_run_credentials(settings, scope)
    result: dict[str, object] | None = None
    primary_error: BaseException | None = None
    containment_error: BaseException | None = None
    try:
        polaris_url = _recovery_stage(
            "stack-start",
            lambda: stack.start(
                credentials,
                exported,
                bootstrap=False,
                region=settings.region,
            ),
        )
        config = RuntimeConfig.isolated(
            settings=settings,
            polaris_url=polaris_url,
            credentials=credentials,
        )
        gateway = _recovery_stage("polaris-readiness", lambda: gateway_waiter(config))
        expected_catalog = manifest.get("catalogFingerprintSha256")
        actual_catalog = _recovery_stage(
            "catalog-fingerprint", lambda: gateway.catalog_fingerprint(scope)
        )
        if actual_catalog != expected_catalog:
            raise RecoveryStageError("catalog-fingerprint", error_kind="mismatch")
        make_operations = operations_factory or _isolated_operations
        operations = _recovery_stage(
            "operation-construction",
            lambda: make_operations(
                scope=scope,
                config=config,
                aws=aws,
                runtime_binding=runtime_binding,
            ),
        )
        operations.gateway = gateway
        result = execute_drill(
            operations=operations,
            manifest_path=plan_path,
            expected_sha256=plan_sha256,
            clock=clock,
            pre_damage_check=operations._verify_capability_canary,
        )
    except BaseException as exc:
        primary_error = exc
    try:
        _recovery_stage("containment", stack.close)
    except BaseException as exc:
        containment_error = exc

    marker_path = plan_path.parent / "damage-started.json"
    evidence_error: BaseException | None = None
    try:
        marker = _read_damage_marker(
            marker_path,
            scope=scope,
            manifest_sha256=plan_sha256,
            nodes=sorted(
                recovery_capture.nodes,
                key=lambda item: (-item.depth, item.key),
            ),
        )
    except DrillError as exc:
        marker = None
        if primary_error is None:
            evidence_error = RecoveryStageError("damage-journal", error_kind="unavailable")
            evidence_error.__cause__ = exc
    if marker is not None and marker.get("schemaVersion") == 2:
        try:
            _set_damage_milestone(
                marker,
                marker_path,
                "containment",
                "failed" if containment_error is not None else "passed",
            )
        except BaseException as exc:
            evidence_error = (
                exc
                if isinstance(exc, RecoveryStageError)
                else RecoveryStageError(
                    "damage-journal",
                    error_kind=(
                        _exception_error_kind(exc) if isinstance(exc, Exception) else "unclassified"
                    ),
                )
            )

    effective_primary = primary_error or evidence_error
    if effective_primary is not None:
        if containment_error is not None and isinstance(effective_primary, Exception):
            containment_kind = (
                containment_error.error_kind
                if isinstance(containment_error, RecoveryStageError)
                else _exception_error_kind(containment_error)
                if isinstance(containment_error, Exception)
                else "unclassified"
            )
            if isinstance(effective_primary, RecoveryStageError):
                raise RecoveryStageError(
                    effective_primary.stage,
                    error_kind=effective_primary.error_kind,
                    containment_error_kind=containment_kind,
                ) from effective_primary
            raise RecoveryStageError(
                "preflight",
                error_kind=_exception_error_kind(effective_primary),
                containment_error_kind=containment_kind,
            ) from effective_primary
        raise effective_primary
    if containment_error is not None:
        raise containment_error
    if result is None or marker is None or marker.get("schemaVersion") != 2:
        raise DrillError("Recovery-A did not produce complete durable evidence")
    milestones = _damage_milestones(marker)
    if milestones != {
        "deletes": "complete",
        "breakProof": "passed",
        "restoration": "complete",
        "finalValidation": "passed",
        "containment": "passed",
    }:
        raise DrillError("Recovery-A durable evidence is incomplete")
    status = result.get("status")
    if status == "recovery-validated":
        result["status"] = "pass"
    elif status == "recovery-validated-after-interruption":
        result["status"] = "recovered-after-interruption"
    else:
        raise DrillError("Recovery-A validation result is invalid")
    return result


def prepare_drill(
    *,
    operations: WarehouseDrillOperations,
    evidence_root: Path,
    token_factory: TokenFactory = _new_run_id,
    runtime_binding: RuntimeBinding | None = None,
) -> dict[str, object]:
    """Create a point-A fixture and write its manifest for deterministic tests."""
    scope = _scope(token_factory())
    capture = operations.prepare(scope, _DETERMINISTIC_ROWS)
    return _write_recovery_plan(
        scope=scope,
        capture=capture,
        evidence_root=evidence_root,
        runtime_binding=runtime_binding,
    )


def _manifest_contract(
    manifest_path: Path,
    expected_sha256: str,
    *,
    clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    allow_expired: bool = False,
) -> tuple[
    dict[str, object],
    DrillScope,
    TableCapture,
    str,
    RuntimeBinding | None,
]:
    if not _SHA256.fullmatch(expected_sha256):
        raise DrillError("approved manifest SHA-256 is invalid")
    try:
        details = manifest_path.lstat()
        if (
            not stat.S_ISREG(details.st_mode)
            or stat.S_IMODE(details.st_mode) != 0o600
            or details.st_size > _MAX_PRIVATE_RESPONSE_BYTES
        ):
            message = (
                "private drill manifest exceeds the size limit"
                if details.st_size > _MAX_PRIVATE_RESPONSE_BYTES
                else "private drill manifest is not a mode-0600 regular file"
            )
            raise DrillError(message)
        payload = manifest_path.read_bytes()
    except DrillError:
        raise
    except OSError as exc:
        raise DrillError("private drill manifest is unavailable") from exc
    actual_sha = hashlib.sha256(payload).hexdigest()
    if not hmac.compare_digest(actual_sha, expected_sha256):
        raise DrillError("private drill manifest does not match the approved SHA-256")
    try:
        raw = json.loads(payload)
    except json.JSONDecodeError as exc:
        raise DrillError("private drill manifest is invalid JSON") from exc
    if not isinstance(raw, dict):
        raise DrillError("private drill manifest has an unexpected shape")
    schema_version = raw.get("schemaVersion")
    expected_keys = {"schemaVersion", "scope", "table", "graph"}
    if schema_version == 4:
        expected_keys.update(
            {
                "runtime",
                "planType",
                "createdAt",
                "expiresAt",
                "parentSeedPlanSha256",
                "stack",
                "catalogFingerprintSha256",
                "retainedResourcesSha256",
                "contract",
            }
        )
    elif schema_version == 2:
        expected_keys.add("runtime")
    elif schema_version != 1:
        raise DrillError("private drill manifest schema is unsupported")
    if set(raw) != expected_keys:
        raise DrillError("private drill manifest has an unexpected shape")
    runtime_binding = (
        _runtime_binding_from_manifest(raw.get("runtime")) if schema_version in {2, 4} else None
    )
    if schema_version == 4:
        parent_sha256 = raw.get("parentSeedPlanSha256")
        catalog_sha256 = raw.get("catalogFingerprintSha256")
        retained_sha256 = raw.get("retainedResourcesSha256")
        if (
            raw.get("planType") != "recovery-a"
            or not isinstance(parent_sha256, str)
            or not _SHA256.fullmatch(parent_sha256)
            or not isinstance(catalog_sha256, str)
            or not _SHA256.fullmatch(catalog_sha256)
            or not isinstance(retained_sha256, str)
            or not _SHA256.fullmatch(retained_sha256)
            or not isinstance(raw.get("stack"), dict)
            or raw.get("contract") != _recovery_contract()
        ):
            raise DrillError("private Recovery-A plan context is invalid")
        try:
            created_at = datetime.fromisoformat(str(raw.get("createdAt")).replace("Z", "+00:00"))
            expires_at = datetime.fromisoformat(str(raw.get("expiresAt")).replace("Z", "+00:00"))
        except ValueError as exc:
            raise DrillError("private Recovery-A timestamps are invalid") from exc
        now = clock().astimezone(UTC)
        if (
            created_at.tzinfo is None
            or expires_at.tzinfo is None
            or expires_at - created_at != _SEED_PLAN_LIFETIME
            or now < created_at
            or (now > expires_at and not allow_expired)
        ):
            raise DrillError("private Recovery-A approval window is invalid or expired")

    raw_scope = raw.get("scope")
    raw_table = raw.get("table")
    raw_graph = raw.get("graph")
    if (
        not isinstance(raw_scope, dict)
        or not isinstance(raw_table, dict)
        or not isinstance(raw_graph, dict)
    ):
        raise DrillError("private drill manifest sections are invalid")
    run_id = raw_scope.get("runId")
    if not isinstance(run_id, str):
        raise DrillError("private drill run ID is missing")
    scope = _scope(run_id)
    if raw_scope != {
        "runId": scope.run_id,
        "prefix": scope.prefix,
        "catalog": scope.catalog,
        "namespace": scope.namespace,
        "table": scope.table,
    }:
        raise DrillError("private drill scope is not the generated run scope")
    if manifest_path.parent.name != run_id or manifest_path.name != "manifest.json":
        raise DrillError("private drill manifest path does not match its run")

    raw_nodes = raw_graph.get("nodes")
    if not isinstance(raw_nodes, list):
        raise DrillError("private drill graph nodes are invalid")
    nodes: list[GraphNode] = []
    try:
        for item in raw_nodes:
            if not isinstance(item, dict) or set(item) != {
                "key",
                "kind",
                "sourceVersionId",
                "etag",
                "size",
                "sha256",
                "depth",
            }:
                raise DrillError("private drill graph node has an unexpected shape")
            values = tuple(item[key] for key in item)
            if (
                not isinstance(item["key"], str)
                or not isinstance(item["kind"], str)
                or not isinstance(item["sourceVersionId"], str)
                or not isinstance(item["etag"], str)
                or isinstance(item["size"], bool)
                or not isinstance(item["size"], int)
                or not isinstance(item["sha256"], str)
                or isinstance(item["depth"], bool)
                or not isinstance(item["depth"], int)
            ):
                raise DrillError("private drill graph node values are invalid")
            del values
            nodes.append(
                GraphNode(
                    key=item["key"],
                    kind=item["kind"],
                    source_version_id=item["sourceVersionId"],
                    etag=item["etag"],
                    size=item["size"],
                    sha256=item["sha256"],
                    depth=item["depth"],
                )
            )
    except KeyError as exc:
        raise DrillError("private drill graph node is incomplete") from exc

    expected_table_keys = {
        "bucket",
        "tableUuid",
        "metadataLocation",
        "snapshotId",
        "schemaSha256",
        "rowCount",
        "rowsSha256",
    }
    if set(raw_table) != expected_table_keys:
        raise DrillError("private drill table contract has an unexpected shape")
    try:
        capture = TableCapture(
            bucket=str(raw_table["bucket"]),
            table_uuid=str(raw_table["tableUuid"]),
            metadata_location=str(raw_table["metadataLocation"]),
            snapshot_id=int(raw_table["snapshotId"]),
            schema_sha256=str(raw_table["schemaSha256"]),
            row_count=int(raw_table["rowCount"]),
            rows_sha256=str(raw_table["rowsSha256"]),
            nodes=tuple(nodes),
        )
    except (TypeError, ValueError) as exc:
        raise DrillError("private drill table contract values are invalid") from exc
    graph, logical_sha = _validate_capture(scope, capture)
    if raw_graph != graph:
        raise DrillError("private drill logical graph does not match its contents")
    return raw, scope, capture, actual_sha, runtime_binding


def _recovery_plan_expired(
    manifest: Mapping[str, object],
    *,
    clock: Callable[[], datetime] = lambda: datetime.now(UTC),
) -> bool:
    if manifest.get("schemaVersion") != 4:
        return False
    try:
        expires_at = datetime.fromisoformat(str(manifest.get("expiresAt")).replace("Z", "+00:00"))
    except ValueError as exc:
        raise DrillError("private Recovery-A expiry is invalid") from exc
    return clock().astimezone(UTC) > expires_at


def _matches_content(node: GraphNode, state: ObjectState) -> bool:
    return (
        state.exists
        and not state.delete_marker
        and state.size == node.size
        and state.sha256 == node.sha256
    )


def _initial_damage_marker(
    *, scope: DrillScope, manifest_sha256: str, nodes: Sequence[GraphNode]
) -> dict[str, object]:
    return {
        "schemaVersion": 2,
        "manifestSha256": manifest_sha256,
        "runId": scope.run_id,
        "milestones": {
            "deletes": "pending",
            "breakProof": "pending",
            "restoration": "pending",
            "finalValidation": "pending",
            "containment": "pending",
        },
        "nodes": [
            {
                "key": node.key,
                "sourceVersionId": node.source_version_id,
                "phase": "pending",
                "deleteMarkerVersionId": None,
                "promotedVersionId": None,
            }
            for node in nodes
        ],
    }


def _damage_milestones(marker: Mapping[str, object]) -> dict[str, str]:
    raw = marker.get("milestones")
    allowed = {
        "deletes": {"pending", "complete", "failed"},
        "breakProof": {"pending", "passed", "failed"},
        "restoration": {"pending", "complete", "failed"},
        "finalValidation": {"pending", "passed", "failed"},
        "containment": {"pending", "passed", "failed"},
    }
    if not isinstance(raw, dict) or set(raw) != set(allowed):
        raise DrillError("damage marker milestones have an unexpected shape")
    for name, values in allowed.items():
        if raw.get(name) not in values:
            raise DrillError("damage marker milestone is invalid")
    return raw


def _set_damage_milestone(
    marker: dict[str, object],
    path: Path,
    name: str,
    value: str,
) -> None:
    milestones = _damage_milestones(marker)
    current = milestones.get(name)
    allowed_transitions = {
        "deletes": {"pending": {"complete", "failed"}},
        "breakProof": {"pending": {"passed", "failed"}},
        "restoration": {
            "pending": {"complete", "failed"},
            "failed": {"complete"},
        },
        "finalValidation": {
            "pending": {"passed", "failed"},
            "failed": {"passed"},
        },
        "containment": {
            "pending": {"passed", "failed"},
            "failed": {"passed"},
        },
    }
    if current == value:
        return
    if value not in allowed_transitions.get(name, {}).get(current, set()):
        raise DrillError("damage marker milestone transition is invalid")
    updated_milestones = dict(milestones)
    updated_milestones[name] = value
    updated_marker = dict(marker)
    updated_marker["milestones"] = updated_milestones
    _persist_damage_marker(path, updated_marker)
    marker["milestones"] = updated_milestones


def _damage_entries(
    marker: Mapping[str, object], nodes: Sequence[GraphNode]
) -> dict[str, dict[str, object]]:
    raw_nodes = marker.get("nodes")
    if not isinstance(raw_nodes, list) or len(raw_nodes) != len(nodes):
        raise DrillError("damage marker graph does not match the approved manifest")
    entries: dict[str, dict[str, object]] = {}
    for raw, node in zip(raw_nodes, nodes, strict=True):
        if not isinstance(raw, dict) or set(raw) != {
            "key",
            "sourceVersionId",
            "phase",
            "deleteMarkerVersionId",
            "promotedVersionId",
        }:
            raise DrillError("damage marker node has an unexpected shape")
        if raw.get("key") != node.key or raw.get("sourceVersionId") != node.source_version_id:
            raise DrillError("damage marker node does not match the approved manifest")
        phase = raw.get("phase")
        delete_marker = raw.get("deleteMarkerVersionId")
        promoted = raw.get("promotedVersionId")
        if phase not in {
            "pending",
            "delete-intent",
            "deleted",
            "promotion-intent",
            "promoted",
        }:
            raise DrillError("damage marker node phase is invalid")
        if delete_marker is not None and not isinstance(delete_marker, str):
            raise DrillError("damage marker delete version is invalid")
        if promoted is not None and not isinstance(promoted, str):
            raise DrillError("damage marker promoted version is invalid")
        if phase in {"pending", "delete-intent"} and (
            delete_marker is not None or promoted is not None
        ):
            raise DrillError("damage marker pending node has unexpected results")
        if phase == "deleted" and (delete_marker is None or promoted is not None):
            raise DrillError("damage marker deleted node is incomplete")
        if phase == "promotion-intent" and promoted is not None:
            raise DrillError("damage marker promotion intent has an unexpected result")
        if phase == "promoted" and promoted is None:
            raise DrillError("damage marker promoted node is incomplete")
        entries[node.key] = raw
    return entries


def _read_damage_marker(
    path: Path,
    *,
    scope: DrillScope,
    manifest_sha256: str,
    nodes: Sequence[GraphNode],
) -> dict[str, object]:
    try:
        details = path.lstat()
        if (
            not stat.S_ISREG(details.st_mode)
            or stat.S_IMODE(details.st_mode) != 0o600
            or details.st_size > _MAX_PRIVATE_RESPONSE_BYTES
        ):
            raise DrillError("damage marker is not a bounded mode-0600 regular file")
        marker = json.loads(path.read_bytes())
    except DrillError:
        raise
    except (OSError, json.JSONDecodeError) as exc:
        raise DrillError("damage marker is unreadable") from exc
    if not isinstance(marker, dict):
        raise DrillError("damage marker has an unexpected shape")
    schema_version = marker.get("schemaVersion")
    expected_keys = {"schemaVersion", "manifestSha256", "runId", "nodes"}
    if schema_version == 2:
        expected_keys.add("milestones")
    elif schema_version != 1:
        raise DrillError("damage marker schema is unsupported")
    if set(marker) != expected_keys:
        raise DrillError("damage marker has an unexpected shape")
    if marker.get("manifestSha256") != manifest_sha256 or marker.get("runId") != scope.run_id:
        raise DrillError("damage marker does not match the approved manifest")
    _damage_entries(marker, nodes)
    if schema_version == 2:
        _damage_milestones(marker)
    return marker


def _persist_damage_marker(path: Path, marker: Mapping[str, object]) -> None:
    _atomic_private_replace(path, _canonical_json(marker))


def _restore_damaged(
    operations: WarehouseDrillOperations,
    nodes: Sequence[GraphNode],
    marker: dict[str, object],
    marker_path: Path,
) -> None:
    ordered = sorted(nodes, key=lambda item: (-item.depth, item.key))
    entries = _damage_entries(marker, ordered)
    for node in ordered:
        entry = entries[node.key]
        phase = entry["phase"]
        state = operations.current_state(node)
        if phase == "pending":
            if _matches_content(node, state) and state.version_id == node.source_version_id:
                continue
            raise DrillError("an untouched graph key has an unknown current version")
        if phase == "promoted":
            if _matches_content(node, state) and state.version_id == entry["promotedVersionId"]:
                continue
            raise DrillError("a promoted graph key has an unknown current version")
        if phase == "promotion-intent" and _matches_content(node, state):
            if not state.version_id or state.version_id == node.source_version_id:
                raise DrillError("a promotion intent has an ambiguous current version")
            entry["phase"] = "promoted"
            entry["promotedVersionId"] = state.version_id
            _persist_damage_marker(marker_path, marker)
            continue
        if phase == "delete-intent" and (
            _matches_content(node, state) and state.version_id == node.source_version_id
        ):
            continue
        if state.exists or not state.delete_marker:
            raise DrillError("a damaged graph key has an unknown current version")
        expected_marker = entry["deleteMarkerVersionId"]
        if expected_marker is not None and state.version_id != expected_marker:
            raise DrillError("a damaged graph key has an unknown delete marker")
        entry["phase"] = "promotion-intent"
        _persist_damage_marker(marker_path, marker)
        restored = operations.restore(node)
        if (
            not _matches_content(node, restored)
            or not restored.version_id
            or restored.version_id == node.source_version_id
        ):
            raise DrillError("a graph key was not restored as a verified new current version")
        entry["phase"] = "promoted"
        entry["promotedVersionId"] = restored.version_id
        _persist_damage_marker(marker_path, marker)


def _validate_result(result: ValidationResult, capture: TableCapture, logical_sha: str) -> None:
    if result != ValidationResult(
        table_uuid=capture.table_uuid,
        metadata_location=capture.metadata_location,
        snapshot_id=capture.snapshot_id,
        logical_graph_sha256=logical_sha,
        row_count=capture.row_count,
        rows_sha256=capture.rows_sha256,
    ):
        raise DrillError("restored table does not match the approved validation contract")


def execute_drill(
    *,
    operations: WarehouseDrillOperations,
    manifest_path: Path,
    expected_sha256: str,
    clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    pre_damage_check: Callable[[], None] | None = None,
) -> dict[str, object]:
    """Damage and recover exactly the approved disposable graph, or resume restoration."""
    manifest, scope, capture, manifest_sha, _runtime = _manifest_contract(
        manifest_path,
        expected_sha256,
        clock=clock,
        allow_expired=True,
    )
    marker_path = manifest_path.parent / "damage-started.json"
    ordered = sorted(capture.nodes, key=lambda item: (-item.depth, item.key))
    raw_graph = manifest.get("graph")
    logical_sha = raw_graph.get("logicalSha256") if isinstance(raw_graph, dict) else None
    if not isinstance(logical_sha, str):
        raise DrillError("private drill logical graph digest is invalid")
    try:
        marker_path.lstat()
    except FileNotFoundError:
        resuming = False
    except OSError as exc:
        raise DrillError("damage marker path is unavailable") from exc
    else:
        resuming = True

    if _recovery_plan_expired(manifest, clock=clock) and not resuming:
        raise DrillError("expired Recovery-A plan cannot begin damage")
    if resuming:
        marker = _read_damage_marker(
            marker_path,
            scope=scope,
            manifest_sha256=manifest_sha,
            nodes=ordered,
        )
        if marker.get("schemaVersion") == 1:
            _restore_damaged(operations, ordered, marker, marker_path)
            raise RecoveryStageError("legacy-evidence", error_kind="inconclusive")
        milestones = _damage_milestones(marker)
        try:
            _restore_damaged(operations, ordered, marker, marker_path)
        except BaseException as restore_exc:
            try:
                _set_damage_milestone(marker, marker_path, "restoration", "failed")
            except BaseException:
                pass
            error_kind = (
                _exception_error_kind(restore_exc)
                if isinstance(restore_exc, Exception)
                else "unclassified"
            )
            raise RecoveryStageError("restoration", error_kind=error_kind) from restore_exc
        try:
            _set_damage_milestone(marker, marker_path, "restoration", "complete")
        except BaseException as journal_exc:
            error_kind = (
                _exception_error_kind(journal_exc)
                if isinstance(journal_exc, Exception)
                else "unclassified"
            )
            raise RecoveryStageError("damage-journal", error_kind=error_kind) from journal_exc
        if milestones["breakProof"] != "passed":
            raise RecoveryStageError("break-proof", error_kind="inconclusive")
    else:

        def validate_point_a() -> None:
            for node in ordered:
                state = operations.current_state(node)
                if not _matches_content(node, state) or state.version_id != node.source_version_id:
                    raise DrillError("graph changed after preparation; damage refused")
            _validate_result(operations.validate(manifest), capture, logical_sha)

        _recovery_stage("point-a-validation", validate_point_a)
        if pre_damage_check is not None:
            _recovery_stage("capability-canary", pre_damage_check)
        marker = _initial_damage_marker(
            scope=scope,
            manifest_sha256=manifest_sha,
            nodes=ordered,
        )
        _recovery_stage(
            "damage-journal",
            lambda: _atomic_private_write(marker_path, _canonical_json(marker)),
        )
        entries = _damage_entries(marker, ordered)

        def stage_error(stage: str, error: BaseException) -> RecoveryStageError:
            if isinstance(error, RecoveryStageError):
                return error
            error_kind = (
                _exception_error_kind(error) if isinstance(error, Exception) else "unclassified"
            )
            return RecoveryStageError(stage, error_kind=error_kind)

        def mark_restoration_failed() -> None:
            try:
                _set_damage_milestone(marker, marker_path, "restoration", "failed")
            except BaseException:
                pass

        def compensate_and_raise(primary: RecoveryStageError) -> None:
            try:
                _restore_damaged(operations, ordered, marker, marker_path)
            except BaseException as restore_exc:
                mark_restoration_failed()
                raise stage_error("restoration", restore_exc) from restore_exc
            try:
                _set_damage_milestone(marker, marker_path, "restoration", "complete")
            except BaseException as journal_exc:
                raise stage_error("damage-journal", journal_exc) from journal_exc
            raise primary

        try:
            for node in ordered:
                current = _recovery_stage(
                    "delete", lambda node=node: operations.current_state(node)
                )
                if (
                    not _matches_content(node, current)
                    or current.version_id != node.source_version_id
                ):
                    raise RecoveryStageError("delete", error_kind="graph-changed")
                entry = entries[node.key]
                entry["phase"] = "delete-intent"
                _recovery_stage(
                    "damage-journal", lambda: _persist_damage_marker(marker_path, marker)
                )
                deleted = _recovery_stage(
                    "delete", lambda node=node: operations.delete_current(node)
                )
                if not deleted.delete_marker or not deleted.version_id:
                    raise RecoveryStageError("delete", error_kind="invalid-delete-marker")
                observed = _recovery_stage(
                    "delete", lambda node=node: operations.current_state(node)
                )
                if (
                    observed.exists
                    or not observed.delete_marker
                    or observed.version_id != deleted.version_id
                ):
                    raise RecoveryStageError("delete", error_kind="delete-readback-mismatch")
                entry["phase"] = "deleted"
                entry["deleteMarkerVersionId"] = deleted.version_id
                _recovery_stage(
                    "damage-journal", lambda: _persist_damage_marker(marker_path, marker)
                )
        except BaseException as exc:
            primary = stage_error("delete", exc)
            if _damage_milestones(marker)["deletes"] == "pending":
                try:
                    _set_damage_milestone(marker, marker_path, "deletes", "failed")
                except BaseException as journal_exc:
                    primary = stage_error("damage-journal", journal_exc)
            compensate_and_raise(primary)

        try:
            _set_damage_milestone(marker, marker_path, "deletes", "complete")
        except BaseException as exc:
            compensate_and_raise(stage_error("damage-journal", exc))

        try:
            _recovery_stage("break-proof", lambda: operations.assert_table_unreadable(manifest))
        except BaseException as exc:
            primary = stage_error("break-proof", exc)
            try:
                _set_damage_milestone(marker, marker_path, "breakProof", "failed")
            except BaseException as journal_exc:
                primary = stage_error("damage-journal", journal_exc)
            compensate_and_raise(primary)
        try:
            _set_damage_milestone(marker, marker_path, "breakProof", "passed")
        except BaseException as exc:
            compensate_and_raise(stage_error("damage-journal", exc))

        try:
            _restore_damaged(operations, ordered, marker, marker_path)
        except BaseException as restore_exc:
            mark_restoration_failed()
            raise stage_error("restoration", restore_exc) from restore_exc
        try:
            _set_damage_milestone(marker, marker_path, "restoration", "complete")
        except BaseException as journal_exc:
            raise stage_error("damage-journal", journal_exc) from journal_exc

    try:
        validation = operations.validate(manifest)
        _validate_result(validation, capture, logical_sha)
    except BaseException as validation_exc:
        primary_kind = (
            _exception_error_kind(validation_exc)
            if isinstance(validation_exc, Exception)
            else "unclassified"
        )
        try:
            _set_damage_milestone(marker, marker_path, "finalValidation", "failed")
        except BaseException as journal_exc:
            journal_kind = (
                _exception_error_kind(journal_exc)
                if isinstance(journal_exc, Exception)
                else "unclassified"
            )
            raise RecoveryStageError("damage-journal", error_kind=journal_kind) from journal_exc
        raise RecoveryStageError("final-validation", error_kind=primary_kind) from validation_exc
    try:
        _set_damage_milestone(marker, marker_path, "finalValidation", "passed")
    except BaseException as journal_exc:
        journal_kind = (
            _exception_error_kind(journal_exc)
            if isinstance(journal_exc, Exception)
            else "unclassified"
        )
        raise RecoveryStageError("damage-journal", error_kind=journal_kind) from journal_exc
    return {
        "status": "recovery-validated-after-interruption" if resuming else "recovery-validated",
        "runId": scope.run_id,
        "manifestSha256": manifest_sha,
        "logicalGraphSha256": logical_sha,
        "nodeCount": len(capture.nodes),
        "rowCount": capture.row_count,
    }


def _verify_live_aws(
    *,
    settings: RecoverySettings,
    scope: DrillScope,
    temp_root: Path,
    credential_exporter: Callable[..., AwsCredentials] = _export_aws_credentials,
) -> VerifiedAwsContext:
    profile_environment = _profile_environment(
        os.environ,
        profile=settings.profile,
        region=settings.region,
    )
    credentials = credential_exporter(environ=profile_environment)
    environment = _credential_environment(
        profile_environment,
        credentials=credentials,
        region=settings.region,
    )
    identity = _verify_non_root_identity(
        environ=environment,
        expected_sha256=settings.identity_sha256,
        region=settings.region,
    )
    root_arn = _require_identity_relationship(
        identity=identity,
        storage_role_arn=settings.storage_role_arn,
    )
    _isolate_parent_aws_environment(os.environ, region=settings.region)
    store = AwsCliVersionStore(
        bucket=settings.bucket,
        prefix=scope.prefix,
        region=settings.region,
        environ=environment,
        expected_owner=identity.account,
        temp_root=temp_root,
    )
    store.verify_bucket_protection(root_arn=root_arn)
    return VerifiedAwsContext(
        environment=environment,
        identity=identity,
        credentials=credentials,
        store=store,
    )


def _isolated_operations(
    *,
    scope: DrillScope,
    config: RuntimeConfig,
    aws: VerifiedAwsContext,
    runtime_binding: RuntimeBinding,
) -> LiveWarehouseDrillOperations:
    return LiveWarehouseDrillOperations(
        scope=scope,
        bucket=config.bucket,
        gateway=PolarisGateway(config=config),
        writer_store=aws.store,
        recovery_store=aws.store,
        runtime_binding=runtime_binding,
    )


def _write_seed_failure_receipt(
    *,
    plan_path: Path,
    plan_sha256: str,
    error: BaseException,
    clock: Callable[[], datetime] = lambda: datetime.now(UTC),
) -> Path:
    if not _SHA256.fullmatch(plan_sha256):
        raise DrillError("failed Seed-A plan SHA-256 is invalid")
    stage = error.stage if isinstance(error, SeedStageError) else "unclassified"
    error_kind = error.error_kind if isinstance(error, SeedStageError) else "unclassified"
    receipt = {
        "schemaVersion": 2,
        "receiptType": "seed-a-failure",
        "planSha256": plan_sha256,
        "errorStage": stage,
        "errorKind": error_kind,
        "recordedAt": clock().astimezone(UTC).isoformat().replace("+00:00", "Z"),
    }
    receipt_path = plan_path.parent / "seed-a-failure.json"
    _atomic_private_write(receipt_path, _canonical_json(receipt))
    return receipt_path


def _sanitized_damage_marker_summary(path: Path) -> dict[str, object]:
    try:
        details = path.lstat()
    except FileNotFoundError:
        return {"present": False}
    except OSError:
        return {"present": True, "readable": False}
    if (
        not stat.S_ISREG(details.st_mode)
        or stat.S_IMODE(details.st_mode) != 0o600
        or details.st_size > _MAX_PRIVATE_RESPONSE_BYTES
    ):
        return {"present": True, "readable": False}
    try:
        marker = json.loads(path.read_bytes())
    except (OSError, json.JSONDecodeError):
        return {"present": True, "readable": False}
    if not isinstance(marker, dict):
        return {"present": True, "readable": False}
    schema_version = marker.get("schemaVersion")
    raw_nodes = marker.get("nodes")
    if schema_version not in {1, 2} or not isinstance(raw_nodes, list):
        return {"present": True, "readable": False}
    phase_counts = {
        name: 0 for name in ("pending", "delete-intent", "deleted", "promotion-intent", "promoted")
    }
    for raw in raw_nodes:
        phase = raw.get("phase") if isinstance(raw, dict) else None
        if phase not in phase_counts:
            return {"present": True, "readable": False}
        phase_counts[phase] += 1
    summary: dict[str, object] = {
        "present": True,
        "readable": True,
        "schemaVersion": schema_version,
        "nodeCount": len(raw_nodes),
        "nodePhaseCounts": phase_counts,
    }
    if schema_version == 2:
        try:
            summary["milestones"] = dict(_damage_milestones(marker))
        except DrillError:
            return {"present": True, "readable": False}
    return summary


def _write_recovery_failure_receipt(
    *,
    plan_path: Path,
    plan_sha256: str,
    error: BaseException,
    clock: Callable[[], datetime] = lambda: datetime.now(UTC),
) -> Path:
    if not _SHA256.fullmatch(plan_sha256):
        raise DrillError("failed Recovery-A plan SHA-256 is invalid")
    if isinstance(error, RecoveryStageError):
        stage = error.stage
        error_kind = error.error_kind
        containment_error_kind = error.containment_error_kind
    else:
        stage = "preflight"
        error_kind = (
            _exception_error_kind(error) if isinstance(error, Exception) else "unclassified"
        )
        containment_error_kind = None
    damage_marker = _sanitized_damage_marker_summary(plan_path.parent / "damage-started.json")
    milestones = damage_marker.get("milestones")
    marker_containment = milestones.get("containment") if isinstance(milestones, dict) else None
    if containment_error_kind is not None:
        containment = {"status": "failed", "errorKind": containment_error_kind}
    elif marker_containment == "failed":
        containment = {"status": "failed", "errorKind": "unclassified"}
    elif marker_containment == "passed":
        containment = {"status": "passed", "errorKind": None}
    else:
        containment = {"status": "not-recorded", "errorKind": None}
    recorded_at = clock().astimezone(UTC).isoformat().replace("+00:00", "Z")
    for invocation in range(1, 17):
        receipt = {
            "schemaVersion": 2,
            "receiptType": "recovery-a-failure",
            "invocation": invocation,
            "planSha256": plan_sha256,
            "errorStage": stage,
            "errorKind": error_kind,
            "containment": containment,
            "damageMarker": damage_marker,
            "recordedAt": recorded_at,
        }
        receipt_path = plan_path.parent / f"recovery-a-failure-{invocation:03d}.json"
        try:
            details = receipt_path.lstat()
        except FileNotFoundError:
            details = None
        except OSError as exc:
            raise DrillError("Recovery-A failure receipt path is unavailable") from exc
        if details is not None:
            if not stat.S_ISREG(details.st_mode) or stat.S_IMODE(details.st_mode) != 0o600:
                raise DrillError("Recovery-A failure receipt path is unsafe")
            continue
        try:
            _atomic_private_write(receipt_path, _canonical_json(receipt))
        except DrillError:
            try:
                raced = receipt_path.lstat()
            except FileNotFoundError:
                raise
            if not stat.S_ISREG(raced.st_mode) or stat.S_IMODE(raced.st_mode) != 0o600:
                raise
            continue
        return receipt_path
    raise DrillError("Recovery-A failure receipt limit was reached")


def diagnose_recovery_plan(
    *,
    settings: RecoverySettings,
    plan_path: Path,
    expected_sha256: str,
    clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    image_inspector: Callable[[str], ImagePin] = _inspect_docker_image,
    docker_fingerprint: Callable[[], str] = _docker_runtime_fingerprint,
    live_aws_factory: Callable[..., VerifiedAwsContext] | None = None,
    stack_factory: Callable[..., IsolatedStage1Stack] = IsolatedStage1Stack,
    credential_exporter: Callable[..., AwsCredentials] = _export_aws_credentials,
) -> dict[str, object]:
    """Inspect one retained Recovery-A run without mutating S3 or Docker."""
    manifest, scope, capture, manifest_sha256, runtime = _manifest_contract(
        plan_path,
        expected_sha256,
        clock=clock,
        allow_expired=True,
    )
    if manifest.get("schemaVersion") != 4 or runtime is None:
        raise DrillError("diagnosis requires an isolated Recovery-A plan")
    parent_sha256 = manifest.get("parentSeedPlanSha256")
    if not isinstance(parent_sha256, str):
        raise DrillError("Recovery-A parent Seed-A hash is invalid")
    seed_plan, seed_scope, image_pins, seed_runtime, verified_parent = _seed_plan_contract(
        plan_path.parent / "seed-a.plan.json",
        parent_sha256,
        clock=clock,
        require_current=False,
        require_runtime_match=False,
    )
    if (
        seed_scope != scope
        or verified_parent != parent_sha256
        or manifest.get("stack") != seed_plan.get("stack")
        or runtime != seed_runtime
    ):
        raise DrillError("Recovery-A plan does not match its approved Seed-A parent")
    _settings_match_seed_plan(settings, seed_plan, scope)
    _verify_pinned_docker(
        seed_plan,
        image_pins,
        image_inspector=image_inspector,
        docker_fingerprint=docker_fingerprint,
    )
    stack_manifest = manifest.get("stack")
    resources = stack_manifest.get("resources") if isinstance(stack_manifest, dict) else None
    if not isinstance(resources, dict):
        raise DrillError("Recovery-A retained resources are invalid")
    stack = stack_factory(
        scope=scope,
        resources=resources,
        images=image_pins,
        seed_plan_sha256=parent_sha256,
        execution_plan_sha256=manifest_sha256,
    )
    expected_retained = manifest.get("retainedResourcesSha256")
    if not isinstance(expected_retained, str):
        raise DrillError("Recovery-A retained resource fingerprint is invalid")
    actual_retained = stack.retained_resources_sha256()
    if not hmac.compare_digest(actual_retained, expected_retained):
        raise DrillError("retained Docker resources changed after Seed-A")

    ordered = sorted(capture.nodes, key=lambda item: (-item.depth, item.key))
    marker = _read_damage_marker(
        plan_path.parent / "damage-started.json",
        scope=scope,
        manifest_sha256=manifest_sha256,
        nodes=ordered,
    )
    entries = _damage_entries(marker, ordered)
    if any(entry["phase"] != "promoted" for entry in entries.values()):
        raise DrillError("read-only diagnosis found incomplete restoration")

    live_aws = live_aws_factory or _verify_live_aws
    aws = live_aws(
        settings=settings,
        scope=scope,
        temp_root=plan_path.parent,
        credential_exporter=credential_exporter,
    )
    current_matches = 0
    source_matches = 0
    for node in ordered:
        current = aws.store.current_state(node)
        if (
            _matches_content(node, current)
            and current.version_id == entries[node.key]["promotedVersionId"]
        ):
            current_matches += 1
        else:
            raise DrillError("read-only diagnosis found a changed current graph object")
        source = aws.store.exact_source_state(node)
        if _matches_content(node, source) and source.version_id == node.source_version_id:
            source_matches += 1
        else:
            raise DrillError("read-only diagnosis found a changed historical source")
    expected_keys = {node.key for node in ordered}
    expected_keys.add(f"{scope.prefix}/capability-canary.bin")
    prefix_match = aws.store.prefix_keys() == frozenset(expected_keys)
    if not prefix_match:
        raise DrillError("read-only diagnosis found an unexpected prefix inventory")

    if marker.get("schemaVersion") == 2:
        milestones = _damage_milestones(marker)
        break_proof = milestones["breakProof"]
        final_validation = milestones["finalValidation"]
    else:
        break_proof = "unknown"
        final_validation = "unknown"
    return {
        "status": "diagnosed-object-state",
        "planType": "recovery-a",
        "objectRestorationState": "verified",
        "nodeCount": len(ordered),
        "currentPromotionsMatch": current_matches,
        "historicalSourcesMatch": source_matches,
        "retainedResourcesMatch": True,
        "prefixInventoryMatch": prefix_match,
        "breakProofState": break_proof,
        "finalValidationState": final_validation,
        "catalogReadbackState": "not-checked",
        "queryReadbackState": "not-checked",
    }


def main(
    argv: Sequence[str] | None = None,
    *,
    settings: RecoverySettings | None = None,
    token_factory: TokenFactory = _new_run_id,
) -> int:
    """Plan Seed-A or execute one exact Seed-A/Recovery-A private plan."""
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    prepare = commands.add_parser("prepare", help="write a mutation-free Seed-A plan")
    prepare.add_argument(
        "--evidence-root",
        type=Path,
        default=_LIVE_EVIDENCE_ROOT,
    )
    execute = commands.add_parser("execute", help="execute one exact approved private plan")
    execute.add_argument("--manifest", required=True, type=Path)
    execute.add_argument("--sha256", required=True)
    diagnose = commands.add_parser(
        "diagnose", help="inspect one retained Recovery-A run without mutation"
    )
    diagnose.add_argument("--manifest", required=True, type=Path)
    diagnose.add_argument("--sha256", required=True)
    args = parser.parse_args(list(argv) if argv is not None else None)
    failure_plan_path: Path | None = None
    failure_plan_type: object = None
    try:
        injected = settings is not None
        selected_settings = settings or RecoverySettings.load()
        if args.command == "prepare":
            evidence_root = (
                args.evidence_root if injected else _require_live_evidence_root(args.evidence_root)
            )
            result = prepare_seed_plan(
                settings=selected_settings,
                evidence_root=evidence_root,
                token_factory=token_factory,
            )
        else:
            plan_path = args.manifest if injected else _require_live_plan_path(args.manifest)
            if args.command == "diagnose":
                result = diagnose_recovery_plan(
                    settings=selected_settings,
                    plan_path=plan_path,
                    expected_sha256=args.sha256,
                )
            else:
                failure_plan_path = plan_path
                plan, _actual_sha256 = _read_exact_private_json(plan_path, args.sha256)
                plan_type = plan.get("planType")
                failure_plan_type = plan_type
                if plan_type == "seed-a":
                    result = execute_seed_plan(
                        settings=selected_settings,
                        plan_path=plan_path,
                        expected_sha256=args.sha256,
                    )
                elif plan_type == "recovery-a":
                    result = execute_recovery_plan(
                        settings=selected_settings,
                        plan_path=plan_path,
                        expected_sha256=args.sha256,
                    )
                else:
                    raise DrillError("private plan type is unsupported")
    except (DrillError, OSError, ValueError) as exc:
        if failure_plan_path is not None and failure_plan_type in {"seed-a", "recovery-a"}:
            try:
                if failure_plan_type == "seed-a":
                    _write_seed_failure_receipt(
                        plan_path=failure_plan_path,
                        plan_sha256=args.sha256,
                        error=exc,
                    )
                else:
                    _write_recovery_failure_receipt(
                        plan_path=failure_plan_path,
                        plan_sha256=args.sha256,
                        error=exc,
                    )
            except (DrillError, OSError, ValueError):
                pass
        print("Iceberg recovery drill refused; inspect private evidence locally", file=sys.stderr)
        return 1
    print(json.dumps(result, sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
