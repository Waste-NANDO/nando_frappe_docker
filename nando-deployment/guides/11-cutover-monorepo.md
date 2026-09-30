# 11 — Cutover to nando-erp-modules + Quality

One-time switch. **This is the only step that touches the live ERP.** Until then, keep the host on its current `nando_frappe_docker` branch and the old app repos.

## Checklist

### 0. Preflight (safe, no live change)

- [ ] `nando-erp-modules` has `master`, `quality`, `dev` matching the old repos (re-run filter-repo import if needed)
- [ ] Feature branch `feature/quality-pipeline` of `nando_frappe_docker` reviewed
- [ ] Host free RAM ≥ ~3 GB for a third stack; disk for one more image set
- [ ] Firewall / security group allows `:3001`
- [ ] DB password set in `erpnext-quality.env` on the host (not the placeholder)

### 1. Freeze + re-import

1. Announce a short freeze on `nando-erpnext-module` and `nando-erp-crm`.
2. Re-run the deterministic `filter-repo` import and merge new commits into `nando-erp-modules`.
3. Push `master` / `quality` / `dev`.

### 2. Switch host tooling

```bash
cd /opt/nando_frappe_docker
git fetch origin
git checkout feature/quality-pipeline   # or main after merge
/opt/nando-erp-ops-venv/bin/pip install -e tools/nando_erp_ops
```

Confirm env files use:

```
NANDO_APPS_REPO=https://github.com/Waste-NANDO/nando-erp-modules.git
NANDO_APPS_BRANCH=dev|quality|master
```

### 3. Rebuild cloud-dev from monorepo

```bash
nando-erp build --stack dev
nando-erp deploy dev --skip-drift   # only if intentional first time
nando-erp drift --stack dev         # expect no drift
```

### 4. Promote to prod (current path once Quality exists)

Until Quality is first brought up, you may still promote from cloud-dev once:

```bash
nando-erp promote --from quality --to main --yes   # after Quality is live
# temporary first cutover if Quality not ready yet:
# nando-erp promote --from dev --to main --yes
```

Confirm prod migrate is a no-op.

### 5. Bring up Quality

```bash
# set real DB_PASSWORD in erpnext-quality.env first
nando-erp build --stack quality
nando-erp deploy quality --skip-drift
nando-erp refresh --target quality --skip-drift
```

Open `:3001`, smoke-test Desk.

### 6. Enable automation

- Switch [deploy.yml](https://github.com/Waste-NANDO/nando-erp-modules/blob/master/.github/workflows/deploy.yml) from `workflow_dispatch` only → also `push` on `dev` / `quality` / `master`
- Branch protection: no direct pushes to `dev`/`quality`/`master` (bot may push `quality`)
- Install host cron: `cron/quality-refresh.sh` (Sunday night)
- Archive `nando-erpnext-module` and `nando-erp-crm` read-only

### Rollback (before archiving old repos)

1. Restore old `NANDO_CRM_*` / `NANDO_FULFILLMENT_*` env vars (or revert env files).
2. Checkout previous host branch of `nando_frappe_docker`.
3. `nando-erp build --stack dev && nando-erp deploy dev` (and promote if needed).
