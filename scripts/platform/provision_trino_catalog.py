#!/usr/bin/env python3
"""Idempotently provision the dedicated Polaris catalog used by Trino/SQLMesh.

The raw catalog is read only. Its storage role is reused by a separate catalog
with a non-overlapping ``sqlmesh-warehouse`` prefix and scoped allowed locations.
"""

from __future__ import annotations

import base64
import copy
import json
import sys
from collections.abc import Mapping
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode, urlsplit
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener

from databox.config.settings import settings

CATALOG_ROLE = "analytics_writer"
PRINCIPAL_ROLE = "service_admin"
DROP_WITH_PURGE_PROPERTY = "polaris.config.drop-with-purge.enabled"
REQUEST_TIMEOUT_SECONDS = 15
MAX_RESPONSE_BYTES = 1024 * 1024


class ProvisioningError(RuntimeError):
    """Provisioning could not be completed safely."""


class ApiError(ProvisioningError):
    """Polaris returned a non-success status without exposing its response body."""

    def __init__(self, status: int) -> None:
        self.status = status
        super().__init__(f"Polaris request failed with HTTP {status}")


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


class PolarisManagementClient:
    """Small secret-safe client for the Polaris management API."""

    def __init__(self, base_url: str, client_id: str, client_secret: str) -> None:
        if not client_id or not client_secret:
            raise ProvisioningError("Polaris client credentials are required")
        self.base_url = base_url.rstrip("/")
        self.client_id = client_id
        self.client_secret = client_secret
        self._opener = build_opener(ProxyHandler({}), _NoRedirectHandler())

    def _request(
        self,
        *,
        method: str,
        url: str,
        headers: Mapping[str, str],
        data: bytes | None = None,
    ) -> dict[str, Any]:
        request = Request(url, data=data, headers=dict(headers), method=method)
        try:
            with self._opener.open(request, timeout=REQUEST_TIMEOUT_SECONDS) as response:
                payload = response.read(MAX_RESPONSE_BYTES + 1)
        except HTTPError as exc:
            raise ApiError(exc.code) from None
        except (OSError, URLError) as exc:
            raise ProvisioningError("Polaris request could not be completed") from exc

        if len(payload) > MAX_RESPONSE_BYTES:
            raise ProvisioningError("Polaris response exceeded the safety limit")
        if not payload:
            return {}
        try:
            value = json.loads(payload)
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ProvisioningError("Polaris returned invalid JSON") from exc
        if not isinstance(value, dict):
            raise ProvisioningError("Polaris returned an unexpected response")
        return value

    def token(self) -> str:
        basic = base64.b64encode(f"{self.client_id}:{self.client_secret}".encode()).decode()
        response = self._request(
            method="POST",
            url=f"{self.base_url}/api/catalog/v1/oauth/tokens",
            headers={
                "Authorization": f"Basic {basic}",
                "Content-Type": "application/x-www-form-urlencoded",
                "Polaris-Realm": "POLARIS",
            },
            data=urlencode(
                {"grant_type": "client_credentials", "scope": "PRINCIPAL_ROLE:ALL"}
            ).encode(),
        )
        # Runtime OAuth response lookup, not a literal credential.
        token = response.get("access_token")  # secret-scan: allow
        if not isinstance(token, str) or not token:
            raise ProvisioningError("Polaris did not return an access token")
        return token

    def management(
        self,
        token: str,
        method: str,
        path: str,
        payload: Mapping[str, object] | None = None,
    ) -> dict[str, Any]:
        body = None
        if payload is not None:
            body = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
        return self._request(
            method=method,
            url=f"{self.base_url}/api/management/v1{path}",
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": "application/json",
                "Content-Type": "application/json",
                "Polaris-Realm": "POLARIS",
            },
            data=body,
        )


def _location_is_within(location: str, allowed_location: str) -> bool:
    """Return whether one object-store URI is at or below another URI."""
    location_parts = urlsplit(location)
    allowed_parts = urlsplit(allowed_location)
    if (
        not location_parts.scheme
        or not location_parts.netloc
        or location_parts.query
        or location_parts.fragment
        or allowed_parts.query
        or allowed_parts.fragment
        or location_parts.scheme.lower() != allowed_parts.scheme.lower()
        or location_parts.netloc != allowed_parts.netloc
    ):
        return False
    location_path = location_parts.path.rstrip("/")
    allowed_path = allowed_parts.path.rstrip("/")
    return location_path == allowed_path or location_path.startswith(f"{allowed_path}/")


