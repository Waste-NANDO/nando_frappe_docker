# Docker command reference

Site name for both stacks: `apps.internal.nandoai.com`

## HRMS (after image rebuild with `INCLUDE_HRMS=yes`)

Dev:

```bash
sudo docker compose --project-name erpnext -f nando-deployment/erpnext-dev.yaml exec backend \
  bench --site apps.internal.nandoai.com install-app hrms
sudo docker compose --project-name erpnext -f nando-deployment/erpnext-dev.yaml exec backend \
  bench --site apps.internal.nandoai.com migrate
```

Main:

```bash
sudo docker compose --project-name erpnext-main -f nando-deployment/erpnext-main.yaml exec backend \
  bench --site apps.internal.nandoai.com install-app hrms
sudo docker compose --project-name erpnext-main -f nando-deployment/erpnext-main.yaml exec backend \
  bench --site apps.internal.nandoai.com migrate
```

See [DEPLOYMENT.md](../DEPLOYMENT.md) for full build/redeploy steps.

## Deploy (default — after app or env changes)

```bash
# Bump CUSTOM_TAG in erpnext-dev.env when the image contents change, then:
./nando-deployment/deploy-stack.sh nando-deployment/erpnext-dev.env
```

This runs: **build image** (includes `bench build` when `BUILD_ASSETS_IN_IMAGE=yes`) → **`up -d`** (configurator materializes assets) → **migrate** → **clear-cache**.

Redeploy only (no rebuild):

```bash
./nando-deployment/deploy-stack.sh nando-deployment/erpnext-dev.env --skip-build
```

Schema/fixtures only (no new image):

```bash
./nando-deployment/deploy-stack.sh nando-deployment/erpnext-dev.env --skip-build --skip-migrate
# or just: bench migrate + clear-cache
```

If Desk assets are still broken after deploy:

```bash
./nando-deployment/setup-assets.sh nando-deployment/erpnext-dev.env
# runtime bench build (JS changed without image rebuild):
./nando-deployment/setup-assets.sh nando-deployment/erpnext-dev.env --full
```

## Dev (port 3003, project `erpnext`)

```bash
# Install custom apps (once per site; skip already installed)
sudo docker compose --project-name erpnext -f nando-deployment/erpnext-dev.yaml exec backend \
  bench --site apps.internal.nandoai.com install-app nando_crm nando_fulfillment

# Deploy / restart
sudo docker compose --project-name erpnext -f nando-deployment/erpnext-dev.yaml up -d

# Stop (keeps volumes)
sudo docker compose --project-name erpnext -f nando-deployment/erpnext-dev.yaml down

# Logs
sudo docker compose --project-name erpnext -f nando-deployment/erpnext-dev.yaml logs -f backend
sudo docker compose --project-name erpnext -f nando-deployment/erpnext-dev.yaml logs -f proxy

# Bench
sudo docker compose --project-name erpnext -f nando-deployment/erpnext-dev.yaml exec backend \
  bench --site apps.internal.nandoai.com migrate

# Rebuild frontend bundles — only if Desk broken after deploy, or JS changed without image rebuild
./nando-deployment/setup-assets.sh nando-deployment/erpnext-dev.env
# Force runtime bench build + materialize:
./nando-deployment/setup-assets.sh nando-deployment/erpnext-dev.env --full

# Shell
sudo docker compose --project-name erpnext -f nando-deployment/erpnext-dev.yaml exec backend bash
```

## Main (port 3000, project `erpnext-main`)

```bash
./nando-deployment/deploy-stack.sh nando-deployment/erpnext-main.env

# Install nando_crm (once per site)
sudo docker compose --project-name erpnext-main -f nando-deployment/erpnext-main.yaml exec backend \
  bench --site apps.internal.nandoai.com install-app nando_crm

# Stop (keeps volumes)
sudo docker compose --project-name erpnext-main -f nando-deployment/erpnext-main.yaml down

# Logs
sudo docker compose --project-name erpnext-main -f nando-deployment/erpnext-main.yaml logs -f backend

# Asset re-sync if Desk broken
./nando-deployment/setup-assets.sh nando-deployment/erpnext-main.env

# Shell
sudo docker compose --project-name erpnext-main -f nando-deployment/erpnext-main.yaml exec backend bash
```

## Regenerate compose files

```bash
./nando-deployment/build-custom-image.sh nando-deployment/erpnext-dev.env
./nando-deployment/render-compose.sh nando-deployment/erpnext-main.env
```

See [DEPLOYMENT.md](../DEPLOYMENT.md) for full workflows.
