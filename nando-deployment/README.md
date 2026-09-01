# Nando deployment

Ops: **[../DEPLOYMENT.md](../DEPLOYMENT.md)**

| Env | Stack | Port | Compose project |
|-----|-------|------|-----------------|
| [`erpnext-dev.env`](erpnext-dev.env) | Dev | `:3003` | `erpnext` |
| [`erpnext-main.env`](erpnext-main.env) | Main | `:3000` | `erpnext-main` |

Passwords live on the server. PAT: copy [`github.env.example`](github.env.example) → `github.env`.

Generated `erpnext-*.yaml` are gitignored (secrets). Re-render after env changes.

```bash
./nando-deployment/build-custom-image.sh nando-deployment/erpnext-dev.env   # image + compose; no up
./nando-deployment/deploy-stack.sh nando-deployment/erpnext-dev.env          # up + migrate; no rebuild
./nando-deployment/deploy-stack.sh nando-deployment/erpnext-dev.env --with-build
```

## `build-custom-image.sh <env>`

Prepares the Docker image and compose file. **Does not** start containers, migrate, or `install-app`.

1. If `INCLUDE_CUSTOM_APP=yes`: [`fetch-custom-app.sh`](fetch-custom-app.sh) clones/updates `custom-apps/<app>` on the branch from the env (`NANDO_CRM_BRANCH`, …).
2. Writes `apps.json` (ERPNext + those apps + HRMS if `INCLUDE_HRMS=yes`).
3. `docker build` → `CUSTOM_IMAGE:CUSTOM_TAG` (Desk assets compiled in the image when `BUILD_ASSETS_IN_IMAGE=yes`).
4. Renders `erpnext-dev.yaml` / `erpnext-main.yaml`.

Use after `hooks.py` / Python / ERPNext version / HRMS pin changes. Bump `CUSTOM_TAG` when image contents change (`PULL_POLICY=never`). HRMS and custom apps still need a one-time `bench install-app` on the site.

## `deploy-stack.sh <env>`

Updates the **running** stack using the existing image. **Does not** rebuild unless `--with-build`.

1. `compose up -d` (wait for configurator).
2. Copy JS/CSS from the image onto the `sites` volume (materialize) and check `assets.json`.
3. Stop workers → `bench migrate` → start workers (`--skip-migrate` to skip).
4. Clear cache, restart frontend, re-check assets.

`--with-build` runs `build-custom-image.sh` first. `migrate` will force-import any fixture JSON **in the image** — do not use deploy to copy Desk UI edits ([README_migrate_customizations.md](README_migrate_customizations.md)).

| Script | Use |
|--------|-----|
| [`build-custom-image.sh`](build-custom-image.sh) | Fetch apps, docker build, render compose — see above |
| [`deploy-stack.sh`](deploy-stack.sh) | `up` + assets + migrate — see above; `--with-build` to rebuild first |
| [`sync-fixtures-dev-to-main.sh`](sync-fixtures-dev-to-main.sh) / [`-main-to-dev`](sync-fixtures-main-to-dev.sh) | Live Desk sync — [README_migrate_customizations.md](README_migrate_customizations.md) |
| [`fetch-custom-app.sh`](fetch-custom-app.sh) | Git checkout into `custom-apps/` only |
| [`render-compose.sh`](render-compose.sh) | Compose YAML only |
| [`setup-assets.sh`](setup-assets.sh) | Broken JS/CSS — [README_assets.md](README_assets.md) |

Branches: `NANDO_CRM_BRANCH` / `NANDO_FULFILLMENT_BRANCH` in the env file (`dev` vs `main`/`master`).

Also: [`docker_commands.md`](docker_commands.md) · [`README_workspaces.md`](README_workspaces.md) · [`README_customfields.md`](README_customfields.md)
