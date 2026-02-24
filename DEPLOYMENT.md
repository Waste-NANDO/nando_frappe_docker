# NandoAI ERPNext Deployment Guide

Production deployment of Frappe + ERPNext at `https://apps.internal.nandoai.com:3003`.

## Architecture

```
Browser (VPC) → https://apps.internal.nandoai.com:3003
                         │
                   Traefik (TLS termination, private CA certs)
                         │
                   Frontend/Nginx (:8080 internal)
                    │              │
              Backend:8000    WebSocket:9000
                    │
              MariaDB + Redis (internal)
              Workers + Scheduler (background)
```

Single Docker Compose stack. Traefik terminates TLS using your private CA
certificate (`nando-erp-server.crt`) and key (`key.pem`), then forwards to
the internal Nginx frontend. All other services are internal only.

## File Layout

```
nando-deployment/
├── certs/
│   ├── .gitkeep
│   ├── traefik-tls.yml           # Traefik dynamic TLS config (committed)
│   ├── key.pem                   # Private key (gitignored, add manually)
│   └── nando-erp-server.crt      # Certificate chain (gitignored, add manually)
├── compose.custom-tls.yaml       # Traefik + TLS compose override
├── compose.backup.yaml           # GCS backup sidecar compose override
├── backup-to-gcs.sh              # Backup entrypoint script (runs inside container)
├── upload-to-gcs.py              # GCS upload + pruning logic
├── rd-devops-prod-...-sa.json    # GCS service account key (gitignored, add manually)
├── erpnext.env                   # Environment variables (edit passwords!)
└── erpnext.yaml                  # Resolved compose file (gitignored, generated)
```

## Prerequisites

- Docker Engine and Docker Compose v2 installed on the remote machine
- SSH access to the remote machine
- Your private CA files: `key.pem` and `nando-erp-server.crt`

## Step 1 — Install Docker

If Docker is not already installed on the remote machine:

```bash
curl -fsSL https://get.docker.com | bash
```

Verify:

```bash
docker --version
docker compose version
```

## Step 2 — Clone the repo

```bash
git clone <your-repo-url> ~/frappe_docker
cd ~/frappe_docker
```

## Step 3 — Add your certificates

Copy your private CA certificate files into the certs directory:

```bash
cp /path/to/key.pem nando-deployment/certs/key.pem
cp /path/to/nando-erp-server.crt nando-deployment/certs/nando-erp-server.crt
```

Verify:

```bash
ls -la nando-deployment/certs/
# Should show: key.pem  nando-erp-server.crt  traefik-tls.yml  .gitkeep
```

## Step 4 — Set passwords

Edit the environment file:

```bash
nano nando-deployment/erpnext.env
```

Change `CHANGE_ME_DB_PASSWORD` to a strong password. This will be the MariaDB
root password and the password used during site creation.

The file should look like:

```env
ERPNEXT_VERSION=v16.5.0
DB_PASSWORD=your_strong_db_password_here
FRAPPE_SITE_NAME_HEADER=apps.internal.nandoai.com
HTTPS_PUBLISH_PORT=3003
GCS_BUCKET=your-gcs-bucket-name
```

## Step 5 — Generate the resolved compose file

From the repo root:

```bash
sudo docker compose --project-name erpnext \
  --env-file nando-deployment/erpnext.env \
  -f compose.yaml \
  -f overrides/compose.redis.yaml \
  -f overrides/compose.mariadb.yaml \
  -f nando-deployment/compose.custom-tls.yaml \
  -f nando-deployment/compose.backup.yaml \
  config | sudo tee nando-deployment/erpnext.yaml > /dev/null
```

This merges all compose layers (including the GCS backup sidecar) into a single
resolved file.

> **Note:** We use `| sudo tee ... > /dev/null` instead of `>` because the
> shell redirect `>` runs as your user and may not have write permissions to
> the directory. `sudo tee` writes the file with root permissions.
> Alternatively, fix ownership once with `sudo chown -R $(whoami):$(whoami) nando-deployment/`.

**Re-run this command every time you change `erpnext.env` or any compose file.**

## Step 6 — Deploy the stack

```bash
sudo docker compose --project-name erpnext -f nando-deployment/erpnext.yaml up -d
```

Watch logs to ensure everything starts:

```bash
sudo docker compose --project-name erpnext -f nando-deployment/erpnext.yaml logs -f
```

