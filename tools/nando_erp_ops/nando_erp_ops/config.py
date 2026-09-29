"""Paths and shared config for nando-erp-ops."""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def find_repo_root(start: Path | None = None) -> Path:
    """Locate nando_frappe_docker repo root (contains compose.yaml + nando-deployment/)."""
    env = os.environ.get("NANDO_DOCKER_REPO")
    if env:
        return Path(env).resolve()
    cur = (start or Path.cwd()).resolve()
    for candidate in [cur, *cur.parents]:
        if (candidate / "nando-deployment").is_dir() and (candidate / "compose.yaml").is_file():
            return candidate
        # tools/nando_erp_ops → repo root
        if (candidate / ".." / ".." / "nando-deployment").is_dir():
            root = (candidate / ".." / "..").resolve()
            if (root / "compose.yaml").is_file():
                return root
    # Package lives at tools/nando_erp_ops/nando_erp_ops/
    pkg_root = Path(__file__).resolve().parents[3]  # nando_frappe_docker
    if (pkg_root / "nando-deployment").is_dir():
        return pkg_root
    raise FileNotFoundError(
        "Cannot find nando_frappe_docker root. Set NANDO_DOCKER_REPO or run from the repo."
    )


@dataclass(frozen=True)
class Paths:
    repo_root: Path

    @property
    def deployment(self) -> Path:
        return self.repo_root / "nando-deployment"

    @property
    def versions_env(self) -> Path:
        return self.deployment / "versions.env"

    @property
    def structure_yaml(self) -> Path:
        return self.deployment / "structure.yaml"

    @property
    def custom_apps(self) -> Path:
        return self.deployment / "custom-apps"

    def env_file(self, stack: str) -> Path:
        if stack == "dev":
            return self.deployment / "erpnext-dev.env"
        if stack in {"main", "prod"}:
            return self.deployment / "erpnext-main.env"
        raise ValueError(f"Unknown stack: {stack}")


def get_paths() -> Paths:
    return Paths(repo_root=find_repo_root())


def local_bench_root() -> Path | None:
    env = os.environ.get("NANDO_LOCAL_BENCH")
    if env:
        return Path(env).resolve()
    # Common layout: sibling ERP_test/nando-bench
    repo = find_repo_root()
    sibling = repo.parent / "ERP_test" / "nando-bench"
    if sibling.is_dir():
        return sibling
    return None
