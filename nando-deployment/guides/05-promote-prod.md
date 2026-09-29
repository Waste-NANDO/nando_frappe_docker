# 05 — Promote to prod

Ship the **exact image** that is running on cloud-dev to prod (`:3000`). No rebuild.

## Gate (enforced by `nando-erp promote`)

1. Cloud-dev drift check is clean
2. You pass `--yes` (explicit approval)
3. Pre-deploy database backup uploads to GCS under `pre-deploy/<image-tag>/`
4. Approval is appended to `nando-deployment/logs/promote-audit.jsonl`

## Steps

### 1. Validate on cloud-dev

- Feature works on `:3003`
- Prefer a recent [data refresh](06-refresh-data.md) so migrate was tested against prod-like data

### 2. Promote

```bash
# On ERP host (or SSM)
nando-erp promote --yes
# optional: nando-erp promote --yes --actor "simone" --image-tag nando-erpnext-custom:…
```

What it does:

1. `nando-erp drift --stack dev` — abort on drift
2. Resolve the running cloud-dev backend image
3. `nando-erp backup --stack main` → GCS `…/pre-deploy/…`
4. `docker tag` source image → prod image name/tag
5. `deploy-stack.sh` for `erpnext-main` (migrate + assets)
6. Write audit log line

### 3. Smoke-check prod

- Open `https://apps.internal.nandoai.com:3000`
- Confirm the change
- If something is wrong: restore from the pre-deploy GCS backup and retag/redeploy the previous image (see [07 — Backups](07-backups.md))

## What not to do

- Do not rebuild a separate image for prod from `main`/`master` for the same change — that breaks “build once, promote”.
- Do not edit structure in the prod Desk UI.
- Do not skip the pre-deploy backup.

## After promote

Merge `dev` → `main`/`master` on the app repos when you want git history on the release branches to match what shipped (image already contains the SHAs from the build).
