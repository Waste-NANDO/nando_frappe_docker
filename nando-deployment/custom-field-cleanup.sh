#!/usr/bin/env bash
# Check or remove Custom Fields that collide with standard DocType fieldnames.
#
# Usage:
#   ./custom-field-cleanup.sh [env-file] check
#   ./custom-field-cleanup.sh [env-file] delete
#   ./custom-field-cleanup.sh [env-file] migrate
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=resolve-env.sh
source "${SCRIPT_DIR}/resolve-env.sh"

ENV_FILE="$(resolve_env_file "${SCRIPT_DIR}" "${1:-}")"
ACTION="${2:-check}"

set -a
# shellcheck disable=SC1090
source "${ENV_FILE}"
set +a

REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
COMPOSE_PROJECT_NAME="${COMPOSE_PROJECT_NAME:-erpnext}"
COMPOSE_FILE_OUTPUT="${COMPOSE_FILE_OUTPUT:-${SCRIPT_DIR}/erpnext-dev.yaml}"
if [[ "${COMPOSE_FILE_OUTPUT}" != /* ]]; then
  COMPOSE_FILE_OUTPUT="${REPO_ROOT}/${COMPOSE_FILE_OUTPUT}"
fi
SITE="${FRAPPE_SITE_NAME_HEADER:-apps.internal.nandoai.com}"

compose() {
  docker compose --project-name "${COMPOSE_PROJECT_NAME}" \
    --project-directory "${REPO_ROOT}" \
    -f "${COMPOSE_FILE_OUTPUT}" "$@"
}

run_console() {
  compose exec -T backend bench --site "${SITE}" console
}

case "${ACTION}" in
  check)
    run_console <<'PY'
import frappe
from collections import defaultdict

std_cache = {}

def standard_fields(doctype):
    if doctype not in std_cache:
        std_cache[doctype] = {df.fieldname for df in frappe.get_doc("DocType", doctype).fields}
    return std_cache[doctype]

print("=== Custom fields colliding with STANDARD fieldnames ===")
conflicts = 0
for cf in frappe.get_all("Custom Field", fields=["name", "dt", "fieldname", "label"], order_by="dt, fieldname"):
    if cf.fieldname in standard_fields(cf.dt):
        print(f"  {cf.name:40} {cf.dt}.{cf.fieldname} ({cf.label})")
        conflicts += 1
if not conflicts:
    print("  (none)")

print("\n=== Duplicate Custom Field rows (same dt + fieldname) ===")
by_key = defaultdict(list)
for cf in frappe.get_all("Custom Field", fields=["name", "dt", "fieldname"], order_by="dt, fieldname"):
    by_key[(cf.dt, cf.fieldname)].append(cf.name)

dupes = 0
for key, names in sorted(by_key.items()):
    if len(names) > 1:
        print(f"  {key[0]}.{key[1]}: {names}")
        dupes += 1
if not dupes:
    print("  (none)")

print(f"\nSummary: {conflicts} standard collision(s), {dupes} duplicate fieldname group(s)")
exit()
PY
    ;;
  delete)
    run_console <<'PY'
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
print("Deleted:", deleted if deleted else "(none)")
exit()
PY
    ;;
  migrate)
    compose exec backend bench --site "${SITE}" migrate
    ;;
  *)
    echo "Usage: $0 [env-file] check|delete|migrate" >&2
    exit 1
    ;;
esac
