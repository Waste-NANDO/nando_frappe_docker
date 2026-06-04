# Migrating Desk customizations (dev → main)

Guide for promoting **GUI-built ERPNext customizations** from dev (`:3003`) to main (`:3000`).

| App | Repo | Role |
|-----|------|------|
| **`nando_crm`** | [nando-erp-crm](https://github.com/Waste-NANDO/nando-erp-crm) | CRM Desk config: scripts, DocTypes, roles, workspaces, reports |
| **`nando_fulfillment`** | [nando-erpnext-module](https://github.com/Waste-NANDO/nando-erpnext-module) | Future fulfillment / ops entities (separate lifecycle) |

Both apps are baked into the **dev** image. **Main** ships `nando_crm` only (see `erpnext-main.env`).

Full deployment: [DEPLOYMENT.md](../DEPLOYMENT.md).  
Workspaces: [README_workspaces.md](README_workspaces.md).

## What migrates

| Artifact | Mechanism |
|----------|-----------|
| Server Script, Client Script | Fixture JSON in `nando_crm` |
| Custom Fields, Property Setters | Fixture JSON |
| Custom DocTypes | App JSON under `nando_crm/.../doctype/` + `migrate` |
| Roles (custom only) | Fixture JSON (filtered in `hooks.py`) |
| Workspaces, Desktop Icons | Fixture JSON or developer-mode export |
| Reports | Fixture JSON and/or app module files |

**Not included:** transactional data (customers, deals, stock, users).

## Architecture

```text
Dev DB (:3003)
  → assign customizations to module NANDO_CRM / app nando_crm
  → export-fixtures + export-doc on dev
  → commit nando-erp-crm
  → build-custom-image.sh (custom-apps/nando_crm + nando_fulfillment)
  → Main (:3000): install-app nando_crm, migrate, import-fixtures
```

Local clones: `nando-deployment/custom-apps/<app_key>/` (via `fetch-custom-app.sh`).

---

## Phase 1 — Rebuild dev with both apps

On the server (PAT configured — see [DEPLOYMENT.md](../DEPLOYMENT.md#github-authentication)):

```bash
./nando-deployment/build-custom-image.sh nando-deployment/erpnext-dev.env
sudo docker compose --project-name erpnext -f nando-deployment/erpnext-dev.yaml up -d
```

Install **new** app on existing dev site (`nando_fulfillment` may already be installed):

```bash
sudo docker compose --project-name erpnext -f nando-deployment/erpnext-dev.yaml exec backend \
  bench --site apps.internal.nandoai.com install-app nando_crm nando_fulfillment

sudo docker compose --project-name erpnext -f nando-deployment/erpnext-dev.yaml exec backend \
  bench --site apps.internal.nandoai.com migrate
```

If `nando_fulfillment` is already installed, run only `install-app nando_crm`.

Verify:

```bash
sudo docker compose --project-name erpnext -f nando-deployment/erpnext-dev.yaml exec backend \
  bench --site apps.internal.nandoai.com list-apps
```

---

## Phase 2 — Tie customizations to `nando_crm`

### 2.1 Module Def on dev

Create or confirm in Desk (**Module Def**):

| Field | Value |
|-------|--------|
| Module Name | `NANDO_CRM` |
| App | `nando_crm` |
| Package | `nando_crm` |
| Custom | checked |

### 2.2 Reassign records

For each customization created in the Desk GUI:

1. Open the record (DocType, Workspace, Report, etc.).
2. Set **Module** → `NANDO_CRM`.
3. Save.

For Client/Server Scripts, set module where applicable. Custom Fields on standard forms stay in fixtures regardless of module.

### 2.3 Inventory (bench console)

```bash
sudo docker compose --project-name erpnext -f nando-deployment/erpnext-dev.yaml exec backend \
  bench --site apps.internal.nandoai.com console
```

```python
import frappe
for d in frappe.get_all("DocType", filters={"custom": 1}, fields=["name", "module"]):
    print(d)
print("Client Scripts:", frappe.get_all("Client Script", pluck="name"))
print("Server Scripts:", frappe.get_all("Server Script", pluck="name"))
for w in frappe.get_all("Workspace", fields=["name", "module", "public"]):
    print(w)
exit()
```

Update **`hooks.py`** in [nando-erp-crm](https://github.com/Waste-NANDO/nando-erp-crm) with fixture filters (especially custom **Role** names), commit, rebuild dev image.

---

## Phase 3 — Export from dev into `nando_crm`

### 3.1 Developer mode

```bash
sudo docker compose --project-name erpnext -f nando-deployment/erpnext-dev.yaml exec backend \
  bench --site apps.internal.nandoai.com set-config developer_mode 1

sudo docker compose --project-name erpnext -f nando-deployment/erpnext-dev.yaml exec backend \
  bench --site apps.internal.nandoai.com clear-cache
```

### 3.2 DocTypes and workspaces

Save each custom DocType in Desk (writes JSON into the app in the container), or:

```bash
sudo docker compose --project-name erpnext -f nando-deployment/erpnext-dev.yaml exec backend \
  bench --site apps.internal.nandoai.com export-doc "DocType" "Your DocType Name"
```

Re-save public workspaces tied to `NANDO_CRM` so they export under the app tree.

### 3.3 Fixtures

After `hooks.py` is in the running image (rebuild if you edited the repo):

```bash
sudo docker compose --project-name erpnext -f nando-deployment/erpnext-dev.yaml exec backend \
  bench --site apps.internal.nandoai.com export-fixtures
```

Copy changes from the container to git if needed:

```bash
sudo docker compose --project-name erpnext -f nando-deployment/erpnext-dev.yaml cp \
  backend:/home/frappe/frappe-bench/apps/nando_crm \
  /tmp/nando_crm_export
# merge into nando-deployment/custom-apps/nando_crm, commit, push
```

Or edit in `custom-apps/nando_crm` locally after `./nando-deployment/fetch-custom-app.sh`.

```bash
cd nando-deployment/custom-apps/nando_crm
git add .
git commit -m "Export CRM Desk customizations from dev"
git push origin main
```

Rebuild dev and smoke-test on `:3003`.

---

## Phase 4 — Promote to main

### 4.1 Backup main

```bash
sudo docker compose --project-name erpnext-main -f nando-deployment/erpnext-main.yaml exec backend \
  bench --site apps.internal.nandoai.com backup --with-files
```

### 4.2 Build main image (includes `nando_crm` only)

`erpnext-main.env` already sets `CUSTOM_APP_KEYS=nando_crm`. On the server:

```bash
sudo ./nando-deployment/build-custom-image.sh nando-deployment/erpnext-main.env
sudo docker compose --project-name erpnext-main -f nando-deployment/erpnext-main.yaml up -d
```

### 4.3 Install app and apply config

```bash
sudo docker compose --project-name erpnext-main -f nando-deployment/erpnext-main.yaml exec backend \
  bench --site apps.internal.nandoai.com install-app nando_crm

sudo docker compose --project-name erpnext-main -f nando-deployment/erpnext-main.yaml exec backend \
  bench --site apps.internal.nandoai.com migrate

sudo docker compose --project-name erpnext-main -f nando-deployment/erpnext-main.yaml exec backend \
  bench --site apps.internal.nandoai.com import-fixtures
```

### 4.4 Server Scripts + cache

```bash
sudo docker compose --project-name erpnext-main -f nando-deployment/erpnext-main.yaml exec backend \
  bench set-config -g server_script_enabled 1

sudo docker compose --project-name erpnext-main -f nando-deployment/erpnext-main.yaml restart backend

sudo docker compose --project-name erpnext-main -f nando-deployment/erpnext-main.yaml exec backend \
  bench --site apps.internal.nandoai.com clear-cache
```

Assign roles on main users (dev and main do not share users).

---

## Env reference (multi-app)

In `erpnext-dev.env`:

```env
CUSTOM_APP_KEYS=nando_crm,nando_fulfillment
SITE_INSTALL_APPS=nando_crm,nando_fulfillment

NANDO_CRM_REPO=https://github.com/Waste-NANDO/nando-erp-crm.git
NANDO_CRM_BRANCH=main

NANDO_FULFILLMENT_REPO=https://github.com/Waste-NANDO/nando-erpnext-module.git
NANDO_FULFILLMENT_BRANCH=main
```

In `erpnext-main.env`:

```env
CUSTOM_APP_KEYS=nando_crm
SITE_INSTALL_APPS=nando_crm
NANDO_CRM_REPO=https://github.com/Waste-NANDO/nando-erp-crm.git
NANDO_CRM_BRANCH=main
```

App key → env prefix: `nando_crm` → `NANDO_CRM_REPO`, `NANDO_CRM_BRANCH`.

Legacy single-app vars (`CUSTOM_APP_REPO`, `CUSTOM_APP_NAME`) still work for one app only.

---

## Checklist

| # | Task |
|---|------|
| 1 | Rebuild dev image with both apps |
| 2 | `install-app nando_crm` on dev |
| 3 | Module Def `NANDO_CRM` → app `nando_crm` |
| 4 | Reassign DocTypes, workspaces, reports to `NANDO_CRM` |
| 5 | Update `hooks.py` filters in nando-erp-crm |
| 6 | `developer_mode 1`, export DocTypes + `export-fixtures` |
| 7 | Commit, push, rebuild dev, verify `:3003` |
| 8 | Backup main |
| 9 | Build main image, deploy |
| 10 | `install-app nando_crm`, `migrate`, `import-fixtures` |
| 11 | `server_script_enabled 1`, clear cache, verify `:3000` |

## Gotchas

- Customizations must be tied to **`nando_crm` / `NANDO_CRM`** before export — not left on orphan modules.
- **`import-fixtures`** may be needed after `migrate` if fixtures did not sync automatically.
- Do **not** restore dev DB onto main.
- Never `docker compose down -v` on production.
