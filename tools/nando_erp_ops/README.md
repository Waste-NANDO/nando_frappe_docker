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
| `nando-erp doctor` | Compare local / cloud-dev / Quality / prod pins against `versions.env` |
| `nando-erp local-bootstrap` | Align native bench apps; symlink from `nando-erp-modules` |
| `nando-erp export` | `export-fixtures` into app folders (local or stack) |
| `nando-erp lint` | Module ownership + hooks coverage of `structure_doctypes` |
| `nando-erp drift` | Diff live site fixtures vs git (blocks deploy) |
| `nando-erp capture` | Export stack drift → monorepo `capture/…` branch + PR |
| `nando-erp build` | Commit-pinned image build from monorepo (`…-apps.<sha7>`) |
| `nando-erp deploy {dev\|quality}` | Drift check → deploy-stack migrate |
| `nando-erp promote` | Quality → prod: gate + backup + retag (optional `--expect-sha`) |
| `nando-erp release` | Capture Quality Desk → push `quality` → open PRs to master/dev |
| `nando-erp backup` | Manual / pre-deploy / pre-refresh backup to GCS |
| `nando-erp refresh` | Restore latest prod GCS backup → sanitize → migrate (`--target quality` supported) |
| `nando-erp baseline` | One-shot: export prod fixtures into git |
| `nando-erp assign-modules` | Assign module on Custom Fields / Property Setters |

## Executors

- `local` (default on ERP host): runs docker compose / bench locally
- `ssm`: laptop / Lambda dispatches via AWS SSM Run Command to the ERP EC2 host

```bash
export NANDO_EXECUTOR=ssm
export NANDO_SSM_INSTANCE_ID=i-…
export NANDO_DOCKER_REPO=/opt/nando_frappe_docker
```

## Stacks

| CLI name | Compose project | Port |
|----------|-----------------|------|
| `dev` | `erpnext` | 3003 |
| `quality` | `erpnext-quality` | 3001 |
| `main` / `prod` | `erpnext-main` | 3000 |

Apps live in [nando-erp-modules](https://github.com/Waste-NANDO/nando-erp-modules) (`dev` / `quality` / `master`).

IAM should deny `promote` / `release` / prod `backup` unless the caller is in the deploy role (`NANDO_ALLOW_PROD=1` for the API).
