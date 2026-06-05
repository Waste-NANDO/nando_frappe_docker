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
docker compose --project-name erpnext -f nando-deployment/erpnext-dev.yaml up -d
```

Install **new** app on existing dev site (`nando_fulfillment` may already be installed):

```bash
docker compose --project-name erpnext -f nando-deployment/erpnext-dev.yaml exec backend \
  bench --site apps.internal.nandoai.com install-app nando_crm nando_fulfillment

docker compose --project-name erpnext -f nando-deployment/erpnext-dev.yaml exec backend \
  bench --site apps.internal.nandoai.com migrate
```

If `nando_fulfillment` is already installed, run only `install-app nando_crm`.

Verify:

```bash
docker compose --project-name erpnext -f nando-deployment/erpnext-dev.yaml exec backend \
  bench --site apps.internal.nandoai.com list-apps
```

---

## Phase 2 — Tie customizations to `nando_crm` and export (detailed)

Complete this on **dev** (`:3003`) after Phase 1 (`nando_crm` installed in the image and on the site).

**Goal:** Every CRM customization is owned by app **`nando_crm`** / module **`NANDO_CRM`**, exported to git in [nando-erp-crm](https://github.com/Waste-NANDO/nando-erp-crm), then verified on dev before touching main.

**Order matters:** Module Def → reassign records → update `hooks.py` → rebuild dev → developer mode → export → commit.

---

### 2.1 Confirm prerequisites

```bash
docker compose --project-name erpnext -f nando-deployment/erpnext-dev.yaml exec backend \
  bench --site apps.internal.nandoai.com list-apps
```

Expect `nando_crm` in the list. If missing:

```bash
docker compose --project-name erpnext -f nando-deployment/erpnext-dev.yaml exec backend \
  bench --site apps.internal.nandoai.com install-app nando_crm

docker compose --project-name erpnext -f nando-deployment/erpnext-dev.yaml exec backend \
  bench --site apps.internal.nandoai.com migrate
```

Server Scripts must already work on dev (`server_script_enabled`). If not:

```bash
docker compose --project-name erpnext -f nando-deployment/erpnext-dev.yaml exec backend \
  bench set-config -g server_script_enabled 1

docker compose --project-name erpnext -f nando-deployment/erpnext-dev.yaml restart backend
```

---

### 2.2 Enable developer mode

Required before DocType/workspace JSON is written into the app tree on save.

```bash
docker compose --project-name erpnext -f nando-deployment/erpnext-dev.yaml exec backend \
  bench --site apps.internal.nandoai.com set-config developer_mode 1

docker compose --project-name erpnext -f nando-deployment/erpnext-dev.yaml exec backend \
  bench --site apps.internal.nandoai.com clear-cache
```

---

### 2.3 Create or fix Module Def `NANDO_CRM`

**Option A — Desk UI**

1. Open `https://apps.internal.nandoai.com:3003`
2. Search bar → **Module Def** → **New** (or open existing `NANDO_CRM`)
3. Set:

   | Field | Value |
   |-------|--------|
   | Module Name | `NANDO_CRM` |
   | App Name | `nando_crm` |
   | Package | `nando_crm` |
   | Custom | ✓ checked |

4. Save

**Option B — bench console** (if record missing or wrong app/package)

```bash
docker compose --project-name erpnext -f nando-deployment/erpnext-dev.yaml exec backend \
  bench --site apps.internal.nandoai.com console
```

```python
import frappe

name = "NANDO_CRM"
if frappe.db.exists("Module Def", name):
    frappe.db.set_value("Module Def", name, {
        "app_name": "nando_crm",
        "package": "nando_crm",
        "custom": 1,
    })
else:
    doc = frappe.get_doc({
        "doctype": "Module Def",
        "module_name": name,
        "app_name": "nando_crm",
        "package": "nando_crm",
        "custom": 1,
    })
    doc.insert(ignore_permissions=True)

frappe.db.commit()
print(frappe.get_doc("Module Def", name).as_dict())
exit()
```

---

### 2.4 Run full inventory

Save this output — you will use it for reassignment and `hooks.py` filters.

```bash
docker compose --project-name erpnext -f nando-deployment/erpnext-dev.yaml exec backend \
  bench --site apps.internal.nandoai.com console
```

