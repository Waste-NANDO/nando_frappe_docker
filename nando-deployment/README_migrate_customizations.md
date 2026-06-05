# Migrating Desk customizations (dev → main)

Guide for promoting **GUI-built ERPNext customizations** from dev (`:3003`) to main (`:3000`).

| App | Repo | Role |
|-----|------|------|
| **`nando_crm`** | [nando-erp-crm](https://github.com/Waste-NANDO/nando-erp-crm) | CRM Desk config: scripts, DocTypes, roles, workspaces, reports |
| **`nando_fulfillment`** | [nando-erpnext-module](https://github.com/Waste-NANDO/nando-erpnext-module) | Fulfillment / ops entities (separate lifecycle) |

Full deployment: [DEPLOYMENT.md](../DEPLOYMENT.md).  
Workspaces: [README_workspaces.md](README_workspaces.md).

## Starting guideline: custom apps bound to images

**Default rule:** Desk customizations you intend to keep must belong to a **custom app** that is listed in `CUSTOM_APP_KEYS` for that stack. The env file defines which apps are fetched, baked into the Docker image, and installed on the site — so it also defines **what you migrate** and what stays dev-only.

| Stack | Env file | `CUSTOM_APP_KEYS` | Role in migration |
|-------|----------|-------------------|-------------------|
| Dev `:3003` | [`erpnext-dev.env`](erpnext-dev.env) | `nando_crm`, `nando_fulfillment` | Workshop: GUI customizations live in the **dev DB**; export targets app repo **`main`** branch; **`dev`** branch stays minimal so dev image rebuilds do not overwrite Desk work |
| Main `:3000` | [`erpnext-main.env`](erpnext-main.env) | `nando_crm` | Production: receives only apps present in this list (today: CRM only) |

**How to know what needs migrating**

1. Compare `CUSTOM_APP_KEYS` on dev vs main. Anything in **dev but not in main** (e.g. `nando_fulfillment`) is **not** part of a main promotion until you add that key to `erpnext-main.env` and rebuild the main image.
2. For each app you **do** promote, every customization must be owned by that app (module + `hooks.py` fixtures) and committed in its repo before you build the target stack's image.
3. Promotion is **app code + fixtures in the image**, not a database copy. Rebuild main with the updated app repo (`main` branch), deploy, then `install-app` / `migrate` / `import-fixtures` on main.

**Workflow in one line:** customize on dev (DB) → assign to the correct app module → export → commit fixtures to app repo **`main`** → rebuild **main** image → `install-app` / `migrate` / `import-fixtures` on main. Dev image rebuilds pull the empty **`dev`** branch and leave DB customizations intact.

**Not in scope for this path:** transactional data (customers, deals, stock, users, calendar events, OAuth tokens). Do not restore the dev database onto main.

## What migrates

Each row below applies to the **owning app** (CRM → `nando_crm`; fulfillment → `nando_fulfillment` when that app is in the target stack's `CUSTOM_APP_KEYS`).

| Artifact | Mechanism | Typical owner |
|----------|-----------|---------------|
| Server Script, Client Script | Fixture JSON | `nando_crm` |
| Custom Fields, Property Setters | Fixture JSON | `nando_crm` |
| Custom DocTypes | App JSON under `<app>/.../doctype/` + `migrate` | `nando_crm` |
| Roles (custom only) | Fixture JSON (filtered in `hooks.py`) | `nando_crm` |
| Workspaces, Desktop Icons | Fixture JSON or developer-mode export | `nando_crm` |
| Reports | Fixture JSON and/or app module files | `nando_crm` |
| Google / email integration (optional) | Fixture JSON — **structure only**; secrets re-entered on main | `nando_crm` |

## Architecture

Desk work and promotion use **three separate layers**. Do not treat the app repo or the main database as a copy of dev.

| Layer | Dev `:3003` | Main `:3000` |
|-------|-------------|--------------|
| **Site database** | **Source of truth** for ongoing GUI work. Edits are saved here and **stay here** across dev image rebuilds (the `sites` volume persists). | Receives config from the app image (`install-app`, `migrate`, `import-fixtures`) — **not** a restore of the dev DB. |
| **App git — `dev` branch** | Baked into the **dev image** (`NANDO_CRM_BRANCH=dev`). Intentionally **minimal**: `hooks.py`, app skeleton, no exported fixture JSON. Rebuilding dev therefore does **not** replace or reset GUI customizations already in the dev DB. | Not used by main (`NANDO_CRM_BRANCH=main` in [`erpnext-main.env`](erpnext-main.env)). |
| **App git — `main` branch** | **Promotion target**: `export-fixtures` / `export-doc` on dev produce files that you copy out and **commit here** (see [§2.6](#26-copy-exported-app-tree-from-container-to-git)). | Baked into the **main image**; fixtures and DocType JSON are applied to the main site on deploy. |

```text
erpnext-dev.env   → CUSTOM_APP_KEYS=nando_crm,nando_fulfillment
                    dev image pulls app repo dev branch (hooks + skeleton only)

erpnext-main.env  → CUSTOM_APP_KEYS=nando_crm
                    main image pulls app repo main branch (fixtures + DocTypes)

── Dev workshop (:3003) — customizations live in the DB ──
  Desk GUI edits  →  saved to dev site DB  (persists across dev rebuilds)
  assign module   →  NANDO_CRM / nando_crm (owning app)
  export          →  export-fixtures + export-doc  (DB → files in container)

── Git — split branches on purpose ──
  dev branch      →  hooks.py + skeleton; fixtures/ empty or absent
  main branch     →  exported fixtures/, doctype/, workspace/, report/, …

── Promote to main (:3000) ──
  commit + push   →  nando-erp-crm main  (not dev)
  build           →  build-custom-image.sh erpnext-main.env
  apply on site   →  install-app, migrate, import-fixtures
```

**Why `dev` stays empty:** if exported JSON lived on `dev`, every `build-custom-image.sh erpnext-dev.env` would bake stale fixtures into the image and `migrate` / `import-fixtures` could fight the live DB. Keeping fixtures on **`main` only** separates “work in progress in the DB” from “released config for production”.

Local clones: `nando-deployment/custom-apps/<app_key>/` (via `fetch-custom-app.sh`). App key must match a name in `CUSTOM_APP_KEYS` for that env file.

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

## Phase 2 — Tie CRM customizations to `nando_crm` and export (detailed)

Complete this on **dev** (`:3003`) after Phase 1 (`nando_crm` installed in the image and on the site).

This phase implements the [starting guideline](#starting-guideline-custom-apps-bound-to-images) for **CRM**: `nando_crm` is in both dev and main `CUSTOM_APP_KEYS`, so it is what you promote. Fulfillment customizations follow the same pattern under `nando_fulfillment` when that app is added to `erpnext-main.env`.

**Goal:** Every CRM customization is owned by app **`nando_crm`** / module **`NANDO_CRM`**, exported to git in [nando-erp-crm](https://github.com/Waste-NANDO/nando-erp-crm), then verified on dev (rebuilt image) before touching main.

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

### 2.3 Run migration inventory

Save this output — it lists only artifacts owned by **`nando_crm`** (the app in main's `CUSTOM_APP_KEYS`), not every record on the site or anything destined for `nando_fulfillment` only.

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
---

### 2.4 Update `hooks.py` in nando-erp-crm

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
]
```

Omit the **Role** block unless CRM depends on a custom role you created. Standard roles (`Employee Self Service`, etc.) already exist on main.

#### Google Settings, Calendar, Email Account (optional)

**Yes — fixtures can export these**, same as other DocTypes. Add them to the `fixtures` list above, run `export-fixtures`, commit JSON under `nando_crm/fixtures/`.

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

### 2.5 Export fixtures (scripts, fields, roles, workspaces, reports)

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

### 2.6 Copy exported app tree from container to git

Exported fixtures and DocTypes belong on the app repo’s **`main`** branch (or **`master`** if that is the default). The **`dev`** branch stays empty — it only carries `hooks.py` and other build-time config used by the dev image (`NANDO_CRM_BRANCH=dev` in [`erpnext-dev.env`](erpnext-dev.env)). Do **not** commit exported JSON to `dev`.

**1. Check out `main` in your local clone** (before copying anything from the container):

```bash
./nando-deployment/fetch-custom-app.sh nando-deployment/erpnext-main.env

cd nando-deployment/custom-apps/nando_crm
git checkout main   # or: git checkout master
git pull origin main
```

**2. Copy the export from the running dev container** into that checkout:

```bash
docker compose --project-name erpnext -f nando-deployment/erpnext-dev.yaml cp \
  backend:/home/frappe/frappe-bench/apps/nando_crm \
  /tmp/nando_crm_export

rsync -a /tmp/nando_crm_export/nando_crm/ ./nando-deployment/custom-apps/nando_crm/
```

Copy only what changed if you prefer (e.g. `fixtures/`, `doctype/`, `workspace/`, `report/`) instead of a full-tree `rsync`.

**3. Commit and push to `main`:**

```bash
cd nando-deployment/custom-apps/nando_crm
git status
git add nando_crm/fixtures/ nando_crm/nando_crm/doctype/ nando_crm/nando_crm/workspace/ nando_crm/nando_crm/report/
git commit -m "Export CRM Desk customizations from dev"
git push origin main
```

Adjust paths to match your app’s module folder layout (`bench new-app` may use `nando_crm/nando_crm/` or similar).

---

### 2.7 Rebuild dev and verify

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

Steps 2.4–2.7 above are the export workflow. Quick reference:

```bash
bench --site apps.internal.nandoai.com set-config developer_mode 1
bench --site apps.internal.nandoai.com export-doc "DocType" "<Name>"   # per DocType
bench --site apps.internal.nandoai.com export-fixtures
# commit nando-erp-crm, rebuild dev image, migrate, verify
```

---

## Phase 4 — Promote to main

Only apps listed in [`erpnext-main.env`](erpnext-main.env) `CUSTOM_APP_KEYS` are in scope. Today that is **`nando_crm` only** — do not expect `nando_fulfillment` on main until you add it to that env file and rebuild the main image.

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

`CUSTOM_APP_KEYS` is the migration boundary: dev can include more apps than main; main receives only what its list contains.

In `erpnext-dev.env` (app repos track **`dev`** branch):

```env
CUSTOM_APP_KEYS=nando_crm,nando_fulfillment
SITE_INSTALL_APPS=nando_crm,nando_fulfillment

NANDO_CRM_REPO=https://github.com/Waste-NANDO/nando-erp-crm.git
NANDO_CRM_BRANCH=dev

NANDO_FULFILLMENT_REPO=https://github.com/Waste-NANDO/nando-erpnext-module.git
NANDO_FULFILLMENT_BRANCH=dev
```

In `erpnext-main.env` (app repos track **`main`** branch):

```env
CUSTOM_APP_KEYS=nando_crm
SITE_INSTALL_APPS=nando_crm
NANDO_CRM_REPO=https://github.com/Waste-NANDO/nando-erp-crm.git
NANDO_CRM_BRANCH=main
```

App key → env prefix: `nando_crm` → `NANDO_CRM_REPO`, `NANDO_CRM_BRANCH`.

---

## Checklist

| # | Task |
|---|------|
| 0 | Confirm scope: compare `CUSTOM_APP_KEYS` in `erpnext-dev.env` vs `erpnext-main.env` — only shared apps are promoted |
| 1 | Rebuild dev image with apps in dev `CUSTOM_APP_KEYS` |
| 2 | `install-app` missing apps on dev site |
| 3 | Module Def `NANDO_CRM` → app `nando_crm` (repeat pattern per app you own) |
| 4 | Reassign DocTypes, workspaces, reports to the owning app module |
| 5 | Update `hooks.py` fixtures in the app repo |
| 6 | `developer_mode 1`, export DocTypes + `export-fixtures` |
| 7 | Commit, push app repo, rebuild **dev** image, verify `:3003` |
| 8 | Backup main |
| 9 | Merge app repo to `main` branch; build **main** image (`erpnext-main.env`), deploy |
| 10 | `install-app`, `migrate`, `import-fixtures` for each app in main `CUSTOM_APP_KEYS` |
| 11 | `server_script_enabled 1`, clear cache, verify `:3000` |

## Gotchas

- Customizations must be tied to an app in **`CUSTOM_APP_KEYS`** for the target stack — not left on orphan modules or apps that exist only on dev.
- If a customization is not in the rebuilt image's app tree, it will not appear on main after `migrate` / `import-fixtures`.
- **`import-fixtures`** may be needed after `migrate` if fixtures did not sync automatically.
- Do **not** restore dev DB onto main.
- Never `docker compose down -v` on production.
