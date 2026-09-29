"""Parse versions.env and stack env files."""
from __future__ import annotations

import re
from pathlib import Path

from nando_erp_ops.config import get_paths

_ENV_LINE = re.compile(r"^([A-Za-z_][A-Za-z0-9_]*)=(.*)$")


def parse_env_file(path: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    if not path.is_file():
        return out
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        m = _ENV_LINE.match(line)
        if not m:
            continue
        key, value = m.group(1), m.group(2).strip().strip("'\"")
        out[key] = value
    return out


def load_versions() -> dict[str, str]:
    paths = get_paths()
    versions = parse_env_file(paths.versions_env)
    # Stack files may override; doctor compares against versions.env as source of truth.
    return versions


def load_stack_env(stack: str) -> dict[str, str]:
    paths = get_paths()
    versions = parse_env_file(paths.versions_env)
    stack_env = parse_env_file(paths.env_file(stack))
    merged = {**versions, **stack_env}
    return merged


REQUIRED_PINS = (
    "ERPNEXT_VERSION",
    "FRAPPE_VERSION",
    "FRAPPE_BRANCH",
    "HRMS_BRANCH",
)
