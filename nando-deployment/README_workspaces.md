# Workspaces (Frappe v16) — lessons learned

Short reference for the **dev** stack (`erpnext`, site `apps.internal.nandoai.com`, port `:3003`).  
Full deployment context: [DEPLOYMENT.md](../DEPLOYMENT.md).

## Public vs private

| Type | Who sees it | Where it lives in Desk |
|------|-------------|------------------------|
| **Private** | Only the owner (`for_user` = their email) | **My Workspaces** / `/desk/private/<slug>` |
| **Public** | Users with matching **Roles** and **module** access | Desktop + public sidebar / `/desk/<slug>` |

Developer mode and server scripts are **unrelated** to making a workspace public.

## The grey **Public** checkbox is normal

On the **Workspace** DocType form (List → Workspace → open a record), the **Public** field is **`read_only` by design** in Frappe v16. It is always grey on create and after save.

Do **not** use that form to toggle public.

### How to create a public workspace

**Option A — Desk UI (preferred)**

1. Open any workspace on Desk.
2. **⋮** → **New**.
3. Check **Public** before **Create** (checkbox only appears if you have **Workspace Manager**).
4. Set **Module** (e.g. `NANDO_CRM`) and **Roles** if the workspace should not be visible to everyone.

**Option B — bench console**

```bash
docker compose --project-name erpnext -f nando-deployment/erpnext-dev.yaml exec backend \
  bench --site apps.internal.nandoai.com console
```

```python
import frappe

ws = frappe.get_doc("Workspace", "NANDO_CRM")  # exact name from Workspace list
ws.public = 1
ws.for_user = ""
ws.is_hidden = 0
ws.module = "NANDO_CRM"
ws.app = "nando_crm"
ws.save(ignore_permissions=True)
frappe.db.commit()
exit()
```

Or set values directly:

```python
frappe.db.set_value("Workspace", "NANDO_CRM", {
    "public": 1, "for_user": "", "is_hidden": 0,
    "module": "NANDO_CRM", "app": "nando_crm",
})
frappe.db.commit()
```

A successful save returns `<Workspace: doctype=Workspace …>` — that is success, not an error.

## Roles and permissions

| Need | Role / setting |
|------|----------------|
| Create/edit **public** workspaces (Desk **New** dialog) | **Workspace Manager** |
| Edit **Server Scripts** | **Script Manager** (+ `server_script_enabled` in config) |
| See a public workspace | Role listed on workspace **Roles** tab (empty = all), and user **Allow Modules** includes the workspace module |

Add roles on **User** → **Roles**, then log out and back in.

## After changing a workspace

Boot info is cached per user in Redis:

```bash
docker compose --project-name erpnext -f nando-deployment/erpnext-dev.yaml exec backend \
  bench --site apps.internal.nandoai.com clear-cache
```

Then log out/in or **Help → Clear Cache**.

Verify in the browser console:

```javascript
frappe.boot.workspaces.pages.filter(p => p.name === "NANDO_CRM")
// expect public: 1
```

Verify in bench:

```python
frappe.db.get_value("Workspace", "NANDO_CRM",
    ["public", "for_user", "is_hidden", "module"], as_dict=1)
```

## v16 Desk visibility

Public in the database is not always enough for the **Desktop** icon grid.

