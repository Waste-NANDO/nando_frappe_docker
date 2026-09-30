# 05 — Promote to prod

Ship the **exact image** that is running on **Quality** to prod (`:3000`). No rebuild.

## Gate (enforced by `nando-erp promote`)

1. Quality drift check is clean
2. You pass `--yes` (explicit approval)
3. Optional `--expect-sha <commit>` — image `apps.<sha>` tree must match that commit
4. Pre-deploy database backup uploads to GCS under `pre-deploy/<image-tag>/`
5. Approval is appended to `nando-deployment/logs/promote-audit.jsonl`

## Steps

### 1. Validate on Quality

- Feature works on `:3001`
- Prefer a recent [data refresh](06-refresh-data.md) so migrate was tested against prod-like data
- For Desk-side hotfixes, run [10 — Release](10-release-hotfix.md) first so git matches Quality

### 2. Promote

```bash
# On ERP host (or SSM)
nando-erp promote --from quality --to main --yes
# CI / merge to master:
# nando-erp promote --from quality --to main --expect-sha "$GITHUB_SHA" --yes --actor github-actions
```

What it does:

1. `nando-erp drift --stack quality` — abort on drift
2. Resolve the running Quality backend image
3. Optionally verify `--expect-sha` against the image tag
4. `nando-erp backup --stack main` → GCS `…/pre-deploy/…`
5. `docker tag` source image → prod image name/tag
6. `deploy-stack.sh` for `erpnext-main` (migrate + assets)
7. Write audit log line

### 3. Smoke-check prod

- Open `https://apps.internal.nandoai.com:3000`
- Confirm the change
- If something is wrong: restore from the pre-deploy GCS backup and retag/redeploy the previous image (see [07 — Backups](07-backups.md))

## What not to do

- Do not rebuild a separate image for prod from `master` for the same change — that breaks “build once, promote”.
- Do not edit structure in the prod Desk UI.
- Do not skip the pre-deploy backup.
- Do not promote from cloud-dev for production releases once Quality is live (use Quality).

## After promote

Merge `quality` → `dev` (back-merge) so the next cloud-dev promotion does not lose the hotfix. The `release` command opens that PR automatically.