```python
import frappe

def section(title):
    print("\n" + "=" * 60)
    print(title)
    print("=" * 60)

section("Custom DocTypes")
for d in frappe.get_all("DocType", filters={"custom": 1},
                      fields=["name", "module"], order_by="name"):
    print(f"  {d.name:40} module={d.module}")

section("Client Scripts")
for s in frappe.get_all("Client Script", fields=["name", "dt", "module"], order_by="name"):
    print(f"  {s.name:40} on={s.dt} module={s.module}")

section("Server Scripts")
for s in frappe.get_all("Server Script", fields=["name", "script_type", "module"], order_by="name"):
    print(f"  {s.name:40} type={s.script_type} module={s.module}")

section("Workspaces")
for w in frappe.get_all("Workspace", fields=["name", "module", "public", "app"], order_by="name"):
    print(f"  {w.name:40} module={w.module} public={w.public} app={w.app}")

section("Desktop Icons")
for d in frappe.get_all("Desktop Icon",
    fields=["name", "label", "link_type", "link_to", "module"], order_by="label"):
    print(f"  {d.label or d.name:40} link={d.link_type}/{d.link_to} module={d.module}")

section("Reports")
for r in frappe.get_all("Report",
    filters={"report_type": ["in", ["Query Report", "Script Report", "Report Builder"]]},
    fields=["name", "module", "report_type", "ref_doctype"], order_by="name"):
    print(f"  {r.name:40} type={r.report_type} module={r.module}")

section("Custom roles")
for role in frappe.get_all("Role", filters={"disabled": 0, "is_custom": 1}, pluck="name"):
    print(f"  {role}")

section("Custom Fields (count by doctype)")
from frappe.utils import get_table_name
rows = frappe.db.sql("""
    select dt, count(*) as n from `tabCustom Field`
    group by dt order by n desc
""", as_dict=1)
for r in rows:
    print(f"  {r.dt:40} {r.n} fields")

section("Module Defs (custom)")
for m in frappe.get_all("Module Def", filters={"custom": 1},
                        fields=["name", "app_name", "package"]):
    print(f"  {m.name:40} app={m.app_name} package={m.package}")

exit()
```

Copy the printed list somewhere safe. Anything **not** on module `NANDO_CRM` (or app `nando_crm` for workspaces) needs reassignment in the next steps.

---

### 2.5 Update `hooks.py` in nando-erp-crm

On your laptop (or after fetch on the server):

```bash
./nando-deployment/fetch-custom-app.sh nando-deployment/erpnext-dev.env
# edit: nando-deployment/custom-apps/nando_crm/nando_crm/hooks.py
```

Set **`fixtures`** using your inventory. Example skeleton:

```python
fixtures = [
    "Custom Field",
    "Property Setter",
    "Client Script",
    "Server Script",
    {
        "dt": "Workspace",
        "filters": [["module", "=", "NANDO_CRM"]],
    },
    {
        "dt": "Desktop Icon",
        "filters": [["module", "=", "NANDO_CRM"]],
    },
    {
        "dt": "Report",
        "filters": [["module", "=", "NANDO_CRM"]],
    },
    {
        "dt": "Role",
        "filters": [["name", "in", [
            "Role Name 1",
            "Role Name 2",
        ]]],
    },
]
```

Replace role names with your **custom** roles only (from inventory). Do **not** export standard ERPNext roles.

Commit and push **before** exporting fixtures if you want a clean git trail:

```bash
cd nando-deployment/custom-apps/nando_crm
git add nando_crm/hooks.py
git commit -m "Configure fixture filters for NANDO_CRM export"
git push origin main
```

Rebuild dev so the container runs the new `hooks.py`:

```bash
# bump CUSTOM_TAG in erpnext-dev.env if you want a new image label
./nando-deployment/build-custom-image.sh nando-deployment/erpnext-dev.env
docker compose --project-name erpnext -f nando-deployment/erpnext-dev.yaml up -d
```

---

### 2.6 Reassign custom DocTypes → module `NANDO_CRM`

**Per DocType — Desk UI**

1. Search → **DocType** list → open each custom DocType from inventory
2. Set **Module** → `NANDO_CRM`
3. Save (with developer mode on, this also writes JSON under `apps/nando_crm/.../doctype/`)

**Include child table DocTypes** (Table type) used by your custom DocTypes — reassign those too.

**Bulk reassignment — bench console** (replace names with yours)

```bash
docker compose --project-name erpnext -f nando-deployment/erpnext-dev.yaml exec backend \
  bench --site apps.internal.nandoai.com console
```

