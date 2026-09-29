"""Load structure.yaml allowlist."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from nando_erp_ops.config import get_paths


@dataclass(frozen=True)
class AppSpec:
    key: str
    module: str
    repo_env: str
    branch_env: str


@dataclass(frozen=True)
class StructureConfig:
    apps: dict[str, AppSpec]
    structure_doctypes: list[str]
    per_environment: list[str]
    data_doctypes: list[str]

    def module_for(self, app: str) -> str:
        return self.apps[app].module

    def app_for_module(self, module: str) -> str | None:
        for key, spec in self.apps.items():
            if spec.module == module:
                return key
        return None


def load_structure(path: Path | None = None) -> StructureConfig:
    path = path or get_paths().structure_yaml
    raw: dict[str, Any] = yaml.safe_load(path.read_text()) or {}
    apps: dict[str, AppSpec] = {}
    for key, cfg in (raw.get("apps") or {}).items():
        apps[key] = AppSpec(
            key=key,
            module=cfg["module"],
            repo_env=cfg.get("repo_env", ""),
            branch_env=cfg.get("branch_env", ""),
        )
    return StructureConfig(
        apps=apps,
        structure_doctypes=list(raw.get("structure_doctypes") or []),
        per_environment=list(raw.get("per_environment") or []),
        data_doctypes=list(raw.get("data_doctypes") or []),
    )


def hooks_fixtures_for_app(module: str, structure_doctypes: list[str]) -> list[dict[str, Any]]:
    """Generate the hooks.py fixtures list shape for documentation / lint."""
    return [
        {"dt": dt, "filters": [["module", "=", module]]}
        for dt in structure_doctypes
    ]
