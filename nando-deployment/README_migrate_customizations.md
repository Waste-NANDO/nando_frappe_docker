# Desk customizations

Edits are in the **ERP UI** (usually `:3003`, sometimes `:3000`). Do not copy the dev DB onto main.

The two git repos are **config carriers**, not a working copy of Desk. You almost only change `hooks.py` there (what `export-fixtures` is allowed to dump). Branches are image build refs, not a place you develop.

| App | Repo | Module |
|-----|------|--------|
| `nando_crm` | [nando-erp-crm](https://github.com/Waste-NANDO/nando-erp-crm) | `NANDO_CRM` |
| `nando_fulfillment` | [nando-erpnext-module](https://github.com/Waste-NANDO/nando-erpnext-module) | `NANDO Fulfillment` |

| Layer | Role |
|-------|------|
| Live site DB | Source of truth for Desk |
| Git `dev` | Code for the **dev** image (`hooks.py`, Python). Keep `fixtures/` empty so rebuild+migrate does not overwrite Desk. |
| Git `main` / `master` | Same code for the **main** image, plus optional `--commit` snapshots (history). Sync applies to the **site**, not via `migrate`. |

`deploy-stack.sh` migrate force-imports whatever fixture JSON is in the **image**. Do not use it to copy Desk config.

## Sync

Wrappers around [`sync-fixtures.sh`](sync-fixtures.sh) (`--from/--to`). [`merge-fixtures.py`](merge-fixtures.py) does the JSON diff.

```bash
./nando-deployment/sync-fixtures-dev-to-main.sh              # report
./nando-deployment/sync-fixtures-dev-to-main.sh --apply       # missing → live main
./nando-deployment/sync-fixtures-main-to-dev.sh --apply --commit --push
```

Optional app args (`nando_crm` …); default is `CUSTOM_APP_KEYS` from the source env.

```bash
# One app
./nando-deployment/sync-fixtures-dev-to-main.sh nando_crm

# One fixture file (all DocTypes in doctype.json)
./nando-deployment/sync-fixtures-dev-to-main.sh --file doctype.json nando_crm

# One document
./nando-deployment/sync-fixtures-dev-to-main.sh --only NANDO_Quotations nando_crm
./nando-deployment/sync-fixtures-dev-to-main.sh --only NANDO_Quotations --apply nando_crm
```

`--file` and `--only` can be repeated. Report first; `--apply` only imports the filtered missing/conflicts.

### What the script does

1. `export-fixtures --app` on **both** live sites, copy JSON out of the containers.
2. Compare by document `name` (ignores `modified` / `creation` / owner noise).
3. Print a report and write `/tmp/fixture-sync-*` (source, dest, missing, conflicts).
4. Stop there unless you pass flags.

| Result | Meaning | `--apply` |
|--------|---------|-----------|
| Missing | Name on source, not on dest | Import onto dest (`force=False`) |
| Conflict | Same name, different content | Left on dest unless `--force-update` |
| Identical | Same name, same content | No-op |
| Dest-only | Name only on dest | Kept |

`--force-update` imports the source version of conflicts (`force=True`). A DocType import replaces the **whole** DocType, not one field.

`--commit` (needs `--apply`): fetch `custom-apps/` on **main/master**, re-export dest, commit that snapshot. `--push` pushes it. Fixtures are never committed to git `dev`.

Does not rebuild images or run `migrate`. Needs the generated `erpnext-*.yaml` and a running dest stack. For `--commit`, `github.env` / `GITHUB_TOKEN`.

Assign new artifacts to `NANDO_CRM` or `NANDO Fulfillment`. Scope `hooks.py` `fixtures` by module — never unfiltered `"Custom Field"`.

Once per site: `developer_mode 1` (dev), `server_script_enabled 1` (both).

## Gotchas

- `export-fixtures` without `--app` dumps every app.
- Standard fieldnames (Customer `first_name`) cannot be custom fields — [README_customfields.md](README_customfields.md).
- Fixture secrets (email passwords) must be re-entered on the other site.
- In-container code edits die on image rebuild; commit them to git.