def _dedicated_location(raw_catalog: Mapping[str, Any]) -> tuple[str, dict[str, Any]]:
    properties = raw_catalog.get("properties")
    storage = raw_catalog.get("storageConfigInfo")
    if not isinstance(properties, dict) or not isinstance(storage, dict):
        raise ProvisioningError("raw catalog configuration is incomplete")

    raw_base = properties.get("default-base-location")
    allowed_locations = storage.get("allowedLocations")
    if not isinstance(raw_base, str) or not raw_base.rstrip("/"):
        raise ProvisioningError("raw catalog has no valid default base location")
    if not isinstance(allowed_locations, list) or not all(
        isinstance(value, str) and value for value in allowed_locations
    ):
        raise ProvisioningError("raw catalog has no valid allowed storage locations")

    base = urlsplit(raw_base)
    dedicated = f"{base.scheme}://{base.netloc}/sqlmesh-warehouse"
    if any(
        _location_is_within(dedicated, allowed) or _location_is_within(allowed, dedicated)
        for allowed in allowed_locations
    ):
        raise ProvisioningError("SQLMesh storage must not overlap raw catalog storage")
    dedicated_storage = copy.deepcopy(storage)
    dedicated_storage["allowedLocations"] = [dedicated]
    return dedicated, dedicated_storage


def _expected_catalog(
    *, target_name: str, dedicated_location: str, storage: Mapping[str, Any]
) -> dict[str, Any]:
    return {
        "name": target_name,
        "type": "INTERNAL",
        "readOnly": False,
        "properties": {
            "default-base-location": dedicated_location,
            DROP_WITH_PURGE_PROPERTY: "true",
        },
        "storageConfigInfo": dict(storage),
    }


def _assert_matching_catalog(actual: Mapping[str, Any], expected: Mapping[str, Any]) -> None:
    checked_fields = ("name", "type", "readOnly", "properties", "storageConfigInfo")
    mismatches = [
        field
        for field in checked_fields
        if actual.get(field, False if field == "readOnly" else None) != expected.get(field)
    ]
    if mismatches:
        fields = ", ".join(mismatches)
        raise ProvisioningError(f"existing target catalog configuration mismatch: {fields}")


def provision(
    client: PolarisManagementClient,
    *,
    raw_name: str,
    target_name: str,
) -> None:
    """Create or verify the analytics catalog, then idempotently ensure its grants."""
    token = client.token()
    raw_path_name = quote(raw_name, safe="")
    target_path_name = quote(target_name, safe="")

    raw_catalog = client.management(token, "GET", f"/catalogs/{raw_path_name}")
    dedicated_location, storage = _dedicated_location(raw_catalog)
    expected = _expected_catalog(
        target_name=target_name,
        dedicated_location=dedicated_location,
        storage=storage,
    )

    try:
        target_catalog = client.management(token, "GET", f"/catalogs/{target_path_name}")
    except ApiError as exc:
        if exc.status != 404:
            raise
        client.management(token, "POST", "/catalogs", {"catalog": expected})
        target_catalog = client.management(token, "GET", f"/catalogs/{target_path_name}")

    # Refuse to repair or mutate a pre-existing catalog with a different safety contract.
    _assert_matching_catalog(target_catalog, expected)

    role_path_name = quote(CATALOG_ROLE, safe="")
    try:
        client.management(
            token,
            "GET",
            f"/catalogs/{target_path_name}/catalog-roles/{role_path_name}",
        )
    except ApiError as exc:
        if exc.status != 404:
            raise
        client.management(
            token,
            "POST",
            f"/catalogs/{target_path_name}/catalog-roles",
            {"catalogRole": {"name": CATALOG_ROLE, "properties": {}}},
        )

    # Polaris models both operations as idempotent PUTs.  Repeating them also
    # repairs a missing privilege or principal-role assignment without changing
    # either catalog's configuration.
    client.management(
        token,
        "PUT",
        f"/catalogs/{target_path_name}/catalog-roles/{role_path_name}/grants",
        {"type": "catalog", "privilege": "CATALOG_MANAGE_CONTENT"},
    )
    client.management(
        token,
        "PUT",
        f"/principal-roles/{quote(PRINCIPAL_ROLE, safe='')}/catalog-roles/{target_path_name}",
        {"catalogRole": {"name": CATALOG_ROLE}},
    )


def main() -> int:
    target_name = settings.trino_iceberg_catalog
    client = PolarisManagementClient(
        settings.polaris_url,
        settings.polaris_client_id.get_secret_value(),
        settings.polaris_client_secret.get_secret_value(),
    )
    try:
        provision(
            client,
            raw_name=settings.iceberg_catalog,
            target_name=target_name,
        )
    except ProvisioningError as exc:
        print(f"provision_trino_catalog: {exc}", file=sys.stderr)
        return 1
    print(
        f"provision_trino_catalog: {target_name} is configured for SQLMesh "
        f"and granted to {PRINCIPAL_ROLE}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
