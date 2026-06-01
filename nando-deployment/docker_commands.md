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

## Dev (port 3003, project `erpnext`)

```bash
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

# Shell
sudo docker compose --project-name erpnext -f nando-deployment/erpnext-dev.yaml exec backend bash
```

## Main (port 3000, project `erpnext-main`)

```bash
# Deploy / restart
sudo docker compose --project-name erpnext-main -f nando-deployment/erpnext-main.yaml up -d

# Stop (keeps volumes)
sudo docker compose --project-name erpnext-main -f nando-deployment/erpnext-main.yaml down

# Logs
sudo docker compose --project-name erpnext-main -f nando-deployment/erpnext-main.yaml logs -f backend
sudo docker compose --project-name erpnext-main -f nando-deployment/erpnext-main.yaml logs -f proxy

# Bench
sudo docker compose --project-name erpnext-main -f nando-deployment/erpnext-main.yaml exec backend \
  bench --site apps.internal.nandoai.com migrate

# Shell
sudo docker compose --project-name erpnext-main -f nando-deployment/erpnext-main.yaml exec backend bash
```

## Regenerate compose files

```bash
./nando-deployment/build-custom-image.sh nando-deployment/erpnext-dev.env
./nando-deployment/render-compose.sh nando-deployment/erpnext-main.env
```

See [DEPLOYMENT.md](../DEPLOYMENT.md) for full workflows.