Wait for the `configurator` service to exit with code 0. The other services
(backend, frontend, websocket, workers, scheduler, db, redis) should settle
into a running state.

Press `Ctrl+C` to stop following logs.

Verify all services are up:

```bash
sudo docker compose --project-name erpnext -f nando-deployment/erpnext.yaml ps
```

## Step 7 — Create the ERPNext site

```bash
sudo docker compose --project-name erpnext -f nando-deployment/erpnext.yaml exec backend \
  bench new-site \
    --mariadb-user-host-login-scope='%' \
    --db-root-password 'YOUR_DB_PASSWORD' \
    --install-app erpnext \
    --admin-password 'YOUR_ADMIN_PASSWORD' \
    --set-default \
    apps.internal.nandoai.com
```

Replace `YOUR_DB_PASSWORD` with the password you set in `erpnext.env`.
Replace `YOUR_ADMIN_PASSWORD` with the password you want for the ERPNext admin user.

> **Important:** Always wrap passwords in **single quotes** (`'...'`).
> Double quotes or unquoted passwords will break if they contain `!`, `$`,
> or other special characters that bash interprets.

When prompted `Enter mysql super user [root]:`, just press **Enter** to
accept the default (`root`).

If you need to re-create the site (e.g. after a failed first attempt), add
`--force` to drop and recreate:

```bash
sudo docker compose --project-name erpnext -f nando-deployment/erpnext.yaml exec backend \
  bench new-site \
    --mariadb-user-host-login-scope='%' \
    --db-root-password 'YOUR_DB_PASSWORD' \
    --install-app erpnext \
    --admin-password 'YOUR_ADMIN_PASSWORD' \
    --force \
    --set-default \
    apps.internal.nandoai.com
```

This takes a few minutes — it creates the database, runs migrations, and
installs ERPNext.

## Step 8 — Verify

From a machine inside your VPC:

```bash
curl -k https://apps.internal.nandoai.com:3003
```

(`-k` skips cert verification. If the machine trusts your private CA, drop `-k`.)

You should see the Frappe login page HTML. Log in via browser at:

```
https://apps.internal.nandoai.com:3003
```

- **Username:** `Administrator`
- **Password:** the admin password you set in Step 7

## Backups

### Manual backup

```bash
sudo docker compose --project-name erpnext -f nando-deployment/erpnext.yaml exec backend \
  bench --site apps.internal.nandoai.com backup --with-files
```

### Automated backup to GCS

The stack includes a `backup` sidecar container that runs inside Docker
alongside the other services. It uses the same ERPNext image and has direct
access to the `sites` volume — no `docker exec` or `docker cp` needed.

**What it does (every 7 days):**

1. Runs `bench --site <site> backup --with-files`
2. Uploads the DB dump + file tarballs to `gs://<bucket>/<site>/<timestamp>/`
3. Prunes old backups in GCS, keeping only the latest 10
4. Cleans up local backup files to save disk space

**Setup:**

1. Place the GCS service account key on the host:

```bash
ls nando-deployment/rd-devops-prod-relearn-0a64b79e2a62-erpnext-sa.json
```

2. Add `GCS_BUCKET` to `nando-deployment/erpnext.env`:

```env
GCS_BUCKET=your-gcs-bucket-name
```

3. Re-run Step 5 to regenerate the resolved compose file (the backup compose
   layer is already included in the generation command).

4. Deploy:

```bash
sudo docker compose --project-name erpnext -f nando-deployment/erpnext.yaml up -d
```

The backup service starts automatically. Check its logs:

```bash
sudo docker compose --project-name erpnext -f nando-deployment/erpnext.yaml logs -f backup
```

**Configuration (via `erpnext.env`):**

| Variable | Default | Description |
|---|---|---|
| `GCS_BUCKET` | *(required)* | GCS bucket name |
| `BACKUP_KEEP` | `10` | Number of backup sets to retain in GCS |
| `BACKUP_INTERVAL_SECONDS` | `604800` | Seconds between backups (default: 7 days) |

**Required IAM permissions** on the service account:
`roles/storage.objectAdmin` on the target bucket (or at minimum
`storage.objects.create`, `storage.objects.delete`, `storage.objects.list`).

## Common Operations

### Stop the stack

```bash
sudo docker compose --project-name erpnext -f nando-deployment/erpnext.yaml down
```

### Restart the stack

```bash
sudo docker compose --project-name erpnext -f nando-deployment/erpnext.yaml up -d
```

### View logs (specific service)

