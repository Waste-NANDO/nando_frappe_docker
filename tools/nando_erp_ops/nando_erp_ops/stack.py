"""Helpers to run docker compose against a stack."""
from __future__ import annotations

from pathlib import Path

from nando_erp_ops.config import Paths, get_paths
from nando_erp_ops.executor import Executor, get_executor
from nando_erp_ops.versions import load_stack_env


class Stack:
    def __init__(self, name: str, paths: Paths | None = None, executor: Executor | None = None) -> None:
        if name not in {"dev", "main", "prod"}:
            raise ValueError(name)
        self.name = "main" if name == "prod" else name
        self.paths = paths or get_paths()
        self.executor = executor or get_executor()
        self.env = load_stack_env(self.name)
        self.project = self.env.get("COMPOSE_PROJECT_NAME", "erpnext" if self.name == "dev" else "erpnext-main")
        compose_rel = self.env.get(
            "COMPOSE_FILE_OUTPUT",
            f"nando-deployment/erpnext-{'dev' if self.name == 'dev' else 'main'}.yaml",
        )
        self.compose_file = Path(compose_rel)
        if not self.compose_file.is_absolute():
            self.compose_file = self.paths.repo_root / self.compose_file
        self.site = self.env.get("FRAPPE_SITE_NAME_HEADER", "apps.internal.nandoai.com")
        self.custom_image = self.env.get("CUSTOM_IMAGE", "nando-erpnext-custom")
        self.custom_tag = self.env.get("CUSTOM_TAG", "latest")

    def compose_argv(self, *args: str) -> list[str]:
        return [
            "docker",
            "compose",
            "--project-name",
            self.project,
            "--project-directory",
            str(self.paths.repo_root),
            "-f",
            str(self.compose_file),
            *args,
        ]

    def run_compose(self, *args: str, timeout: int | None = None):
        return self.executor.run(self.compose_argv(*args), cwd=str(self.paths.repo_root), timeout=timeout)

    def bench(self, *bench_args: str, timeout: int | None = None):
        return self.run_compose(
            "exec",
            "-T",
            "backend",
            "bench",
            "--site",
            self.site,
            *bench_args,
            timeout=timeout,
        )
