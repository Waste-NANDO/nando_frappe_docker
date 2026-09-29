# 02 — Develop a structure change

Normal path for DocTypes, custom fields, scripts, workspaces, sidebars, reports, etc.

## Rules

1. Edit structure on **local** Desk (preferred) or cloud-dev (then [capture](04-capture-drift.md)).
2. Every new/changed document must have `module` = `NANDO_CRM` or `NANDO_Operations` (pick the owning app).
3. Never put Email Account / Google Settings / System Settings in fixtures.
4. Do not edit files under `apps/erpnext` or `apps/frappe` — only custom apps. (See [Customizing core DocTypes](#customizing-core-doctypes) below.)

## Customizing core DocTypes

Adding fields, scripts, or layout tweaks **on** a standard DocType (Customer, Item, Delivery Note, Sales Order, …) is **not** editing core files.

| Do this (supported) | Not this |
|---------------------|----------|
| Desk → **Customize Form** / Custom Field / Property Setter / Client Script / Server Script targeting a core DocType | Editing Python/JS/JSON under `apps/erpnext/…` or `apps/frappe/…` |
| Set **Module** = `NANDO_CRM` or `NANDO_Operations` on that document | Leaving Module empty (export ownership breaks / lint fails) |
| `nando-erp export` → commit fixtures in `nando_crm` or `nando_fulfillment` | Committing changes inside the `erpnext` / `frappe` git checkouts |

Example: field `custom_service_order` on Delivery Note → Custom Field with module `NANDO_Operations` → ends up in `nando_fulfillment/.../fixtures/custom_field.json`. Same pattern for Property Setters and scripts that run on core DocTypes.

If you need **behavior** that Customize Form cannot express, put overrides in the custom app (`doc_events`, `override_doctype_class`, app Python, patches) — still not in core trees. Forking or patching `erpnext`/`frappe` source is out of band and breaks version pins.

## Steps (local)

### 1. Branch

```bash
cd "$NANDO_LOCAL_BENCH/apps/nando_fulfillment"   # or nando_crm
git fetch origin
git checkout dev
git pull
git checkout -b feature/my-change
```

### 2. Make the change in Desk

- Set **Module** on the document to `NANDO_Operations` or `NANDO_CRM`.
- Core DocTypes: use Customize Form / Custom Field / etc., then set that same Module (see above).

### 3. Export and lint

```bash
nando-erp export --target local
nando-erp lint
```

Fix any ownership / missing-module errors before committing.

### 4. Commit and open a PR into `dev`

```bash
cd "$NANDO_LOCAL_BENCH/apps/nando_fulfillment"
git add -A
git status   # should only touch fixtures/ + your Python under the app
git commit -m "Add …"
git push -u origin HEAD
gh pr create --base dev --title "…" --body "…"
```

Repeat for `nando_crm` if that app also changed.

### 5. Ship

After the PR is merged to `dev`:

1. [03 — Deploy to cloud-dev](03-deploy-cloud-dev.md)
2. Validate
3. [05 — Promote to prod](05-promote-prod.md) when ready

## Python / patches (not Desk)

Put Python under the app package, add entries to `patches.txt` when needed, commit on the same feature branch. Image rebuild (`nando-erp build`) is required for Python changes; fixture-only changes still need a build so the image contains the new JSON.

## What not to do

- Do not edit or commit under `apps/erpnext` or `apps/frappe` — customize core DocTypes via Custom Field / Property Setter / scripts with a Module set (see above).
- Do not commit fixture JSON to git `dev` that came from an unfiltered `export-fixtures` (would overwrite the other app’s module).
- Do not use `deprecated/sync-fixtures-*.sh` for normal work — that path is legacy.
- Do not `docker compose down -v` on the server.
