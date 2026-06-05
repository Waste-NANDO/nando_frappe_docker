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
| Google / email integration (optional) | Fixture JSON — **structure only**; secrets re-entered on main |

**Not included:** transactional data (customers, deals, stock, users, calendar **events**, per-user OAuth tokens).

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

### 2.4 Run migration inventory

Save this output — it lists only artifacts you own for **`nando_crm`**, not every record on the site.

| Section | Filter | Migrate? |
|---------|--------|----------|
| Custom DocTypes | `custom=1` (flag wrong module) | Yes — reassign to `NANDO_CRM` |
| Client / Server Scripts | `module=NANDO_CRM` | Yes |
| Workspaces | `module=NANDO_CRM` | Yes |
| Desktop Icons | `standard=0` | Yes — `standard=1` is ERPNext/Frappe stock |
| Reports | `module=NANDO_CRM` | Yes |
| Custom roles | — | Skip unless you created roles for CRM |
| Custom Fields | — | Skip in inventory — exported via `"Custom Field"` fixture if needed |
| Module Def | target module only | Verify app/package |

**Desktop Icons:** `standard=1` icons ship with ERPNext, Frappe, and HRMS — do **not** export them. Only `standard=0` records are yours (created in Desk or bench console).

```bash
docker compose --project-name erpnext -f nando-deployment/erpnext-dev.yaml exec backend \
  bench --site apps.internal.nandoai.com console
```

```python
import frappe

TARGET_MODULE = "NANDO_CRM"
TARGET_APP = "nando_crm"

def section(title):
    print("\n" + "=" * 60)
    print(title)
    print("=" * 60)

section(f"Custom DocTypes (target module={TARGET_MODULE})")
for d in frappe.get_all("DocType", filters={"custom": 1},
                        fields=["name", "module"], order_by="name"):
    flag = "" if d.module == TARGET_MODULE else f"  <-- reassign from {d.module}"
    print(f"  {d.name:40} module={d.module}{flag}")

section(f"Client Scripts (module={TARGET_MODULE})")
for s in frappe.get_all("Client Script",
        filters={"module": TARGET_MODULE},
        fields=["name", "dt", "module"], order_by="name"):
    print(f"  {s.name:40} on={s.dt} module={s.module}")

section(f"Server Scripts (module={TARGET_MODULE})")
for s in frappe.get_all("Server Script",
        filters={"module": TARGET_MODULE},
        fields=["name", "script_type", "module"], order_by="name"):
    print(f"  {s.name:40} type={s.script_type} module={s.module}")

section(f"Workspaces (module={TARGET_MODULE})")
for w in frappe.get_all("Workspace",
        filters={"module": TARGET_MODULE},
        fields=["name", "module", "public", "app"], order_by="name"):
    print(f"  {w.name:40} module={w.module} public={w.public} app={w.app}")

section("Desktop Icons (standard=0 only — yours to export)")
for d in frappe.get_all("Desktop Icon",
        filters={"standard": 0},
        fields=["name", "label", "link_type", "link_to", "sidebar", "app"],
        order_by="label"):
    print(f"  {d.label or d.name:40} link={d.link_type}/{d.link_to} app={d.app}")

section(f"Reports (module={TARGET_MODULE})")
for r in frappe.get_all("Report",
        filters={"module": TARGET_MODULE},
        fields=["name", "module", "report_type", "ref_doctype"], order_by="name"):
    print(f"  {r.name:40} type={r.report_type} module={r.module}")

section(f"Module Def ({TARGET_MODULE})")
if frappe.db.exists("Module Def", TARGET_MODULE):
    m = frappe.db.get_value("Module Def", TARGET_MODULE,
        ["name", "app_name", "package", "custom"], as_dict=1)
    print(f"  {m.name:40} app={m.app_name} package={m.package} custom={m.custom}")
else:
    print(f"  MISSING — create {TARGET_MODULE} in step 2.3")

exit()
```

**Expected for your site (sanity check):**

- **DocTypes:** 5× `NANDO_*` on `NANDO_CRM`; **`Business Unit`** still on `CRM` → reassign in step 2.6.
- **Scripts:** 3 client + 15 server scripts on `NANDO_CRM`. Ignore `Apply Dev Color` (`module=None`, dev-only).
- **Workspace:** `NANDO_CRM` with `app=nando_crm`.
- **Desktop Icons (`standard=0`):** point at **app** Workspace Sidebars (`standard=1`) — icon `label` = sidebar name (usually workspace name). Do not create custom sidebars in console; see [README_workspaces.md](README_workspaces.md).
- **Reports (6):** All Contracts Value of the year, Last signed contract, Leads with laast contact greater then a week, Sidebar Clients, Sidebar Leads, Sidebar Prospects.
- **Module Def:** `NANDO_CRM` must show `app=nando_crm`, `package=nando_crm` (not `app=frappe`).

