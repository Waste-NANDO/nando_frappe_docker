# Nando deployment assets

Operational guide: **[../DEPLOYMENT.md](../DEPLOYMENT.md)**

## Environment files

| File | Stack | Compose project |
|------|-------|-----------------|
| [`erpnext-dev.env`](erpnext-dev.env) | Dev `:3003`, custom app + HRMS | `erpnext` |
| [`erpnext-main.env`](erpnext-main.env) | Main `:3000`, ERPNext + HRMS | `erpnext-main` |
| [`erpnext.env`](erpnext.env) | Legacy dev alias | `erpnext` |

Edit passwords on the server. Do not commit real secrets.

GitHub PAT for private custom app repos: copy [`github.env.example`](github.env.example) to `github.env` (gitignored) or `export GITHUB_TOKEN=...`. See [DEPLOYMENT.md](../DEPLOYMENT.md#github-authentication).

## Scripts

| Script | Purpose |
|--------|---------|
| [`deploy-stack.sh`](deploy-stack.sh) | **Default deploy:** build image + `up -d` + migrate + clear-cache |
| [`build-custom-image.sh`](build-custom-image.sh) | Fetch apps (if enabled), build image (includes asset compile when `BUILD_ASSETS_IN_IMAGE=yes`), render compose |
| [`setup-assets.sh`](setup-assets.sh) | Re-sync assets to volume (materialize only by default; `--full` for runtime bench build) |
| [`render-compose.sh`](render-compose.sh) | Render compose YAML only |
| [`fetch-custom-app.sh`](fetch-custom-app.sh) | Clone/update apps into `custom-apps/<key>/` (reads `CUSTOM_APP_KEYS`) |
| [`materialize-assets.sh`](materialize-assets.sh) | Copy `apps/*/public` (incl. `dist/`) into `sites/assets` on the shared volume |
| [`resolve-env.sh`](resolve-env.sh) | Shared env resolution (sourced by scripts) |

Default env resolution: argument → `erpnext-dev.env` → `erpnext.env`.

**App git branches:** set `NANDO_CRM_BRANCH` / `NANDO_FULFILLMENT_BRANCH` per env file (`dev` in `erpnext-dev.env`, `main` in `erpnext-main.env`). Fetch and build scripts read these automatically. Clones live under `custom-apps/<key>/` (one checkout per app; branch switches when you pass a different env file).

## Generated files (gitignored)

- `erpnext-dev.yaml` — dev stack (contains inlined secrets)
- `erpnext-main.yaml` — main stack

Regenerate after env or compose changes. Never commit.

## Quick reference

[`deploy-stack.sh`](deploy-stack.sh) — **usual deploy**  
[`docker_commands.md`](docker_commands.md)  
[`README_assets.md`](README_assets.md) — asset troubleshooting  
[`README_workspaces.md`](README_workspaces.md) — public/private workspaces, roles, v16 Desk visibility  
[`README_migrate_customizations.md`](README_migrate_customizations.md) — dev → main: empty config app, fixtures, DocTypes, scripts
