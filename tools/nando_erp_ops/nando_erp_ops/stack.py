"""Helpers to run docker compose against a stack."""
from __future__ import annotations

from pathlib import Path

from nando_erp_ops.config import Paths, get_paths, normalize_stack
from nando_erp_ops.executor import Executor, get_executor
from nando_erp_ops.versions import load_stack_env


class Stack:
    def __init__(self, name: str, paths: Paths | None = None, executor: Executor | None = None) -> None:
        self.name = normalize_stack(name)
        self.paths = paths or get_paths()
        self.executor = executor or get_executor()
        self.env = load_stack_env(self.name)
        defaults = {
            "dev": ("erpnext", "nando-deployment/erpnext-dev.yaml"),
            "quality": ("erpnext-quality", "nando-deployment/erpnext-quality.yaml"),
            "main": ("erpnext-main", "nando-deployment/erpnext-main.yaml"),
        }
        default_project, default_compose = defaults[self.name]
        self.project = self.env.get("COMPOSE_PROJECT_NAME", default_project)
        compose_rel = self.env.get("COMPOSE_FILE_OUTPUT", default_compose)
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

    def running_backend_image(self) -> str:
        r = self.executor.run(
            ["docker", "inspect", "-f", "{{.Config.Image}}", f"{self.project}-backend-1"],
            cwd=str(self.paths.repo_root),
        )
        running = (r.stdout or "").strip()
        if running:
            return running
        r = self.run_compose("ps", "-q", "backend")
        cid = r.stdout.strip().splitlines()[0] if r.ok and r.stdout.strip() else ""
        if cid:
            r = self.executor.run(["docker", "inspect", "-f", "{{.Config.Image}}", cid])
            return (r.stdout or "").strip()
        return ""
