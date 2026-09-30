# 03 — Deploy to cloud-dev

Build a commit-pinned image from `nando-erp-modules` branch `dev` and deploy the `:3003` stack.

Run these on the **ERP host** (or from your laptop with `NANDO_EXECUTOR=ssm` — see [09](09-cli-ssm-api.md)).

## Prerequisites

- App PRs merged into `dev` on [nando-erp-modules](https://github.com/Waste-NANDO/nando-erp-modules).
- `github.env` present on the host (PAT / GitHub App for private clones).
- Host CLI installed ([09](09-cli-ssm-api.md)).

## Steps

### 1. Drift check (optional preview)

```bash
nando-erp drift --stack dev
```

Exit `2` means cloud-dev Desk diverged from git. Fix with [04 — Capture drift](04-capture-drift.md) before deploying, or the deploy will abort.

### 2. Build

```bash
export NANDO_DOCKER_REPO=/opt/nando_frappe_docker   # or your checkout
cd "$NANDO_DOCKER_REPO"
nando-erp build --stack dev
```

This:

1. Fetches `nando-erp-modules` @ `dev` and materializes each app into `custom-apps/`
2. Records the monorepo short SHA in the image tag (`…-apps.<sha7>`)
3. Runs `build-custom-image.sh` and renders `erpnext-dev.yaml`

Note the printed `IMAGE_TAG=…`.

### 3. Deploy

```bash
nando-erp deploy dev
# or: nando-erp deploy dev --with-build
```

Drift is checked again unless `--skip-drift`.

### 4. Smoke-check

Open `https://apps.internal.nandoai.com:3003`.

## Next

- Need prod data on cloud-dev? → [06 — Refresh data](06-refresh-data.md)
- Ready for UAT? → PR `dev` → `quality`, then `nando-erp build --stack quality && nando-erp deploy quality`
- Hotfix / prod? → [10 — Release hotfix](10-release-hotfix.md) / [05 — Promote](05-promote-prod.md)