Copy the printed list somewhere safe. Anything **not** on module `NANDO_CRM` needs reassignment in the next steps.

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
        "dt": "Workspace Sidebar",
        "filters": [["name", "in", ["NANDO_CRM"]]],  # standard app sidebars only
    },
    {
        "dt": "Desktop Icon",
        "filters": [
            ["standard", "=", 0],
            ["link_to", "in", ["NANDO_CRM"]],  # must match Workspace Sidebar name
        ],
    },
    {
        "dt": "Report",
        "filters": [["module", "=", "NANDO_CRM"]],
    },
    # Optional — only if you created custom roles for CRM:
    # {
    #     "dt": "Role",
    #     "filters": [
    #         ["is_custom", "=", 1],
    #         ["disabled", "=", 0],
    #         ["name", "like", "NANDO%"],       # name starts with NANDO
    #         # ["name", "like", "%CRM%"],     # or name contains CRM
    #     ],
    # },
    #
    # Optional — integration *structure* (see §2.10.1; re-enter secrets on main):
    # "Google Settings",                    # Single — OAuth client id (not secret)
    # "GCalendar Settings",                 # Single — Google Calendar app credentials
    # {
    #     "dt": "Email Account",
    #     "filters": [["name", "like", "NANDO%"]],  # or email_id / domain filter
    # },
]
```

Omit the **Role** block unless CRM depends on a custom role you created. Standard roles (`Employee Self Service`, etc.) already exist on main.

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

In v16, add tiles with **Add To Desktop** on the Workspace form (see [README_workspaces.md — Desktop Icons](README_workspaces.md#desktop-icons-v16)). Do not create custom Workspace Sidebars in the console.

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

Roles are global — no module field. List custom roles in inventory and ensure they match the **`Role`** fixture filter in `hooks.py` (step 2.5).

Fixture filters use the same operators as `frappe.get_all`:

| Intent | Filter |
|--------|--------|
| Exact names | `["name", "in", ["Role A", "Role B"]]` |
| Name starts with | `["name", "like", "NANDO%"]` |
| Name contains | `["name", "like", "%CRM%"]` |
| All custom roles | `["is_custom", "=", 1]` (recommended baseline) |

Combine with `AND` by listing multiple filter rows in the same `filters` list.

To verify which roles match before export:

```python
import frappe
# Preview what your fixture filter would export:
print(frappe.get_all("Role", filters=[
    ["is_custom", "=", 1],
    ["disabled", "=", 0],
    ["name", "like", "NANDO%"],
], pluck="name"))
exit()
```

**Do not** bulk-export all roles — only names you created.

---

### 2.10.1 Google Settings, Calendar, Email Account (optional)

**Yes — fixtures can export these**, same as other DocTypes. Add them to `hooks.py`, run `export-fixtures`, commit JSON under `nando_crm/fixtures/`.

| DocType | Type | Typical use |
|---------|------|-------------|
| **Google Settings** | Single | Google OAuth client id, API key (Maps, Drive, etc.) |
| **GCalendar Settings** | Single | Google **Calendar** integration app credentials |
| **Email Account** | Multi | Incoming/outgoing mail setup, linked DocTypes |
| **GCalendar Account** | Multi | Per-user calendar OAuth — **do not** fixture (user-specific) |
| **Event** / calendar data | Multi | Transactional — **not** fixtures |

**Secrets warning:** `Password` fields (Email Account SMTP/app password, Google client secret) are encrypted with the **site** key. Fixture JSON may contain ciphertext, but it usually **does not work** on main after `import-fixtures` — plan to **re-enter passwords and re-authorize OAuth** on main. Do not commit real production secrets; use dev credentials in git or redact before push.

**Discover what to export** (bench console):

```python
import frappe

for single in ["Google Settings", "GCalendar Settings"]:
    if frappe.db.exists("DocType", single):
        d = frappe.get_single(single).as_dict()
        print(single, {k: d.get(k) for k in ("enable", "client_id", "api_key") if k in d})

print("\nEmail Account:")
for ea in frappe.get_all("Email Account",
        fields=["name", "email_id", "enable_incoming", "enable_outgoing", "default_incoming", "default_outgoing"],
        order_by="name"):
    print(f"  {ea.name!r}  {ea.email_id}  in={ea.enable_incoming} out={ea.enable_outgoing}")
exit()
```

**Example `hooks.py` additions** (adjust filters to your account names):

```python
"Google Settings",
"GCalendar Settings",
{
    "dt": "Email Account",
    "filters": [
        ["name", "like", "NANDO%"],           # account name prefix
        # ["email_id", "like", "%@yourdomain.com"],
    ],
},
```

Preview filter matches before export:

```python
import frappe
print(frappe.get_all("Email Account", filters=[["name", "like", "NANDO%"]], pluck="name"))
exit()
```

After `import-fixtures` on main:

1. **Google Settings** / **GCalendar Settings** → re-enter **Client Secret**; update Google Cloud redirect URIs for main URL.
2. **Email Account** → re-enter **Password** / app password; verify SMTP/IMAP against main hostname.
3. **GCalendar Account** (per user) → each user re-authorizes Google Calendar on main.
4. Update **Authorized redirect URIs** in Google Cloud from dev (`:3003`) to main (`:3000`) domain.

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
