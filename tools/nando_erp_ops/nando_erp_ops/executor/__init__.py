"""Command execution backends: local shell vs AWS SSM."""
from __future__ import annotations

import os
import subprocess
import time
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Sequence


@dataclass
class CommandResult:
    returncode: int
    stdout: str
    stderr: str
    command_id: str | None = None

    @property
    def ok(self) -> bool:
        return self.returncode == 0


class Executor(ABC):
    @abstractmethod
    def run(self, argv: Sequence[str], *, cwd: str | None = None, timeout: int | None = None) -> CommandResult:
        ...

    def run_shell(self, script: str, *, cwd: str | None = None, timeout: int | None = None) -> CommandResult:
        return self.run(["bash", "-lc", script], cwd=cwd, timeout=timeout)


class LocalExecutor(Executor):
    def run(self, argv: Sequence[str], *, cwd: str | None = None, timeout: int | None = None) -> CommandResult:
        proc = subprocess.run(
            list(argv),
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
        return CommandResult(proc.returncode, proc.stdout, proc.stderr)


class SSMExecutor(Executor):
    """Dispatch commands to the ERP EC2 host via AWS Systems Manager Run Command."""

    def __init__(
        self,
        instance_id: str | None = None,
        region: str | None = None,
        remote_cwd: str | None = None,
        poll_seconds: float = 5.0,
    ) -> None:
        self.instance_id = instance_id or os.environ["NANDO_SSM_INSTANCE_ID"]
        self.region = region or os.environ.get("AWS_REGION") or os.environ.get("AWS_DEFAULT_REGION") or "eu-west-1"
        self.remote_cwd = remote_cwd or os.environ.get("NANDO_DOCKER_REPO", "/opt/nando_frappe_docker")
        self.poll_seconds = poll_seconds
        import boto3

        self._ssm = boto3.client("ssm", region_name=self.region)

    def run(self, argv: Sequence[str], *, cwd: str | None = None, timeout: int | None = None) -> CommandResult:
        workdir = cwd or self.remote_cwd
        # Quote args safely for remote bash
        quoted = " ".join(subprocess.list2cmdline([a]).split() if False else [_shell_quote(a) for a in argv])
        remote = f"cd {_shell_quote(workdir)} && {quoted}"
        timeout_seconds = timeout or int(os.environ.get("NANDO_SSM_TIMEOUT", "14400"))
        resp = self._ssm.send_command(
            InstanceIds=[self.instance_id],
            DocumentName="AWS-RunShellScript",
            Parameters={"commands": [remote]},
            TimeoutSeconds=timeout_seconds,
            Comment=f"nando-erp-ops {uuid.uuid4().hex[:8]}",
        )
        command_id = resp["Command"]["CommandId"]
        return self._wait(command_id, timeout_seconds)

    def _wait(self, command_id: str, timeout_seconds: int) -> CommandResult:
        deadline = time.time() + timeout_seconds
        while time.time() < deadline:
            inv = self._ssm.get_command_invocation(
                CommandId=command_id,
                InstanceId=self.instance_id,
            )
            status = inv["Status"]
            if status in {"Success", "Cancelled", "TimedOut", "Failed"}:
                code = 0 if status == "Success" else int(inv.get("ResponseCode") or 1)
                return CommandResult(
                    returncode=code,
                    stdout=inv.get("StandardOutputContent") or "",
                    stderr=inv.get("StandardErrorContent") or "",
                    command_id=command_id,
                )
            time.sleep(self.poll_seconds)
        return CommandResult(1, "", f"SSM command {command_id} timed out", command_id)


def _shell_quote(s: str) -> str:
    return "'" + s.replace("'", "'\"'\"'") + "'"


def get_executor() -> Executor:
    kind = (os.environ.get("NANDO_EXECUTOR") or "local").lower()
    if kind == "ssm":
        return SSMExecutor()
    return LocalExecutor()