```bash
sudo docker compose --project-name erpnext -f nando-deployment/erpnext.yaml logs -f backend
sudo docker compose --project-name erpnext -f nando-deployment/erpnext.yaml logs -f proxy
```

### Run bench commands

```bash
sudo docker compose --project-name erpnext -f nando-deployment/erpnext.yaml exec backend \
  bench --site apps.internal.nandoai.com [command]
```

### Migrate after ERPNext version update

1. Update `ERPNEXT_VERSION` in `nando-deployment/erpnext.env`
2. Re-run Step 5 to regenerate the resolved compose file
3. Pull new images and restart:

```bash
sudo docker compose --project-name erpnext -f nando-deployment/erpnext.yaml pull
sudo docker compose --project-name erpnext -f nando-deployment/erpnext.yaml up -d
```

4. Run migration:

```bash
sudo docker compose --project-name erpnext -f nando-deployment/erpnext.yaml exec backend \
  bench --site apps.internal.nandoai.com migrate
```

### Open a shell in the backend container

```bash
sudo docker compose --project-name erpnext -f nando-deployment/erpnext.yaml exec backend bash
```

## Troubleshooting

### Site not resolving

If you get "404 not found" from Frappe, the site name doesn't match. Check:

```bash
sudo docker compose --project-name erpnext -f nando-deployment/erpnext.yaml exec backend \
  bench --site apps.internal.nandoai.com list-apps
```

If it fails, the site name is wrong. The `FRAPPE_SITE_NAME_HEADER` in
`erpnext.env` must match the site name you created in Step 7.

### Traefik not picking up certs

Check Traefik logs:

```bash
sudo docker compose --project-name erpnext -f nando-deployment/erpnext.yaml logs proxy
```

Verify certs are readable inside the container:

```bash
sudo docker compose --project-name erpnext -f nando-deployment/erpnext.yaml exec proxy ls -la /certs/
```

### MariaDB not starting

Check DB logs:

```bash
sudo docker compose --project-name erpnext -f nando-deployment/erpnext.yaml logs db
```

### Volumes and data safety

- `docker compose down` preserves volumes (data safe)
- `docker compose down -v` **destroys volumes** (data lost) — never use this in production

### Traefik errors about other containers

If you see Traefik errors like `Router uses a nonexistent certificate resolver`
or `error while parsing rule` referencing services you didn't deploy (e.g. CVAT),
this is because Traefik discovers **all** Docker containers on the host via the
Docker socket. It tries to parse their labels and complains about invalid ones.
These errors are harmless and don't affect the ERPNext deployment.

## Gotchas & Lessons Learned

Things that tripped us up during the first deployment (2026-02-17):

### 1. File permissions on the remote machine

The `>` shell redirect runs as your user, not as root. So
`sudo docker compose ... config > file` fails with "Permission denied"
because the redirect is handled by your shell before `sudo` kicks in.

**Fix:** Use `sudo docker compose ... config | sudo tee file > /dev/null`
or fix directory ownership with `sudo chown -R $(whoami):$(whoami) nando-deployment/`.

### 2. Special characters in passwords break bash

Passwords containing `!`, `$`, backticks, or other shell metacharacters
will be interpreted by bash if passed in double quotes or unquoted.
For example, `--admin-password My!Pass` causes `-bash: !Pass: event not found`.

**Fix:** Always wrap passwords in **single quotes**: `--admin-password 'My!Pass'`.

### 3. "Site already exists" after a failed creation

If `bench new-site` partially runs (e.g. you `Ctrl+C` or hit a password
parsing error), the site may be in a half-created state. Re-running the
same command gives `Site already exists`.

**Fix:** Add `--force` to the `bench new-site` command to drop and recreate.

### 4. MySQL super user prompt

During `bench new-site`, you'll be prompted:
`Enter mysql super user [root]:`. This is asking for the **username**,
not a password. Just press **Enter** to accept the default `root`.

### 5. Firewall / security group for the port

`curl` from the server itself works, but browsers from VPN clients can't
reach the port. This means the cloud firewall (GCP/AWS/Azure security
group) is blocking inbound traffic on port 3003.

**Fix:** Add a firewall rule allowing TCP port 3003 inbound from your
VPC CIDR range (e.g. `10.0.0.0/8`). Verify the port is listening first:
`sudo ss -tlnp | grep 3003`.

### 6. Default admin login

The admin username is `Administrator` (capital A, full word) — not
`admin` or `Admin`.
