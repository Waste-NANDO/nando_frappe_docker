# Nando deployment

**Pipeline (start here):** **[PIPELINE.md](PIPELINE.md)** · **[guides/](guides/)**

Infrastructure detail: **[../DEPLOYMENT.md](../DEPLOYMENT.md)** · CLI: **[`../tools/nando_erp_ops`](../tools/nando_erp_ops)**

| Env | Port | Compose project | Env file | Apps branch |
|-----|------|-----------------|----------|-------------|
| Cloud-dev | `:3003` | `erpnext` | [`erpnext-dev.env`](erpnext-dev.env) | `dev` |
| Quality | `:3001` | `erpnext-quality` | [`erpnext-quality.env`](erpnext-quality.env) | `quality` |
| Prod | `:3000` | `erpnext-main` | [`erpnext-main.env`](erpnext-main.env) | `master` |

Shared pins: [`versions.env`](versions.env). Structure allowlist: [`structure.yaml`](structure.yaml).
Apps monorepo: [Waste-NANDO/nando-erp-modules](https://github.com/Waste-NANDO/nando-erp-modules).

## Active scripts (minimum set)

Prefer the `nando-erp` CLI; these are what it wraps:

| Script | Role |
|--------|------|
| [`build-custom-image.sh`](build-custom-image.sh) | Fetch apps, docker build, render compose |
| [`deploy-stack.sh`](deploy-stack.sh) | up → materialize assets → migrate |
| [`fetch-custom-app.sh`](fetch-custom-app.sh) | Clone monorepo + materialize `custom-apps/` |
| [`render-compose.sh`](render-compose.sh) | Compose YAML only |
| [`refresh-from-gcs.sh`](refresh-from-gcs.sh) | Restore prod SQL from GCS (`nando-erp refresh`) |
| [`setup-assets.sh`](setup-assets.sh) | Remediation if Desk assets are broken |
| [`backup-to-gcs.sh`](backup-to-gcs.sh) / [`upload-to-gcs.py`](upload-to-gcs.py) | Backup sidecar |
| [`materialize-assets.sh`](materialize-assets.sh) / [`rewrite-assets-manifest.py`](rewrite-assets-manifest.py) / [`sync-assets-manifest.sh`](sync-assets-manifest.sh) | Mounted into containers on deploy |
| [`build-assets-in-image.sh`](build-assets-in-image.sh) | Runs inside Docker image build |
| [`resolve-env.sh`](resolve-env.sh) | Shared helpers |
| [`cron/quality-refresh.sh`](cron/quality-refresh.sh) | Weekly Quality refresh (host cron after cutover) |

```bash
nando-erp build --stack dev && nando-erp deploy dev
nando-erp build --stack quality && nando-erp deploy quality
nando-erp promote --from quality --to main --yes
nando-erp release --yes
```

## Docs layout

| Path | Contents |
|------|----------|
| [PIPELINE.md](PIPELINE.md) | High-level flow |
| [guides/](guides/) | Step-by-step recipes |
| [PHASE0_BASELINE.md](PHASE0_BASELINE.md) | One-time prod → git baseline |
| [reference/](reference/) | Assets, custom fields, workspaces, raw compose snippets |
| [deprecated/](deprecated/) | Old live-DB sync scripts and docs — **do not use** |

Passwords live on the server. PAT: copy [`github.env.example`](github.env.example) → `github.env`. Generated `erpnext-*.yaml` are gitignored.
