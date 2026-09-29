# 09 — CLI, SSM, and API

Install and run `nando-erp` on the ERP host, from a laptop via SSM, or from the FastAPI/Lambda backend.

## A. Install on the ERP EC2 host

```bash
cd /opt/nando_frappe_docker   # your checkout
sudo bash tools/nando_erp_ops/install-host.sh
# or manually:
python3 -m venv /opt/nando-erp-ops-venv
/opt/nando-erp-ops-venv/bin/pip install -e tools/nando_erp_ops
```

```bash
export NANDO_DOCKER_REPO=/opt/nando_frappe_docker
export NANDO_EXECUTOR=local
export PATH="/opt/nando-erp-ops-venv/bin:$PATH"
nando-erp doctor --no-local
```

Optional: publish to GCP Artifact Registry and `pip install nando-erp-ops` instead of editable:

```bash
./tools/nando_erp_ops/publish.sh <gcp-project> [repo] [region]
```

Host needs registry auth (WIF or SA key) — see [`api/iam.md`](../../tools/nando_erp_ops/nando_erp_ops/api/iam.md).

## B. Laptop → host via SSM

```bash
# laptop venv with nando-erp-ops installed
export NANDO_EXECUTOR=ssm
export NANDO_SSM_INSTANCE_ID=i-0123456789abcdef0
export NANDO_DOCKER_REPO=/opt/nando_frappe_docker
export AWS_REGION=eu-west-1   # or your region

nando-erp doctor --stack dev
nando-erp drift --stack dev
# long jobs (build/promote) work; SSM timeout default 4h (NANDO_SSM_TIMEOUT)
```

Caller IAM needs `ssm:SendCommand` + `ssm:GetCommandInvocation` on that instance. Audit trail is CloudTrail.

## C. FastAPI / Lambda

```python
from fastapi import FastAPI
from nando_erp_ops.api import create_router

app = FastAPI()
app.include_router(create_router(), prefix="/erp-ops")
```

Env on the Lambda (prod-capable alias only):

```bash
NANDO_EXECUTOR=ssm
NANDO_SSM_INSTANCE_ID=i-...
NANDO_DOCKER_REPO=/opt/nando_frappe_docker
NANDO_ALLOW_PROD=1          # omit on staging aliases — blocks promote/prod backup
AWS_REGION=eu-west-1
```

Example calls:

```http
POST /erp-ops/jobs
{"action": "doctor", "params": {"stack": "dev"}}

POST /erp-ops/jobs
{"action": "promote", "params": {"confirm": true}, "actor": "simone"}
```

`promote` without `confirm: true` is rejected. Without `NANDO_ALLOW_PROD=1`, all prod-gated actions fail in-process.

Job logs: read SSM command output (CloudWatch / GetCommandInvocation). For multi-hour builds, prefer invoking from the host or an async worker; Lambda max duration may be shorter than a full image build.

## D. Command index

Full table: [tools/nando_erp_ops/README.md](../../tools/nando_erp_ops/README.md).

| You want… | Command |
|-----------|---------|
| Check pins | `nando-erp doctor` |
| Align local bench | `nando-erp local-bootstrap` |
| Export Desk → git | `nando-erp export --target local\|dev\|main` |
| Ownership check | `nando-erp lint` |
| Live vs git | `nando-erp drift --stack dev` |
| Save cloud-dev Desk | `nando-erp capture --push` |
| Build image | `nando-erp build --stack dev` |
| Ship to `:3003` | `nando-erp deploy dev` |
| Ship to `:3000` | `nando-erp promote --yes` |
| Backup | `nando-erp backup --stack main` |
| Pull prod data | `nando-erp refresh --target dev` |
| One-time prod → git | `nando-erp baseline` / [Phase 0](../PHASE0_BASELINE.md) |
