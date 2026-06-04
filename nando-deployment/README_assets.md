# Syncing Desk assets (JS/CSS bundles)

How JS/CSS reach nginx in this Docker setup.

**Site:** `apps.internal.nandoai.com`  
**Stacks:** dev `:3003` (`erpnext`) · main `:3000` (`erpnext-main`)

---

## Default: you usually do nothing extra

With **`BUILD_ASSETS_IN_IMAGE=yes`** (default in `erpnext-*.env`):

1. **`bench build --production`** runs **inside `docker build`** → bundles live in `apps/*/public/dist/` in the image.
2. **`deploy-stack.sh`** or **`compose up -d`** → **configurator** runs **`materialize-assets.sh`** → copies into **`sites/assets/`** on the shared volume.
3. **`deploy-stack.sh`** clears Redis cache.

**Minimum deploy after code changes:**

```bash
./nando-deployment/deploy-stack.sh nando-deployment/erpnext-dev.env
```

No separate `setup-assets.sh` step unless Desk is still broken.

---

## Why materialize still exists

| Container | Role |
|-----------|------|
| **backend / frontend** | Same image: `apps/*/public/dist/` baked at build time |
| **frontend nginx** | Serves `/assets/*` from **`sites/assets/`** on the **persistent volume**, not from `apps/` |

The volume masks image `sites/` content. **Materialize** copies real files from `apps/` (in the image) → `sites/assets/` (on the volume) so nginx and backend agree.

---

## When to run `setup-assets.sh`

| Situation | Command |
|-----------|---------|
| Desk 404 / broken CSS after deploy | `./nando-deployment/setup-assets.sh <env>` |
| Changed **JS in custom app** without rebuilding image | `setup-assets.sh <env> --full` |
| `BUILD_ASSETS_IN_IMAGE=no` | `setup-assets.sh <env> --full` after each deploy |
| Normal deploy with in-image build | **Not needed** (configurator handles materialize) |

**Default** (`setup-assets.sh` without `--full`): materialize + clear-cache + restart frontend — **no runtime bench build**.

**`--full`:** runtime `bench build --force` + materialize + clear-cache + restart frontend (~10–15 min with HRMS).

---

## Manual sync (troubleshooting)

```bash
sudo docker compose --project-name erpnext -f nando-deployment/erpnext-dev.yaml exec backend \
  bash /home/frappe/frappe-bench/materialize-assets.sh

sudo docker compose --project-name erpnext -f nando-deployment/erpnext-dev.yaml exec backend \
  bench --site apps.internal.nandoai.com clear-cache

sudo docker compose --project-name erpnext -f nando-deployment/erpnext-dev.yaml restart frontend
```

Verify:

```bash
sudo docker compose --project-name erpnext -f nando-deployment/erpnext-dev.yaml exec frontend \
  ls sites/assets/frappe/dist/css/website.bundle.*.css | head -1
```

---

## Env vars

```env
BUILD_ASSETS_IN_IMAGE=yes           # bench build during docker build (default)
BENCH_BUILD_NODE_MEMORY_MB=6144     # Node heap during image build
BUILD_HRMS_FULL=0                   # 0 = skip HRMS PWA/roster in image (recommended)
MATERIALIZE_ASSETS_ON_START=1       # configurator materialize on compose up (default)
```

**HRMS note:** Full `bench build --production` runs `yarn build-pwa && yarn build-roster` for HRMS, which often fails in Docker (`yarn run production --run-build-command`). With `BUILD_HRMS_FULL=0` (default), the image build uses esbuild for HRMS **Desk** bundles only. HRMS in Desk usually works; separate HRMS PWA/roster UIs may need a one-time `setup-assets.sh --full` on the server if you use them.

Set `BUILD_HRMS_FULL=1` to attempt the full HRMS build in Docker (needs plenty of RAM; may still fail).

---

## Checking RAM before image build

On the VM during `docker build` or first trial:

```bash
free -h
grep MemAvailable /proc/meminfo
watch -n 2 'free -h | grep Mem'
```

Aim for **~8–12 GiB MemAvailable** when HRMS is in the image. Your e2-highmem-8 with ~34 GiB available is fine.

After OOM: `sudo dmesg -T | grep -i oom | tail -10`

---

## Troubleshooting

### Desk 404 on `/assets/*.bundle.*`

1. `./nando-deployment/setup-assets.sh nando-deployment/erpnext-dev.env`
2. Confirm backend and frontend share one **`sites` volume** ([DEPLOYMENT.md](../DEPLOYMENT.md))
3. `restart frontend`

### Server Script editor 404 (ace.js)

Materialize copies `ace-builds` into `sites/assets/frappe/node_modules/`. Run `setup-assets.sh` without `--full`.

### Symlinks vs copies

Symlinks under `sites/assets` → `apps/` break across containers when **`bench build` runs only in backend** at runtime. **In-image build + materialize** avoids that for normal deploys.

---

## Scripts

| Script | Purpose |
|--------|---------|
| [`deploy-stack.sh`](deploy-stack.sh) | Build + up + migrate + clear-cache |
| [`setup-assets.sh`](setup-assets.sh) | Re-sync volume; `--full` = runtime bench build |
| [`materialize-assets.sh`](materialize-assets.sh) | Copy `apps/*/public` → `sites/assets/` |

Related: [README_workspaces.md](README_workspaces.md), [DEPLOYMENT.md](../DEPLOYMENT.md)
