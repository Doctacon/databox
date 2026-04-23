# Secrets

Databox resolves runtime config through `databox.config.settings.DataboxSettings`,
a Pydantic `BaseSettings` subclass. The default flow reads from environment
variables (backed by a project-root `.env` file). That is the baseline and
requires no extra machinery.

This page explains how to swap that baseline for an external secrets manager
(1Password, Vault, AWS Secrets Manager, Doppler) without forking the settings
module.

## Default flow

```python
from databox.config.settings import settings

print(settings.motherduck_token)  # read from MOTHERDUCK_TOKEN env var
```

`SettingsConfigDict(env_file=".env")` means local dev can keep secrets in a
gitignored `.env`. CI and prod inject the same env vars through their own
mechanisms. Nothing else is required for the common case.

## Pydantic extension contract

Pydantic v2 exposes `settings_customise_sources` — a classmethod that returns
the ordered tuple of sources Pydantic walks to populate fields. The first
source that yields a value wins. Add a custom source at the front of the
tuple and it overrides env/dotenv:

```python
from pydantic_settings import (
    BaseSettings,
    PydanticBaseSettingsSource,
    SettingsConfigDict,
)


class MySettings(BaseSettings):
    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls,
        init_settings,
        env_settings,
        dotenv_settings,
        file_secret_settings,
    ):
        return (
            init_settings,
            MyExternalSource(settings_cls),  # new: checked before env
            env_settings,
            dotenv_settings,
            file_secret_settings,
        )
```

A source is any callable that returns `dict[str, Any]`. The `PydanticBaseSettingsSource`
base class gives you `get_field_value` + `__call__` to implement.

## Worked example: 1Password

A ~30-line source that resolves `op://vault/item/field` references via the
`op` CLI. It reads a YAML mapping of field names to refs (gitignored):

```yaml
# secret_refs.yaml
motherduck_token: "op://databox/motherduck/token"
```

```python
# one_password_source.py
from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

import yaml
from pydantic.fields import FieldInfo
from pydantic_settings import BaseSettings, PydanticBaseSettingsSource


class OnePasswordSource(PydanticBaseSettingsSource):
    """Resolve field values from 1Password refs listed in a YAML file."""

    def __init__(self, settings_cls: type[BaseSettings], refs_path: Path) -> None:
        super().__init__(settings_cls)
        self._refs: dict[str, str] = (
            yaml.safe_load(refs_path.read_text()) if refs_path.exists() else {}
        )

    def get_field_value(self, field: FieldInfo, field_name: str) -> tuple[Any, str, bool]:
        ref = self._refs.get(field_name)
        if ref is None:
            return None, field_name, False
        result = subprocess.run(["op", "read", ref], check=True, capture_output=True, text=True)
        return result.stdout.strip(), field_name, False

    def __call__(self) -> dict[str, Any]:
        return {name: self.get_field_value(None, name)[0] for name in self._refs}  # type: ignore[arg-type]
```

Wire it into `DataboxSettings` by subclassing and returning the source first:

```python
from pathlib import Path
from databox.config.settings import DataboxSettings
from one_password_source import OnePasswordSource

REFS = Path("secret_refs.yaml")


class OnePasswordSettings(DataboxSettings):
    @classmethod
    def settings_customise_sources(
        cls, settings_cls, init_settings, env_settings, dotenv_settings, file_secret_settings
    ):
        return (
            init_settings,
            OnePasswordSource(settings_cls, REFS),
            env_settings,
            dotenv_settings,
            file_secret_settings,
        )


settings = OnePasswordSettings()
```

Prerequisites: `op` CLI installed, `op signin` already run (or `OP_SERVICE_ACCOUNT_TOKEN`
exported), refs resolve to real items.

## Other backends

The same pattern applies — swap the source implementation:

- **HashiCorp Vault** — replace `subprocess.run(["op", "read", ref])` with an
  `hvac` client call; treat `vault://<mount>/<path>#<key>` as the ref shape.
- **AWS Secrets Manager** — use `boto3.client("secretsmanager").get_secret_value`;
  ref shape `aws-secrets://<secret-id>#<json-key>`.
- **Doppler** — `doppler secrets get <name> --plain` via subprocess, or their
  Python SDK; ref shape `doppler://<project>/<config>#<name>`.

The ref scheme is convention only — Pydantic never parses it. Your source
decides what string to accept.

## Secret-scanner hygiene

`scripts/check_secrets.py` runs as a pre-commit hook and in CI. It treats
external-ref schemes (`op://`, `vault://`, `aws-secrets://`, `doppler://`)
as pointers, not plaintext. Committing `motherduck_token: "op://databox/motherduck/token"`
in `secret_refs.yaml` is safe — the string is a lookup key, not a credential.

If you introduce a new scheme, add it to `ALLOWED_VALUES` in
`scripts/check_secrets.py` and document it here.

## When to migrate

Keep `.env` for local dev — it is the lowest-friction path. Migrate to an
external manager when any of these are true:

- Secrets are shared across operators or machines.
- You need audit logs for secret access.
- You need rotation without redeploying.
- Compliance requires secrets live outside developer filesystems.
