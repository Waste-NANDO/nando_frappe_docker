# 07 — Backups

GCS is the durable store. Files under `sites/<site>/private/backups/` are temporary (Frappe deletes them after ~24h by default). Redeploy does **not** wipe the `sites` volume; `docker compose down -v` does.

## Schedule

| Stack | Interval | Keep (sidecar) | GCS prefix |
|-------|----------|----------------|------------|
| Prod (`erpnext-main`) | **Daily** (`BACKUP_INTERVAL_SECONDS=86400`) | ~14 | `nando-erp-main/<ERPNEXT_VERSION>/` |
| Cloud-dev (`erpnext`) | Weekly | ~10 | `nando-erp-dev/<ERPNEXT_VERSION>/` |

Configured in [`erpnext-main.env`](../erpnext-main.env) / [`erpnext-dev.env`](../erpnext-dev.env) via [`compose.backup.yaml`](../compose.backup.yaml).

## Manual backup

```bash
# Prod, with files, upload to GCS
nando-erp backup --stack main

# DB only, no upload
nando-erp backup --stack main --no-files --no-upload

# Custom prefix (used by promote)
nando-erp backup --stack main --no-files \
  --prefix "nando-erp-main/pre-deploy/my-tag"
```

## Automatic backups in the pipeline

| Event | What runs |
|-------|-----------|
| `nando-erp promote` | Mandatory prod DB backup → `…/pre-deploy/<image-tag>/` before retag/migrate |
| `nando-erp refresh` | Pre-refresh backup of the **target** stack |

## Restore (rollback)

1. Find the object in GCS (pre-deploy or daily).
2. Use [`refresh-from-gcs.sh`](../refresh-from-gcs.sh) against the target stack, **or** `bench restore` inside the backend container.
3. Re-deploy the previous image tag if the bad change was code/fixtures.

Example restore onto prod (careful — production):

```bash
./nando-deployment/refresh-from-gcs.sh \
  --target main \
  --object nando-erp-main/pre-deploy/<tag>/<file>-database.sql.gz
# then sanitize is NOT automatic on main via that script alone —
# prefer restore drills on cloud-dev first.
```

Practice restores by refreshing cloud-dev ([06](06-refresh-data.md)) — that exercises the same path.
