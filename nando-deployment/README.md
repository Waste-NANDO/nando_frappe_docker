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
| [`build-custom-image.sh`](build-custom-image.sh) | Fetch app (if enabled), build image (ERPNext + optional custom app + HRMS), render compose |
| [`render-compose.sh`](render-compose.sh) | Render compose YAML only |
| [`fetch-custom-app.sh`](fetch-custom-app.sh) | Clone/update apps into `custom-apps/<key>/` (reads `CUSTOM_APP_KEYS`) |
| [`materialize-assets.sh`](materialize-assets.sh) | Copy `apps/*/public` (incl. `dist/`) into `sites/assets` on the shared volume |
| [`setup-assets.sh`](setup-assets.sh) | `bench build --force` + materialize + clear-cache (run on VM after deploy) |
| [`resolve-env.sh`](resolve-env.sh) | Shared env resolution (sourced by scripts) |

Default env resolution: argument → `erpnext-dev.env` → `erpnext.env`.

## Generated files (gitignored)

- `erpnext-dev.yaml` — dev stack (contains inlined secrets)
- `erpnext-main.yaml` — main stack

Regenerate after env or compose changes. Never commit.

## Quick reference

[`docker_commands.md`](docker_commands.md)  
[`README_workspaces.md`](README_workspaces.md) — public/private workspaces, roles, v16 Desk visibility  
[`README_migrate_customizations.md`](README_migrate_customizations.md) — dev → main: empty config app, fixtures, DocTypes, scripts
