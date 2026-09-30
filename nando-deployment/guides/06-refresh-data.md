# 06 — Refresh data from prod

Copy **data** down. Structure still comes from git via `migrate` after restore.

```
prod (GCS backup) → Quality / cloud-dev / local → sanitize → bench migrate
```

## Before you start

- On the target: run `nando-erp drift --stack <target>`. Refresh **aborts** if there is uncaptured Desk drift (use [04](04-capture-drift.md) or [10](10-release-hotfix.md) first).
- For cron on Quality, use `--skip-if-drift` so a mid-test Desk edit does not fail the job.
- Know that Email / Google / scheduler settings will be wiped on the target (sanitize).

## Quality

```bash
nando-erp refresh --target quality
# weekly cron:
nando-erp refresh --target quality --skip-if-drift
```

## Cloud-dev

```bash
nando-erp refresh --target dev
```

This:

1. Drift-checks the target
2. Takes a pre-refresh backup of the target
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
#    - clear Email Account / Google Settings secrets
bench --site "$NANDO_LOCAL_SITE" migrate
bench --site "$NANDO_LOCAL_SITE" clear-cache
```