```python
import frappe

TARGET_MODULE = "NANDO_CRM"
# Edit this list from your inventory:
DOCTYPE_NAMES = [
    "My Custom DocType",
    "My Child Table",
]

for name in DOCTYPE_NAMES:
    if not frappe.db.exists("DocType", name):
        print(f"SKIP missing: {name}")
        continue
    doc = frappe.get_doc("DocType", name)
    doc.module = TARGET_MODULE
    doc.save(ignore_permissions=True)
    print(f"OK {name} -> {TARGET_MODULE}")

frappe.db.commit()
exit()
```

**Explicit export** (if Save did not write files, or you prefer CLI):

```bash
docker compose --project-name erpnext -f nando-deployment/erpnext-dev.yaml exec backend \
  bench --site apps.internal.nandoai.com export-doc "DocType" "My Custom DocType"
```

Repeat for each DocType and child table.

**Verify files in container:**

```bash
docker compose --project-name erpnext -f nando-deployment/erpnext-dev.yaml exec backend \
  find /home/frappe/frappe-bench/apps/nando_crm -path '*/doctype/*' -name '*.json' | head -30
```

---

### 2.7 Reassign Client Scripts and Server Scripts

**Desk UI**

- **Client Script** list → open each → set **Module** → `NANDO_CRM` → Save
- **Server Script** list → open each → set **Module** → `NANDO_CRM` → Save

Custom Fields on standard forms (Sales Order, Customer, etc.) **do not** need a module change — they are picked up by the `"Custom Field"` fixture entry.

**Bulk — bench console**

```python
import frappe

TARGET = "NANDO_CRM"
for dt in ("Client Script", "Server Script"):
    for name in frappe.get_all(dt, pluck="name"):
        frappe.db.set_value(dt, name, "module", TARGET)
        print(f"{dt}: {name} -> {TARGET}")
frappe.db.commit()
exit()
```

Run inside `bench console` as above.

---

### 2.8 Reassign Workspaces and Desktop Icons

See also [README_workspaces.md](README_workspaces.md).

**Workspaces — Desk UI**

1. **Workspace** list → open each CRM workspace
2. Set **Module** → `NANDO_CRM`
3. Save

**Workspaces — fix app + module in bulk** (use exact workspace **names** from inventory)

```python
import frappe

WORKSPACE_NAMES = ["NANDO_CRM"]  # extend from inventory

for name in WORKSPACE_NAMES:
    frappe.db.set_value("Workspace", name, {
        "module": "NANDO_CRM",
        "app": "nando_crm",
    })
    print(f"Workspace {name} updated")
frappe.db.commit()
exit()
```

If a workspace must be **public**, use the console patterns in [README_workspaces.md](README_workspaces.md) (`public=1`, `for_user=""`, `is_hidden=0`).

**Desktop Icons**

1. **Desktop Icon** list → open each icon for your CRM sidebar
2. Set **Module** → `NANDO_CRM` where the field exists
3. Save

After workspace changes:

```bash
docker compose --project-name erpnext -f nando-deployment/erpnext-dev.yaml exec backend \
  bench --site apps.internal.nandoai.com clear-cache
```

Log out/in on Desk or **Help → Clear Cache**.

---

### 2.9 Reassign Reports

**Desk UI**

1. **Report** list → filter custom / script / query reports you use
2. Open each → **Module** → `NANDO_CRM` → Save

**Script Reports** with Python code: after reassignment, open once in Desk and Save so developer mode exports `.py` + `.json` into `apps/nando_crm/.../report/`.

**CLI export:**

```bash
docker compose --project-name erpnext -f nando-deployment/erpnext-dev.yaml exec backend \
  bench --site apps.internal.nandoai.com export-doc "Report" "My Report Name"
```

---

### 2.10 Custom roles (for `hooks.py` only)

Roles are global — no module field. List custom roles in inventory and ensure they appear in the **`Role`** fixture filter in `hooks.py` (step 2.5).

To verify which roles are custom:

```python
import frappe
print(frappe.get_all("Role", filters={"is_custom": 1, "disabled": 0}, pluck="name"))
exit()
```

**Do not** bulk-export all roles — only names you created.

---

### 2.11 Export fixtures (scripts, fields, roles, workspaces, reports)

Runs against the **`fixtures`** list in `hooks.py` inside the running container.

```bash
docker compose --project-name erpnext -f nando-deployment/erpnext-dev.yaml exec backend \
  bench --site apps.internal.nandoai.com export-fixtures
```

**Verify fixture files:**

```bash
docker compose --project-name erpnext -f nando-deployment/erpnext-dev.yaml exec backend \
  ls -la /home/frappe/frappe-bench/apps/nando_crm/nando_crm/fixtures/
```

You should see JSON files such as `client_script.json`, `server_script.json`, `custom_field.json`, `workspace.json`, etc. (exact names depend on what was exported).

