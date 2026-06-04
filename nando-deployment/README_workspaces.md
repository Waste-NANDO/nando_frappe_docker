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
3. If the icon is missing on the Desktop home screen, create a **Desktop Icon**:
   - **Link Type**: `Workspace Sidebar`
   - **Link To**: workspace title (e.g. `NANDO_CRM`)
   - **Roles**: same as intended audience

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
