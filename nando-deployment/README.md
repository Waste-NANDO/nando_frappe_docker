# Nando deployment

Ops: **[../DEPLOYMENT.md](../DEPLOYMENT.md)**

| Env | Stack | Port | Compose project |
|-----|-------|------|-----------------|
| [`erpnext-dev.env`](erpnext-dev.env) | Dev | `:3003` | `erpnext` |
| [`erpnext-main.env`](erpnext-main.env) | Main | `:3000` | `erpnext-main` |

Passwords live on the server. PAT: copy [`github.env.example`](github.env.example) → `github.env`.

Generated `erpnext-*.yaml` are gitignored (secrets). Re-render after env changes.

```bash
./nando-deployment/build-custom-image.sh nando-deployment/erpnext-dev.env   # fetch + image + compose
./nando-deployment/deploy-stack.sh nando-deployment/erpnext-dev.env          # up + migrate (no rebuild)
./nando-deployment/deploy-stack.sh nando-deployment/erpnext-dev.env --with-build
```

| Script | Use |
|--------|-----|
| [`build-custom-image.sh`](build-custom-image.sh) | Fetch apps, docker build, render compose |
| [`deploy-stack.sh`](deploy-stack.sh) | Running stack; `--with-build` to rebuild first |
| [`sync-fixtures-dev-to-main.sh`](sync-fixtures-dev-to-main.sh) / [`-main-to-dev`](sync-fixtures-main-to-dev.sh) | Live Desk sync — [README_migrate_customizations.md](README_migrate_customizations.md) |
| [`fetch-custom-app.sh`](fetch-custom-app.sh) | Git checkout into `custom-apps/` only |
| [`render-compose.sh`](render-compose.sh) | Compose YAML only |
| [`setup-assets.sh`](setup-assets.sh) | Broken JS/CSS — [README_assets.md](README_assets.md) |

Branches: `NANDO_CRM_BRANCH` / `NANDO_FULFILLMENT_BRANCH` in the env file (`dev` vs `main`/`master`).

Also: [`docker_commands.md`](docker_commands.md) · [`README_workspaces.md`](README_workspaces.md) · [`README_customfields.md`](README_customfields.md)