---

### 2.12 Copy exported app tree from container to git

If you edited on the server and need to commit from a checkout:

```bash
docker compose --project-name erpnext -f nando-deployment/erpnext-dev.yaml cp \
  backend:/home/frappe/frappe-bench/apps/nando_crm \
  /tmp/nando_crm_export

# merge into your clone, e.g.:
rsync -a /tmp/nando_crm_export/ ./nando-deployment/custom-apps/nando_crm/
```

Or fetch fresh and copy only changed paths:

```bash
./nando-deployment/fetch-custom-app.sh nando-deployment/erpnext-dev.env
# manually copy doctype/, fixtures/, workspace/ from container export
```

**Commit and push:**

```bash
cd nando-deployment/custom-apps/nando_crm
git status
git add nando_crm/fixtures/ nando_crm/nando_crm/doctype/ nando_crm/nando_crm/workspace/ nando_crm/nando_crm/report/
git commit -m "Export CRM Desk customizations from dev"
git push origin main
```

Adjust paths to match your app’s module folder layout (`bench new-app` may use `nando_crm/nando_crm/` or similar).

---

### 2.13 Rebuild dev and verify

```bash
# bump CUSTOM_TAG in erpnext-dev.env
./nando-deployment/build-custom-image.sh nando-deployment/erpnext-dev.env
docker compose --project-name erpnext -f nando-deployment/erpnext-dev.yaml up -d

docker compose --project-name erpnext -f nando-deployment/erpnext-dev.yaml exec backend \
  bench --site apps.internal.nandoai.com migrate

docker compose --project-name erpnext -f nando-deployment/erpnext-dev.yaml exec backend \
  bench --site apps.internal.nandoai.com clear-cache
```

**Desk checks on** `https://apps.internal.nandoai.com:3003`:

- [ ] Custom DocTypes open and list views work
- [ ] Client Scripts run (form events, buttons)
- [ ] Server Scripts run (validate, API, scheduler if used)
- [ ] Custom fields visible on standard forms
- [ ] Workspaces appear (roles + **Allow Modules** includes `NANDO_CRM`)
- [ ] Reports run

**Console sanity check — nothing left on wrong module:**

```python
import frappe
wrong = frappe.get_all("DocType", filters={"custom": 1, "module": ["!=", "NANDO_CRM"]}, pluck="name")
print("DocTypes not on NANDO_CRM:", wrong)
exit()
```

When Phase 2 passes, proceed to [Phase 4 — Promote to main](#phase-4--promote-to-main). Phase 3 below is a short summary of export steps (included above).

---

## Phase 3 — Export summary (reference)

Steps 2.11–2.13 above are the export workflow. Quick reference:

```bash
bench --site apps.internal.nandoai.com set-config developer_mode 1
bench --site apps.internal.nandoai.com export-doc "DocType" "<Name>"   # per DocType
bench --site apps.internal.nandoai.com export-fixtures
# commit nando-erp-crm, rebuild dev image, migrate, verify
```

---

## Phase 4 — Promote to main

### 4.1 Backup main

```bash
docker compose --project-name erpnext-main -f nando-deployment/erpnext-main.yaml exec backend \
  bench --site apps.internal.nandoai.com backup --with-files
```

### 4.2 Build main image (includes `nando_crm` only)

`erpnext-main.env` already sets `CUSTOM_APP_KEYS=nando_crm`. On the server:

```bash
./nando-deployment/build-custom-image.sh nando-deployment/erpnext-main.env
docker compose --project-name erpnext-main -f nando-deployment/erpnext-main.yaml up -d
```

### 4.3 Install app and apply config

```bash
docker compose --project-name erpnext-main -f nando-deployment/erpnext-main.yaml exec backend \
  bench --site apps.internal.nandoai.com install-app nando_crm

docker compose --project-name erpnext-main -f nando-deployment/erpnext-main.yaml exec backend \
  bench --site apps.internal.nandoai.com migrate

docker compose --project-name erpnext-main -f nando-deployment/erpnext-main.yaml exec backend \
  bench --site apps.internal.nandoai.com import-fixtures
```

### 4.4 Server Scripts + cache

```bash
docker compose --project-name erpnext-main -f nando-deployment/erpnext-main.yaml exec backend \
  bench set-config -g server_script_enabled 1

docker compose --project-name erpnext-main -f nando-deployment/erpnext-main.yaml restart backend

docker compose --project-name erpnext-main -f nando-deployment/erpnext-main.yaml exec backend \
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
