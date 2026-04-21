"""1Password-backed settings source for `DataboxSettings`.

Resolves `op://<vault>/<item>/<field>` references at settings-load time by
shelling out to the `op` CLI. Drop-in example — copy, adapt, wire via
`settings_customise_sources`. See `docs/secrets.md` for full walkthrough.
"""

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
