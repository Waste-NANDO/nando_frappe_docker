# Nando deployment assets

Operational guide: **[../DEPLOYMENT.md](../DEPLOYMENT.md)**

## Environment files

| File | Stack | Compose project |
|------|-------|-----------------|
| [`erpnext-dev.env`](erpnext-dev.env) | Dev `:3003`, custom app + HRMS | `erpnext` |
| [`erpnext-main.env`](erpnext-main.env) | Main `:3000`, ERPNext + HRMS | `erpnext-main` |

Edit passwords on the server. Do not commit real secrets.

GitHub PAT for private custom app repos: copy [`github.env.example`](github.env.example) to `github.env` (gitignored) or `export GITHUB_TOKEN=...`. See [DEPLOYMENT.md](../DEPLOYMENT.md#github-authentication).

## Scripts

Two-step workflow (recommended):

| Step | Script | What it does |
|------|--------|----------------|
| **1. Build** | [`build-custom-image.sh`](build-custom-image.sh) | Fetch custom apps → build Docker image → render compose YAML |
| **2. Deploy** | [`deploy-stack.sh`](deploy-stack.sh) | `compose up` → materialize assets → migrate → clear-cache → restart frontend |

```bash
# After app or env changes — rebuild image (~10–20 min), then deploy
./nando-deployment/build-custom-image.sh nando-deployment/erpnext-dev.env
./nando-deployment/deploy-stack.sh nando-deployment/erpnext-dev.env

# Config / fixture changes only — deploy existing image (fast)
./nando-deployment/deploy-stack.sh nando-deployment/erpnext-dev.env

# Rebuild + deploy in one command
./nando-deployment/deploy-stack.sh nando-deployment/erpnext-dev.env --with-build
```

| Script | Purpose |
|--------|---------|
| [`build-custom-image.sh`](build-custom-image.sh) | **Build only** — fetch apps, docker build, render compose (no `up`, no migrate) |
| [`deploy-stack.sh`](deploy-stack.sh) | **Deploy only** by default — running stack update; use `--with-build` to rebuild first |
| [`setup-assets.sh`](setup-assets.sh) | Re-sync assets to volume (materialize only by default; `--full` for runtime bench build) |
| [`render-compose.sh`](render-compose.sh) | Render compose YAML only (no fetch, no docker build) |
| [`fetch-custom-app.sh`](fetch-custom-app.sh) | Fetch/update apps into `custom-apps/<key>/` only |
| [`materialize-assets.sh`](materialize-assets.sh) | Copy `apps/*/public` (incl. `dist/`) into `sites/assets` on the shared volume |
| [`resolve-env.sh`](resolve-env.sh) | Shared env resolution (sourced by scripts) |

Default env resolution: explicit argument → `erpnext-dev.env`.

**App git branches:** set `NANDO_CRM_BRANCH` / `NANDO_FULFILLMENT_BRANCH` per env file (`dev` in `erpnext-dev.env`, `main` in `erpnext-main.env`). Fetch and build scripts read these automatically. Clones live under `custom-apps/<key>/` (one checkout per app; branch switches when you pass a different env file).

## Generated files (gitignored)

- `erpnext-dev.yaml` — dev stack (contains inlined secrets)
- `erpnext-main.yaml` — main stack

Regenerate after env or compose changes. Never commit.

## Quick reference

**Build** → [`build-custom-image.sh`](build-custom-image.sh)  
**Deploy** → [`deploy-stack.sh`](deploy-stack.sh)  
[`docker_commands.md`](docker_commands.md)  
[`README_assets.md`](README_assets.md) — asset troubleshooting  
[`README_workspaces.md`](README_workspaces.md) — public/private workspaces, roles, v16 Desk visibility  
[`README_migrate_customizations.md`](README_migrate_customizations.md) — dev → main: empty config app, fixtures, DocTypes, scripts
