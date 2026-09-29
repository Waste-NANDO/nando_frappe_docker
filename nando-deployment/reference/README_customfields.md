# Custom fields — duplicates and cleanup

Fix `migrate` / `install-app` failures like:

```text
A field with the name first_name already exists in Customer
Customer: Fieldname first_name appears multiple times in rows 50, 50
```

Two causes:

| Type | What happened |
|------|----------------|
| **Standard collision** | Custom Field uses a `fieldname` that ERPNext already defines on the DocType (e.g. Customer `first_name`, `last_name` in v16). |
| **DB duplicate** | Two `Custom Field` rows with the same `dt` + `fieldname`. |
| **Fixture collision** | `custom_field.json` tries to insert a field that already exists in DB or as a standard field. |

Prevention: scope exports with `{"dt": "Custom Field", "filters": [["module", "=", "NANDO_CRM"]]}` in `hooks.py` and use `export-fixtures --app nando_crm` only. See [README_migrate_customizations.md](README_migrate_customizations.md).

---

## Quick check (one DocType)

Dev stack example — change `--project-name` / compose file for main.

```bash
docker compose --project-name erpnext -f nando-deployment/erpnext-dev.yaml exec backend \
  bench --site apps.internal.nandoai.com console
```

```python
import frappe

doctype = "Customer"
std = {df.fieldname for df in frappe.get_doc("DocType", doctype).fields}

rows = frappe.get_all(
    "Custom Field",
    filters={"dt": doctype, "fieldname": ["in", list(std)]},
    fields=["name", "fieldname", "label"],
)

print("Conflicts with STANDARD fields on", doctype)
for cf in rows:
    print(" ", cf)

from collections import defaultdict
by_key = defaultdict(list)
for cf in frappe.get_all("Custom Field", filters={"dt": doctype}, fields=["name", "fieldname"]):
    by_key[cf.fieldname].append(cf.name)

print("\nDuplicate fieldnames (same dt, multiple Custom Field rows)")
for fn, names in sorted(by_key.items()):
    if len(names) > 1:
        print(f"  {fn}: {names}")

exit()
```

---

## Check all DocTypes

```python
import frappe
from collections import defaultdict

std_cache = {}

def standard_fields(doctype):
    if doctype not in std_cache:
        std_cache[doctype] = {df.fieldname for df in frappe.get_doc("DocType", doctype).fields}
    return std_cache[doctype]

print("=== Custom fields colliding with STANDARD fieldnames ===")
for cf in frappe.get_all("Custom Field", fields=["name", "dt", "fieldname", "label"], order_by="dt, fieldname"):
    if cf.fieldname in standard_fields(cf.dt):
        print(f"  {cf.name:40} {cf.dt}.{cf.fieldname} ({cf.label})")

print("\n=== Duplicate Custom Field rows (same dt + fieldname) ===")
by_key = defaultdict(list)
for cf in frappe.get_all("Custom Field", fields=["name", "dt", "fieldname"], order_by="dt, fieldname"):
    by_key[(cf.dt, cf.fieldname)].append(cf.name)

for key, names in sorted(by_key.items()):
    if len(names) > 1:
        print(f"  {key[0]}.{key[1]}: {names}")

exit()
```

---

## Remove conflicts (DB)

Removes Custom Fields whose `fieldname` matches a **standard** field on that DocType. Safe for Customer `first_name` / `last_name` style issues.

```python
import frappe

doctype = "Customer"  # or omit loop below for all doctypes
doctypes = [doctype] if doctype else list({r.dt for r in frappe.get_all("Custom Field", fields=["dt"])})

deleted = []
for dt in doctypes:
    std = {df.fieldname for df in frappe.get_doc("DocType", dt).fields}
    names = frappe.get_all(
        "Custom Field",
        filters={"dt": dt, "fieldname": ["in", list(std)]},
        pluck="name",
    )
    for name in names:
        print("Deleting", name)
        frappe.delete_doc("Custom Field", name, force=1)
        deleted.append(name)

frappe.db.commit()
print("Deleted:", deleted)
exit()
```

Delete **all** conflicting custom fields site-wide — set `doctypes = list({...})` instead of a single DocType:

```python
import frappe

doctypes = list({r.dt for r in frappe.get_all("Custom Field", fields=["dt"])})
deleted = []

for dt in doctypes:
    std = {df.fieldname for df in frappe.get_doc("DocType", dt).fields}
    for name in frappe.get_all(
        "Custom Field",
        filters={"dt": dt, "fieldname": ["in", list(std)]},
        pluck="name",
    ):
        print("Deleting", name)
        frappe.delete_doc("Custom Field", name, force=1)
        deleted.append(name)

frappe.db.commit()
print("Deleted:", deleted)
exit()
```

Then:

```bash
docker compose --project-name erpnext -f nando-deployment/erpnext-dev.yaml exec backend \
  bench --site apps.internal.nandoai.com migrate
```

---

## Remove bad entries from fixture JSON (container)

Run after DB cleanup so the next `migrate` does not re-import them. Checks **all installed apps**.

```python
import json, os, frappe

def standard_fields(doctype):
    return {df.fieldname for df in frappe.get_doc("DocType", doctype).fields}

removed = 0
for app in frappe.get_installed_apps():
    fixtures_path = frappe.get_app_path(app, "fixtures")
    if not os.path.isdir(fixtures_path):
        continue
    for fname in os.listdir(fixtures_path):
        if "custom_field" not in fname or not fname.endswith(".json"):
            continue
        path = os.path.join(fixtures_path, fname)
        with open(path) as f:
            docs = json.load(f)
        before = len(docs)
        docs = [
            d for d in docs
            if not (
                d.get("doctype") == "Custom Field"
                and d.get("dt")
                and d.get("fieldname")
                and d.get("fieldname") in standard_fields(d["dt"])
            )
        ]
        if len(docs) < before:
            with open(path, "w") as f:
                json.dump(docs, f, indent=1)
                f.write("\n")
            print(f"{app}/{fname}: removed {before - len(docs)}")
            removed += before - len(docs)

print("Total removed from fixtures:", removed)
exit()
```

Commit the same changes to the app repo **`main`** branch — in-container edits are lost on image rebuild.

---

## Helper script (non-interactive)

From repo root on the server:

```bash
# List conflicts
./nando-deployment/custom-field-cleanup.sh erpnext-dev.env check

# Delete DB conflicts, then migrate
./nando-deployment/custom-field-cleanup.sh erpnext-dev.env delete
./nando-deployment/custom-field-cleanup.sh erpnext-dev.env migrate
```

Use `erpnext-main.env` and `--project-name erpnext-main` is handled inside the script for the main stack.

---

## After cleanup

1. DB: conflicting `Custom Field` rows deleted.
2. Fixtures: bad JSON removed; commit to git `main` / `master`.
3. `hooks.py`: filter by module — never unfiltered `"Custom Field"`.
4. Re-export on dev only after DB is clean: `export-fixtures --app nando_crm`.
5. `migrate` on target site.
