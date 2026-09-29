# NANDO ERP pipeline — overview

High-level guide for how we develop and ship ERPNext customizations.
For infrastructure (compose, Traefik, TLS), see [DEPLOYMENT.md](../DEPLOYMENT.md).
For step-by-step recipes, see the [guides/](guides/) folder.

## Mental model

| What | Moves | Source of truth |
|------|-------|-----------------|
| **Structure** (DocTypes, custom fields, property setters, client/server scripts, workspaces, sidebars, reports, dashboards, roles, workflows) | **Up only:** local → git → cloud-dev → prod | Git fixtures in the two app repos |
| **Data** (customers, items, Business Units, Configuration Templates, transactions, …) | **Down only:** prod → cloud-dev → local | Prod DB (restored from GCS backups) |
| **Secrets / site settings** (Email Account, Google Settings, System Settings, API keys) | **Never synced** | Each environment |

Desk UI edits are allowed on **local** and **cloud-dev**. Prod runs with `developer_mode=0` — never edit structure there.

```mermaid
flowchart LR
  subgraph structure [Structure moves up]
    localBench["Local bench"] -->|"export + PR"| gitDev[git dev]
    cloudDevUI["Cloud-dev Desk"] -->|"capture + PR"| gitDev
    gitDev -->|"build + deploy"| cloudDev[Cloud-dev]
    cloudDev -->|"promote identical image"| prod[Prod]
  end
  subgraph data [Data moves down]
    prod -->|daily backup| gcs[GCS]
    gcs -->|refresh| cloudDev
    gcs -->|refresh| localBench
  end
```

## Environments

| Env | Where | URL / site | Image |
|-----|-------|------------|-------|
| **Local** | Native bench on your laptop | `nando.local` | N/A (bench apps) |
| **Cloud-dev** | Docker stack `erpnext` | `:3003` | Built from app `dev` branches |
| **Prod (main)** | Docker stack `erpnext-main` | `:3000` | **Same image** promoted from cloud-dev (retag, no rebuild) |

Version pins for Frappe / ERPNext / HRMS live in one file: [`versions.env`](versions.env).
What counts as structure lives in [`structure.yaml`](structure.yaml).

## Apps and ownership

| App | GitHub repo | Module |
|-----|-------------|--------|
| `nando_crm` | [nando-erp-crm](https://github.com/Waste-NANDO/nando-erp-crm) | `NANDO_CRM` |
| `nando_fulfillment` | [nando-erpnext-module](https://github.com/Waste-NANDO/nando-erpnext-module) | `NANDO_Operations` |

Every structure document must belong to exactly one module. Lint fails if a fixture has no module (or the wrong one), or if both apps would export the same document.

Desktop Icon and Role have no `module` field in Frappe — we own them by name prefix (`NANDO…` / `Nando…`).

## Tooling

One CLI/library: **`nando-erp`** ([`tools/nando_erp_ops`](../tools/nando_erp_ops)).

- Run on the **ERP EC2 host** with `NANDO_EXECUTOR=local` (talks to Docker directly).
- Run from **laptop / Lambda** with `NANDO_EXECUTOR=ssm` (AWS SSM Run Command on that host).

Command cheat-sheet: [tools/nando_erp_ops/README.md](../tools/nando_erp_ops/README.md).

## Day-to-day in one glance

1. Edit structure on **local** Desk (or occasionally on cloud-dev).
2. `nando-erp export` → `nando-erp lint` → commit → PR into app `dev`.
3. On the host: `nando-erp build` → `nando-erp deploy dev` (aborts if cloud-dev has uncaptured Desk drift).
4. Validate on cloud-dev with realistic data (`nando-erp refresh` when needed).
5. `nando-erp promote --yes` → identical image on prod (after pre-deploy GCS backup).

If someone edited Desk on cloud-dev without exporting: `nando-erp capture --push`, merge the PR, then deploy again.

## Step-by-step guides

| Guide | When to use it |
|-------|----------------|
| [01 — Local setup](guides/01-local-setup.md) | First time on a laptop, or after version pin changes |
| [02 — Develop a structure change](guides/02-develop-structure.md) | Normal feature work (DocTypes, scripts, UI, …) |
| [03 — Deploy to cloud-dev](guides/03-deploy-cloud-dev.md) | Ship `dev` to `:3003` |
| [04 — Capture cloud-dev drift](guides/04-capture-drift.md) | Desk was edited on cloud-dev; deploy is blocked |
| [05 — Promote to prod](guides/05-promote-prod.md) | Ship the validated image to `:3000` |
| [06 — Refresh data from prod](guides/06-refresh-data.md) | Pull prod data down to cloud-dev or local |
| [07 — Backups](guides/07-backups.md) | Scheduled + pre-deploy / pre-refresh backups |
| [08 — Phase 0 baseline](PHASE0_BASELINE.md) | **One-time** cutover: git fixtures = prod |
| [09 — CLI, SSM, and API](guides/09-cli-ssm-api.md) | Install `nando-erp`, SSM from laptop/Lambda, FastAPI mount |

## Related docs

| Path | Contents |
|------|----------|
| [guides/](guides/) | Step-by-step recipes |
| [PHASE0_BASELINE.md](PHASE0_BASELINE.md) | One-time prod → git cutover |
| [reference/](reference/) | Assets, custom fields, workspaces, compose snippets |
| [deprecated/](deprecated/) | Old live-DB sync — do not use |
| [../DEPLOYMENT.md](../DEPLOYMENT.md) | Stacks, Traefik, volumes, upgrades |
| [../tools/nando_erp_ops/README.md](../tools/nando_erp_ops/README.md) | CLI command list |
