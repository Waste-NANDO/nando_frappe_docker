# 03 — Deploy to cloud-dev

Build a commit-pinned image from app `dev` branches and deploy the `:3003` stack.

Run these on the **ERP host** (or from your laptop with `NANDO_EXECUTOR=ssm` — see [09](09-cli-ssm-api.md)).

## Prerequisites

- App PRs merged into `dev` on both repos (as needed).
- `github.env` present on the host (PAT for private app clones).
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

1. Fetches custom apps at the `dev` branch pins
2. Records short SHAs in the image tag
3. Runs `build-custom-image.sh` and renders `erpnext-dev.yaml`

Note the printed `IMAGE_TAG=…`.

### 3. Deploy

```bash
nando-erp deploy dev
```

This runs drift check again, then `deploy-stack.sh` (compose up → materialize assets → `bench migrate` → clear-cache).

`migrate` **force-imports** fixture JSON from the image. That is intentional: git → image → site.

### 4. Smoke-check

- Open `https://apps.internal.nandoai.com:3003`
- Confirm the change (DocType, script, workspace, …)
- Watch logs if migrate failed: `docker compose -p erpnext -f nando-deployment/erpnext-dev.yaml logs backend --tail 200`

## Flags

| Flag | Meaning |
|------|---------|
| `nando-erp deploy dev --with-build` | Build + deploy in one shot |
| `nando-erp deploy dev --skip-drift` | **Emergency only** — skips the gate (can wipe uncaptured Desk edits) |

## After deploy

- Need prod data on cloud-dev? → [06 — Refresh data](06-refresh-data.md)
- Ready for prod? → [05 — Promote to prod](05-promote-prod.md)
