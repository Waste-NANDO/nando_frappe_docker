# 08 — Phase 0: baseline from prod (run on ERP host)

> Part of the pipeline docs: **[PIPELINE.md](PIPELINE.md)**.

One-time cutover so git fixtures match **prod** (what's actually running). After this, migrate on prod with those fixtures must be a no-op.

## Prerequisites

1. Align both stacks to [`versions.env`](versions.env) (`FRAPPE_VERSION=v16.28.0`, ERPNext/HRMS as pinned). Rebuild cloud-dev first, then promote.
2. Install the CLI on the host:

```bash
cd /opt/nando_frappe_docker   # or your checkout
python3 -m venv /opt/nando-erp-ops-venv
/opt/nando-erp-ops-venv/bin/pip install -e tools/nando_erp_ops
export PATH="/opt/nando-erp-ops-venv/bin:$PATH"
export NANDO_DOCKER_REPO=/opt/nando_frappe_docker
export NANDO_EXECUTOR=local
```

3. App hooks already filter by module (`NANDO_CRM` / `NANDO_Operations`). Deploy those hook commits to both stacks **before** the baseline export (or export will still dump unfiltered rows).

## Steps

```bash
# 1. Assign module on Custom Field / Property Setter rows that lack one
nando-erp assign-modules --stack main
# review JSON assignment list
nando-erp assign-modules --stack main --apply

# 2. Same on cloud-dev if you want parity before refresh
nando-erp assign-modules --stack dev --apply

# 3. Export prod fixtures into custom-apps/ and commit
./nando-deployment/fetch-custom-app.sh nando-deployment/erpnext-main.env
nando-erp baseline --stack main --commit

# 4. Push to origin main/master on both app repos, merge into dev
# 5. Rebuild cloud-dev from dev branches; promote identical image to prod
nando-erp build --stack dev
nando-erp deploy dev --skip-drift   # first time only if intentional
nando-erp promote --yes

# 6. Confirm prod migrate changed nothing meaningful
docker compose --project-name erpnext-main -f nando-deployment/erpnext-main.yaml \
  exec -T backend bench --site apps.internal.nandoai.com migrate
```

Dev-only Desk work that was never on prod is **not** in this baseline. Re-apply it as normal feature PRs after cutover.
