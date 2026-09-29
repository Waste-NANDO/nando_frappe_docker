# 04 — Capture cloud-dev drift

Use when `nando-erp deploy dev` or `nando-erp drift` reports that the live cloud-dev site has Desk edits that are not in git.

If you deploy without capturing, migrate would overwrite those edits with whatever is in the image.

## Steps

### 1. See the drift

```bash
nando-erp drift --stack dev
```

Inspect the listed missing / changed documents.

### 2. Capture into a branch + PR

```bash
# On the ERP host (custom-apps/ must be git checkouts — fetch-custom-app first if needed)
./nando-deployment/fetch-custom-app.sh nando-deployment/erpnext-dev.env

nando-erp capture --stack dev --push
```

This:

1. Exports fixtures from the live cloud-dev site
2. Writes them into `nando-deployment/custom-apps/<app>/`
3. Commits on `capture/<YYYYMMDD>`
4. With `--push`, pushes and opens a PR into `dev` (via `gh`)

### 3. Review and merge

- Open the PR(s) on GitHub
- Confirm module ownership (`NANDO_CRM` vs `NANDO_Operations`)
- Merge into `dev`

### 4. Pull locally and redeploy

```bash
# laptop — sync your working copies
cd "$NANDO_LOCAL_BENCH/apps/nando_crm" && git checkout dev && git pull
cd "$NANDO_LOCAL_BENCH/apps/nando_fulfillment" && git checkout dev && git pull

# host
nando-erp build --stack dev
nando-erp deploy dev
```

Drift check should now be clean.

## Without opening a PR

```bash
nando-erp capture --stack dev          # commit locally on the host checkout only
# then push / PR by hand
```
