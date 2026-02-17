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
├── erpnext.env                   # Environment variables (edit passwords!)
├── backup.sh                     # Backup script
├── backups/                      # Backup output dir (gitignored, created by script)
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
```

## Step 5 — Generate the resolved compose file

From the repo root:

```bash
docker compose --project-name erpnext \
  --env-file nando-deployment/erpnext.env \
  -f compose.yaml \
  -f overrides/compose.redis.yaml \
  -f overrides/compose.mariadb.yaml \
  -f nando-deployment/compose.custom-tls.yaml \
  config > nando-deployment/erpnext.yaml
```

This merges all compose layers into a single resolved file.

**Re-run this command every time you change `erpnext.env` or any compose file.**

## Step 6 — Deploy the stack

```bash
docker compose --project-name erpnext -f nando-deployment/erpnext.yaml up -d
```

Watch logs to ensure everything starts:

```bash
docker compose --project-name erpnext -f nando-deployment/erpnext.yaml logs -f
```

Wait for the `configurator` service to exit with code 0. The other services
(backend, frontend, websocket, workers, scheduler, db, redis) should settle
into a running state.

Press `Ctrl+C` to stop following logs.

Verify all services are up:

```bash
docker compose --project-name erpnext -f nando-deployment/erpnext.yaml ps
```

## Step 7 — Create the ERPNext site

```bash
docker compose --project-name erpnext -f nando-deployment/erpnext.yaml exec backend \
  bench new-site \
    --mariadb-user-host-login-scope='%' \
    --db-root-password YOUR_DB_PASSWORD \
    --install-app erpnext \
    --admin-password YOUR_ADMIN_PASSWORD \
    --set-default \
    apps.internal.nandoai.com
```

Replace `YOUR_DB_PASSWORD` with the password you set in `erpnext.env`.
Replace `YOUR_ADMIN_PASSWORD` with the password you want for the ERPNext admin user.

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
docker compose --project-name erpnext -f nando-deployment/erpnext.yaml exec backend \
  bench --site apps.internal.nandoai.com backup --with-files
```

### Automated backup (cron)

The included `backup.sh` script runs a backup, copies files out of the Docker
volume to `nando-deployment/backups/` on the host, and cleans up backups older
than 7 days.

Test it manually first:

```bash
./nando-deployment/backup.sh
```

Then set up a cron job (e.g., every 6 hours):

```bash
crontab -e
```

Add:

```cron
0 */6 * * * /root/frappe_docker/nando-deployment/backup.sh >> /root/frappe_docker/nando-deployment/backups/backup.log 2>&1
```

Adjust the path if you cloned the repo somewhere other than `~/frappe_docker`.

## Common Operations

### Stop the stack

```bash
docker compose --project-name erpnext -f nando-deployment/erpnext.yaml down
```

### Restart the stack

```bash
docker compose --project-name erpnext -f nando-deployment/erpnext.yaml up -d
```

### View logs (specific service)

```bash
docker compose --project-name erpnext -f nando-deployment/erpnext.yaml logs -f backend
docker compose --project-name erpnext -f nando-deployment/erpnext.yaml logs -f proxy
```

### Run bench commands

```bash
docker compose --project-name erpnext -f nando-deployment/erpnext.yaml exec backend \
  bench --site apps.internal.nandoai.com [command]
```

### Migrate after ERPNext version update

1. Update `ERPNEXT_VERSION` in `nando-deployment/erpnext.env`
2. Re-run Step 5 to regenerate the resolved compose file
3. Pull new images and restart:

```bash
docker compose --project-name erpnext -f nando-deployment/erpnext.yaml pull
docker compose --project-name erpnext -f nando-deployment/erpnext.yaml up -d
```

4. Run migration:

```bash
docker compose --project-name erpnext -f nando-deployment/erpnext.yaml exec backend \
  bench --site apps.internal.nandoai.com migrate
```

### Open a shell in the backend container

```bash
docker compose --project-name erpnext -f nando-deployment/erpnext.yaml exec backend bash
```

## Troubleshooting

### Site not resolving

If you get "404 not found" from Frappe, the site name doesn't match. Check:

```bash
docker compose --project-name erpnext -f nando-deployment/erpnext.yaml exec backend \
  bench --site apps.internal.nandoai.com list-apps
```

If it fails, the site name is wrong. The `FRAPPE_SITE_NAME_HEADER` in
`erpnext.env` must match the site name you created in Step 7.

### Traefik not picking up certs

Check Traefik logs:

```bash
docker compose --project-name erpnext -f nando-deployment/erpnext.yaml logs proxy
```

Verify certs are readable inside the container:

```bash
docker compose --project-name erpnext -f nando-deployment/erpnext.yaml exec proxy ls -la /certs/
```

### MariaDB not starting

Check DB logs:

```bash
docker compose --project-name erpnext -f nando-deployment/erpnext.yaml logs db
```

### Volumes and data safety

- `docker compose down` preserves volumes (data safe)
- `docker compose down -v` **destroys volumes** (data lost) — never use this in production
