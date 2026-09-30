# 01 — Local setup

Get a native bench that matches cloud-dev / prod pins, with editable custom apps.

**Prerequisites:** MariaDB, Redis, Node, and a working `bench` (existing `ERP_test/nando-bench` is fine).

## 1. Install the CLI

```bash
cd /path/to/nando_frappe_docker
python3 -m venv tools/nando_erp_ops/.venv
tools/nando_erp_ops/.venv/bin/pip install -e tools/nando_erp_ops

# shell env (add to ~/.zshrc if you like)
export PATH="$PWD/tools/nando_erp_ops/.venv/bin:$PATH"
export NANDO_DOCKER_REPO="$PWD"
export NANDO_LOCAL_BENCH="/path/to/ERP_test/nando-bench"
export NANDO_LOCAL_SITE="nando.local"
export NANDO_EXECUTOR=local   # laptop talks to local bench; use ssm for cloud stacks
```

## 2. Check drift against the manifest

```bash
nando-erp doctor
```

Expect Frappe / ERPNext / HRMS to match [`versions.env`](../versions.env). Custom apps should be present.

## 3. Align versions

```bash
nando-erp local-bootstrap
# or dry-run first:
nando-erp local-bootstrap --dry-run
```

This force-checkouts `frappe`, `erpnext`, and (unless `--skip-hrms`) `hrms` to the pinned tags. Missing custom apps are symlinked from the local [`nando-erp-modules`](https://github.com/Waste-NANDO/nando-erp-modules) checkout (set `NANDO_APPS_CHECKOUT` if it is not a sibling of `nando_frappe_docker`).

Recommended layout after cutover:

```bash
# one-time
export NANDO_APPS_CHECKOUT="$HOME/dev/ReLearn-dev/nando-erp-modules"
mkdir -p "$NANDO_LOCAL_BENCH/_old_apps"
# move old per-app clones aside if present, then:
ln -sfn "$NANDO_APPS_CHECKOUT/nando_crm" "$NANDO_LOCAL_BENCH/apps/nando_crm"
ln -sfn "$NANDO_APPS_CHECKOUT/nando_fulfillment" "$NANDO_LOCAL_BENCH/apps/nando_fulfillment"
cd "$NANDO_LOCAL_BENCH"
bench pip install -e apps/nando_crm
bench pip install -e apps/nando_fulfillment
```

Then on the bench:

```bash
cd "$NANDO_LOCAL_BENCH"
bench --site "$NANDO_LOCAL_SITE" migrate
bench build
bench --site "$NANDO_LOCAL_SITE" clear-cache
```

## 4. Developer site flags

```bash
bench --site "$NANDO_LOCAL_SITE" set-config developer_mode 1
bench --site "$NANDO_LOCAL_SITE" set-config server_script_enabled 1
bench --site "$NANDO_LOCAL_SITE" clear-cache
```

## 5. Optional: load prod-like data

See [06 — Refresh data](06-refresh-data.md). Prefer a DB-only restore on local (no file attachments).

## 6. Start working

```bash
cd "$NANDO_LOCAL_BENCH"
# or your existing start.sh
bench start
```

Custom apps should be on a **feature branch**, never on `main`/`master` for day-to-day edits.

Next: [02 — Develop a structure change](02-develop-structure.md).
