"""FastAPI router for Lambda / internal backend.

Mount with:

    from nando_erp_ops.api import create_router
    app.include_router(create_router(), prefix="/erp-ops")

All mutating endpoints require the process to use NANDO_EXECUTOR=ssm and
IAM that allows ssm:SendCommand on the ERP instance. Prod-risk actions
are gated by NANDO_ALLOW_PROD=1 plus an explicit confirm flag.
"""
from __future__ import annotations

import os
from typing import Any, Callable

from nando_erp_ops import commands as cmd

# Actions that may touch prod / destroy data
PROD_ACTIONS = {"promote", "backup_main", "assign_modules_main", "baseline", "release"}


def _allow_prod() -> bool:
    return os.environ.get("NANDO_ALLOW_PROD", "").lower() in {"1", "true", "yes"}


def run_action(action: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
    params = params or {}
    if action in PROD_ACTIONS and not _allow_prod():
        return {"ok": False, "error": "NANDO_ALLOW_PROD not set — prod actions denied"}
    mapping: dict[str, Callable[..., int]] = {
        "doctor": lambda: cmd.cmd_doctor(stack=params.get("stack"), local=False),
        "drift": lambda: cmd.cmd_drift(stack=params.get("stack", "dev")),
        "capture": lambda: cmd.cmd_capture(
            stack=params.get("stack", "dev"),
            push=bool(params.get("push")),
            base=params.get("base"),
        ),
        "build": lambda: cmd.cmd_build(stack=params.get("stack", "dev")),
        "deploy": lambda: cmd.cmd_deploy(
            stack=params.get("stack", "dev"),
            skip_drift=bool(params.get("skip_drift")),
            with_build=bool(params.get("with_build")),
        ),
        "deploy_dev": lambda: cmd.cmd_deploy(
            stack="dev",
            skip_drift=bool(params.get("skip_drift")),
            with_build=bool(params.get("with_build")),
        ),
        "promote": lambda: cmd.cmd_promote(
            image_tag=params.get("image_tag"),
            yes=bool(params.get("confirm")),
            actor=params.get("actor"),
            source=params.get("source", "quality"),
            target=params.get("target", "main"),
            expect_sha=params.get("expect_sha"),
        ),
        "release": lambda: cmd.cmd_release(
            yes=bool(params.get("confirm")),
            actor=params.get("actor"),
        ),
        "backup": lambda: cmd.cmd_backup(
            stack=params.get("stack", "main"),
            with_files=bool(params.get("with_files", True)),
            prefix=params.get("prefix"),
            upload=bool(params.get("upload", True)),
        ),
        "backup_main": lambda: cmd.cmd_backup(stack="main", with_files=True),
        "refresh": lambda: cmd.cmd_refresh(
            target=params.get("target", "dev"),
            skip_drift=bool(params.get("skip_drift")),
            skip_if_drift=bool(params.get("skip_if_drift")),
        ),
        "baseline": lambda: cmd.cmd_baseline(stack=params.get("stack", "main"), commit=bool(params.get("commit"))),
        "assign_modules_main": lambda: cmd.cmd_assign_modules(stack="main", apply=bool(params.get("apply"))),
        "lint": lambda: cmd.cmd_lint(),
    }
    if action not in mapping:
        return {"ok": False, "error": f"Unknown action: {action}"}
    if action in {"promote", "release"} and not params.get("confirm"):
        return {"ok": False, "error": f"{action} requires confirm=true"}
    rc = mapping[action]()
    return {"ok": rc == 0, "returncode": rc, "action": action}


def create_router():
    try:
        from fastapi import APIRouter, HTTPException
        from pydantic import BaseModel, Field
    except ImportError as exc:
        raise ImportError("Install nando-erp-ops[api] for FastAPI support") from exc

    router = APIRouter(tags=["erp-ops"])

    class JobRequest(BaseModel):
        action: str
        params: dict[str, Any] = Field(default_factory=dict)
        actor: str | None = None

    @router.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok", "executor": os.environ.get("NANDO_EXECUTOR", "local")}

    @router.post("/jobs")
    def create_job(body: JobRequest) -> dict[str, Any]:
        params = dict(body.params)
        if body.actor:
            params["actor"] = body.actor
        result = run_action(body.action, params)
        if not result.get("ok"):
            raise HTTPException(status_code=400, detail=result)
        return result

    @router.get("/actions")
    def list_actions() -> dict[str, Any]:
        return {
            "actions": [
                "doctor", "drift", "capture", "build", "deploy", "deploy_dev",
                "promote", "release", "backup", "refresh", "baseline", "lint",
            ],
            "prod_gated": sorted(PROD_ACTIONS),
            "allow_prod": _allow_prod(),
        }

    return router
