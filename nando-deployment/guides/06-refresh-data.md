# 06 — Refresh data from prod

Copy **data** down. Structure still comes from git via `migrate` after restore.

```
prod (GCS backup) → cloud-dev or local → sanitize → bench migrate
```

## Before you start

- On cloud-dev: run `nando-erp drift --stack dev`. Refresh **aborts** if there is uncaptured Desk drift (use [04](04-capture-drift.md) first).
- Know that Email / Google / scheduler settings will be wiped on the target (sanitize).

## Cloud-dev

```bash
# On ERP host
nando-erp refresh --target dev
```

This:

1. Drift-checks cloud-dev
2. Takes a pre-refresh backup of cloud-dev
3. Finds the latest prod SQL object in GCS (`nando-erp-main/<ERPNEXT_VERSION>/…`)
4. Runs [`refresh-from-gcs.sh`](../refresh-from-gcs.sh) (download + `bench restore`)
5. Sanitizes (disable scheduler/email, clear credentials)
6. Runs `bench migrate` so git structure is re-applied on top of prod data

Skip drift gate only if you intentionally accept losing uncaptured edits:

```bash
nando-erp refresh --target dev --skip-drift
```

## Local

Full automation expects GCS credentials on the machine. Typical manual flow:

```bash
# 1. Download latest prod DB (from a machine with GCS access)
gsutil ls gs://nando-it-backups/nando-erp-main/v16.5.0/
gsutil cp gs://nando-it-backups/nando-erp-main/v16.5.0/<timestamp>/*-database.sql.gz /tmp/

# 2. Restore (DB only — skip files on laptop)
cd "$NANDO_LOCAL_BENCH"
bench --site "$NANDO_LOCAL_SITE" restore /tmp/…-database.sql.gz

# 3. Re-apply structure + sanitize by hand or:
#    - disable outgoing email / scheduler in System Settings
#    - clear Email Account passwords
bench --site "$NANDO_LOCAL_SITE" migrate
bench --site "$NANDO_LOCAL_SITE" clear-cache
```

`nando-erp refresh --target local` prints this checklist (attachments skipped by default).

## After refresh

- Re-enter any per-environment secrets (email, Google OAuth, …).
- Confirm custom apps still match `versions.env` (`nando-erp doctor`).
