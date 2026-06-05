# Docker command reference

Site name for both stacks: `apps.internal.nandoai.com`

## HRMS (after image rebuild with `INCLUDE_HRMS=yes`)

Dev:

```bash
docker compose --project-name erpnext -f nando-deployment/erpnext-dev.yaml exec backend \
  bench --site apps.internal.nandoai.com install-app hrms
docker compose --project-name erpnext -f nando-deployment/erpnext-dev.yaml exec backend \
  bench --site apps.internal.nandoai.com migrate
```

Main:

```bash
docker compose --project-name erpnext-main -f nando-deployment/erpnext-main.yaml exec backend \
  bench --site apps.internal.nandoai.com install-app hrms
docker compose --project-name erpnext-main -f nando-deployment/erpnext-main.yaml exec backend \
  bench --site apps.internal.nandoai.com migrate
```

See [DEPLOYMENT.md](../DEPLOYMENT.md) for full build/redeploy steps.

## Build and deploy

| Step | Command | Duration |
|------|---------|----------|
| **Build** (app/image changes) | `./nando-deployment/build-custom-image.sh nando-deployment/erpnext-dev.env` | ~10–20 min |
| **Deploy** (start stack, migrate) | `./nando-deployment/deploy-stack.sh nando-deployment/erpnext-dev.env` | minutes |

Bump `CUSTOM_TAG` in `erpnext-dev.env` when image contents change, then **build**, then **deploy**.

**Build** — fetch custom apps, `docker build`, render compose YAML. Does not run containers.

**Deploy** — `compose up -d`, materialize assets, migrate, clear-cache, restart frontend. Does not rebuild the image (use `--with-build` for the old all-in-one behaviour).

```bash
# Full cycle after app changes
./nando-deployment/build-custom-image.sh nando-deployment/erpnext-dev.env
./nando-deployment/deploy-stack.sh nando-deployment/erpnext-dev.env

# Redeploy only (fixtures, migrate, cache — no rebuild)
./nando-deployment/deploy-stack.sh nando-deployment/erpnext-dev.env

# Rebuild + deploy in one command
./nando-deployment/deploy-stack.sh nando-deployment/erpnext-dev.env --with-build

# Deploy without migrate
./nando-deployment/deploy-stack.sh nando-deployment/erpnext-dev.env --skip-migrate
```

If Desk assets are still broken after deploy:

```bash
./nando-deployment/setup-assets.sh nando-deployment/erpnext-dev.env
# runtime bench build (JS changed without image rebuild):
./nando-deployment/setup-assets.sh nando-deployment/erpnext-dev.env --full
```

## Dev (port 3003, project `erpnext`)

Run `docker compose` from the **repo root** (`nando_frappe_docker/`), or pass `--project-directory .` — bind mounts use `./nando-deployment/...` paths.

Prefer `./nando-deployment/deploy-stack.sh` over raw `compose up` (materialize, migrate, cache).

```bash
# Install custom apps (once per site; skip already installed)
docker compose --project-name erpnext --project-directory . \
  -f nando-deployment/erpnext-dev.yaml exec backend \
  bench --site apps.internal.nandoai.com install-app nando_crm nando_fulfillment

# Deploy / restart (prefer deploy-stack.sh instead)
docker compose --project-name erpnext --project-directory . \
  -f nando-deployment/erpnext-dev.yaml up -d

# Stop (keeps volumes)
docker compose --project-name erpnext -f nando-deployment/erpnext-dev.yaml down

# Logs
docker compose --project-name erpnext -f nando-deployment/erpnext-dev.yaml logs -f backend
docker compose --project-name erpnext -f nando-deployment/erpnext-dev.yaml logs -f proxy

# Bench
docker compose --project-name erpnext -f nando-deployment/erpnext-dev.yaml exec backend \
  bench --site apps.internal.nandoai.com migrate

# Rebuild frontend bundles — only if Desk broken after deploy, or JS changed without image rebuild
./nando-deployment/setup-assets.sh nando-deployment/erpnext-dev.env
# Force runtime bench build + materialize:
./nando-deployment/setup-assets.sh nando-deployment/erpnext-dev.env --full

# Shell
docker compose --project-name erpnext -f nando-deployment/erpnext-dev.yaml exec backend bash
```

## Main (port 3000, project `erpnext-main`)

```bash
./nando-deployment/deploy-stack.sh nando-deployment/erpnext-main.env

# Install nando_crm (once per site)
docker compose --project-name erpnext-main -f nando-deployment/erpnext-main.yaml exec backend \
  bench --site apps.internal.nandoai.com install-app nando_crm

# Stop (keeps volumes)
docker compose --project-name erpnext-main -f nando-deployment/erpnext-main.yaml down

# Logs
docker compose --project-name erpnext-main -f nando-deployment/erpnext-main.yaml logs -f backend

# Asset re-sync if Desk broken
./nando-deployment/setup-assets.sh nando-deployment/erpnext-main.env

# Shell
docker compose --project-name erpnext-main -f nando-deployment/erpnext-main.yaml exec backend bash
```

## Regenerate compose files

```bash
./nando-deployment/build-custom-image.sh nando-deployment/erpnext-dev.env
./nando-deployment/render-compose.sh nando-deployment/erpnext-main.env
```

See [DEPLOYMENT.md](../DEPLOYMENT.md) for full workflows.