1. **`is_hidden`** must be `0` for non–Workspace Managers to see the page in the sidebar.
2. Users need the workspace **module** in **Allow Modules** (and not in **Block Modules**).
3. If the icon is missing on the Desktop home screen, create a **Desktop Icon** (see [Fix broken Desktop Icons](#fix-broken-desktop-icons-v16) below).

URLs:

- Public: `https://apps.internal.nandoai.com:3003/desk/nando-crm`
- Private: `https://apps.internal.nandoai.com:3003/desk/private/nando-crm`

## Custom module gotcha

Saving a **public** workspace tied to a **custom** module can fail with:

`Package must be set for custom Module …`

Fix on **Module Def** (e.g. `NANDO_CRM`):

- Set **Package** to the app name (`nando_crm`), **or**
- Uncheck **Custom** if that matches how the module is shipped in the app repo.

## Private → public in the UI

If a workspace was first saved as **private**, the **Public** flag is not reliably toggled later from the Workspace form (known v16 limitation). Prefer creating a **new** workspace with **Public** checked upfront, or use bench/`db.set_value` as above.

## Version control (custom app)

With **developer_mode** on, saving a **public** workspace with a **module** set can export JSON under the app tree (e.g. `apps/nando_crm/.../workspace/`). Commit those files to promote the workspace with the app image to main.

## Related fixes (same dev session)

- **Server Script** code editor 404: Ace lives under `sites/assets/frappe/node_modules/ace-builds/`. [`materialize-assets.sh`](materialize-assets.sh) copies it after each materialize (frontend nginx does not see `apps/` in the backend container layer).
- Asset rebuild: [`setup-assets.sh`](setup-assets.sh) or [`README_assets.md`](README_assets.md).

## Desktop Icons (v16)

Custom **Workspace Sidebars** come from the app (`workspace_sidebar/*.json` + `bench migrate`). Use the GUI to add desktop tiles — do not duplicate sidebars in the console.

### Remove custom desktop icons (console)

```bash
docker compose --project-name erpnext -f nando-deployment/erpnext-dev.yaml exec backend \
  bench --site apps.internal.nandoai.com console
```

Paste **one block**:

```python
import frappe
from frappe.desk.doctype.desktop_icon.desktop_icon import clear_desktop_icons_cache

# Labels to delete (Desktop Icon name = label in v16)
TO_REMOVE = [
    "NANDO_CRM", "NANDO.CRM", "NANDO.Fulfillment", "NANDO.Fulfillment",
    "Fulfillment", "NANDO Fulfillment",
]

# Optional: remove every non-standard icon you own
# TO_REMOVE = frappe.get_all("Desktop Icon", filters={"standard": 0}, pluck="name")

print("Removing desktop icons...")
for name in TO_REMOVE:
    if frappe.db.exists("Desktop Icon", name):
        frappe.delete_doc("Desktop Icon", name, ignore_permissions=True)
        print(f"  deleted icon {name!r}")

print("Removing mistaken custom sidebars (standard=0 only)...")
for name in ["NANDO.CRM", "NANDO.Fulfillment"]:
    if frappe.db.exists("Workspace Sidebar", name):
        sb = frappe.get_doc("Workspace Sidebar", name)
        if not sb.standard:
            frappe.delete_doc("Workspace Sidebar", name, ignore_permissions=True)
            print(f"  deleted sidebar {name!r}")

frappe.db.commit()
clear_desktop_icons_cache()
print("Done. Run clear-cache, then add icons from the GUI.")
exit()
```

```bash
docker compose --project-name erpnext -f nando-deployment/erpnext-dev.yaml exec backend \
  bench --site apps.internal.nandoai.com clear-cache
```

Log out and back in. Standard ERPNext icons (`standard=1`) are untouched.

### Add desktop icons (GUI) — preferred

Use **Add to Desktop** on the **Workspace** form (one tile per workspace).

1. Search → **Workspace** list → open **NANDO_CRM**.
2. Click **Add to Desktop** (top of the form, next to actions).
3. For a **second** tile (e.g. fulfillment): open **NANDO_FULFILLMENT** in the Workspace list and repeat.
4. Go to Desk home (`/desk/home`).
5. If the tile is missing: **Help → Clear Cache** or `bench clear-cache`, then log out/in.

**Why the button disappears**

Frappe only shows **Add to Desktop** when **no Workspace Sidebar yet links to that workspace** (including app sidebars from migrate). After you add one — or if `nando_crm` / `nando_fulfillment` already ship a sidebar — the button is hidden **for that workspace**. That is normal; you do not get two tiles from the same workspace.

| Situation | What to do |
|-----------|------------|
| First workspace, no app sidebar yet | **Add to Desktop** on Workspace form |
| Button gone on that workspace | Tile already linked — check Desk home |
| Second workspace (e.g. fulfillment) | Open **that** workspace’s form; if button still missing, use **Desktop Icon → New** (below) |

Requirements:

- Workspace is **public** (`public=1`, `for_user` empty).
- Your user has the workspace **module** in **Allow Modules**.

### Add desktop icons (GUI) — manual Desktop Icon form

Use this for the **second app** when **Add to Desktop** is already hidden (app sidebar exists):

1. Search → **Desktop Icon** list → **Add Desktop Icon** (or **New**).
2. Set:

   | Field | Value |
   |-------|--------|
   | **Label** | Same as **Workspace Sidebar** name (usually workspace name, e.g. `NANDO_CRM`) |
   | **Icon Type** | `Link` |
   | **Link Type** | `Workspace Sidebar` |
   | **Link To** | Pick the app sidebar (e.g. `NANDO_CRM`) — must already exist |
   | **Standard** | unchecked |

3. Save → clear cache → log out/in.

**Important:** **Label** must match the **Workspace Sidebar** name exactly (Desk looks up `label.lower()`). Do not invent labels like `NANDO.CRM` unless the app defines a sidebar with that title. Edit sidebar content in the **app repo**, not by creating a second sidebar in the DB.

### Troubleshooting

**"Icon is not correctly configured…"** — **Label** / **Link To** do not match an existing **Workspace Sidebar**, or that sidebar has no items. Fix the app sidebar + `bench migrate`; do not add a duplicate sidebar in the console.

Discover which sidebar names exist:

```python
import frappe
for ws in ["NANDO_CRM", "NANDO_FULFILLMENT"]:
    rows = frappe.db.sql("""
        select ws.name, ws.standard, ws.app
        from `tabWorkspace Sidebar` ws
        left join `tabWorkspace Sidebar Item` wsi
          on wsi.parent = ws.name and wsi.link_type = 'Workspace' and wsi.link_to = %s
        where ws.name = %s or wsi.name is not null
    """, (ws, ws), as_dict=1)
    print(ws, "->", rows or "NO SIDEBAR — fix in app")
exit()
```

### Compare two sidebars + desktop icons

Use when one tile works and another shows **"Icon is not correctly configured"**. Paste **one block** in bench console (no functions — avoids partial-paste errors):

**Naming trap:** **Add to Desktop** creates `Workspace Sidebar.title` = **Workspace.name** (the workspace record you opened), not an arbitrary label. If you expected `test_icon_sidebar` but the workspace is named `My Test`, the sidebar is **`My Test`**, not `test_icon_sidebar`. Run the trace script below first.

#### Trace what Add to Desktop actually created

```python
import frappe

print("=" * 70)
print("DESKTOP ICONS (custom, standard=0)")
print("=" * 70)
for ic in frappe.get_all("Desktop Icon", filters={"standard": 0},
        fields=["name", "label", "link_type", "link_to", "hidden"], order_by="modified desc"):
    sb_exists = frappe.db.exists("Workspace Sidebar", ic.link_to or ic.label)
    print(f"  icon {ic.name!r}  label={ic.label!r}  link_to={ic.link_to!r}  sidebar_exists={bool(sb_exists)}")

print("\n" + "=" * 70)
print("WORKSPACE SIDEBARS matching 'test' or recent custom")
print("=" * 70)
for sb in frappe.get_all("Workspace Sidebar",
        filters={"name": ["like", "%test%"]},
        fields=["name", "title", "standard", "app", "module"], order_by="modified desc"):
    n_items = frappe.db.count("Workspace Sidebar Item", {"parent": sb.name})
    print(f"  {sb.name!r}  standard={sb.standard}  app={sb.app}  items={n_items}")

print("\n" + "=" * 70)
print("WORKSPACES matching 'test'")
print("=" * 70)
for ws in frappe.get_all("Workspace", filters={"name": ["like", "%test%"]},
        fields=["name", "title", "module", "public", "app"]):
    has_icon = frappe.db.exists("Desktop Icon", ws.name)
    has_sidebar = frappe.db.exists("Workspace Sidebar", ws.name)
    print(f"  {ws.name!r}  public={ws.public}  icon={has_icon}  sidebar={has_sidebar}")
exit()
```

Use the **`link_to`** / **`name`** values from that output as `SIDEBARS` in the comparison script — not a guessed name.

#### Side-by-side comparison

```python
import frappe
boot = frappe.boot.get_bootinfo()

SIDEBARS = ["NANDO_FULFILLMENT", "test_icon_sidebar"]

print("=" * 70)
print("FUZZY RESOLVE")
print("=" * 70)
for hint in ["NANDO", "Fulfillment", "test_icon"]:
    rows = frappe.get_all(
        "Workspace Sidebar",
        filters={"name": ["like", f"%{hint}%"]},
        fields=["name", "title", "standard", "app", "module"],
    )
    if rows:
        print(f"  {hint!r}:", rows)

print("\n" + "=" * 70)
print("COMPARISON")
print("=" * 70)
reports = {}

for raw in SIDEBARS:
    name = raw
    if not frappe.db.exists("Workspace Sidebar", name):
        hits = frappe.get_all("Workspace Sidebar", filters={"name": ["like", f"%{raw}%"]}, pluck="name")
        name = hits[0] if hits else raw

    print(f"\n--- {raw!r} -> sidebar {name!r} ---")
    if not frappe.db.exists("Workspace Sidebar", name):
        print("  MISSING Workspace Sidebar")
        reports[raw] = None
        continue

    sb = frappe.get_doc("Workspace Sidebar", name)
    ws_links = [
        {"label": i.label, "link_type": i.link_type, "link_to": i.link_to}
        for i in (sb.items or [])
        if i.type != "Section Break" and i.link_type == "Workspace"
    ]
    boot_key = name.lower()
    boot_entry = boot.workspace_sidebar_item.get(boot_key)
    boot_ok = boot_key in boot.workspace_sidebar_item
    boot_items = len(boot_entry["items"]) if boot_entry else 0

    print(f"  standard={sb.standard}  app={sb.app}  module={sb.module!r}  for_user={sb.for_user!r}")
    print(f"  db_items={len(sb.items or [])}  workspace_links={[x['link_to'] for x in ws_links]}")
    print(f"  boot_key={boot_key!r}  in_bootinfo={boot_ok}  boot_items={boot_items}")

    for x in ws_links:
        ws = x["link_to"]
        if frappe.db.exists("Workspace", ws):
            w = frappe.db.get_value("Workspace", ws, ["public", "module", "app", "is_hidden"], as_dict=1)
            print(f"    workspace {ws!r}: {w}")
        else:
            print(f"    workspace {ws!r}: MISSING")

    icons = frappe.get_all(
        "Desktop Icon",
        or_filters=[["link_to", "=", name], ["label", "=", name], ["name", "=", name]],
        fields=["name", "label", "link_type", "link_to", "standard", "hidden"],
    )
    print(f"  desktop icons ({len(icons)}):")
    icon_rows = []
    for ic in icons:
        icon = frappe.get_doc("Desktop Icon", ic.name)
        label_key = (icon.label or "").lower()
        entry = boot.workspace_sidebar_item.get(label_key)
        issues = []
        if not entry:
            issues.append(f"no boot key [{label_key!r}]")
        elif not entry.get("items"):
            issues.append("0 boot items")
        if icon.link_to and icon.link_to != icon.label:
            issues.append(f"link_to={icon.link_to!r} != label={icon.label!r}")
        try:
            permitted = icon.is_permitted(boot)
        except Exception as e:
            permitted = f"ERROR: {e}"
        print(f"    {icon.name!r}  label={icon.label!r}  link_to={icon.link_to!r}  permitted={permitted}")
        if issues:
            print(f"      ISSUES: {issues}")
        icon_rows.append({"label": icon.label, "link_to": icon.link_to, "permitted": permitted, "issues": issues})

    reports[raw] = {
        "standard": sb.standard, "app": sb.app, "module": sb.module,
        "item_count": len(sb.items or []), "boot_ok": boot_ok, "boot_items": boot_items,
        "icons": icon_rows,
    }

print("\n" + "=" * 70)
print("DIFF SUMMARY")
print("=" * 70)
if reports.get(SIDEBARS[0]) and reports.get(SIDEBARS[1]):
    a, b = SIDEBARS[0], SIDEBARS[1]
    ra, rb = reports[a], reports[b]
    for field in ["standard", "app", "module", "item_count", "boot_ok", "boot_items"]:
        va, vb = ra[field], rb[field]
        mark = "  <-- DIFF" if va != vb else ""
        print(f"  {field}: {a}={va!r}  |  {b}={vb!r}{mark}")
    print(f"  icons: {a}={len(ra['icons'])}  |  {b}={len(rb['icons'])}")

print("\nDone.")
exit()
```
