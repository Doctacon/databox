from __future__ import annotations

import copy
from typing import Any

import pytest

from scripts.platform import provision_trino_catalog as provisioner

RAW_CATALOG = {
    "name": "databox_lake",
    "type": "INTERNAL",
    "properties": {"default-base-location": "s3://databox-bucket/raw-warehouse"},
    "storageConfigInfo": {
        "storageType": "S3",
        "allowedLocations": ["s3://databox-bucket/raw-warehouse"],
        "roleArn": "arn:aws:iam::123456789012:role/databox-storage",
        "externalId": "polaris-storage",
    },
}
TARGET_NAME = "configured_analytics"


def test_dedicated_location_is_nonoverlapping_sibling() -> None:
    dedicated, _ = provisioner._dedicated_location(RAW_CATALOG)
    raw_base = RAW_CATALOG["properties"]["default-base-location"]

    assert dedicated == "s3://databox-bucket/sqlmesh-warehouse"
    assert not provisioner._location_is_within(dedicated, raw_base)
    assert not provisioner._location_is_within(raw_base, dedicated)


def test_dedicated_storage_narrows_allowed_locations_and_preserves_role() -> None:
    raw = copy.deepcopy(RAW_CATALOG)

    dedicated, storage = provisioner._dedicated_location(raw)

    assert storage == {
        "storageType": "S3",
        "allowedLocations": [dedicated],
        "roleArn": "arn:aws:iam::123456789012:role/databox-storage",
        "externalId": "polaris-storage",
    }
    assert raw == RAW_CATALOG
    assert storage is not raw["storageConfigInfo"]


class ExistingTargetClient:
    def __init__(self, target: dict[str, Any]) -> None:
        self.target = target
        self.requests: list[tuple[str, str, Any]] = []

    def token(self) -> str:
        return "test-token"

    def management(
        self,
        token: str,
        method: str,
        path: str,
        payload: Any = None,
    ) -> dict[str, Any]:
        assert token == "test-token"
        self.requests.append((method, path, payload))
        if path == "/catalogs/databox_lake":
            return copy.deepcopy(RAW_CATALOG)
        if path == f"/catalogs/{TARGET_NAME}":
            return copy.deepcopy(self.target)
        raise AssertionError(f"unexpected request after mismatch: {method} {path}")


def test_preexisting_target_mismatch_is_refused_before_grant_writes() -> None:
    dedicated, storage = provisioner._dedicated_location(RAW_CATALOG)
    target = provisioner._expected_catalog(
        target_name=TARGET_NAME,
        dedicated_location=dedicated,
        storage=storage,
    )
    target["properties"][provisioner.DROP_WITH_PURGE_PROPERTY] = "false"
    client = ExistingTargetClient(target)

    with pytest.raises(
        provisioner.ProvisioningError,
        match="existing target catalog configuration mismatch: properties",
    ):
        provisioner.provision(
            client,
            raw_name="databox_lake",
            target_name=TARGET_NAME,
        )

    assert client.requests == [
        ("GET", "/catalogs/databox_lake", None),
        ("GET", f"/catalogs/{TARGET_NAME}", None),
    ]


class StatefulMockClient:
    def __init__(self) -> None:
        self.target: dict[str, Any] | None = None
        self.role_exists = False
        self.requests: list[tuple[str, str, Any]] = []
        self.token_calls = 0

    def token(self) -> str:
        self.token_calls += 1
        return "test-token"

    def management(
        self,
        token: str,
        method: str,
        path: str,
        payload: Any = None,
    ) -> dict[str, Any]:
        assert token == "test-token"
        self.requests.append((method, path, copy.deepcopy(payload)))
        target_path = f"/catalogs/{TARGET_NAME}"
        role_path = f"{target_path}/catalog-roles/{provisioner.CATALOG_ROLE}"

        if method == "GET" and path == "/catalogs/databox_lake":
            return copy.deepcopy(RAW_CATALOG)
        if method == "GET" and path == target_path:
            if self.target is None:
                raise provisioner.ApiError(404)
            response = copy.deepcopy(self.target)
            response.pop("readOnly", None)  # Polaris omits false in its GET response.
            return response
        if method == "POST" and path == "/catalogs":
            assert payload is not None
            self.target = copy.deepcopy(payload["catalog"])
            return {}
        if method == "GET" and path == role_path:
            if not self.role_exists:
                raise provisioner.ApiError(404)
            return {"name": provisioner.CATALOG_ROLE}
        if method == "POST" and path == f"{target_path}/catalog-roles":
            self.role_exists = True
            return {}
        if method == "PUT":
            return {}
        raise AssertionError(f"unexpected request: {method} {path}")


def test_provision_is_idempotent_with_expected_request_sequence() -> None:
    client = StatefulMockClient()

    provisioner.provision(client, raw_name="databox_lake", target_name=TARGET_NAME)
    provisioner.provision(client, raw_name="databox_lake", target_name=TARGET_NAME)

    target_path = f"/catalogs/{TARGET_NAME}"
    role_path = f"{target_path}/catalog-roles/{provisioner.CATALOG_ROLE}"
    grant_path = f"{role_path}/grants"
    assignment_path = f"/principal-roles/{provisioner.PRINCIPAL_ROLE}/catalog-roles/{TARGET_NAME}"
    assert [(method, path) for method, path, _ in client.requests] == [
        ("GET", "/catalogs/databox_lake"),
        ("GET", target_path),
        ("POST", "/catalogs"),
        ("GET", target_path),
        ("GET", role_path),
        ("POST", f"{target_path}/catalog-roles"),
        ("PUT", grant_path),
        ("PUT", assignment_path),
        ("GET", "/catalogs/databox_lake"),
        ("GET", target_path),
        ("GET", role_path),
        ("PUT", grant_path),
        ("PUT", assignment_path),
    ]
    assert client.token_calls == 2
    assert sum(method == "POST" for method, _, _ in client.requests) == 2

    create_payload = client.requests[2][2]
    assert create_payload["catalog"]["name"] == TARGET_NAME
    assert create_payload["catalog"]["properties"] == {
        "default-base-location": "s3://databox-bucket/sqlmesh-warehouse",
        provisioner.DROP_WITH_PURGE_PROPERTY: "true",
    }
    assert create_payload["catalog"]["storageConfigInfo"]["allowedLocations"] == [
        "s3://databox-bucket/sqlmesh-warehouse"
    ]
