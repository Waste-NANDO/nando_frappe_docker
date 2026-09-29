# nando-erp-ops

Python CLI and library for the NANDO ERPNext structure/data pipeline.

**How the pipeline works (read this first):** [nando-deployment/PIPELINE.md](../../nando-deployment/PIPELINE.md)

Step-by-step: [guides/](../../nando-deployment/guides/) · Host/SSM/API: [guides/09-cli-ssm-api.md](../../nando-deployment/guides/09-cli-ssm-api.md)

## Install

```bash
# Editable (laptop / ERP host)
pip install -e /path/to/nando_frappe_docker/tools/nando_erp_ops

# From private GCP Artifact Registry (after publish)
pip install nando-erp-ops --index-url https://<region>-python.pkg.dev/<project>/<repo>/simple/
```

## Commands

| Command | Purpose |
|---------|---------|
| `nando-erp doctor` | Compare local / cloud-dev / prod pins against `versions.env` |
| `nando-erp local-bootstrap` | Align native bench apps to the version manifest |
| `nando-erp export` | `export-fixtures` into app repos (local or stack) |
| `nando-erp lint` | Module ownership + structure allowlist |
| `nando-erp drift` | Diff live site fixtures vs git (blocks deploy) |
| `nando-erp capture` | Export cloud-dev drift → `capture/<date>` branch + PR |
| `nando-erp build` | Commit-pinned image build (wraps `build-custom-image.sh`) |
| `nando-erp deploy dev` | Drift check → deploy-stack migrate |
| `nando-erp promote` | Gate + pre-deploy GCS backup + retag image → prod |
| `nando-erp backup` | Manual / pre-deploy / pre-refresh backup to GCS |
| `nando-erp refresh` | Restore latest prod GCS backup → sanitize → migrate |
| `nando-erp baseline` | One-shot: export prod fixtures into git main+dev |
| `nando-erp assign-modules` | Assign module on Custom Fields / Property Setters |

## Executors

- `local` (default on ERP host): runs docker compose / bench locally
- `ssm`: laptop / Lambda dispatches via AWS SSM Run Command to the ERP EC2 host

```bash
export NANDO_EXECUTOR=ssm
export NANDO_SSM_INSTANCE_ID=i-...
export NANDO_DOCKER_REPO=/opt/nando_frappe_docker
nando-erp doctor --stack dev
```

## FastAPI / Lambda

```python
from nando_erp_ops.api import create_router
app.include_router(create_router(), prefix="/erp-ops")
```

IAM should deny `promote` / prod `backup` unless the caller is in the deploy role.
See `nando_erp_ops/api/iam.md`.

## Publish to Artifact Registry

```bash
cd tools/nando_erp_ops
python -m build
twine upload --repository-url https://<region>-python.pkg.dev/<project>/<repo>/ dist/*
```
