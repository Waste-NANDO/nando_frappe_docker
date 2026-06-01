# NandoAI ERPNext Deployment Guide

Two isolated Frappe/ERPNext stacks on one server:

| Stack | URL | Compose project | Purpose |
|-------|-----|-----------------|--------|
| **Dev** | `https://apps.internal.nandoai.com:3003` | `erpnext` | Custom app, Desk customizations, test data |
| **Main** | `https://apps.internal.nandoai.com:3000` | `erpnext-main` | Stock ERPNext, fresh site (no custom app yet) |

Both use the same hostname and Frappe site name (`apps.internal.nandoai.com`). Isolation is by **port**, **Compose project**, and **separate volumes** (MariaDB + `sites`).

Canonical ops reference for this repo. Upstream Frappe Docker docs live under [`docs/`](docs/).

## Architecture

```
Browser :3003  →  Traefik (project erpnext)       →  frontend → backend → MariaDB (erpnext_db-data)
Browser :3000  →  Traefik (project erpnext-main) →  frontend → backend → MariaDB (erpnext-main_db-data)
```

Each stack has its own Traefik, Redis, workers, scheduler, and backup sidecar. Traefik is constrained to its Compose project via Docker labels (see [Traefik isolation](#traefik-isolation)).

## File layout

```
nando-deployment/
├── certs/                    # TLS (key.pem, nando-erp-server.crt — gitignored)
├── compose.custom-tls.yaml   # Traefik + per-project routing
├── compose.backup.yaml       # GCS backup sidecar
├── erpnext-dev.env           # Dev configuration (edit passwords on server)
├── erpnext-main.env          # Main configuration
├── erpnext.env                 # Legacy dev alias (scripts still accept it)
├── erpnext-dev.yaml            # Generated dev compose (gitignored — contains secrets)
├── erpnext-main.yaml           # Generated main compose (gitignored)
├── build-custom-image.sh       # Build dev image + render dev compose
├── render-compose.sh           # Render compose only (main or after env edits)
├── fetch-custom-app.sh         # Clone/update custom app (dev only)
├── resolve-env.sh              # Shared env file resolution
├── docker_commands.md          # Quick command reference
└── README.md                   # Index of scripts and env files
```

## Prerequisites

- Docker Engine and Docker Compose v2
- Private CA files in `nando-deployment/certs/`: `key.pem`, `nando-erp-server.crt`
- For dev custom app build: SSH agent with GitHub deploy key for `nando-erpnext-module`

## Environment files

Edit on the server (never commit real passwords). Templates are committed with `CHANGE_ME_*` placeholders.

### Dev — `nando-deployment/erpnext-dev.env`

| Variable | Typical value |
|----------|----------------|
| `COMPOSE_PROJECT_NAME` | `erpnext` (keeps existing `erpnext_*` volumes) |
| `COMPOSE_FILE_OUTPUT` | `nando-deployment/erpnext-dev.yaml` |
| `HTTPS_PUBLISH_PORT` | `3003` |
| `FRAPPE_HOST_NAME` | `https://apps.internal.nandoai.com:3003` |
| `INCLUDE_CUSTOM_APP` | `yes` |
| `APP_NAME` | `nando-erp-dev` (GCS backup path prefix) |
| `TRAEFIK_ROUTER_PREFIX` | `erpnext` |
| `TRAEFIK_HOST_RULE` | `'Host(\`apps.internal.nandoai.com\`)'` |

### Main — `nando-deployment/erpnext-main.env`

| Variable | Typical value |
|----------|----------------|
| `COMPOSE_PROJECT_NAME` | `erpnext-main` |
| `COMPOSE_FILE_OUTPUT` | `nando-deployment/erpnext-main.yaml` |
| `HTTPS_PUBLISH_PORT` | `3000` |
| `FRAPPE_HOST_NAME` | `https://apps.internal.nandoai.com:3000` |
| `INCLUDE_CUSTOM_APP` | `no` |
| `CUSTOM_IMAGE` / `CUSTOM_TAG` | `frappe/erpnext` / `v16.5.0` |
| `APP_NAME` | `nando-erp-main` |
| `DB_PASSWORD` | **Different** from dev |

### Legacy `erpnext.env`

Same shape as `erpnext-dev.env`. Scripts prefer `erpnext-dev.env` when no file argument is passed; `erpnext.env` still works with a deprecation note.

## Generated compose files (security)

`docker compose config` writes **inlined secrets** (e.g. `DB_PASSWORD`) into `erpnext-dev.yaml` and `erpnext-main.yaml`.

- Both files are **gitignored** — never commit them.
- Regenerate after any env or compose change.

```bash
./nando-deployment/render-compose.sh nando-deployment/erpnext-main.env
# or for dev after image build:
./nando-deployment/build-custom-image.sh nando-deployment/erpnext-dev.env
```

## Traefik isolation

Each stack runs its own Traefik container bound to a different host port. [`compose.custom-tls.yaml`](nando-deployment/compose.custom-tls.yaml) configures:

1. **Docker provider constraint** — only containers from the same Compose project:
   `Label(\`com.docker.compose.project\`,\`<COMPOSE_PROJECT_NAME>\`)`
2. **Unique router names** — `TRAEFIK_ROUTER_PREFIX` (e.g. `erpnext-https` vs `erpnext-main-https`)
3. **Host rule** — `TRAEFIK_HOST_RULE` (default `Host(\`apps.internal.nandoai.com\`)`)

Two Traefik processes on one host is expected. Unrelated containers on the host may still appear in Traefik logs (harmless if constraints are correct).

## Same hostname and browser cookies

Session cookies are scoped by **domain**, not port. Using dev (`:3003`) and main (`:3000`) in the **same browser profile** can confuse or overwrite sessions.

Mitigations:

- Separate browser profiles (e.g. “ERP Dev” vs “ERP Main”)
- Different browsers per stack
- Private/incognito when switching
- Log out before switching ports
- Bookmark full URLs including the port

## Dev deployment

### 1. Configure env

```bash
nano nando-deployment/erpnext-dev.env
# Set DB_PASSWORD, GCS_BUCKET, CUSTOM_APP_* as needed
```

### 2. Build image and render compose

```bash
eval "$(ssh-agent -s)"
ssh-add ~/.ssh/<github-key>

./nando-deployment/build-custom-image.sh nando-deployment/erpnext-dev.env
```

This fetches `custom-app-src`, builds `nando-erpnext-custom:<tag>`, and writes `nando-deployment/erpnext-dev.yaml`.

### 3. Deploy

```bash
sudo docker compose --project-name erpnext -f nando-deployment/erpnext-dev.yaml up -d
```

### 4. Site (existing or new)

Existing server with site already created — skip `new-site`.

New site:

```bash
sudo docker compose --project-name erpnext -f nando-deployment/erpnext-dev.yaml exec backend \
  bench new-site \
    --mariadb-user-host-login-scope='%' \
    --db-root-password 'YOUR_DB_PASSWORD' \
    --install-app erpnext \
    --admin-password 'YOUR_ADMIN_PASSWORD' \
    --set-default \
    apps.internal.nandoai.com
```

Install custom app once:

```bash
sudo docker compose --project-name erpnext -f nando-deployment/erpnext-dev.yaml exec backend \
  bench --site apps.internal.nandoai.com install-app nando_fulfillment
```

### 5. Enable Server Scripts (dev)

```bash
sudo docker compose --project-name erpnext -f nando-deployment/erpnext-dev.yaml exec backend \
  bench set-config -g server_script_enabled 1

sudo docker compose --project-name erpnext -f nando-deployment/erpnext-dev.yaml restart backend
```

## Main deployment

### 1. Configure env

```bash
nano nando-deployment/erpnext-main.env
# Set CHANGE_ME_MAIN_DB_PASSWORD, GCS_BUCKET
```

### 2. Render compose (no custom image build)

```bash
./nando-deployment/render-compose.sh nando-deployment/erpnext-main.env
```

### 3. Firewall

Allow **TCP 3000** from your VPC (same pattern as 3003).

### 4. Deploy

```bash
sudo docker compose --project-name erpnext-main -f nando-deployment/erpnext-main.yaml up -d
```

### 5. Create empty site (ERPNext only)

```bash
sudo docker compose --project-name erpnext-main -f nando-deployment/erpnext-main.yaml exec backend \
  bench new-site \
    --mariadb-user-host-login-scope='%' \
    --db-root-password 'YOUR_MAIN_DB_PASSWORD' \
    --install-app erpnext \
    --admin-password 'YOUR_ADMIN_PASSWORD' \
    --set-default \
    apps.internal.nandoai.com
```

No `install-app` for the custom app on main until you enable it (see [Promoting customizations](#promoting-customizations-to-main)).

### 6. Verify

```bash
curl -k https://apps.internal.nandoai.com:3000
```

## Operating both stacks

See [`nando-deployment/docker_commands.md`](nando-deployment/docker_commands.md).

| Action | Dev | Main |
|--------|-----|------|
| Up | `compose -p erpnext -f nando-deployment/erpnext-dev.yaml up -d` | `compose -p erpnext-main -f nando-deployment/erpnext-main.yaml up -d` |
| Down | same with `down` | same with `down` |
| Logs | `logs -f backend` | `logs -f backend` |
| Bench | `exec backend bench --site apps.internal.nandoai.com …` | same on main yaml |

**Never** run `docker compose down -v` in production (destroys volumes).

## Custom app workflow (dev)

1. Set `CUSTOM_APP_BRANCH` in `erpnext-dev.env` if needed (e.g. `develop`).
2. `./nando-deployment/fetch-custom-app.sh nando-deployment/erpnext-dev.env`
3. Bump `CUSTOM_TAG`, rebuild: `./nando-deployment/build-custom-image.sh nando-deployment/erpnext-dev.env`
4. Redeploy dev stack.
5. `bench --site apps.internal.nandoai.com migrate`

App code must live in the **image** (`apps.json` at build time), not only inside a running container.

## Promoting customizations to main

Dev Desk changes (Custom Fields, Server Scripts, etc.) live in the **dev database**. They do not copy to main automatically.

**Recommended path:**

1. Add fixture types to `hooks.py` in `nando-erpnext-module`:

   ```python
   fixtures = [
       "Custom Field",
       "Property Setter",
       "Custom Script",
       "Client Script",
       "Server Script",
   ]
   ```

2. On dev:

   ```bash
   sudo docker compose --project-name erpnext -f nando-deployment/erpnext-dev.yaml exec backend \
     bench --site apps.internal.nandoai.com export-fixtures
   ```

3. Commit fixture JSON in the custom app repo; merge branch (`develop` → `main`).

4. When ready on main: set `INCLUDE_CUSTOM_APP=yes` in `erpnext-main.env`, rebuild image, `install-app nando_fulfillment`, `migrate` / `import-fixtures`.

Transactional data (customers, orders, stock) requires explicit export/import — not fixtures.

## Backups

Backup sidecar uses `APP_NAME` and `ERPNEXT_VERSION` for GCS paths:

`gs://<GCS_BUCKET>/<APP_NAME>/<ERPNEXT_VERSION>/<timestamp>/`

- Dev: `APP_NAME=nando-erp-dev`
- Main: `APP_NAME=nando-erp-main`

Optional override: set `GCS_PREFIX` in the env file (see [`compose.backup.yaml`](nando-deployment/compose.backup.yaml)).

Manual backup:

```bash
sudo docker compose --project-name erpnext -f nando-deployment/erpnext-dev.yaml exec backend \
  bench --site apps.internal.nandoai.com backup --with-files
```

## Upgrades

### Dev (custom image)

1. Update `ERPNEXT_VERSION` and `CUSTOM_TAG` in `erpnext-dev.env`
2. `./nando-deployment/fetch-custom-app.sh nando-deployment/erpnext-dev.env`
3. `./nando-deployment/build-custom-image.sh nando-deployment/erpnext-dev.env`
4. `docker compose … up -d`
5. `bench --site apps.internal.nandoai.com migrate`

### Main (official image)

1. Update `ERPNEXT_VERSION` / `CUSTOM_TAG` in `erpnext-main.env`
2. `./nando-deployment/render-compose.sh nando-deployment/erpnext-main.env`
3. `docker compose … pull` (if `PULL_POLICY` allows) and `up -d`
4. `bench --site apps.internal.nandoai.com migrate`

## Migrating an existing single-stack server

If you already run project `erpnext` on port 3003:

1. Copy `erpnext.env` → `erpnext-dev.env` (or use the committed template + your passwords).
2. Ensure `COMPOSE_PROJECT_NAME=erpnext` and `HTTPS_PUBLISH_PORT=3003`.
3. Rebuild/render with Traefik constraints: `./nando-deployment/build-custom-image.sh nando-deployment/erpnext-dev.env`
4. Redeploy: `compose -p erpnext -f nando-deployment/erpnext-dev.yaml up -d` — volumes unchanged.
5. Bootstrap main separately (new project `erpnext-main`, port 3000).

## Frappe HRMS

HRMS is baked into the image when `INCLUDE_HRMS=yes` in the env file ([`build-custom-image.sh`](nando-deployment/build-custom-image.sh) adds `frappe/hrms` to `apps.json`). Install on each **site** once with `bench install-app hrms`.

| Stack | Image contents | Env file |
|-------|----------------|----------|
| Dev | ERPNext + custom app + HRMS | `erpnext-dev.env` |
| Main | ERPNext + HRMS (no custom app yet) | `erpnext-main.env` |

Env variables:

```env
INCLUDE_HRMS=yes
HRMS_BRANCH=v16.5.0
FRAPPE_BRANCH=version-16
```

`ERPNEXT_VERSION` (e.g. `v16.5.0`) is the ERPNext **git** tag in `apps.json`. `FRAPPE_BRANCH` must be `version-16` for `frappe/build` and `frappe/base` Docker images — do not set it to `v16.5.0`.

**Pin `HRMS_BRANCH` to the same tag as `ERPNEXT_VERSION`** (e.g. both `v16.5.0`). The moving `version-16` branch can install HRMS 16.7.x against ERPNext 16.5.0 and break setup (e.g. `AttributeError: repost_allowed_types` on Accounts Settings). When you bump ERPNext, bump `HRMS_BRANCH` and rebuild the image.

### Users and data between stacks

Dev and main do **not** share users, employees, or HR records. Each stack has its own database. Install HRMS on both sites separately; configure employees/users on each environment as needed.

### Rollout on dev (`:3003`)

1. Set `INCLUDE_HRMS=yes` and bump `CUSTOM_TAG` in `erpnext-dev.env` (e.g. `v16.5.0-custom-hrms`).
2. Build and redeploy:

```bash
sudo ./nando-deployment/fetch-custom-app.sh nando-deployment/erpnext-dev.env
sudo ./nando-deployment/build-custom-image.sh nando-deployment/erpnext-dev.env
sudo docker compose --project-name erpnext -f nando-deployment/erpnext-dev.yaml up -d
```

3. Install HRMS on the existing site:

```bash
sudo docker compose --project-name erpnext -f nando-deployment/erpnext-dev.yaml exec backend \
  bench --site apps.internal.nandoai.com install-app hrms

sudo docker compose --project-name erpnext -f nando-deployment/erpnext-dev.yaml exec backend \
  bench --site apps.internal.nandoai.com migrate
```

### Rollout on main (`:3000`)

1. Set in `erpnext-main.env`: `INCLUDE_HRMS=yes`, `CUSTOM_IMAGE=nando-erpnext-main`, `CUSTOM_TAG=v16.5.0-hrms`, `PULL_POLICY=never`.
2. Build and redeploy (no custom app fetch):

```bash
sudo ./nando-deployment/build-custom-image.sh nando-deployment/erpnext-main.env
sudo docker compose --project-name erpnext-main -f nando-deployment/erpnext-main.yaml up -d
```

3. Install HRMS:

```bash
sudo docker compose --project-name erpnext-main -f nando-deployment/erpnext-main.yaml exec backend \
  bench --site apps.internal.nandoai.com install-app hrms

sudo docker compose --project-name erpnext-main -f nando-deployment/erpnext-main.yaml exec backend \
  bench --site apps.internal.nandoai.com migrate
```

4. Enable scheduler on main if needed: `bench --site apps.internal.nandoai.com enable-scheduler`.

### Verify

```bash
sudo docker compose --project-name erpnext -f nando-deployment/erpnext-dev.yaml exec backend \
  bench --site apps.internal.nandoai.com list-apps
# expect hrms among installed apps

sudo docker compose --project-name erpnext-main -f nando-deployment/erpnext-main.yaml exec backend \
  bench --site apps.internal.nandoai.com list-apps
```

HR workspaces should appear in Desk on both ports after install.

## Troubleshooting

### Broken Desk / 404 on `/assets/*.bundle.*` (split `sites/assets` volumes)

**Symptom:** Browser 404 + MIME `text/html` for CSS/JS; `docker inspect` shows **different** anonymous volume IDs at `/home/frappe/frappe-bench/sites/assets` on `backend` vs `frontend`; `bench build` in backend does not fix the UI.

**Cause:** The layered image used to declare `sites/assets` as its own `VOLUME` while compose only mounts the shared `sites` volume. Each container then gets a separate anonymous `sites/assets` mount ([frappe_docker#1850](https://github.com/frappe/frappe_docker/issues/1850)).

**Fix (one-time, dev or main):**

1. Rebuild the custom image (includes the Containerfile change):

   ```bash
   ./nando-deployment/build-custom-image.sh nando-deployment/erpnext-dev.env
   ```

2. Recreate containers **without** `-v` (keeps `erpnext_sites` / DB):

   ```bash
   sudo docker compose --project-name erpnext -f nando-deployment/erpnext-dev.yaml down
   sudo docker compose --project-name erpnext -f nando-deployment/erpnext-dev.yaml up -d --force-recreate
   ```

3. Rebuild assets on the shared `sites` volume (do **not** use `--hard-link` in Docker):

   ```bash
   sudo docker compose --project-name erpnext -f nando-deployment/erpnext-dev.yaml exec backend \
     bench --site apps.internal.nandoai.com build --force
   sudo docker compose --project-name erpnext -f nando-deployment/erpnext-dev.yaml exec backend \
     bench --site apps.internal.nandoai.com clear-cache
   sudo docker compose --project-name erpnext -f nando-deployment/erpnext-dev.yaml restart frontend
   ```

4. Verify backend and frontend share the same path (no separate anonymous volume at `sites/assets`):

   ```bash
   docker inspect $(docker compose --project-name erpnext -f nando-deployment/erpnext-dev.yaml ps -q backend) \
     --format '{{range .Mounts}}{{println .Destination .Name}}{{end}}' | grep assets
   docker inspect $(docker compose --project-name erpnext -f nando-deployment/erpnext-dev.yaml ps -q frontend) \
     --format '{{range .Mounts}}{{println .Destination .Name}}{{end}}' | grep assets
   ```

   Expect **no line** for `sites/assets`, or the same `erpnext_sites` volume only. HRMS CSS counts should match:

   ```bash
   sudo docker compose --project-name erpnext -f nando-deployment/erpnext-dev.yaml exec backend \
     ls sites/assets/hrms/dist/css 2>/dev/null | wc -l
   sudo docker compose --project-name erpnext -f nando-deployment/erpnext-dev.yaml exec frontend \
     ls sites/assets/hrms/dist/css 2>/dev/null | wc -l
   ```

5. Optional: remove orphaned anonymous asset volumes after the stack is healthy:

   ```bash
   docker volume ls -f dangling=true
   ```

**Consequences:** Site data and DB are unchanged. Old per-container asset anonymous volumes are abandoned; step 3 repopulates `sites/assets` inside `erpnext_sites`. Repeat the same flow for `erpnext-main` when promoting the image.

### Site 404

`FRAPPE_SITE_NAME_HEADER` must match the site folder name under `sites/`.

### Traefik / certs

```bash
sudo docker compose --project-name erpnext -f nando-deployment/erpnext-dev.yaml logs proxy
sudo docker compose --project-name erpnext -f nando-deployment/erpnext-dev.yaml exec proxy ls -la /certs/
```

### Wrong stack answering

Check Traefik constraint in generated yaml: `com.docker.compose.project` must match `COMPOSE_PROJECT_NAME`.

### Passwords in shell

Always use **single quotes** for `bench new-site` passwords (`'My!Pass'`).

### Gotchas (from first deployment)

- Use `sudo docker compose … config | sudo tee file` if redirect permission fails
- `bench new-site` “Site already exists” → `--force` to recreate
- MySQL prompt `Enter mysql super user [root]:` → press Enter
- Admin user is `Administrator` (capital A)
