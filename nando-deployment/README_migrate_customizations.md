# Migrating Desk customizations (dev → main)

Promote **GUI-built ERPNext config** from dev (`:3003`) to main (`:3000`).

| App | Repo | Module |
|-----|------|--------|
| `nando_crm` | [nando-erp-crm](https://github.com/Waste-NANDO/nando-erp-crm) | `NANDO_CRM` |
| `nando_fulfillment` | [nando-erpnext-module](https://github.com/Waste-NANDO/nando-erpnext-module) | `NANDO Fulfillment` |

See also: [DEPLOYMENT.md](../DEPLOYMENT.md), [README_workspaces.md](README_workspaces.md).

**Not in scope:** transactional data (customers, deals, stock, users). Never restore the dev DB onto main.

---

## 1. Architecture

Three layers — do not confuse them.

| Layer | Dev `:3003` | Main `:3000` |
|-------|-------------|--------------|
| **Site DB** | Live Desk — UI edits happen here **and** on main | Live Desk — UI edits happen here too |
| **Git `dev` branch** | App **code** only (`hooks.py` + skeleton). **No fixture JSON** in the image, so rebuild+migrate does not fight Desk. | Not used. |
| **Git `main` / `master`** | History ledger for fixture snapshots (`--commit`). | Same ledger. Do **not** treat `migrate` after image rebuild as the sync tool while both sites are edited in the UI. |

```text
Either site  →  export  →  compare live vs live  →  import missing onto dest
             →  --commit snapshot of dest onto git main/master  (history)
```

**Env boundary** — only apps in `CUSTOM_APP_KEYS` for that stack are built and promoted:

| Stack | Env | Branch per app | Typical `CUSTOM_APP_KEYS` |
|-------|-----|----------------|---------------------------|
| Dev | [`erpnext-dev.env`](erpnext-dev.env) | `dev` | `nando_crm`, `nando_fulfillment` |
| Main | [`erpnext-main.env`](erpnext-main.env) | `main` / `master` | check env file |

**Why `dev` branch stays empty:** rebuilding dev with fixture JSON would make `migrate` fight the live DB on every deploy.

---

## 2. Work on dev — assign to the right app

All customizations you intend to migrate must belong to **`nando_crm`** or **`nando_fulfillment`** (whichever owns the feature), via **module** assignment.

| Artifact | Assign module | Notes |
|----------|---------------|-------|
| Client / Server Script | `NANDO_CRM` or `NANDO Fulfillment` | |
| Workspace, Report | same | |
| Custom DocType | same | Set `custom=1` records to the target module |
| Custom Field, Property Setter | owned by module filter in `hooks.py` | Do **not** create fields whose `fieldname` already exists as a **standard** field on the DocType (e.g. Customer `first_name`, `last_name` in ERPNext v16) |
| Desktop Icon | `standard=0` only | Do not export stock icons |

**One-time on dev** (if not already set):

```bash
docker compose --project-name erpnext -f nando-deployment/erpnext-dev.yaml exec backend \
  bench --site apps.internal.nandoai.com set-config developer_mode 1

docker compose --project-name erpnext -f nando-deployment/erpnext-dev.yaml exec backend \
  bench set-config -g server_script_enabled 1
```

Update **`hooks.py`** on the app repo with scoped `fixtures` filters (module-based). Commit `hooks.py` to the **`dev`** branch, rebuild dev image so the container picks it up — or edit in-container for a quick test.

Example (`nando_crm`):

```python
fixtures = [
    {"dt": "Custom Field", "filters": [["module", "=", "NANDO_CRM"]]},
    {"dt": "Property Setter", "filters": [["module", "=", "NANDO_CRM"]]},
    {"dt": "Client Script", "filters": [["module", "=", "NANDO_CRM"]]},
    {"dt": "Server Script", "filters": [["module", "=", "NANDO_CRM"]]},
    {"dt": "Workspace", "filters": [["module", "=", "NANDO_CRM"]]},
    {"dt": "Report", "filters": [["module", "=", "NANDO_CRM"]]},
]
```

Use `"NANDO Fulfillment"` instead for `nando_fulfillment`. Never use unfiltered `"Custom Field"` — it exports the whole site.

---

## 3. Export fixtures (per app)

Always export **one app at a time** with `--app`:

```bash
# CRM
docker compose --project-name erpnext -f nando-deployment/erpnext-dev.yaml exec backend \
  bench --site apps.internal.nandoai.com export-fixtures --app nando_crm

# Fulfillment
docker compose --project-name erpnext -f nando-deployment/erpnext-dev.yaml exec backend \
  bench --site apps.internal.nandoai.com export-fixtures --app nando_fulfillment
```

Custom DocTypes (if any): save in developer mode, or export explicitly:

```bash
docker compose --project-name erpnext -f nando-deployment/erpnext-dev.yaml exec backend \
  bench --site apps.internal.nandoai.com export-doc "DocType" "<DocType Name>"
```

Verify output in the container:

```bash
docker compose --project-name erpnext -f nando-deployment/erpnext-dev.yaml exec backend \
  ls -la apps/nando_crm/nando_crm/fixtures/
```

---

## 4. Branch sync

| Branch | Contents | Used by |
|--------|----------|---------|
| **`dev`** | `hooks.py`, app skeleton, empty `fixtures/` | Dev image rebuild |
| **`main`** / **`master`** | Exported `fixtures/`, `doctype/`, `workspace/`, etc. | Main image build |

Workflow:

1. Export on dev (container) — step 3.
2. Copy files out — step 5.
3. Commit and push to **`main`** (or **`master`** for fulfillment) — **not** `dev`.
4. Rebuild **main** image — step 6.

Fetch the production branch before copying:

```bash
./nando-deployment/fetch-custom-app.sh nando-deployment/erpnext-main.env

cd nando-deployment/custom-apps/nando_crm
git checkout main && git pull origin main

cd ../nando_fulfillment   # if promoting fulfillment
git checkout master && git pull origin master
```

---

## 5. Copy export from container to git

From the repo root on the server:

```bash
# CRM
docker compose --project-name erpnext -f nando-deployment/erpnext-dev.yaml cp \
  backend:/home/frappe/frappe-bench/apps/nando_crm \
  /tmp/nando_crm_export

rsync -rl --no-owner --no-group --no-times --no-perms \
  /tmp/nando_crm_export/nando_crm/ \
  nando-deployment/custom-apps/nando_crm/nando_crm/

# Fulfillment (repeat for each app you export)
docker compose --project-name erpnext -f nando-deployment/erpnext-dev.yaml cp \
  backend:/home/frappe/frappe-bench/apps/nando_fulfillment \
  /tmp/nando_fulfillment_export

rsync -rl --no-owner --no-group --no-times --no-perms \
  /tmp/nando_fulfillment_export/nando_fulfillment/ \
  nando-deployment/custom-apps/nando_fulfillment/nando_fulfillment/
```

`--no-owner --no-group --no-times --no-perms` avoids needing root on the checkout and does not rewrite ownership or timestamps on existing files.

Commit only what changed:

```bash
cd nando-deployment/custom-apps/nando_crm
git add nando_crm/hooks.py nando_crm/fixtures/ nando_crm/nando_crm/
git commit -m "Export CRM Desk customizations from dev"
git push origin main
```

Adjust paths to match your app layout. Repeat for `nando_fulfillment` → `master`.

---

## 6. Rebuild and apply on main

**Backup first:**

```bash
docker compose --project-name erpnext-main -f nando-deployment/erpnext-main.yaml exec backend \
  bench --site apps.internal.nandoai.com backup --with-files
```

**Build and deploy** (image rebuild + `compose up` + migrate + clear-cache):

```bash
./nando-deployment/deploy-stack.sh nando-deployment/erpnext-main.env --with-build
```

Equivalent to `build-custom-image.sh` then `deploy-stack.sh` without `--with-build`. Build takes ~10–20 min.

**Install apps** if not already on the site (run after deploy if needed):

```bash
docker compose --project-name erpnext-main -f nando-deployment/erpnext-main.yaml exec backend \
  bench --site apps.internal.nandoai.com install-app nando_crm

docker compose --project-name erpnext-main -f nando-deployment/erpnext-main.yaml exec backend \
  bench --site apps.internal.nandoai.com install-app nando_fulfillment
```

If you ran `install-app`, migrate again — `migrate` syncs fixtures; there is no separate `import-fixtures` command:

```bash
docker compose --project-name erpnext-main -f nando-deployment/erpnext-main.yaml exec backend \
  bench --site apps.internal.nandoai.com migrate
```

Skip `install-app` / extra `migrate` when apps are already installed and deploy completed cleanly.

Enable server scripts (once per site):

```bash
docker compose --project-name erpnext-main -f nando-deployment/erpnext-main.yaml exec backend \
  bench set-config -g server_script_enabled 1

docker compose --project-name erpnext-main -f nando-deployment/erpnext-main.yaml restart backend
```

(`deploy-stack.sh` already clears cache; restart backend only if enabling server scripts for the first time.)

---

## Checklist

| Step | Action |
|------|--------|
| 1 | Customize on dev DB (`:3003`) |
| 2 | Assign artifacts to `NANDO_CRM` or `NANDO Fulfillment` |
| 3 | Set scoped `fixtures` in each app's `hooks.py` |
| 4 | `export-fixtures --app nando_crm` (and/or `nando_fulfillment`) |
| 5 | `docker compose cp` + `rsync` → commit/push to **`main`** / **`master`** |
| 6 | `deploy-stack.sh erpnext-main.env --with-build` |
| 7 | `install-app` (if needed) → extra `migrate` if needed → verify `:3000` |

## Gotchas

- **`export-fixtures` without `--app`** exports every installed app — easy way to pull in wrong custom fields.
- **Unfiltered `"Custom Field"` in hooks** exports the entire site; always filter by module.
- **Standard fieldnames** (Customer `first_name`, `last_name`) cannot be custom fields in v16. See [README_customfields.md](README_customfields.md).
- **Secrets** in fixtures (email passwords, OAuth) must be re-entered on main.
- **In-container edits** are lost on image rebuild — always commit to git.
- **Dev rebuild** is safe for DB customizations; only commit fixture JSON to **`main`**, not **`dev`**.

---

## 7. Bidirectional fixture sync (normal operations)

While the ERP structure is still changing, people edit Desk on **both** sites. The old one-way path (export dev → bake into main image → `migrate`) cannot be the daily tool: `migrate` force-imports every document in the image snapshot and will overwrite UI work on the dest site.

Use live-vs-live sync instead. Git `main`/`master` is **history**, not the apply engine.

| Script | Direction |
|--------|-----------|
| [`sync-fixtures-dev-to-main.sh`](sync-fixtures-dev-to-main.sh) | live dev → live main |
| [`sync-fixtures-main-to-dev.sh`](sync-fixtures-main-to-dev.sh) | live main → live dev |

```bash
# Report: missing vs same-name conflicts (no writes)
./nando-deployment/sync-fixtures-dev-to-main.sh
./nando-deployment/sync-fixtures-main-to-dev.sh nando_crm

# Import missing docs onto dest (leaves conflicts on dest)
./nando-deployment/sync-fixtures-dev-to-main.sh --apply

# After apply: commit dest snapshot on git main/master (history), then push
./nando-deployment/sync-fixtures-main-to-dev.sh --apply --commit --push
```

`--force-update` imports conflicting docs from source onto dest. Use when you **intend** dest to take source’s version (e.g. a field definition you just finished on one site).

`--commit` always records fixtures on **`main`/`master`**, never on git `dev`, so a later dev image rebuild does not fight the live dev DB.

Routine `deploy-stack.sh` is for image/code/HRMS. Do not rebuild+migrate just to copy Desk customizations.

When the model stabilizes, you can go back to baking a reviewed fixture library into the main image for new sites. Until then, both DBs are editable and sync is this script.
