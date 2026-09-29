# Deprecated

Old live-DB / site-to-site workflow. **Do not use for normal work.**

Current flow: **[../PIPELINE.md](../PIPELINE.md)** and **[../guides/](../guides/)**.

| Item | What it was | Use instead |
|------|-------------|-------------|
| `sync-fixtures.sh` (+ wrappers) | Copy Desk fixtures live between cloud-dev and prod | `nando-erp export` / `nando-erp capture` → git → `nando-erp deploy` / `nando-erp promote` |
| `merge-fixtures.py` | JSON merge helper for sync-fixtures | Built into `nando-erp-ops` (`nando_erp_ops.fixtures`) |
| `README_migrate_customizations.md` | Docs for “live DB is source of truth” | [PIPELINE.md](../PIPELINE.md) |
| `custom-field-cleanup.sh` | One-off DB cleanup for colliding Custom Fields | [../reference/README_customfields.md](../reference/README_customfields.md); prefer module-filtered fixtures + `nando-erp assign-modules` |

These scripts may still run if you point at them explicitly (paths updated for this folder). They are not part of the supported pipeline.
