"""Example: mount ERP ops routes on the internal FastAPI backend (Lambda).

Copy into your backend package and wire IAM + env:

  NANDO_EXECUTOR=ssm
  NANDO_SSM_INSTANCE_ID=i-...
  NANDO_DOCKER_REPO=/opt/nando_frappe_docker
  NANDO_ALLOW_PROD=1          # only on the prod-capable alias
  AWS_REGION=eu-west-1
"""
from __future__ import annotations

# from fastapi import FastAPI
# from nando_erp_ops.api import create_router
#
# app = FastAPI()
# app.include_router(create_router(), prefix="/erp-ops")
#
# POST /erp-ops/jobs  {"action": "doctor", "params": {"stack": "dev"}}
# POST /erp-ops/jobs  {"action": "promote", "params": {"confirm": true}, "actor": "simone"}

from nando_erp_ops.api import create_router, run_action

__all__ = ["create_router", "run_action"]
